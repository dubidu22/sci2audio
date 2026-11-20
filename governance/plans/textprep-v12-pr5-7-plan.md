# Combined PR for D-605 items 5 to 7 (plan)

One branch from main (`textprep/links-citations-quotes`), one PR. It is critical, because it adds golden regression cases, so it waits for approval before any code. The readings are those of D-605 (plan sections PR 5 to 7), and nothing new is decided here.

Order inside the branch, one commit series per part, each with its tests first:

1. **Links (#326, #337), links step and citations step.**
   - #326: a URL ends before a ")" that closes a bracket opened before the URL, when "(" or "[" follows right after it. "(see https://example.org)(Smith, 2019) it holds." reads "it holds.", and "(Smith, 2019, https://example.org)(Smith, 2019) it holds." reads "Smith it holds.", on both runs.
   - Also for #326, the carve-out in the citations sibling-bracket property for link brackets glued to the next bracket goes.
   - #337: a join word or separator ("and"/"und", ";", ",") that a removed link leaves at a bracket's edge goes with the link, as #305 does after a removed citation. "It holds (see https://example.org and Lee, 2019) here." reads "It holds here."
2. **Citation nests (#338, #339, #278 subject row), citations step, inside the D-599 work cap.**
   - #338: a glued "[12]" after a removed citation goes with it, the D-605 reading. "As said by Lee (Smith, 2019)[12] it holds." reads "As said by Lee it holds."
   - #339: year shells around a citation that goes go with it, the D-605 reading. A nest 2, 3 or 4 deep reads "Text more."
   - #278: the subject row "((Smith, 2019); Jones, 2020) is cited." reads "Smith and Jones is cited.", as the flat form does. #278 closes with this PR.
3. **#342, German abbreviations step.** A German abbreviation that ends a sentence before a closing quote („…“, »…«, ›…‹) and a capital keeps its full stop: "Er schrieb „usw.“ Dann ging er." reads "Er schrieb „und so weiter.“" and then "Dann ging er." A title abbreviation before a name ("„Dr.“ Müller") must not end the sentence.

Tests: for each issue, an English and a German regression case where the issue asks for both, plus unit rows. Every case also reads the same on a second run.

Probes before the PR opens:
- the #330 token fuzz (20k texts, en and de, whole chain twice);
- nests one deeper than any look cap;
- the timing ratios on main and on the branch (#317 lesson);
- nightly seeds 7, 555 and 8080;
- the 13 corpus documents compared byte for byte with main.

Size: medium to large, about 3 source files (links, citations, abbreviations) and 4 test files.
