# Mosaic demo: cheap-first plans for provenance screening

Which works in the National Gallery of Art (NGA) changed hands between 1933 and 1945 through a person on the 1946 ALIU
Red Flag Names List, and where is the evidence insufficient? This folder answers that question with several **plans**
and measures each one on quality, unsupported facts and compute time. The plans run locally with open-weight models; the
reference labels, the Chicago judgments and the one-off reading for the graph were made by Claude (see below).

## Requirements
- macOS or Linux, Python 3.9+, no Python packages beyond the standard library.
- [Ollama](https://ollama.com) with `qwen3:8b` and `qwen2.5:14b` (`ollama pull qwen3:8b && ollama pull qwen2.5:14b`).
  Measured on an Apple M4 Pro, 24 GB.
- The data files in `data/` (frozen) and `../phase0/data/` (NGA open data, AIC export, Red Flag list).
- On a Mac, wrap long runs in `caffeinate -i` so the machine does not sleep.

## Rerun everything (about 2 hours of model time; seconds when `cache/` is present)
```bash
python3 -I -u extract.py qwen3:8b    data/testset_nga.json out/run_P1.json      # P1 small model
python3 -I -u extract.py qwen2.5:14b data/testset_nga.json out/run_P2.json      # P2 large model
python3 -u cascade.py qwen3:8b qwen2.5:14b data/testset_nga.json out/run_P3.json # P3 cascade (reuses P1/P2 answers)
python3 reference_labels.py                                                     # agreement of the two labelers
python3 score.py out/run_P1.json out/run_P2.json out/run_P3.json --ci            # P0 included; 95% bootstrap intervals
python3 contradictions.py                                                       # FR-10 report -> analysis/
python3 -u retry.py qwen3:8b data/testset_nga.json out/run_P1r.json             # P1r: same-model retry baseline
python3 -u verify.py qwen3:8b qwen3:8b data/testset_nga.json out/run_P4.json    # P4: extractor + verifier
python3 -u adjudicate.py qwen3:8b out/run_P3.json out/run_P5.json               # P5: Red Flag adjudicator
python3 results.py && python3 figure.py && python3 make_resultspage.py          # final numbers, figure, results page
```
Or run every remaining model job in one go, kept awake and restarting Ollama if it quits: `caffeinate -i sh run_queue.sh`.
It also re-measures P1, P2 and P3 on the 30 dev documents with empty caches (`out/timing.txt`): real clock time,
including model loading, which the cached per-call durations above leave out. `repro_check.py` recomputes 10 test
documents into an empty cache and compares them with the original answers.
Every model answer is cached in `cache/` under a hash of the full request (model, prompt, options), so a rerun with the
same settings reproduces the same output without calling a model. Delete `cache/` to recompute from scratch.

Second institution (Art Institute of Chicago, 20 texts):
```bash
python3 -I -u extract.py qwen3:8b    data/aic20.json out/aic_P1.json
python3 -I -u extract.py qwen2.5:14b data/aic20.json out/aic_P2.json
python3 -u cascade.py qwen3:8b qwen2.5:14b data/aic20.json out/aic_P3.json
python3 score_aic.py                                                            # uses data/aic_judged.json
```

Ask a question in plain language (the plan is chosen from the measured results in `out/plan_table.json`):
```bash
python3 ask.py "Which paintings passed through a Red Flag dealer between 1933 and 1945? I want a quick answer."
python3 ask.py --plan-only "Same question, I have 10 minutes."
```

## Provenance graph (read once with Claude, ask with a local model)

```bash
python3 graph.py                                          # build graph/graph.json and score Claude's reading
python3 ask_graph.py "Who owned Saint Jerome in the Wilderness?"
python3 ask_graph.py "From whom did Samuel H. Kress buy paintings?"
```

- **Reading:** four Claude agents (Opus, through Claude Code) read the 100 test texts once into ownership events
  (`graph/claude_events_*.json`), seeing only id, title and text (never the museum's owner list), under one set of
  explicit rules: one step per holding (repeat owners included), joint buyers marked, agents of a sale kept as
  sellers, years only from dates the text gives, and the text's own hedge words ("possibly") kept. A Claude agent
  then merged 30 name variants, each with a written reason (`graph/owner_aliases.json`); a person and their
  foundation, family members, branches in different cities and generic labels stay apart. This step is not local; it
  was done once and its output is committed, so everything after it runs offline. A first reading with looser rules
  is kept in `graph/previous/`.
- **Checks and scores:** every kept step's quote is in the source text (705 of 705); `graph.py` scores the reading
  like any plan: owners F1 0.790 (P 0.698, R 0.911; 95% interval 0.757-0.823), no different from the best local plan
  P3 (paired difference -0.019 to +0.018). The first, looser reading scored 0.813, so reading conventions move this
  score as much as the model. Screening: precision 1.00, recall 0.73 (19 of 26), F1 0.844.
- **Why the misses happen** (`linking_gap.py`): each of the 7 missed texts holds the decisive step. One is a spelling
  ("K. Muhlmann", listed as "Muehlmann"), three rest on firm entries (Wildenstein, Durand-Ruel), one needs to know
  that the Buchholz Gallery was Karl Buchholz's firm, two holders have no date. The full-name rule can link only 616
  of the list's 1,019 surnames (firms, agencies and "Surname Forename" entries have no parsable forename; common
  surnames such as Fischer are skipped). Repairing person names recovers the spelling case with no new false flag
  (F1 0.844 -> 0.870); also linking firm names recovers three more but flags disputed Knoedler cases. This is a
  sensitivity analysis: the published numbers keep the original linker.
- **Asking:** the local model (`qwen3:8b`) only turns the question into a lookup (history, works of an owner, sellers
  to an owner, Red Flag screening with a period). Plain code answers from the graph in milliseconds (reading the question takes about 2 s)
  and quotes the text for every step; a history ends with how the museum itself acquired the work. Artworks or owners outside the graph get "NOT IN GRAPH"; questions outside the four
  lookups (prices, painters, general knowledge) get "OUT OF SCOPE" instead of a guess. "Was X a Nazi?" is answered
  only with the 1946 list's own note on X, in full, and X's listed holdings, never with a verdict. If no entry
  matches, the answer shows same-surname entries as unconfirmed candidates and says that this is not proof of absence.
- **Tests:** `test_graph.py` (39 tests, 7 of them live with Ollama). `question_bank.py` asks 31 plain-language
  questions (paraphrases, typos and accents, periods, listed and unlisted people, questions outside the data, a
  prompt injection) and checks each answer against an expectation written before the run: 31/31.

## Tests

```bash
python3 -m unittest -v      # from demo/: 104 tests, about 20 s, no model needed
```

- `test_logic.py`: the rules every number rests on (name matching, holding periods, scoring, JSON checks, escalation).
  One test is marked as an expected failure: the known Hotel Drouot false positive (NGA 52183).
- `test_demo.py`: every published number recomputes from the saved runs; every flag quotes the source text; `ask.py`
  gives the same answers offline and handles artworks outside its sources. Five live tests check how the local model
  reads questions; they are skipped when Ollama is not running.

## Plans
| Plan | What it does |
|---|---|
| P0 | Red Flag full-name string match on the raw text; no model |
| P1 | `qwen3:8b` extracts ownership events (owner, role, date, year, place, exact quote) |
| P2 | `qwen2.5:14b` does the same |
| P3 | P1 first; the document goes to P2 only when a free check fails (error, quote not in text, no dated 1933-45 event) |
| P4 | P1, then a verifier pass that fixes, drops or adds events (`verify.py`) |
| P1r | P1, and on a parse error or truncation the same model retries with a larger output limit (`retry.py`) |
| P5 | An adjudicator reads each flagged match with the list entry's note: same person? which role? (`adjudicate.py`) |

## How the numbers are made
- **Owners** (headline): extracted owners vs the NGA's own structured list of previous owners (`objects_constituents.csv`).
  The receiving museum is not counted as a previous owner; quotes are compared with whitespace normalised.
- **Screening**: an owner's holding period runs from their event's year to the next dated event; a document is
  flagged when a listed owner's period meets 1933-45. Only events whose quote is found in the text count.
- **Labels**: reference labels from two Claude agents (through Claude Code), the second blind to the first
  (`data/label_proposals.json`, `data/labels_second.json`; agreement 91%, Cohen's kappa 0.84). Both are the same model,
  so agreement overstates independence. Disagreements are left out. No domain expert was available. Chicago precision
  comes from a blind Claude judge (`data/aic_judged.json`).
- **Test set**: 100 distinct NGA texts, stratified (`build_testset.py`, seed 42, frozen). Prompts were developed on a
  separate 30-document dev split (`data/devset_nga.json`); scoring rules changed after test results were seen, for all
  plans alike (write-up section 6).
- **Cost**: model calls, tokens, and seconds on the machine above. Cached answers keep their original timing.

## Files
| Path | What |
|---|---|
| `extract.py`, `retry.py`, `cascade.py`, `verify.py`, `adjudicate.py` | the plans |
| `score.py`, `score_aic.py`, `score_p5.py`, `reference_labels.py` | scoring |
| `results.py`, `figure.py`, `make_resultspage.py` | final numbers (`out/results.json`), `docs/figure.svg`, `docs/results-page.html` |
| `run_queue.sh`, `repro_check.py` | remaining runs in one go; reproducibility check |
| `ask.py` | question to plan to answer |
| `contradictions.py` | FR-10: text vs structured owner list |
| `build_testset.py`, `build_aic.py` | frozen samples (refuse to overwrite without `--force`) |
| `out/` | run outputs, logs, `scores*.txt`, `plan_table.json` |
| `analysis/` | error analysis and contradiction report |
