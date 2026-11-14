"""The script job on the corpus papers (#70): golden files of the script and the report for
two papers, and every paper's chapters.

The golden files change with every text step that lands (#64 to #68): accept a wanted
change with `uv run pytest --snapshot-update` and explain the diff in the PR.
"""

import json
from functools import cache
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.app import JobSettings, ScriptJob, run_script_job

pytestmark = pytest.mark.timeout(120)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
PAPERS = sorted((CORPUS / "papers").glob("*.pdf"))
# The German paper's script and report are recorded as main reads it: they change with every
# German text rule that lands (#130, #101, #212), which records them again (#235, D-510).
GOLDEN = ["acl2023-hardt-ellipsis", "arxiv2017-maass-privacyscore", "joss2021-waskom-seaborn"]
# Steps that do not speak German yet, with the Issue that teaches them (#235, D-509): on the
# German paper they are reported as not run. An Issue that lands takes its steps out.
GERMAN_LATER_STEPS = {
    "formula-notices": 212,
    "table-figure-notices": 212,
    "footnotes": 212,
    "links": 101,
    "citations": 101,
    "statistics": 130,
    "numbers": 130,
}
GERMAN = {"arxiv2017-maass-privacyscore"}

# Chapter titles per paper as laid out today; "*" marks the reference list (not chosen).
CHAPTERS = {
    "acl2023-chi-plue": [
        "acl2023-chi-plue", "Abstract", "1 Introduction",
        "2 Policy Language Understanding Evaluation (PLUE) Benchmark", "3 Experiment Results",
        "4 Related Work", "5 Conclusion and Future work", "Limitations", "Ethics Statement",
        "Acknowledgements", "*References", "Supplementary Material: Appendices",
        "ACL 2023 Responsible NLP Checklist",
    ],
    "acl2023-hardt-ellipsis": [
        "acl2023-hardt-ellipsis", "Abstract", "1 Introduction", "2 Related Work", "3 Data",
        "4 Test", "5 Results", "6 Analysis", "7 Conclusion", "8 Limitations", "*References",
        "A Appendix", "ACL 2023 Responsible NLP Checklist",
    ],
    "acl2023-nowak-prefix-probabilities": [
        "acl2023-nowak-prefix-probabilities", "Abstract", "1 Introduction", "2 Preliminaries",
        "3 Jelinek and Lafferty (1991)", "4 Our Speed-up", "5 Generalization to Semirings",
        "6 Conclusion", "Limitations", "Ethics Statement", "Acknowledgements", "*References",
        "A Proof of Lem. 1", "B Extension of Alg. 3 to Semirings",
    ],
    "arxiv2024-arsiwalla-qualia-meaning": [
        "arxiv2024-arsiwalla-qualia-meaning", "Abstract", "1 Introduction",
        "2 Subjective Meaning in Phenomenology of Experience",
        "3 Do Raw Feels Have Subjective Meaning?", "4 The Formal Structure of Meaning",
        "5 Discussion", "Acknowledgments", "*References",
    ],
    "arxiv2017-maass-privacyscore": [
        "PrivacyScore", "1 Einleitung", "2 Verwandte Arbeiten", "3 PrivacyScore im Überblick",
        "4 Sicherheits- und Privatheitstests", "5 Ethische Fragestellungen",
        "6 Rechtliche Fragestellungen", "7 Schlussbemerkungen", "*Literaturverzeichnis",
    ],
    "arxiv2024-liu-orbital-hall": ["arxiv2024-liu-orbital-hall"],
    "joss2021-waskom-seaborn": [
        "seaborn: statistical data visualization", "Summary", "Statement of need", "Example",
        "Overview", "Acknowledgements", "*References",
    ],
    "joss2022-biggs-pymedphys": [
        "PyMedPhys: A community effort to develop an open, Python-based standard library for "
        "medical physics applications", "Summary", "Statement of need", "Acknowledgements",
        "*References",
    ],
}  # fmt: skip


@cache
def job(stem: str, folder: Path) -> ScriptJob:
    return run_script_job(
        CORPUS / "papers" / f"{stem}.pdf", JobSettings(output_folder=folder), folder / "work"
    )


@pytest.fixture(scope="module")
def out(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("corpus-jobs")


def test_every_paper_is_listed() -> None:
    assert sorted(CHAPTERS) == [paper.stem for paper in PAPERS]


@pytest.mark.parametrize("stem", sorted(CHAPTERS))
def test_every_paper_runs_with_its_chapters_and_no_problem(stem: str, out: Path) -> None:
    done = job(stem, out)
    got = [("" if c.selected else "*") + c.chapter.title for c in done.result.chapters]
    assert got == CHAPTERS[stem]
    assert done.report.problems == ()
    if stem in GERMAN:
        assert set(done.report.not_run) <= set(GERMAN_LATER_STEPS)
    else:
        assert done.report.not_run == ()
    assert all(c.spoken > 0 for c in done.result.chapters if c.selected)


@pytest.mark.parametrize("stem", GOLDEN)
def test_the_script_is_as_recorded(stem: str, out: Path, snapshot: SnapshotAssertion) -> None:
    assert job(stem, out).files.script.read_text(encoding="utf-8") == snapshot


@pytest.mark.parametrize("stem", GOLDEN)
def test_the_report_is_as_recorded(stem: str, out: Path, snapshot: SnapshotAssertion) -> None:
    done = job(stem, out)
    data = json.loads(done.files.report_json.read_text(encoding="utf-8"))
    data["sci2audio"] = "<version>"  # changes with every release, not with the job
    assert data == snapshot(name="json")
    assert done.files.report_markdown.read_text(encoding="utf-8") == snapshot(name="markdown")


@pytest.mark.benchmark
def test_benchmark_script_job(tmp_path: Path, benchmark) -> None:  # type: ignore[no-untyped-def]
    """A 20-page paper is prepared in under 30 s (#11): the 28-page arsiwalla paper."""
    source = CORPUS / "papers" / "arxiv2024-arsiwalla-qualia-meaning.pdf"

    def run() -> ScriptJob:
        return run_script_job(
            source, JobSettings(output_folder=tmp_path), tmp_path / "work", overwrite=True
        )

    benchmark.pedantic(run, rounds=3, iterations=1)
    assert benchmark.stats.stats.max < 30
