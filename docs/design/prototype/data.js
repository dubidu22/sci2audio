/* Synthetic demonstration content. Every paper, author and number here is invented for the prototype. */
window.S2A_DATA = (() => {
  const cut = (t) => `<span class="cut" data-why="cit">${t}</span>`;
  const said = (printed, read, why) => `<span class="said" title="Printed “${printed}”, read as “${read}”. ${why}">${printed}</span>`;

  // Chapter 3 of the main demo paper: blocks in reading order.
  // p = paragraph of sentences; h = section heading; pb = page break; fn = footnote read after its mark; skip = spoken notice
  const sleepCh3 = [
    { h: "3.1 Sleep duration" },
    { p: [
      `Across the 36 participants, nightly sleep in the diary weeks averaged 6.4 ${said("h","hours","Unit read as a word.")} on early shifts and 7.5 ${said("h","hours","Unit read as a word.")} on late shifts ${cut("(Okafor &amp; Lind, 2021)")}.`,
      `Reaction times on the vigilance task fell by 12 ${said("ms","milliseconds","Unit read as a word.")} for each additional hour of sleep ${cut("(t(34) = 2.81, p &lt; .01)")}.<span class="fnmark" aria-label="footnote 3">3</span>`,
    ]},
    { fn: "3", text: "Two participants did not complete the second diary week; their first-week data are included." },
    { p: [
      `Naps, ${said("e.g.","for example","Abbreviation spelled out.")} after lunch, were not counted, because the diaries did not record them reliably.`,
      `Shorter sleep went with slower responses in every shift pattern we observed, including the rotating one.`,
      `The effect held after controlling for age and caffeine intake, which suggests that duration rather than timing drives the change.`,
    ]},
    { skip: "Table 2 is skipped. It lists reaction times by shift pattern." },
    { pb: "Page 8" },
    { h: "3.2 Timing of sleep" },
    { p: [
      `When we compared participants who slept the same number of hours at different times of day, the difference in reaction time shrank to 3 ${said("ms","milliseconds","Unit read as a word.")} ${cut("[14]")}.`,
      `This is smaller than the variation between test sessions, so we do not interpret it further.`,
      `Participants on late shifts reported more interrupted sleep, but interruptions did not predict reaction times once total duration was known.`,
    ]},
    { p: [
      `Taken together, the results point to a simple rule for shift planning: protect the length of the sleep window first, and its position second.`,
      `We return to the limits of this rule in the discussion.`,
    ]},
  ];

  const papers = [
    {
      id: "sleep", title: "Sleep and reaction time in shift workers", authors: "M. Varga, T. Ahn (synthetic example)",
      kind: "pdf", lang: "en", langSource: "stated in the file", pages: 24, words: 9180, audio: "1 h 08 min", audioSec: 4080,
      state: "ready", listened: 0.38, lastOpened: "Today, 09:14", voice: "Heart", speed: 1.25,
      chapters: [
        { t: "1. Introduction", page: 1, sentences: 64, sec: 520 },
        { t: "2. Method", page: 4, sentences: 118, sec: 980 },
        { t: "3. Results", page: 7, sentences: 96, sec: 790 },
        { t: "4. Discussion", page: 12, sentences: 141, sec: 1140 },
        { t: "5. Limitations", page: 18, sentences: 52, sec: 420 },
        { t: "6. Conclusion", page: 21, sentences: 28, sec: 230 },
        { t: "References", page: 22, sentences: 0, sec: 0, off: "references" },
      ],
      currentChapter: 2, resumeSentence: 2, content: sleepCh3,
    },
    {
      id: "gruen", title: "Aufmerksamkeit und Erholung in städtischen Grünräumen", authors: "J. Brandt (synthetisches Beispiel)",
      kind: "pdf", lang: "de", langSource: "aus dem Text erkannt", pages: 18, words: 7020, audio: "54 min", audioSec: 3240,
      state: "ready", listened: 0, lastOpened: "Yesterday", voice: "Thorsten", speed: 1,
      chapters: [
        { t: "1. Einleitung", page: 1, sentences: 48, sec: 460 }, { t: "2. Forschungsstand", page: 3, sentences: 102, sec: 990 },
        { t: "3. Methode", page: 9, sentences: 66, sec: 640 }, { t: "4. Ergebnisse und Diskussion", page: 12, sentences: 120, sec: 1150 },
        { t: "Literatur", page: 17, sentences: 0, sec: 0, off: "references" },
      ],
    },
    {
      id: "methods", title: "Methods reader, week 6: mixed-effects models", authors: "Course reader (synthetic example)",
      kind: "pdf", lang: "en", langSource: "stated in the file", pages: 142, words: 51200, audio: "about 6 h 20 min",
      state: "making", progress: 0.64, lastOpened: "Today, 08:02",
      job: { chapter: 5, chapters: 8, sentences: 2484, total: 3880, left: "about 41 minutes left" },
      chapters: Array.from({ length: 8 }, (_, i) => ({ t: `${i + 1}. Unit ${i + 1}`, page: 1 + i * 17 + (i % 3), sentences: 310 + ((i * 137) % 260), sec: 2100 + ((i * 523) % 1400) })),
    },
    {
      id: "seg", title: "A survey of sentence segmentation for speech output", authors: "R. Ilunga (synthetic example)",
      kind: "epub", lang: "en", langSource: "stated in the file", pages: 61, words: 21400, audio: "about 2 h 40 min",
      state: "analysed", lastOpened: "Mon 12 Nov",
      chapters: [
        { t: "Title page", page: 1, sentences: 3, sec: 0 }, { t: "Preface", page: 2, sentences: 22, sec: 0 },
        { t: "1. Why sentences matter", page: 4, sentences: 140, sec: 0 }, { t: "2. Rule-based segmenters", page: 14, sentences: 260, sec: 0 },
        { t: "3. Statistical segmenters", page: 29, sentences: 240, sec: 0 }, { t: "4. Abbreviations and numbers", page: 41, sentences: 190, sec: 0 },
        { t: "5. Evaluation", page: 52, sentences: 120, sec: 0 }, { t: "Imprint", page: 60, sentences: 6, sec: 0, off: "publisher" },
        { t: "Bibliography", page: 60, sentences: 0, sec: 0, off: "references" },
      ],
    },
    {
      id: "power", title: "Lecture notes: statistical power", authors: "Pasted text", kind: "txt", lang: "en", langSource: "not analysed yet",
      pages: 0, words: 2310, state: "new", lastOpened: "Mon 12 Nov", chapters: [],
    },
    {
      id: "field", title: "Field notes on community organising in three neighbourhoods", authors: "A. Okoye (synthetic example)",
      kind: "pdf", lang: "en", langSource: "stated in the file", pages: 88, words: 30400, audio: "about 3 h 50 min",
      state: "failed", progress: 0.42, lastOpened: "Sun 11 Nov",
      failure: { chapter: 4, reason: "The voice stopped: the computer ran out of memory.", kept: 3 },
      chapters: Array.from({ length: 7 }, (_, i) => ({ t: `${i + 1}. Part ${i + 1}`, page: 1 + i * 12 + (i % 2), sentences: 220 + ((i * 91) % 180), sec: 1500 + ((i * 377) % 900) })),
    },
    {
      id: "longbook", title: "Foundations of measurement theory, volumes I–III", authors: "Made on the command line (synthetic example)",
      kind: "epub", lang: "en", langSource: "stated in the file", pages: 1140, words: 402000, audio: "51 h 40 min",
      state: "cli", listened: 0.07, lastOpened: "Fri 9 Nov", chapters: Array.from({ length: 38 }, (_, i) => ({ t: `Chapter ${i + 1}`, page: 1 + i * 30, sentences: 640 + ((i * 211) % 520), sec: 3600 + ((i * 733) % 2600) })),
    },
  ];

  // Change categories with counts for the prepare view of "sleep"
  const categories = [
    { id: "page-furniture", n: 96, heard: 0, examples: [["Sleep and reaction time · 7", "not read", "Running head, repeated on 22 pages."], ["7", "not read", "Page number."]] },
    { id: "characters", n: 41, heard: 12, examples: [["reac-↵tion", "reaction", "A word hyphenated at the line end is joined again."], ["ﬁ", "fi", "Ligature read as plain letters."]] },
    { id: "citations", n: 58, heard: 58, examples: [["(Okafor & Lind, 2021)", "not read", "Author-year citation."], ["[14]", "not read", "Numbered citation."]] },
    { id: "links", n: 4, heard: 4, examples: [["at https://osf.io/example", "not read", "Link; “at” goes too, so the sentence still reads."]] },
    { id: "units", n: 23, heard: 23, examples: [["12 ms", "12 milliseconds", "Unit read as a word."], ["6.4 h", "6.4 hours", "Unit read as a word."]] },
    { id: "statistics", n: 17, heard: 17, examples: [["t(34) = 2.81, p < .01", "not read", "Test statistic inside a citation bracket."], ["95% CI [4.1, 19.9]", "95% confidence interval 4.1 to 19.9", "Confidence interval read in words."]] },
    { id: "abbreviations", n: 12, heard: 12, examples: [["e.g.", "for example", "Abbreviation spelled out."], ["i.e.", "that is", "Abbreviation spelled out."]] },
    { id: "footnotes", n: 6, heard: 6, examples: [["…reliably.³", "Footnote 3. Two participants…", "Read right after the sentence with its mark (page 7)."]] },
    { id: "placeholders", n: 5, heard: 5, examples: [["Table 2", "Table 2 is skipped. It lists reaction times by shift pattern.", "A table is replaced by a short spoken notice."]] },
  ];

  const captures = [
    { id: "c1", paper: "sleep", ch: 2, kind: "quote", s: 1, text: "Reaction times on the vigilance task fell by 12 ms for each additional hour of sleep.", page: 7, at: "18:42" },
    { id: "c2", paper: "sleep", ch: 2, kind: "note", s: 2, quote: "Naps, e.g. after lunch, were not counted, because the diaries did not record them reliably.", text: "Check whether naps were excluded in the 2019 cohort too. Ask in seminar.", page: 7, at: "19:05" },
    { id: "c3", paper: "sleep", ch: 2, kind: "card", s: 4, front: "What drives the reaction-time effect: sleep duration or sleep timing?", back: "Duration. The effect held after controlling for age and caffeine; timing changed it by only 3 ms.", page: 7, at: "20:11" },
    { id: "c4", paper: "sleep", ch: 0, kind: "mark", s: 0, text: "Definition of shift patterns", page: 2, at: "03:30" },
    { id: "c5", paper: "sleep", ch: 1, kind: "quote", text: "Each participant kept a sleep diary for two consecutive weeks.", page: 4, at: "09:58" },
    { id: "c6", paper: "sleep", ch: 1, kind: "card", front: "How long did participants keep the sleep diary?", back: "Two consecutive weeks.", page: 4, at: "10:02" },
    { id: "c7", paper: "gruen", ch: 1, kind: "note", quote: "Die Erholungswirkung war in kleinen Parks ähnlich stark wie in großen.", text: "Gegenargument zu Kapitel 2 der Hausarbeit.", page: 5, at: "12:40" },
    { id: "c8", paper: "gruen", ch: 3, kind: "quote", text: "Aufmerksamkeit erholte sich nach zwanzig Minuten im Grünen messbar.", page: 13, at: "41:12" },
    { id: "c9", paper: "longbook", ch: 2, kind: "card", front: "What is an interval scale?", back: "A scale with meaningful differences but no true zero.", page: 88, at: "2:14:05" },
  ];

  return { papers, categories, captures };
})();
