"""Run one reading step in a child process with a memory and a time limit (#185, #28, D-581).

PDFium decodes streams and loads pages before our code can count anything, so a 1 MB file
can ask it for gigabytes, and a crash inside it would end the whole program. `run` does the
work in a fresh child process (the "spawn" start method on every system, safe from threads)
and gives back its result, or `Stopped` when the child needed more memory than allowed,
took longer than allowed for one step, or ended without a result.

Memory is watched from inside the child: a thread reads the process's memory every 20 ms
(`peak_memory`) and ends the child with `MEMORY_EXIT` above the limit. Where the system
offers a hard limit, it is set at twice the limit, for an allocation that grows faster
than the watch: the address space on Linux, a job object on Windows; macOS has neither.
Time is watched from the parent: the child reports each step it starts (`report`), and a
step that takes longer than allowed ends the child. The child's watch also ends it with
`TIME_EXIT` when no step started for twice that long, so a child whose parent is gone
(killed, crashed) does not read on.

At most `Readers.limit` children run at once; a further `run` waits for a free slot, so the
memory limit holds for the program, not only for one child.

The child imports only what the step needs: the program's main module is not imported in
the child (multiprocessing would otherwise run it, and with it every other layer).
"""

from __future__ import annotations

import importlib.machinery
import multiprocessing
import os
import pickle
import sys
import threading
import time
import types
from collections.abc import Callable
from dataclasses import dataclass
from multiprocessing.connection import Connection
from typing import Any

MEMORY_EXIT = 86  # the child's exit code when the watch ended it for memory
TIME_EXIT = 87  # ... and for a step that took more than twice its time
_WATCH_SECONDS = 0.02

_report: Callable[[str], None] | None = None  # set in the child
_step_started = 0.0  # in the child: when the current step started (time.monotonic)
_MAIN = threading.Lock()  # the main module is swapped while a child starts


@dataclass(frozen=True)
class Stopped:
    """Why the child ended without a result: "memory", "time" (in `step`) or "ended"."""

    reason: str
    step: str = ""


class NotStarted(Exception):
    """No child process could be started (the system refused a process or a pipe)."""


class Readers:
    """At most `limit` children alive at once; a further one waits for a free slot."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.alive = 0
        self.most = 0  # the most alive at once, for tests
        self._free = threading.Condition()

    def __enter__(self) -> None:
        with self._free:
            self._free.wait_for(lambda: self.alive < self.limit)
            self.alive += 1
            self.most = max(self.most, self.alive)

    def __exit__(self, *_: object) -> None:
        with self._free:
            self.alive -= 1
            self._free.notify()


def report(step: str) -> None:
    """In the child, start the time limit of `step` anew (e.g. "page 3"); else nothing."""
    if _report is not None:
        _report(step)


def run(
    target: Callable[..., Any],
    args: tuple[Any, ...],
    *,
    memory: int,
    step_seconds: float,
    readers: Readers,
) -> Any:
    """`target(*args)` in a child process: its result, `Stopped`, or the exception it
    raised, raised again here. `target` must be a module-level function; `memory` is in
    bytes, `step_seconds` the longest any reported step may take. Raises `NotStarted` when
    no child could be started.

    The wait for a free slot in `readers` has no time limit and is not part of any step's
    time: a third read waits until one of two running reads ends."""
    context = multiprocessing.get_context("spawn")
    with readers:
        child, receive = _start(context, target, args, memory, step_seconds)
        try:
            return _wait(child, receive, step_seconds)
        finally:
            receive.close()
            if child.is_alive():
                child.kill()
            child.join()
            child.close()


def _start(
    context: Any, target: Callable[..., Any], args: tuple[Any, ...], memory: int, step: float
) -> tuple[Any, Connection]:
    """A started child and the end of the pipe its words come through."""
    try:
        receive, send = context.Pipe(duplex=False)
    except OSError as error:
        raise NotStarted(str(error)) from error
    try:
        child = context.Process(
            target=_child,
            args=(send, target, args, memory, step),
            daemon=True,
            name="sci2audio-reader",
        )
        with _MAIN:  # the child does not import the main module: see `_without_main`
            main = sys.modules["__main__"]
            sys.modules["__main__"] = _without_main()
            try:
                child.start()
            finally:
                sys.modules["__main__"] = main
    except OSError as error:
        receive.close()
        raise NotStarted(str(error)) from error
    finally:
        send.close()  # the child holds its own copy
    return child, receive


def _without_main() -> types.ModuleType:
    """A stand-in main module that multiprocessing does not import in the child: the real
    one may be the `sci2audio` command, which imports every layer."""
    module = types.ModuleType("__main__")
    module.__spec__ = importlib.machinery.ModuleSpec("__main__", None)
    return module


def _wait(child: Any, receive: Connection, step_seconds: float) -> Any:
    step = "opening"
    while True:
        if not receive.poll(step_seconds):
            child.kill()
            return Stopped("time", step)
        try:
            kind, value = receive.recv()
        except (EOFError, OSError):  # ended without a word: the watch, a hard limit, a crash
            child.join()
            reason = {MEMORY_EXIT: "memory", TIME_EXIT: "time"}.get(child.exitcode, "ended")
            return Stopped(reason, step)
        if kind == "step":
            step = value
        elif kind == "done":
            return value
        else:  # "raised"
            raise value


# ---- in the child ----------------------------------------------------------------------


def _child(
    send: Connection,
    target: Callable[..., Any],
    args: tuple[Any, ...],
    memory: int,
    step_seconds: float,
) -> None:
    global _report, _step_started
    _hard_limit(2 * memory)
    _step_started = time.monotonic()
    watch = threading.Thread(
        target=_watch, args=(memory, 2 * step_seconds), daemon=True, name="memory-watch"
    )
    watch.start()

    def started(step: str) -> None:
        global _step_started
        _step_started = time.monotonic()
        send.send(("step", step))

    _report = started
    try:
        result = target(*args)
    except MemoryError:  # a hard limit refused an allocation Python asked for
        os._exit(MEMORY_EXIT)
    except BaseException as error:
        send.send(("raised", _sendable(error)))
        return
    send.send(("done", result))


def _sendable(error: BaseException) -> BaseException:
    """`error`, or a RuntimeError naming it when it would not arrive whole in the parent
    (an exception that pickles but cannot be rebuilt from its pickle, for example)."""
    try:
        pickle.loads(pickle.dumps(error))  # noqa: S301 (our own pickle, made just now)
    except Exception:
        return RuntimeError(f"{type(error).__name__}: {error}")
    return error


def _watch(memory: int, step_limit: float) -> None:
    """End the child above `memory`, or when its step started more than `step_limit`
    seconds ago: the parent ends it after one step time, so a step this old means the
    parent is gone."""
    while True:
        if peak_memory() > memory:
            os._exit(MEMORY_EXIT)
        if time.monotonic() - _step_started > step_limit:
            os._exit(TIME_EXIT)
        time.sleep(_WATCH_SECONDS)


def peak_memory() -> int:
    """The memory this process holds, in bytes, as the watch reads it: on Linux the peak
    resident memory since the program started (`VmHWM`; `getrusage` would also count the
    parent's memory from before the child's start), on macOS the resident memory now, on
    Windows the peak committed private memory, which is what Windows charges."""
    if sys.platform == "win32":
        return _windows_peak()
    if sys.platform == "darwin":
        return _mac_resident()
    with open("/proc/self/status", "rb") as status:
        for line in status:
            if line.startswith(b"VmHWM:"):
                return int(line.split()[1]) * 1024
    return 0


def _hard_limit(limit: int) -> None:
    """The system's own limit on the child's memory, where it has one."""
    if sys.platform == "win32":
        _windows_job(limit)
    elif sys.platform.startswith("linux"):
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    # macOS enforces no limit on a process's memory: the watch alone holds it


if sys.platform == "win32":  # pragma: no cover (run by the Windows CI job)
    import ctypes
    from ctypes import wintypes

    class _Counters(ctypes.Structure):  # PROCESS_MEMORY_COUNTERS
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    class _BasicLimits(ctypes.Structure):  # JOBOBJECT_BASIC_LIMIT_INFORMATION
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):  # IO_COUNTERS
        _fields_ = [
            (name, ctypes.c_uint64)
            for name in ("Reads", "Writes", "Others", "ReadBytes", "WriteBytes", "OtherBytes")
        ]

    class _ExtendedLimits(ctypes.Structure):  # JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        _fields_ = [
            ("BasicLimitInformation", _BasicLimits),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    _kernel32.K32GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_Counters),
        wintypes.DWORD,
    ]
    _kernel32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
    _kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _JOB_LIMIT_PROCESS_MEMORY = 0x100
    _JOB_EXTENDED_LIMITS = 9  # JobObjectExtendedLimitInformation
    _jobs: list[int] = []  # kept open for the child's life

    def _mac_resident() -> int:
        raise NotImplementedError

    def _windows_peak() -> int:
        counters = _Counters()
        counters.cb = ctypes.sizeof(counters)
        process = _kernel32.GetCurrentProcess()
        if not _kernel32.K32GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
            return 0
        return int(counters.PeakPagefileUsage)

    def _windows_job(limit: int) -> None:
        """Put this process in a job of its own whose memory is capped at `limit`. Jobs
        nest from Windows 8 on, so this works inside a job the shell already made."""
        job = _kernel32.CreateJobObjectW(None, None)
        if not job:
            return
        limits = _ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = _JOB_LIMIT_PROCESS_MEMORY
        limits.ProcessMemoryLimit = limit
        size = ctypes.sizeof(limits)
        if _kernel32.SetInformationJobObject(job, _JOB_EXTENDED_LIMITS, ctypes.byref(limits), size):
            _kernel32.AssignProcessToJobObject(job, _kernel32.GetCurrentProcess())
        _jobs.append(job)

elif sys.platform == "darwin":  # pragma: no cover (run by the macOS CI job)
    import ctypes
    import ctypes.util

    class _TaskInfo(ctypes.Structure):  # mach_task_basic_info
        _pack_ = 4
        _fields_ = [
            ("virtual_size", ctypes.c_uint64),
            ("resident_size", ctypes.c_uint64),
            ("resident_size_max", ctypes.c_uint64),
            ("user_time", ctypes.c_int32 * 2),
            ("system_time", ctypes.c_int32 * 2),
            ("policy", ctypes.c_int32),
            ("suspend_count", ctypes.c_int32),
        ]

    _libc = ctypes.CDLL(ctypes.util.find_library("c"))
    _libc.task_info.argtypes = [
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    _libc.task_info.restype = ctypes.c_int
    _MACH_TASK_BASIC_INFO = 20

    def _mac_resident() -> int:
        info = _TaskInfo()
        count = ctypes.c_uint32(ctypes.sizeof(info) // 4)
        task = ctypes.c_uint32.in_dll(_libc, "mach_task_self_").value
        if _libc.task_info(task, _MACH_TASK_BASIC_INFO, ctypes.byref(info), ctypes.byref(count)):
            return 0
        return int(info.resident_size)

    def _windows_peak() -> int:
        raise NotImplementedError

    def _windows_job(limit: int) -> None:
        raise NotImplementedError

else:

    def _mac_resident() -> int:
        raise NotImplementedError

    def _windows_peak() -> int:
        raise NotImplementedError

    def _windows_job(limit: int) -> None:
        raise NotImplementedError


def loaded(prefix: str) -> list[str]:
    """The modules whose names start with `prefix`, for the test that keeps the child
    small (D-581): a child that imported every layer would cost seconds per read."""
    return sorted(name for name in sys.modules if name.startswith(prefix))
