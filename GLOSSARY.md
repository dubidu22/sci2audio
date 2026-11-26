# sci2audio

A local app that turns a scientific text into a faithful audiobook: the printed text is kept, and every change made for listening is a marked, explained edit.

## Language

### Text preparation

**Listening script**:
The text as it will be spoken, after the accepted edits.
_Avoid_: spoken version, rewritten text

**Text step**:
One rule set (citations, numbers, units, abbreviations ...) that looks at the printed text and proposes edits; it never changes the text itself.
_Avoid_: rule, filter, pass

**Edit**:
A proposed change to one span of a block (remove, replace, pause, ask), with its reason and category.
_Avoid_: change, rewrite, fix

**Reading**:
What the built-in text steps say for a span of printed text in one language: the span, the words spoken and the category of the step that reads it.
_Avoid_: prediction, interpretation

**Second run**:
The text steps run again over the listening script as if it were printed; a reading is stable when the second run speaks the same words.
_Avoid_: idempotency run, re-run
