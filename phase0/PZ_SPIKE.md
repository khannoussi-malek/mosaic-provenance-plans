# Palimpzest spike: verdict

**USE IT PARTIALLY.** Palimpzest (PZ) 1.5.3 runs end to end on a local Ollama model with no key and no cost. It is a good fit for the operator layer: `sem_filter`, `sem_flat_map`, its physical-operator zoo (bonded LLM call, mixture-of-agents, critique-and-refine, RAG reduction, split-merge) and its per-operator stats (time, $, tokens). Its *public* API only returns the single plan the policy picks. To build a "compare N plans" table we have to call optimizer internals (`plans.py`, about 40 lines) or loop over configs ourselves. Plan for a thin harness of our own on top of PZ: plan enumeration, gold labels, a quality metric and the comparison table. Don't write a planner from scratch, and don't rely on PZ's built-in optimizer story.

Code: `phase0/pz_spike/` (`pipeline.py` = the program, `plans.py` = plan enumeration and execution, `data/provenance5.json`, `out/`).

## 1. Install
- `uv venv --python 3.12 && uv pip install palimpzest` took **37 s** and installed cleanly. It needs **Python >= 3.12** (the system 3.9 won't work). The venv is **1.5 GB / 186 packages**: torch (553 MB), sentence-transformers, chromadb, gradio, vllm hooks, smolagents, kubernetes, plus pins `numpy==2.0.2`, `psutil==5.9.5` and `litellm<1.82.7`. Keep it in its own venv.
- **`import palimpzest` fails offline.** At import time it fetches its model and price table from S3 (`pz_models_information.json`). With no network: `ValueError: Palimpzest currently does not contain information about this model.` That's a live-demo risk. Fix: vendor the JSON with a one-line patch.

## 2. Model backends
- Every call goes through `litellm.completion` except Gemini, which uses its own `google-genai` client. Built-in `Model` constants cover OpenAI, Azure OpenAI, Anthropic, Gemini (AI Studio and Vertex), Together (Llama and DeepSeek), and `ollama/nomic-embed-text` (embeddings only). Any other model works through `pz.Model(id, api_base=...)`, which PZ treats as a "vLLM" model with $0 cost.
- **Local Ollama works:** `pz.Model("hosted_vllm/qwen2.5:14b", api_base="http://localhost:11434/v1")`. No model was pulled; qwen2.5:7b/14b, llama3.1:8b and qwen3:8b were already present.
- Limits: **only one api_base model per run** (raises ValueError). Building a plan that includes a Gemini model needs a key even if the model is never called. **PZ bug:** input tokens show as 0 for api_base models; there's a three-line monkeypatch in `pipeline.py`.
- **Failed LLM calls are swallowed.** An auth error becomes `passed_operator=False` / `None` fields, so a plan can "succeed" with 0 rows. The quality harness has to count errors.
- **Cost for ~2,000 docs (paid API).** Measured per document on our prompts: ~0.7k in / 0.1k out for the filter, and ~2.4k in / 1.9k out for the event flat-map. The output is long because the model writes reasoning plus a verbatim span per event. That's ~**6.2M in / 3.9M out tokens** per full plan, assuming every document passes the filter. AIC provenance averages 571 chars (n = 100 sample; 35k AIC works have provenance), so our 5 docs (767 chars) are representative. Priced with **PZ's own table** ($/M in, out):

  | model | $/M in, out | one plan × 2k docs |
  |---|---|---|
  | gpt-5-nano | 0.05, 0.40 | ≈ $1.9 + reasoning tokens |
  | gpt-4o-mini | 0.15, 0.60 | ≈ $3.3 |
  | Llama-3.3-70B (Together) | 0.88, 0.88 | ≈ $8.9 |
  | claude-haiku-4.5 | 1.00, 1.25 | ≈ $11 |

  PZ's Haiku output price looks stale: Anthropic lists $5/M, which would make it ≈ $26. Mixture-of-agents and critic plans cost about 3–4× a single-call plan. **Comparing ~5 plans over 2k docs is roughly $20–60 on mini/nano-tier models**, or about a tenth of that on a 200-doc labelled subset.

## 3. Pipeline (ran locally on 5 AIC texts: Haberstock ×2, Gurlitt ×2, Seligmann ×1)
The pipeline is `MemoryDataset → sem_filter("ownership change 1933–1945") → sem_flat_map(OwnershipEvent{owner, role, date, place, source_span}) → map(match_dealer)`. The last step is a plain Python surname/difflib match against a dealer list, with no LLM. A nested `list[BaseModel]` column **does not work**: PZ only puts field names and descriptions in the prompt and doesn't validate nested output (the model returned `{from, to, date}`). Use `sem_flat_map` instead, with one row per event.

| local model | filter (truth: 4 pass, 1 fail) | events | verbatim spans | wall (5 docs) |
|---|---|---|---|---|
| qwen2.5:7b | **0/4 kept**. Wrongly reasoned "1935 / 1939 are not between 1933 and 1945" | n/a | n/a | 64 s |
| qwen2.5:14b | **4/4 kept, 1/1 dropped** | 29 | 17/29 | **1,113 s** (flat-map 1,008 s) |

The 14b sample output is good (e.g. `Hildebrand Gurlitt | dealer | 1941`, `Reichsministerium für Volksaufklärung… | state/confiscation | Aug. 28, 1937`). It also has typical errors: Haberstock is tagged "collector", the AIC is tagged "heir", and Bignou's 1933 event is missed. Local inference is fine for a 20–50-doc live demo but **too slow for 2,000 docs × several plans** (14b ≈ 3.7 min/doc on this Mac).

## 4. Optimizer and plan comparison
- **Policies:** `MaxQuality`, `MinCost`, `MinTime`, plus `…AtFixedCost/Time/Quality`. They're set via `QueryProcessorConfig(policy=…, available_models=[…], allow_mixtures/critic/rag_reduction/split_merge/bonded_query=…, optimizer_strategy="pareto"|"greedy"|"none")`.
- **Stats:** `out.execution_stats` gives `total_execution_cost/time`, token counts, `plan_strs`, and `plan_stats[id].operator_stats[op]` with `total_op_time`, `total_op_cost`, input/output tokens and per-record `RecordOpStats`. That's enough for the latency and cost columns.
- **Abacus:** `ds.optimize_and_run(config, train_dataset=…, validator=MyValidator())` samples operators (MAB "sentinel" strategy) to replace prior estimates with measured quality, cost and time. `Validator` is subclassable with `filter_score_fn`, `flat_map_score_fn` etc., so we can score against gold labels without an LLM judge. The default judge is o4-mini, which is paid. Not exercised in this spike.
- **Alternative plans:** the built-in policies give zero weight to the metrics they don't optimize, which **collapses PZ's Pareto frontier to one plan**. `plans.py` uses a custom policy weighting cost, time and quality, then calls `optimizer.strategy._get_candidate_pareto_physical_plans(...)`, a private method. That produced **20 candidate plans** with estimated (cost, time, quality) over the local model plus gpt-5-nano, gpt-4o-mini and Llama-3.3-70B, **without any LLM call**. Each plan can then run via `processor.execution_strategy.execute_plan(plan)` to get actual stats (`plans.py --run`).
- **The prior estimates are almost useless:**
  - With only the local model, all five filter variants (LLM, mixture-of-agents ×3, critic) and all five convert variants get the **same prior quality, 0.52**. The frontier therefore collapses to the fastest plan, even though 5×5 physical alternatives exist in `optimizer.groups`.
  - Estimated filter time is 0.02 s per record; actual was about 5–10 s.
  - The executed 7b plan was estimated at 3.2 s and 0.27 quality. Actual: 22–38 s, 0/4 kept.
  - To get meaningful quality numbers we need sampling (Abacus with our gold Validator) or our own runs. Enumerate the cross-product of `group.physical_expressions` ourselves.
- **What we still own:** gold labels, a quality metric (filter accuracy, event P/R, span exactness), the loop over chosen plans, and the comparison table and plots.

## 5. Risks (2-week solo)
1. The comparison relies on **private optimizer APIs**. Pin `palimpzest==1.5.3`; the fallback is looping over public configs.
2. **Silent failure** (errors become empty answers) and the **offline import** problem. Both are patchable but easy to miss in a live demo.
3. **Local models are slow or weak.** The demo needs one small paid key (OpenAI gpt-4o-mini or gpt-5-nano is cheapest in PZ's table; Gemini needs a key even for planning), or a pre-computed results cache.
4. Building the **gold set** (say 50–100 annotated provenance texts) is the real critical path, not PZ.
5. 1.5 GB of dependencies and several pins (numpy 2.0.2, litellm < 1.82.7) could clash with the rest of the Mosaic stack, so keep it in its own venv.
