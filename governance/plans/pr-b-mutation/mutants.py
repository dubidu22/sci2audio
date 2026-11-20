"""PR B (#474) planned mutants. Usage from the repo root:
    python3 mutants.py NAME   (applies one mutant in place; restore with git checkout)
Each must make tests/unit/test_web_markers.py or test_web_markers_survive.py fail."""
import sys

P = "src/sci2audio/web/markers.py"
MUTANTS = {
    # broken-file guard (D-728 ruling 1)
    "G1": ('        raise MarkersBroken(f"{path} can\'t be read: {error}") from None', "        return []"),
    "G2": ('        raise MarkersBroken(f"{path} is not a plain file")', "        return []"),
    "G3": ('        raise MarkersBroken(f"{path} is larger than {FILE_LIMIT} bytes")', "        pass"),
    # never dropped (D-728 ruling 1)
    "N1": ('            lost.append(Placed(marker, None, "not-found"))\n', "\n"),
    "N2": ("    return [item[2] for item in found] + unread + lost", "    return [item[2] for item in found] + unread"),
    "N3": ('            unread.append(Placed(marker, None, "not-read"))', "            pass"),
    # undo store expiry and limit
    "U1": ("self._clock() - entry[1] > UNDO_SECONDS", "self._clock() - entry[1] > UNDO_SECONDS * 2"),
    "U2": ("            while len(kept) > UNDO_KEPT:", "            while len(kept) > UNDO_KEPT + 1:"),
    # removal-box count (D-728 ruling 3)
    "C1": ("        return len(read_markers(work, document_id))", "        return 2"),
}

name = sys.argv[1]
old, new = MUTANTS[name]
text = open(P).read()
assert text.count(old) == 1, (name, old)
open(P, "w").write(text.replace(old, new, 1))
