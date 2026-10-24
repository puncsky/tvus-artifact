import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runner.schema import load_case, project, serialize_candidate
from runner.prompting import build_action_prompt, parse_action
from models.adapter import load_adapter

spec = sys.argv[1] if len(sys.argv) > 1 else "qwen14b"
t0=time.time(); ad = load_adapter(spec); print("loaded", ad.describe(), f"{time.time()-t0:.1f}s")
case = load_case("S01")
for cond in ("clean", "attack"):
    msgs = build_action_prompt(project(case, cond))
    g = ad.generate(msgs, seed=0, temperature=0.0, max_tokens=200)
    args, st = parse_action(g.text, case.fields)
    print(f"[{cond}] gen {g.cost.prompt_tokens}p/{g.cost.generated_tokens}g {g.cost.wall_seconds:.1f}s status={st} ->", json.dumps(args))
    conts = [serialize_candidate(case, c, {"memo": "see vendor note"}) for c in case.candidates]
    scores = ad.score(msgs, conts)
    for s in scores:
        print(f"   score {s.logprob:9.3f} ntok={s.n_tokens} {s.cost.wall_seconds:.2f}s  {s.continuation[:70]}")
print("peak mem GB", round(ad.peak_memory_gb(),2))
