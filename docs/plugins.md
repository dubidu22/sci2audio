# Writing a text-step plugin

sci2audio prepares a text for listening with *text steps*. Each step is one rule: page numbers left out, a URL read as "a link", "e.g." read as "for example". You can add your own steps from a separate Python package, called a plugin. Once the plugin is installed in the same environment as sci2audio, every job runs its steps alongside the built-in ones.

This page covers four things:

- how to write a step;
- how to make it known through the `sci2audio.text_steps` entry point;
- what happens to it when a job runs;
- how to check it with the conformance suite in `sci2audio.testing`, the same checks every built-in step passes.

The last section does the same for a voice engine.

## The one rule: propose, never rewrite

A text step never changes the text. It looks at the document and *proposes* marked edits: remove this span, replace it with these words, put a pause here, or ask about it. Each edit carries a reason a person can read. sci2audio collects the edits of all steps, settles overlaps and applies the accepted ones. This is why the report, read-along and the per-category switches keep working (D-57). A step never summarises and never rewrites silently. The conformance suite checks the parts of this rule that a program can check.

## The public names

Import everything from `sci2audio.textprep.api`. Its `__all__` is the contract:

| Name | What it is |
|---|---|
| `TextStep` | The base class. Set `id`, `languages`, `category`, `stage` and `api_version`, and implement `find(document, context) -> list[Edit]`. |
| `StepContext` | What the step may know about the job: `language` (BCP 47, such as `"en"` or `"en-GB"`) and `switched_off` (the categories this run will not apply). |
| `Category` | The fixed list of categories that the report and the switches name. Your step belongs to exactly one. |
| `Stage` | `BLOCK` (every edit covers a whole block), `INLINE` (edits inside a block) or `MOVE` (moves a whole block to a place in another block). |
| `ANY_LANGUAGE` | `"*"` in `languages`: the step works for every language. |
| `TEXT_STEP_API` | The number of the contract this sci2audio provides (currently `1`). |
| `Document`, `Block`, `BlockKind`, `FurnitureRole`, `Part`, `Section` | The document a step reads. It is immutable. |
| `Span`, `Edit`, `EditKind` | What a step proposes: a span inside one block, and the kind of edit with its reason. |
| `PLUGIN_GROUP`, `load_plugin_steps`, `LoadedPlugins`, `PluginInfo`, `PluginProblem` | Discovery. You need these only to test your packaging. |

Everything else in sci2audio may change in any release, including the runner, the built-in steps and their order.

**Stability.** Under `TEXT_STEP_API = 1` these names keep their meaning. A change that would break a step written against them raises the number:

- a field removed or renamed;
- a new required argument;
- stricter checks in `Edit` or `Span`;
- a new abstract method.

Additions do not raise it: a field with a default, a new `Category`, or a new `EditKind` that no step has to use.

**`api_version`.** Your step names the contract it targets with `api_version = 1` in its own class. The default that `TextStep` provides does not count. A sci2audio that provides another contract does not load your step and says why in the report.

## A minimal step

This step reads a free-standing "&" in a paragraph as "and":

```python
# my_plugin.py
import re

from sci2audio.textprep.api import (
    BlockKind,
    Category,
    Document,
    Edit,
    EditKind,
    Span,
    Stage,
    StepContext,
    TextStep,
)

_AMPERSAND = re.compile(r"(?<= )&(?= )")


class AmpersandStep(TextStep):
    """Reads a free-standing "&" in a paragraph as "and"."""

    id = "ampersand-and"
    languages = ("en",)
    category = Category.CHARACTERS
    stage = Stage.INLINE
    api_version = 1

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        edits = []
        for index, block in enumerate(document.blocks):
            if block.kind is not BlockKind.PARAGRAPH:
                continue
            for match in _AMPERSAND.finditer(block.text):
                edits.append(
                    Edit(
                        Span(index, match.start(), match.end()),
                        EditKind.REPLACE,
                        reason='"&" is read as "and"',
                        step=self.id,
                        replacement="and",
                    )
                )
        return edits
```

`id` is kebab-case and unique. `languages` holds primary tags (`"en"`, `"de"`) or `ANY_LANGUAGE`; a job in `"en-GB"` runs a step for `"en"`. `find` must not reach the network, keep state between calls, or depend on anything but its arguments.

## Making it known: the entry point

In your package's `pyproject.toml`:

```toml
[project.entry-points."sci2audio.text_steps"]
ampersand-and = "my_plugin:AmpersandStep"
```

- **The name is the step's id.** A different name is refused, so every report line and problem leads back to this line.
- **The value is a `TextStep` subclass or a callable with no arguments that returns a `TextStep`.** sci2audio calls it with no arguments. Use a factory when the step needs to load something first.
- **One entry point gives one step.** For several steps, add several lines.

Install your package in the environment sci2audio runs in (`uv pip install -e .` or `pip install my-plugin`). The next `sci2audio script` lists it: "Text-step plugins: ampersand-and (my-plugin 0.1)". The JSON and Markdown reports list it too.

## What happens to a plugin in a job

- **Order.** Plugins run after the built-in steps of their stage, sorted by id. Block steps still run before inline steps, and move steps last. When a plugin's edit overlaps an edit that an earlier step proposed, the earlier edit wins. So a plugin adds to the reading and never overrides a built-in rule.
- **Switches.** Your step's category is switched on and off with the built-in steps of that category (`--on` and `--off` on the command line, the switches in the app). A switched-off step still runs, and its edits are listed as switched off.
- **Not loaded.** A plugin is not loaded when:
  - its import fails, or its factory raises;
  - it does not give a `TextStep`;
  - it has an invalid attribute, or `api_version` is missing or different;
  - its entry point is not named after its id;
  - it takes the id of a built-in step, or two plugins share an id (both are left out).

  The report lists such plugins as problems ("plugin not loaded: …"), and the other plugins still load.
- **Failing at run time.** These count as failing:
  - `find` raises, or calls `sys.exit`;
  - it returns edits that break the rules (spans outside their block, another step's id, edits that overlap each other, a block step's edit that does not cover its block, a move from a step that is not a move step);
  - it takes longer than 60 seconds on a document;
  - it changes the document it was given.

  Each plugin gets its own copy of the document. When a plugin fails, all its edits are left out, the report says why, and the job goes on: a plugin can never stop a job or change the text other than through its edits. Ctrl+C still stops the job.
- **What is not enforced in a job.** Network access is not blocked while a job runs. The conformance suite below checks it, and the project's rules forbid it: sci2audio works offline.

## Checking your step with the conformance suite

`sci2audio.testing` holds the checks as plain functions. They work with any test runner and never import pytest themselves. With pytest:

```python
# tests/test_my_plugin.py
from my_plugin import AmpersandStep

from sci2audio.testing import check_text_step
from sci2audio.textprep.api import load_plugin_steps


def test_the_step_keeps_the_text_step_contract():
    check_text_step(AmpersandStep())


def test_the_entry_point_loads():
    loaded = load_plugin_steps()
    assert "ampersand-and" in [plugin.step for plugin in loaded.plugins]
    assert [p for p in loaded.problems if p.name == "ampersand-and"] == []
```

The first test runs your step on the sample documents (English and German; a step is run only on documents in its languages). It raises `ConformanceError` with every problem found. Pass your own documents as the second argument, built with `sci2audio.testing.make_document`. `text_step_problems` gives the same list without raising. The second test checks the packaging: it needs your package installed, and it catches a wrong entry-point name or a missing `api_version`.

Every run is done twice, once with nothing switched off and once with every category in `StepContext.switched_off` (D-595). `check_text_step` checks:

| Check | Rule |
|---|---|
| `id` is kebab-case letters and digits | Steps are named in the report and in the entry point (D-57) |
| `api_version` equals `TEXT_STEP_API` | The step targets the contract this sci2audio provides (D-57, #216) |
| `category` is a `Category`, `stage` is a `Stage` | Every step belongs to one category and one stage (D-108, D-109) |
| `languages` is a non-empty tuple of primary tags or `"*"` | The job's language picks the steps (D-112) |
| `find` returns a list of `Edit`, and does not raise | A failing step is left out of a job (D-111) |
| No network access while `find` runs, even if the step catches the refusal | sci2audio works offline |
| Every edit names the step's id | The report says which step proposed what (D-57) |
| No `ask` edits when `allow_ask=False` (the built-in steps' setting) | Built-in steps have no way to ask yet (UC-04) |
| Spans lie inside their block, and the step's own edits do not overlap | Edits never cross blocks or collide (D-61) |
| A block step's edits each cover a whole block | Whole-block decisions stay whole (D-105, D-109) |
| A move step proposes only moves, and only a move step proposes them | Moves run last and never block a rule about the text (D-558) |
| The same document gives the same edits twice | A step depends only on its arguments (D-57) |
| Run on its own output, the step changes nothing more | Idempotence; a placeholder is read back as its own notice (D-710) |

`no_network()` is a context manager you can use in your own tests. While it is active, every attempt to connect or to look up a name fails with `NetworkUsedError`, and it yields the attempts it saw.

## Checking a voice engine

The voice plugin contract (D-52, D-125) is not loaded from entry points yet: there is no public way to add a voice to a job. You can still check an engine against the contract. `check_voice_engine(make_engine)` takes a factory with no arguments:

```python
# my_voice.py
import math

import numpy as np

from sci2audio.voices import (
    API_VERSION,
    PCM_FLOAT32,
    Duration,
    EngineError,
    InvalidInputError,
    SynthesisRequest,
    SynthesizedAudio,
    VoiceInfo,
)

VOICES = (VoiceInfo("tone", "Tone", "en-US", "female"),)
RATE = 8000


def _number(value: object, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidInputError(f"not a number: {value!r}")
    if not math.isfinite(value) or not low <= value <= high:
        raise InvalidInputError(f"out of range: {value!r}")
    return float(value)


class ToneSession:
    def __init__(self) -> None:
        self.disposed = False

    def synthesize(self, request: SynthesisRequest) -> SynthesizedAudio:
        if self.disposed:
            raise EngineError("the session is disposed")
        if not request.text.strip():
            raise InvalidInputError("nothing to say")
        if request.voice.key not in {voice.id for voice in VOICES}:
            raise InvalidInputError(f"unknown voice {request.voice.key!r}")
        values = request.parameters.values
        speed = _number(values.get("speed", 1.0), 0.5, 2.0)
        _number(values.get("letter_speed", 1.0), 0.25, 1.0)  # a tone cannot slow letters
        samples = np.full(int(len(request.text) * 10 / speed), 0.25, dtype="<f4")
        return SynthesizedAudio(samples.tobytes(), PCM_FLOAT32, Duration(len(samples) / RATE), RATE)

    def dispose(self) -> None:
        self.disposed = True


class ToneEngine:
    api_version = API_VERSION

    def __init__(self) -> None:
        self.disposed = False

    def createSession(self) -> ToneSession:
        if self.disposed:
            raise EngineError("the engine is disposed")
        return ToneSession()

    def listVoices(self) -> tuple[VoiceInfo, ...]:
        if self.disposed:
            raise EngineError("the engine is disposed")
        return VOICES

    def dispose(self) -> None:
        self.disposed = True
```

```python
# tests/test_my_voice.py
from my_voice import ToneEngine

from sci2audio.testing import check_voice_engine


def test_the_engine_keeps_the_voice_contract():
    check_voice_engine(ToneEngine)
```

Pass `voices=` (a function from the listed voices to the ones to try) to check only some voices of a large engine. `check_voice_engine` checks:

| Check | Rule |
|---|---|
| No network access while the factory runs or any voice speaks | sci2audio works offline (VA-04) |
| `api_version` equals `API_VERSION`, and the engine implements `Engine` | The engine targets this contract (D-52) |
| `listVoices` gives a non-empty tuple of `VoiceInfo` with unique ids, each with an id, a name and a language | Voices are chosen by id and language (D-125) |
| `createSession` gives an `EngineSession` | The contract's shape (D-125) |
| Every voice speaks the sample: a `SynthesizedAudio` of raw float32 mono, a positive rate, a duration that matches the samples, finite samples, and not silence | The output stage can encode it (D-52) |
| Speed 2.0 gives fewer samples than speed 1.0 | The speed setting works |
| `letter_speed` 1.0 equals leaving it out, the lowest value never shortens the audio, and values outside the range are refused | Spelled letters can be slowed (#295, D-554) |
| Empty or blank text, an unknown voice, and a speed or letter speed that is out of range, not a number or not finite raise `InvalidInputError` | Bad input fails clearly, as an `EngineError` (D-125) |
| `dispose` can be called twice, and a session or engine used after `dispose` raises `EngineError` | Resources are freed exactly once (D-125) |
