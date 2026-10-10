# Cheap first, escalate on failure

Plan choice for provenance screening with local LLMs. An independent work sample by Malek Khannoussi for the PhD
position in the Mosaic project (agentic data processing for the digital humanities). Not affiliated with HPI or MIT;
not peer-reviewed.

**Question.** Which works in the National Gallery of Art passed between 1933 and 1945 through a person or firm on the
1946 ALIU Red Flag Names List, and how should a system spend compute to answer that reliably? Seven plans, from plain
name matching to a two-model cascade, run on 100 provenance texts (plus 20 from the Art Institute of Chicago) with
local models on one laptop, scored with 95% bootstrap intervals. Every answer quotes the sentence it rests on.

**Read first:** [`docs/WRITEUP.pdf`](docs/WRITEUP.pdf) (4 pages).

## Results in brief

| Plan | Owner F1 (95% CI) | Screening F1 | Compute (s / 100 docs) |
|---|---|---|---|
| P0 name match | — | 0.66 | 0 |
| P1 small model (`qwen3:8b`) | 0.766 (0.725–0.808) | 0.85 | 2,137 |
| P1r small + retry on failure | 0.773 (0.735–0.812) | 0.85 | 2,234 |
| P2 large model (`qwen2.5:14b`) | 0.779 (0.741–0.812) | 0.77 | 2,928 |
| P3 cascade | 0.791 (0.756–0.827) | 0.85 | 2,853 |
| P4 small + verifier | 0.764 (0.722–0.805) | 0.85 | 4,531 |

- Reading the text instead of matching names raises screening precision from 0.54 to 0.95.
- A larger model alone is not reliably better; the cascade beats the small model but not the large one, and it is
  only cheaper than the large model when cost ratio plus escalation share is below 1.
- The museum's own structured owner list omits up to 148 owners that its texts name.
- A one-off reading of the texts by Claude, stored as a provenance graph, held the decisive step in every missed
  case: linking names to the 1946 list and dating holdings, not reading, limit screening. The graph answers questions
  through a local model in milliseconds and refuses what it does not cover (`demo/ask_graph.py`).
- Limits (small samples, LLM-made labels, approximate name matching) are in section 6 of the write-up.

## How this was made

I built the study with an AI coding assistant (Claude Code). I set the goals and constraints (public data, local models at zero cost, measured comparisons), made the decisions and reviewed the results; the assistant wrote most of the code, ran the experiments and drafted the analyses. The plans ran on local models; Claude also made the reference labels, judged the Chicago answers and read the texts once for the graph. Every number can be recomputed from this repository: the Claude-made labels, judgments and
graph reading are committed, so nothing needs Claude to rerun.

## Rerun

Requirements: Python 3.9+ (standard library only) and, for new model runs, [Ollama](https://ollama.com) with
`qwen3:8b` and `qwen2.5:14b`. Every model answer is cached in `demo/cache/`, so the commands below recompute all
numbers in seconds without a model:

```bash
cd demo
python3 results.py        # every plan with 95% intervals -> out/results.json
python3 score.py out/run_P1.json out/run_P2.json out/run_P3.json --ci
python3 figure.py         # -> docs/figure.svg
python3 -m unittest      # 104 tests: rules, published numbers, evidence, ask.py, graph
```

To recompute from scratch, delete `demo/cache/` and run `caffeinate -i sh run_queue.sh` (about two hours on an Apple M4
Pro). Details, every script and how each number is made: [`demo/README.md`](demo/README.md).

## Repository

| Path | What |
|---|---|
| `docs/` | write-up (PDF and Markdown), figure, results page |
| `demo/` | the plans, scoring, frozen test and dev sets, labels, cached model answers, run outputs, analyses |
| `phase0/` | data feasibility and Palimpzest spikes; scripts that fetch and filter the source data |

## Data and licences

- Code: MIT licence (see `LICENSE`).
- National Gallery of Art open data and Art Institute of Chicago API: CC0. The raw downloads are not included;
  `phase0/scripts/` fetches them.
- ALIU Red Flag Names List (1946, OSS Art Looting Investigation Unit, NARA): a US government document; the parsed list
  in `phase0/data/red_flag_names.csv` comes from the transcription published by the Commission for Looted Art in Europe
  (lootedart.com), credited here.
- Model answers in `demo/cache/` were produced locally with open-weight models.

Output of this code lists candidates and evidence for experts. It is not a finding about any person and not a
restitution claim.
