---
title: "Listening to Papers: a Pilot Note"
author:
  - name: A. Example
    affiliation: Nowhere Lab
  - name: B. Sample
date: 2026-11-13
lang: en-GB
doi: 10.0000/sci2audio.sample
---

# Listening to Papers

This note was written for the sci2audio tests. It describes a *made-up* pilot study
and **no real data**. Every sentence here is our own.[^own]

## 1 Introduction

People listen to papers while they walk, cook or commute. Spoken text runs at about
150 words per minute, so a 6,000-word paper takes 40 minutes.  
A hard line break sits just before this line.

Some readers prefer the café at noon; others read in Zürich at 7 °C. A dash – en, and
one — em; quotes “like these” and µs for microseconds.

### 1.1 Questions

1. How fast can a listener follow a formula such as $E = mc^2$?
2. Do footnotes[^fn] help or hurt?
   - when read in place
   - when read at the end

Prices like $5 and $10 stay text.

## 2 Method

> Listening is not reading.
>
> > A quote inside a quote.

We timed each session with this function:

```python
def words_per_minute(words, seconds):
    return 60 * words / seconds
```

    indented code is code too

| Group | Listeners | Minutes |
|:------|----------:|--------:|
| A     | 12        | 41      |
| B     | 9         | 38      |

![A bar chart of minutes per group](figures/minutes.png "Minutes")

![](figures/decoration.png)

The mean is

$$
\bar{x} = \frac{1}{n} \sum_{i=1}^{n} x_i
$$

and the sources are on [the project page](https://example.org/sci2audio) and
<https://example.org/data>; see also [the method](#method) and [note 1](#fn1).

Raw HTML stays: H<sub>2</sub>O and x<sup>2</sup>.<!-- a comment is not read -->

~~An old claim.~~ AT&amp;T &copy; 2026.

***

## 3 Results

Listeners kept up.[^fn]

[^own]: Nothing in this note is taken from anyone else.

[^fn]: A footnote with **bold** text,
    continued on a second line.
