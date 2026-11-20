"""Sentence-boundary evaluation (plan D-719, section 3): our cutter against pySBD and syntok.

Not part of the repo. It imports the repo's metric (`tests/unit/sentence_metric.py`) and the
set list of `tests/unit/test_sentence_boundaries.py`, and swaps the splitter inside the
utterance cutter (`sci2audio.textprep.utterances._sentences`) for each candidate, so every
candidate sees the same text: the run text after the text steps, with the cutter's guard that
a cut never falls after replacement text inside a replacement. Utterances, the length limit
and the metric are the repo's own.

Run from a checkout, with pySBD 0.3.4 and syntok 1.4.4 in a scratch folder (MIT both):

    uv pip install --target SITE pysbd==0.3.4 syntok==1.4.4
    PYTHONPATH=tests/unit uv run python plans/.../eval.py --site SITE [--out result.json]

Candidates: "ours" (the repo's rules), "pysbd" (Segmenter(language, clean=False,
char_span=True)), "syntok" (segmenter.analyze; language-independent). Excluded up front: NLTK
Punkt and neural splitters, which need a model download (plan section 3).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--site", required=True, help="folder holding pysbd and syntok")
parser.add_argument("--out", help="write the result as JSON here")
parser.add_argument("--only", nargs="*", help="candidates to run (default: all)")
args = parser.parse_args()
sys.path.append(args.site)

import pysbd  # noqa: E402
from sentence_metric import Score, compare, read_truth, script_of, stress_source, system_words  # noqa: E402
from syntok import segmenter  # noqa: E402
from test_sentence_boundaries import CORPUS, NATURAL, SENTENCES, STRESS  # noqa: E402

from sci2audio.textprep import utterances as cutter  # noqa: E402

OURS = cutter._sentences
_PYSBD: dict[str, pysbd.Segmenter] = {}
TIMES: list[float] = []


def _starts_pysbd(text: str, language: str) -> list[int]:
    code = "de" if language.startswith("de") else "en"
    seg = _PYSBD.setdefault(code, pysbd.Segmenter(language=code, clean=False, char_span=True))
    return [span.start for span in seg.segment(text)]


def _starts_syntok(text: str, language: str) -> list[int]:
    return [sentence[0].offset for paragraph in segmenter.analyze(text) for sentence in paragraph]


def splitter(starts_of):
    """A `_sentences` replacement: the candidate's sentence starts, moved to the first
    letter after white space, never after replacement text inside a replacement."""

    def sentences(run, abbreviations, language="en"):
        text = run.text
        began = time.perf_counter()
        # a line break inside a block is white space (`spoken_text`); pySBD would cut at
        # every one, so both candidates get the text with one space for each (same offsets)
        found = starts_of(text.replace("\r", " ").replace("\n", " "), language)
        TIMES.append(time.perf_counter() - began)
        cuts = [0]
        for start in sorted(set(found)):
            while start < len(text) and text[start].isspace():
                start += 1
            if start <= cuts[-1] or start >= len(text):
                continue
            if not text[:start].strip():
                continue
            inside = run.inside_replacement(start)
            if inside and text[inside[0] : start].strip():
                continue
            cuts.append(start)
        cuts.append(len(text))
        return [(a, b) for a, b in zip(cuts, cuts[1:]) if a < b]

    return sentences


CANDIDATES = {"ours": None, "pysbd": _starts_pysbd, "syntok": _starts_syntok}


def score(name: str, folder: Path) -> tuple[str, Score]:
    truth = SENTENCES / f"{name}.txt"
    if name in NATURAL:
        source = CORPUS / NATURAL[name]
    else:
        source = folder / f"{name}.txt"
        source.write_text(stress_source(truth), encoding="utf-8")
    document, utterances = script_of(source)
    return document.language.split("-", 1)[0], compare(read_truth(truth), system_words(document, utterances))


def main() -> None:
    result: dict = {}
    for candidate, starts_of in CANDIDATES.items():
        if args.only and candidate not in args.only:
            continue
        cutter._sentences = OURS if starts_of is None else splitter(starts_of)
        TIMES.clear()
        totals: dict[str, Score] = {}
        files: dict = {}
        errors: dict[str, list] = {}
        with tempfile.TemporaryDirectory() as tmp:
            for name in [*NATURAL, *STRESS]:
                language, got = score(name, Path(tmp))
                group = f"{language} {'natural' if name in NATURAL else 'stress'}"
                totals.setdefault(group, Score()).add(got)
                files[name] = got.summary()
                errors[name] = sorted(f"{e.kind} {e.at}" for e in got.errors)
        cutter._sentences = OURS
        result[candidate] = {
            "groups": {
                group: {
                    "precision": round(s.precision, 4),
                    "recall": round(s.recall, 4),
                    "f1": round(s.f1, 4),
                    "hits": s.hits,
                    "fp": s.false_positives,
                    "fn": s.false_negatives,
                    "errors": s.false_positives + s.false_negatives,
                }
                for group, s in sorted(totals.items())
            },
            "files": files,
            "errors": errors,
            "ms_per_run_median": round(1000 * statistics.median(TIMES), 3) if TIMES else None,
            "runs": len(TIMES),
        }
        print(f"== {candidate}")
        for group, row in result[candidate]["groups"].items():
            print(f"  {group}: P {row['precision']} R {row['recall']} F1 {row['f1']} "
                  f"errors {row['errors']} ({row['fp']} FP, {row['fn']} FN)")
        if TIMES:
            print(f"  splitter: median {result[candidate]['ms_per_run_median']} ms per run, {len(TIMES)} runs")
    if "ours" in result:
        base = {n: Counter(v) for n, v in result["ours"]["errors"].items()}
        for candidate in result:
            if candidate == "ours":
                continue
            only = {n: sorted((Counter(v) - base[n]).elements()) for n, v in result[candidate]["errors"].items()}
            fixed = {n: sorted((base[n] - Counter(v)).elements()) for n, v in result[candidate]["errors"].items()}
            result[candidate]["new_vs_ours"] = {n: v for n, v in only.items() if v}
            result[candidate]["fixed_vs_ours"] = {n: v for n, v in fixed.items() if v}
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")


main()
