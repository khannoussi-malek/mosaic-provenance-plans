"""Minimal Palimpzest pipeline over AIC provenance texts, run against a local Ollama model.

usage: .venv/bin/python pipeline.py [ollama_model]   (default qwen2.5:7b)
"""
import difflib
import json
import os
import sys
import time
from pathlib import Path

import palimpzest as pz
from palimpzest.prompts.prompt_manager import PromptManager
from pydantic import BaseModel, Field

HERE = Path(__file__).parent
OLLAMA = "http://localhost:11434/v1"  # Ollama's OpenAI-compatible endpoint
os.environ.setdefault("VLLM_API_KEY", "ollama")  # ponytail: dummy; Ollama ignores it
DEALERS = ["Karl Haberstock", "Hildebrand Gurlitt", "Jacques Seligmann", "Arnold Seligmann", "Paul Rosenberg",
           "Etienne Bignou", "Arthur Tooth", "Walter Andreas Hofer", "Alois Miedl", "Theo Hermsen"]

# PZ 1.5.3 bug: for api_base ("vLLM") models extract_usage_stats() never copies prompt_tokens -> input tokens = 0.
_orig_usage = PromptManager.extract_usage_stats
def _usage(self, usage, is_audio_op):
    stats = _orig_usage(self, usage, is_audio_op)
    if self.model.is_vllm_model():
        stats["input_text_tokens"] = usage.get("prompt_tokens") or 0
    return stats
PromptManager.extract_usage_stats = _usage


# One output row per event (sem_flat_map). PZ only puts field name + description in the prompt,
# so a nested list[BaseModel] field loses its inner schema -- flat rows are the idiomatic shape.
class OwnershipEvent(BaseModel):
    owner: str = Field(description="Name of the person, dealer, gallery, auction house or institution that held or sold the work in this event")
    role: str = Field(description="Role of the owner, one of: dealer, collector, auction, museum, heir, state/confiscation, unknown")
    date: str | None = Field(description="Year or date of the event as written in the text, e.g. '1939' or 'April 1, 1939'")
    place: str | None = Field(description="City or place associated with the owner in this event, if stated")
    source_span: str = Field(description="The exact verbatim substring of provenance_text that supports this event")


def match_dealer(owner: str | None) -> str | None:
    """Deterministic (non-LLM) match against the dealer list: substring on surname, else fuzzy."""
    if not owner:
        return None
    for d in DEALERS:
        if d.split()[-1].lower() in owner.lower():
            return d
    hit = difflib.get_close_matches(owner, DEALERS, n=1, cutoff=0.8)
    return hit[0] if hit else None


def build(records: list[dict]) -> pz.Dataset:
    ds = pz.MemoryDataset(id="aic-provenance", vals=records)
    ds = ds.sem_filter("The provenance text records a change of ownership or custody of the artwork "
                       "that happened between 1933 and 1945.", depends_on=["provenance_text"])
    ds = ds.sem_flat_map(OwnershipEvent, desc="Extract every ownership/custody event in the provenance text, in order.",
                         depends_on=["provenance_text"])
    return ds.map(lambda r: {"dealer_match": match_dealer(r["owner"])},
                          cols=[{"name": "dealer_match", "type": str, "desc": "matched dealer from list"}])


def load_records() -> list[dict]:
    return json.loads((HERE / "data/provenance5.json").read_text())


def local_model(name: str) -> pz.Model:
    # `hosted_vllm/` = litellm's generic OpenAI-compatible provider; api_base makes PZ treat it as a local, $0 model
    return pz.Model(f"hosted_vllm/{name}", api_base=OLLAMA)


def run(model: pz.Model, policy: pz.Policy | None = None, **flags):
    config = pz.QueryProcessorConfig(policy=policy or pz.MaxQuality(), available_models=[model], progress=False,
                                     max_workers=1, **flags)  # ponytail: 1 worker; Ollama serializes anyway
    t0 = time.time()
    out = build(load_records()).run(config)
    return out, time.time() - t0


def op_rows(out) -> list[dict]:
    return [{"op": op.op_name, "time_s": round(op.total_op_time, 1), "cost_usd": op.total_op_cost,
             "in_tok": int(op.input_text_tokens), "out_tok": int(op.output_text_tokens)}
            for ps in out.execution_stats.plan_stats.values() for op in ps.operator_stats.values()]


if __name__ == "__main__":
    assert match_dealer("Karl Haberstock, Berlin") == "Karl Haberstock" and match_dealer("Christie's") is None
    model = local_model(sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:7b")
    out, wall = run(model)
    df = out.to_df()
    (HERE / "out").mkdir(exist_ok=True)
    df.to_json(HERE / f"out/{model.get_model_name()}.json", orient="records", indent=1, force_ascii=False)
    print(df.drop(columns=["source_span", "provenance_text", "title", "query"], errors="ignore").to_string(max_colwidth=40))
    s = out.execution_stats
    print(f"\nkept docs {sorted(set(df.get('id', [])))} | {len(df)} events | wall {wall:.1f}s | cost ${s.total_execution_cost:.4f}"
          f" | in_tok {s.input_text_tokens:.0f} out_tok {s.output_text_tokens:.0f}")
    print(*out.executed_plans, sep="\n")
    for r in op_rows(out):
        print(r)
