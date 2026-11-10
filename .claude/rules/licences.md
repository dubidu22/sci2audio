# Licence gate

Applies to every PR that adds or moves in a dependency, copied code, a model, a voice, a font, an icon or a sample text.

1. Find the licence at the source (repository LICENSE file, model card, PyPI metadata). Quote its SPDX identifier.
2. Allowed: MIT, BSD, Apache-2.0, ISC, MPL-2.0, LGPL, GPL-2.0-or-later, GPL-3.0, CC0, CC BY (texts and data, with attribution), public domain.
3. Refused: AGPL, SSPL, any non-commercial or research-only licence, "no licence stated", model weights with restricted licences, voices trained on data with unclear rights.
4. Copied code keeps its original copyright and licence notice at the top of each file.
5. Add a row to `THIRD_PARTY_LICENSES.md` (code, dependencies, models, programs) or `tests/corpus/LICENSES.md` (sample texts) in the same PR.
6. Code moved in from the private `audiobook-generator` repo: check it contains no third-party text, no personal data (names, addresses, e-mail), no keys or tokens, and no cloud or payment code.
7. When unsure, stop and ask in the PR; label it `risk:high`.
