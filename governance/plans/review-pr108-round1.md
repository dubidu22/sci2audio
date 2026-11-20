# Review of sci2audio PR #108 (#72 command line), round 1

Reviewed head `3bd338a` (base `3ef8ac5`, which is main today). Plan: `plans/issue72-cli-plan.md`, decisions D-210 to D-226.

## What I ran

- `ruff check`, `ruff format --check`, `lint-imports` (2 contracts kept), `deptry src`: clean.
- Fast suite with `HYPOTHESIS_PROFILE=ci`: 1298 passed, 12 deselected, 46 snapshots passed (108 s).
- Nightly Hypothesis profile: run on the round 2 head, see review-pr108-round2.md (56 property tests passed).
- CI on `3bd338a`: all green, and the new smoke step ran and passed on Linux, macOS and Windows (the Windows log shows the chapter list and the three `D:\a\_temp\smoke\...` files).
- Probes with the installed `sci2audio` (folders under a scratch XDG home): missing voice gives exit 6; `voices download` with stdin from /dev/null and no `--yes` prints the plan and refuses with exit 2; `--chapters 0`, `--speed 3` and `--on citations --off citations` give exit 2 with one line; `--chapters 9,2` warns "there is no chapter 9 (the document has chapters 1 to 7); ignored" and goes on; output folder under a file or in `/proc` gives one line and exit 1; a settings file with a voice in it is read and left byte-for-byte unchanged; no settings file is created when none exists.
- Ctrl-C probes in a real process (a fake slow voice, two SIGINTs 10 to 300 ms apart, 16 runs): every run ended at once with 130 (or death by SIGINT, which a shell also shows as 130), one `sci2audio:` line, no traceback. The first Ctrl-C alone stops after the current sentence, as the existing test shows.

## Focus points (all hold unless listed under findings)

D-210 commands and no command = help with exit 2; D-211 one command table, `ui` will be one more `Command(...)` row plus its two functions, separate lines from the others; D-212 codes pinned by `test_the_codes_are_the_documented_ones` against both `Exit` and the `--help` epilog, README table matches, every error path is one line and the catch-all names a bug without a traceback; D-213 `load_settings` only, `save_settings` never imported; D-214 1-based, out-of-range numbers warn and the run goes on; D-215 conflict is a usage error; D-216 work folder `default_work_folder` for both jobs; D-217 `--with-script`; D-218 resume summary; D-219 first Ctrl-C sets the cancel event, second exits at once (verified by probe, see S1); D-220 progress on stderr; D-221 consent flow, `--yes`, refusal without a terminal; D-222 `download_voice_files` is called only from `voices download`, `convert` has no network path; D-223 `UnreadableFileError(JobError)`, 4 lines, the three app tests assert the subclass; D-224 the step runs the installed console script on all three systems, and the nightly convert kill-and-resume test exists; D-225 `reconfigure(errors="replace")` on both streams; D-226 not duplicated, `clean` maps `JobBusyError` to 8 and a test covers it; D-114 `cli.py` imports nothing from `sci2audio.testing`, and `test_the_command_line_loads_nothing_heavy` checks it at run time.

No decision of D-210 to D-226 changes in substance.

## Findings

### Should fix in this PR

**S1. No test pins "a second Ctrl-C exits at once" (D-219).** `test_ctrl_c_stops_after_the_current_sentence_and_the_rerun_continues` covers the first Ctrl-C only. The behaviour is right (probe below), but nothing stops a later change from making the second `_wait` swallow it. Add a test: a fake voice whose first sentence calls `_thread.interrupt_main()` twice about 0.5 s apart and then blocks for several seconds; assert exit 130, the "stopping after the current sentence" line, the "stopped; run the same command again" line, and that `run` returned well before the sentence would have ended. The probe I used:

```python
def block(text):
    if not count["n"]:
        count["n"] += 1
        _thread.interrupt_main(); time.sleep(0.5); _thread.interrupt_main(); time.sleep(5)
    return False
# Cli(tmp_path, voice=FakeVoice(fail_on=block))("convert", source, "-o", out, "-q")
# -> code 130 after 0.6 s
```

**S2. `--chapters all` reads the whole file before the voice id is checked (D-222 / plan Q13 says "before the file is read").** `run_convert_command` calls `_settings`, and `_settings` resolves `all` with `_all_chapters`, which runs `read_document`; only then is `voice_id` checked. Probe: `convert note.pdf --voice zz --chapters all` reads the document once, then exits 2. Fix: resolve `all` after the voice check (for example, `_settings` returns the settings with `chapters` left for later and `run_convert_command` calls `_all_chapters` after the voice check), and add a test that an unknown voice with `--chapters all` exits 2 without reading the file. Related: `all` reads and lays out the document twice (once in the cli, once in the job), outside the job's work-folder lock. On seaborn that is 0.2 s; on a long book it is the whole extraction and layout again. Either fix it now or file an issue (lane app, e.g. an "every chapter" value for `JobSettings.chapters`), and say which.

**S3. `convert --with-script` can leave a half set and exit 7.** When the audiobook exists and the script does not (a person ran `convert`, then `convert --with-script`), the script job writes `.script.txt`, `.report.json` and `.report.md`, and then the audio job refuses with exit 7. Probe output: before `[mp3, m4b, readalong]`, after the failed run `[mp3, m4b, readalong, report.json, report.md, script.txt]`, exit 7. This is the "nothing half-written when it cannot go on" rule of D-140/D-119 at the command level. One way: without `--overwrite`, check `script_files(...)` up front, then run the audio job first (its target check comes before any speech) and the script job second. Add a test for both orders (audiobook exists / script exists) asserting the folder is unchanged and exit 7.

### Nits (fix or leave, say which)

- N1. `_categories_help()` is chosen by `command.name in ("script", "convert")`; an `epilog` field on `Command` would keep the table the one place that describes a command.
- N2. `FILE` help says "the PDF to read"; it will need to change when #73 adds EPUB (no action needed now if #73 carries it).
- N3. `voices download` prints the plan and the `[y/N]` question on stdout. With stdout redirected (`sci2audio voices download > log`) and stdin a terminal, the person sees nothing and the command waits. Consider writing the question (or the whole plan) to stderr, or treating a non-terminal stdout like a non-terminal stdin.

## Verdict

Request changes: S1, S2 and S3, each fixed or (S2's double read only) deferred with an issue. The nits are the author's call, but the reply names each one.
