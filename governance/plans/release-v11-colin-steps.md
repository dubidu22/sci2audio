# v1.1.0: Colin's hand steps

The release branch `release/1.1` is ready at 08d5965. Steps 1 to 5 take about an hour and can be done in any order after step 1. Send the results in the thread, and I'll write them into the release-day PR. Steps 6 and 7 come later, when I say so.

**1. Get the release branch**

```
cd ~/Documents/Projekte/sci2audio
git fetch origin
git switch -c release/1.1 --track origin/release/1.1
uv sync
uv run sci2audio --version
```

This switches your clone to the release branch and installs its packages. The last line must print 1.1.0. If `uv run` says "No module named 'sci2audio'", run `chflags -R nohidden .venv` and try again (the iCloud flag, #255).

**2. Listening test (about 30 minutes, plus the time the audiobooks take to make)**

```
uv run sci2audio voices download --language de
for f in joss2021-waskom-seaborn acl2023-chi-plue acl2023-hardt-ellipsis acl2023-nowak-prefix-probabilities arxiv2024-liu-orbital-hall arxiv2024-arsiwalla-qualia-meaning arxiv2017-maass-privacyscore; do uv run sci2audio convert tests/corpus/papers/$f.pdf -o ~/Desktop/sci2audio-1.1/$f; done
```

The first line fetches the German voice Thorsten (about 330 MB). It shows the files and asks before it downloads. The second line makes the seven audiobooks in folders on your Desktop: the six English papers from last time and the German one.

```
uv run sci2audio listen tests/corpus/papers/joss2021-waskom-seaborn.pdf -o ~/Desktop/sci2audio-1.1/joss2021-waskom-seaborn
```

This opens one audiobook in the read-along player. For each of the others, run the same line with the other paper's name in both places.

Listen to the same 10 paragraphs as for 1.0.0 (rows 1 to 10 in `docs/listening-tests/1.0.0.md`), plus three new German rows:

- **11.** `arxiv2017-maass-privacyscore.pdf`, ch. 3 "2 Verwandte Arbeiten", from "Mehrere Dienste erlauben eine automatisierte Untersuchung" to the notice "Abbildung 1 wird übersprungen." and its caption. This checks German prose, names and a German figure notice.
- **12.** The same paper, ch. 4 "3 PrivacyScore im Überblick", from "Flexibilität durch Nutzerorientierung" through the next sentence, which ends "… voneinander zu unterscheiden und Zusammenhangsanalysen durchzuführen." This checks "z. B." read as "zum Beispiel", and the lead-in heading run into the paragraph.
- **13.** The same paper, ch. 7 "6 Rechtliche Fragestellungen", from "Zuerst stellt sich allerdings die Frage, wem die zu untersuchenden Daten „gehören“" to the end of the next sentence, "… im Sinne von § 90 BGB bestehen." This checks German legal citations such as "§ 903 BGB".

This time, give each row a score from 1 (bad) to 5 (perfect) for each of these: terms and names; numbers, units and statistics; pauses; notices; read-along in sync. Add a few words on anything you heard.

**3. Screen reader, short (about 15 minutes)**

Turn on VoiceOver (Cmd-F5) and use only the keyboard to try what is new in 1.1:
- the Speed choice in the player;
- "Continue from …" and "Start from the beginning" when you open the player again;
- "Move up" and "Move down" in a document's chapter list;
- the subtitles checkbox on the document page.

The known VoiceOver trouble is #314 and is planned for the redesign, so no need to report it again. Say what else got in your way.

**4. Speed on the M4 (about 10 minutes)**

```
uv run python scripts/speed.py
```

This measures the English voice on the MPS and CPU devices and writes a JSON file in the clone. Paste the printed rows into the thread, and keep the JSON file.

**5. Security alerts**

Open https://github.com/dubidu22/sci2audio/security/dependabot and say whether any alert is open.

**Optional:** open one `.m4b` from the Desktop folders in Apple Books. Check the chapter titles, jumping between chapters, the cover, and the AI-generated label in the details.

**6. Later: the tag** (only when I post the exact commit)

```
cd ~/Documents/Projekte/sci2audio
git fetch origin
git tag -a v1.1.0 -m "sci2audio 1.1.0" origin/release/1.1
git push origin v1.1.0
```

This puts the release tag on the tip of the release branch and pushes it, which starts the release run.

**7. Later: approve the publish**

When I say the run is waiting, open the run link I send, click "Review deployments", tick "pypi" and click "Approve and deploy".
