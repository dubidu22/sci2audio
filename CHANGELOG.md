# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Project setup: package layout in layers, CI on Linux, macOS and Windows, licence and layer checks, contributor and agent guidelines.
- PDF extraction (#23): records each page's text lines with font, size, bold, italic and position, its pictures and drawings, and the file's metadata as `Content`, deciding nothing (D-63, D-65); damaged, empty and password-protected files are refused with a clear message.
- Layout, step 1 (#21): a new pipeline stage turns the extracted `Content` into a `Document` in reading order: page furniture (running heads, page numbers, footers, line numbers, side stamps, a printed table of contents, a sidebar) is found and kept apart, columns are found band by band, and each page is read column by column (D-63, D-67). Blocks are still single lines; paragraphs, kinds and sections follow.
- Testing pipeline (D-58): property-based tests (Hypothesis), golden files (syrupy), security checks (Ruff security rules, pip-audit, zizmor), nightly slow tests and benchmarks, manual mutation testing (mutmut), release checklist and listening-test template.
