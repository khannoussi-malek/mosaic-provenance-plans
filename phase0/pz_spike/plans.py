"""Enumerate Palimpzest's alternative physical plans + estimated (cost, time, quality), WITHOUT calling any LLM.

PZ's public API only returns the single plan its policy picks; the candidate (Pareto) set lives in
optimizer internals. We build the Optimizer directly (this also skips the API-key check, so cloud models can be
*costed* from PZ's price table without being *called*).

usage: .venv/bin/python plans.py            # list candidates
       .venv/bin/python plans.py --run      # also execute the fastest and the highest-quality local-only plan
"""
import sys

import palimpzest as pz
from palimpzest.query.optimizer.cost_model import SampleBasedCostModel
from palimpzest.query.optimizer.optimizer import Optimizer
from palimpzest.query.processor.query_processor_factory import QueryProcessorFactory

import pipeline as p

LOCAL = p.local_model("qwen2.5:7b")
CLOUD = [pz.Model.GPT_4o_MINI, pz.Model.GPT_5_NANO, pz.Model.LLAMA3_3_70B]  # Gemini excluded: its client needs a key even to build a plan


class Frontier(pz.MaxQuality):
    """Non-zero weight on all 3 metrics, so PZ keeps the full (cost, time, quality) Pareto frontier.
    Built-in policies zero out the metrics they don't optimize, which collapses the frontier to ~1 plan."""
    def get_dict(self):
        return {"cost": 1.0, "time": 1.0, "quality": 1.0}


def candidate_plans(models, policy=Frontier(), **flags):
    ds = p.build(p.load_records())
    ds._generate_unique_logical_op_ids()
    opt = Optimizer(policy=policy, cost_model=SampleBasedCostModel(), available_models=models,
                    allow_rag_reduction=True, allow_mixtures=True, allow_critic=True, **flags)
    gid = opt.convert_query_plan_to_group_tree(ds.copy())
    opt.search_optimization_space(gid)
    # ponytail: private method; the public optimize() collapses this list to the single policy-best plan
    plans = opt.strategy._get_candidate_pareto_physical_plans(opt.groups, gid, policy)
    return ds, sorted(plans, key=lambda pl: pl.plan_cost.cost)


def _short(m) -> str:
    return getattr(m, "value", str(m)).split("/")[-1]


def describe(plan) -> str:
    parts = []
    for op in plan:
        if hasattr(op, "proposer_models"):
            props = ",".join(f"{_short(m)}@t{t}" for m, t in zip(op.proposer_models, op.temperatures))
            parts.append(f"{op.op_name()}[{props} -> {_short(op.aggregator_model)}]")
        elif hasattr(op, "critic_model"):
            parts.append(f"{op.op_name()}[{_short(getattr(op, "model", None))}; critic={_short(op.critic_model)}; refine={_short(op.refine_model)}]")
        elif getattr(op, "model", None) is not None:
            parts.append(f"{op.op_name()}[{_short(op.model)}]")
    return " -> ".join(parts)


if __name__ == "__main__":
    ds, plans = candidate_plans([LOCAL, *CLOUD])
    print(f"{len(plans)} candidate plans (estimates are PZ priors: price table + MMLU-Pro, not measured)\n")
    print(f"{'#':>2} {'est_cost$':>10} {'est_time_s':>10} {'est_quality':>11}  plan")
    for i, pl in enumerate(plans):
        c = pl.plan_cost
        print(f"{i:>2} {c.cost:>10.5f} {c.time:>10.1f} {c.quality:>11.3f}  {describe(pl)}")

    if "--run" in sys.argv:
        # mixed-pool frontier keeps ~1 local-only plan (others are dominated), so re-plan with the local model only
        ds, local_only = candidate_plans([LOCAL])
        print(f"\nlocal-only frontier: {len(local_only)} plans")
        config = pz.QueryProcessorConfig(available_models=[LOCAL], progress=False, max_workers=1)
        proc = QueryProcessorFactory.create_processor(ds, config)
        picks = [min(local_only, key=lambda pl: pl.plan_cost.time), max(local_only, key=lambda pl: pl.plan_cost.quality)]
        for pl in picks:
            records, stats = proc.execution_strategy.execute_plan(plan=pl)
            kept = sorted({r.to_dict().get("id") for r in records})
            print(f"est: time={pl.plan_cost.time:.1f}s quality={pl.plan_cost.quality:.3f} | actual: time={stats.total_plan_time:.1f}s cost=${stats.total_plan_cost:.4f} "
                  f"rows={len(records)} kept_docs={kept}  | {describe(pl)}")
