# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Project setup: package layout in layers, CI on Linux, macOS and Windows, licence and layer checks, contributor and agent guidelines.
- PDF extraction (#23): records each page's text lines with font, size, bold, italic and position, its pictures and drawings, and the file's metadata as `Content`, deciding nothing (D-63, D-65); damaged, empty and password-protected files are refused with a clear message.
- Testing pipeline (D-58): property-based tests (Hypothesis), golden files (syrupy), security checks (Ruff security rules, pip-audit, zizmor), nightly slow tests and benchmarks, manual mutation testing (mutmut), release checklist and listening-test template.
