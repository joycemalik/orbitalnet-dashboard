# Writing style for this paper (Joyce's voice, academic register)

Derived from the author's own informal writing (patterns only, no content copied), combined with
Gopen & Swan, "The Science of Scientific Writing" (1990), and Mensh & Kording, "Ten simple rules
for structuring papers" (2017). Numbers are never changed by a rewrite: they come from
`generated/*.tex` macros.

## The voice in one line
A sharp engineer explaining what they built and what they found: direct, practical, reasoning in
steps, confident where the data is strong, plain about what failed.

## Do
1. **Say what it does, then why it matters.** Lead with the action or the finding, then the consequence.
   "We add an explicit 'none of the above' class to the planner. This stops it from becoming
   confident about objects it has never seen."
2. **Reason in a visible chain.** Let one sentence set up the next with *so, then, which, because, even*.
   The reader should feel the logic move forward, one step per sentence.
3. **Keep sentences short to medium.** Aim for 12–24 words, and mix in a short one when a point lands.
   Split a sentence that needs a semicolon. Joining two clauses with ", so" or ", but" is welcome.
4. **Use plain words.** Write "use", not "leverage". Write "show", not "demonstrate". Write "help", not "facilitate".
   Write "about", not "approximately". A technical term is fine once it has been defined.
5. **Give concrete comparisons and examples.** Use a real event, a real satellite or a number, never an abstraction.
6. **Use "we" and the active voice.** "We replay 489 supernovae", not "489 supernovae were replayed".
7. **Put old information first and new information last** (Gopen & Swan). The end of a sentence is the stress position.
8. **One message per paragraph.** The first sentence says the message, the middle supports it,
   and the last sentence links it to what comes next.
9. **Be plain about failures.** "Realistic links did not help (−1.5 points). Two things explain this." No spin.
10. **Allow at most one big-picture sentence per section**, in the Introduction or Discussion, never in Results.

## Signature moves (measured from about 450 of the author's own messages)
These are the author's habits, translated into academic register. Use them, but don't overuse them.
- **Fact, then "so", then consequence.** "So" is the author's main connective, used about 4 times as often as
  "because". Prefer forward reasoning: "The fleet is sparse, so links are rarely up." Use "because"
  only when the cause must come second.
- **Claim, then "but", then a qualification.** "But" is the second most common linker. The author states something,
  then bounds it honestly: "The gain is small, but it holds on every seed." Use this for limitations.
- **Close with "that is why".** End a paragraph by naming the consequence: "That is why we report
  both runs." Use it at most once per section.
- **Concede, then commit.** "It may not reach X, but we consider it Y." Hedge once, then take a clear position.
- **"Once X, then Y"** for sequential method steps: "Once the posterior is updated, the planner…"
- **"Even" for surprising extremes.** "Even with ideal links, the dense fleet scores lower."
- **Examples come inline, with no "for example" scaffolding.** Name the thing directly: "tidal
  disruption events and superluminous supernovae, the real unknowns here, …"
- **Use "we can" and "we need" for capability and requirement.** "We can combine e-values by averaging." "We need no calibration data."
- **Plain, slightly informal words are fine** where they stay precise: "a lot more", "one of the best",
  "able to", "fits least badly", "does not help". Keep contractions out of the paper.
- **Flowing rather than chopped.** The author uses about twice as many commas as full stops. Join two short
  related clauses with a comma and "so" or "but", rather than leaving many 6-word sentences.
- **Self-assessment is honest and practical.** "We were not satisfied with the first version, so we
  re-ran it" fits better than "The methodology was subsequently refined."

## Don't (AI tells: remove on sight)
- "X is not Y; it is Z" / "not merely … but …" reveal constructions
- Colon set-ups for a punchline ("The answer is simple: …"), and semicolon chains
- *Italics* for emphasis (keep italics for defined terms and variables only)
- Em-dashes used as dramatic pauses, at most one per page
- Inline enumerations "(i) … (ii) … (iii)" inside a paragraph. Use a short list or separate sentences
- Triads of adjectives or clauses for rhythm ("simple, robust and general")
- Filler words: delve, crucial, pivotal, landscape, notably, furthermore, moreover, it is worth noting,
  plays a key role, in the realm of, a testament to, seamless, robust (unless measured), novel (let the reader judge)
- Stacked hedges ("may potentially suggest"). Hedge once, where the evidence is actually weak
- Rhetorical questions in the body text (the Introduction's research questions are fine as a list)

## Paper-level structure
- Abstract: problem (1 sentence), gap (1), what we did (2), key numbers (2–3), meaning (1).
- Introduction: context, then the problem in one concrete example, then the questions, then the contributions as a short list, then the roadmap in one sentence.
- Results: each subsection opens with the answer, then the evidence, then the caveat.
- Discussion: what it means, what it doesn't show, what we would do next.

## Process
Rewrite one section at a time in `rewrite/`, then the author reviews it. Add each piece of feedback here as a rule.

## Calibration from aggregate counts (500 of the author's own messages, 2026-11-24)
Only word rates were computed. No message was quoted or copied, and the source stays on the author's machine.
- "so" about 7.8 per 1k words, "because" about 0.3, so prefer forward "X, so Y" almost always.
- "but" about 5.8 per 1k: the main way to qualify a claim.
- "also" (3.2), "then" (2.5), "still" and "even" (about 1.5 each) are natural additive and contrast words.
- "then we" and "so we" are common openings for a step in reasoning.
- About 2 commas per full stop, so longer flowing sentences joined by commas fit the voice.
