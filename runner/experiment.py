"""Development-matrix driver: cases x conditions x run specs x interventions.

For every scheduled execution it records the raw signals every defense needs:

* the B0 proposal (ordinary agent, contract prompt) and its parse status;
* full-action teacher-forced scores of every frozen candidate under the
  original context and under each contract-conditioned intervention;
* fresh regenerations under the joint / neutral / closure interventions;
* the trusted-reconstruction (B2) proposal, incl. typed scoped releases;
* validity flags for every intervention and the cost of every model call.

Gate decisions are *not* taken here: ``analyze.py`` applies frozen thresholds
post hoc, so calibration and evaluation are separable and auditable.

Usage:
    envs/mlx/bin/python -B runner/experiment.py --model qwen14b --run-id dev-qwen [--cases S01 R01] [--seeds 0 11 23]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runner.paths import resolve_out, CATEGORY  # noqa: E402
from runner.schema import load_all, validate_case, runtime_hash, CONDITIONS, project  # noqa: E402
from runner import simulator, recording  # noqa: E402
from runner.simulator import PublicCase, run_agent, score_candidates, AgentRun  # noqa: E402
from runner.prompting import build_release_prompt  # noqa: E402
from models.adapter import load_adapter, Cost  # noqa: E402

RUN_SPECS = [(0, 0.0), (11, 0.7), (23, 0.7)]  # precommitted: greedy + two sampled seeds


def _ledger_slice(adapter, start: int) -> dict:
    entries = adapter.ledger.entries[start:]
    tot = Cost()
    for e in entries:
        tot = tot.add(Cost(e["prompt_tokens"], e["generated_tokens"], e["scored_tokens"], e["forward_passes"], e["wall_seconds"]))
    by_label: dict[str, dict] = {}
    usd = 0.0
    for e in entries:
        d = by_label.setdefault(e["label"], {"prompt_tokens": 0, "generated_tokens": 0, "scored_tokens": 0, "forward_passes": 0, "wall_seconds": 0.0})
        for k in d:
            d[k] += e[k]
        usd += e.get("usd", 0.0)
    return {"total": asdict(tot), "by_label": by_label, "usd": usd}


def _valid_intervention(case: PublicCase, drop: set[str], replace: dict[str, str]) -> tuple[bool, str]:
    """An intervention is invalid when it removes required legitimate information
    or touches an authorized source (which the contract says may influence G)."""
    auth = set(case.authorized_sources())
    released_sources = {r["source"] for r in (case.runtime["contract"].get("releases") or [])}
    for s in case.sources():
        if s["id"] in drop or s["id"] in replace:  # "user" is never a source; it is handled by project()
            if s["id"] in released_sources:
                continue  # the typed released fact is injected in place of the raw text: legitimate information preserved
            if s.get("required_for_task"):
                return False, f"removes required source {s['id']}"
            if s["id"] in auth:
                return False, f"touches authorized source {s['id']}"
    return True, "ok"


def _run_and_score(adapter, case, condition, seed, temp, free, *, intervention, drop, replace, closure,
                   reuse_notes, label, regenerate: bool, released_all: list[dict] | None = None,
                   tuple_only: bool = False, reuse_run: AgentRun | None = None) -> dict:
    valid, why = _valid_intervention(case, drop, replace)
    # a release source that is deleted/replaced keeps its typed released fact (scoped release preserved)
    released = [r for r in (released_all or []) if r["source"] in drop or r["source"] in replace]
    rec: dict = {"intervention": intervention, "drop": sorted(drop), "replace": replace, "closure": closure,
                 "valid": valid, "validity_reason": why, "released": released}
    if not valid and not (intervention == "all_external" or intervention.startswith("loo:")):
        # contract-conditioned interventions never touch authorized sources by construction
        rec["skipped"] = True
        return rec
    # context for scoring: same notes as the audited run unless closure regenerates them;
    # closure keeps the original notes up to h0 when history.h0_after_step is set
    h0_notes = reuse_run.notes if (closure and reuse_run is not None) else None
    if simulator.HARNESS in ("h2", "h3"):
        # H2/H3: closure = replay the loop; in-place = edit the original transcript; both yield a scorable transcript (H2 only)
        if closure or regenerate:
            probe = run_agent(adapter, case, condition, seed=seed, temperature=temp, intervention=intervention,
                              drop=drop, replace=replace, closure=closure, released=released, reuse_run=reuse_run,
                              h0_notes=h0_notes, label=f"{label}/regen")
        else:
            from runner.harness_react import _inplace_transcript
            ctx = project(case._case, condition, drop_sources=drop, replace=replace, released=released)
            probe = AgentRun(condition, seed, temp, intervention, sorted(drop), dict(replace), False, released, notes=list(reuse_run.notes),
                             candidates=reuse_run.candidates, candidate_source=reuse_run.candidate_source)
            probe.transcript = _inplace_transcript(reuse_run, ctx, drop, replace)
    elif closure:
        probe = run_agent(adapter, case, condition, seed=seed, temperature=temp, intervention=intervention,
                          drop=drop, replace=replace, closure=True, released=released, h0_notes=h0_notes,
                          label=f"{label}/regen") if regenerate else None
        if probe is None:
            # closure without regeneration still needs the regenerated notes for scoring
            from runner.simulator import run_history_steps
            ctx = project(case._case, condition, drop_sources=drop, replace=replace, released=released)
            notes = run_history_steps(adapter, case, ctx, seed=seed, temperature=temp, label=f"{label}/notes",
                                      h0_notes=h0_notes) if ctx.get("history") else []
            probe = AgentRun(condition, seed, temp, intervention, sorted(drop), dict(replace), True, released, notes=notes)
    else:
        probe = AgentRun(condition, seed, temp, intervention, sorted(drop), dict(replace), False, released, notes=list(reuse_notes or []))
        if regenerate:
            g = run_agent(adapter, case, condition, seed=seed, temperature=temp, intervention=intervention,
                          drop=drop, replace=replace, closure=False, reuse_notes=reuse_notes, released=released, label=f"{label}/regen")
            probe.text, probe.args, probe.status, probe.cost = g.text, g.args, g.status, g.cost
    if simulator.HARNESS == "h3":
        rec["scores"] = None   # hosted API: no log-probabilities; score-based gates are not applicable
    else:
        rec["scores"] = score_candidates(adapter, case, condition, probe, free, label=f"{label}/score", tuple_only=tuple_only)
    if regenerate:
        rec["regen"] = {"text": probe.text, "args": probe.args, "status": probe.status,
                        "protected": probe.protected(case) if probe.args else None, "notes": probe.notes}
        if probe.candidates is not None:
            rec["regen"]["candidates"], rec["regen"]["candidate_source"] = probe.candidates, probe.candidate_source
    elif probe.notes:
        rec["notes"] = probe.notes
    return rec


def extract_releases(adapter, case: PublicCase, condition: str, seed: int, label: str) -> list[dict]:
    """Typed extraction of every contract release (one model call per release, greedy)."""
    out = []
    ctx = project(case._case, condition)
    for rel in case.runtime["contract"].get("releases", []) or []:
        src_ctx = next((s for s in ctx["sources"] if s["id"] == rel["source"]), None)
        if src_ctx is None:
            continue
        g = adapter.generate(build_release_prompt(ctx, rel, src_ctx), seed=seed, temperature=0.0, max_tokens=40,
                             label=f"{label}/release:{rel['field']}")
        val = g.text.strip().strip('"').splitlines()[0].strip() if g.text.strip() else "NONE"
        out.append({"field": rel["field"], "value": val, "source": rel["source"], "verified_by": rel.get("verified_by"), "raw": g.text})
    return out


def _reconstruct(adapter, case: PublicCase, condition: str, seed: int, temp: float, label: str,
                 released: list[dict] | None = None, base: AgentRun | None = None) -> dict:
    """B2: trusted reconstruction with field isolation and typed scoped releases.

    Under H2 the loop is replayed from scratch without the unauthorized sources.

    Unauthorized sources are dropped from h0; each contract release is turned
    into a typed extracted fact; the protected group is regenerated; free fields
    are later merged from the full-context proposal (field isolation).

    ``base`` (the B0 run) supplies what reconstruction receives as given rather
    than regenerates: the notes up to h0 when ``history.h0_after_step`` is set
    (A4), and the choice set when ``candidate_generation`` is "untrusted" (A1).
    """
    if simulator.HARNESS in ("h2", "h3"):
        from runner import harness_react
        mod = harness_react if simulator.HARNESS == "h2" else simulator.h3_module(adapter)
        if simulator.HARNESS == "h2":
            return mod.reconstruct(adapter, case, condition, seed, temp, label, released=released, base=base)
        return mod.reconstruct(adapter, case, condition, seed, temp, label, released=released)
    released = list(released or [])
    rec: dict = {"releases": released}
    drop = set(case.unauthorized_sources())   # a release source outside authorized_sources is dropped; its typed fact stays
    ctx = project(case._case, condition, drop_sources=drop, released=released)
    from runner.simulator import run_history_steps, _memory_note, action_candidates
    from runner.prompting import build_action_prompt, parse_action
    notes = run_history_steps(adapter, case, ctx, seed=seed, temperature=temp, label=f"{label}/notes",
                              h0_notes=base.notes if base else None) if ctx.get("history") else []
    cands, cand_src = action_candidates(case, notes, base.candidates if base else None)
    if cands is not None:
        ctx = project(case._case, condition, drop_sources=drop, released=released, candidates=cands)
        rec.update({"candidates": cands, "candidate_source": cand_src})
    hist = ctx.get("history")
    msgs = build_action_prompt(ctx, memory_note=_memory_note(case, notes),
                               hide_sources=bool(hist and hist.get("hide_sources_at_action", True)))
    g = adapter.generate(msgs, seed=seed, temperature=temp, max_tokens=260, label=f"{label}/action")
    args, status = parse_action(g.text, case.fields)
    rec.update({"drop": sorted(drop), "text": g.text, "args": args, "status": status,
                "protected": case.protected_tuple(args) if args else None, "notes": notes})
    return rec


def build_adapter(model_spec: str, harness: str, cap_usd: float, spend_file: str):
    """Local MLX/Torch adapter, or a hosted agent (claude:/openai:/gemini:) which requires --harness h3."""
    if model_spec.startswith("claude"):
        from runner.harness_claude import ClaudeAgent, DEFAULT_MODEL
        model_id = model_spec.split(":", 1)[1] if ":" in model_spec else DEFAULT_MODEL
        if harness != "h3":
            raise SystemExit("hosted Claude agents run under --harness h3")
        return ClaudeAgent(model=model_id, cap_usd=cap_usd, spend_file=spend_file)
    if model_spec.startswith(("openai:", "gemini:")):
        provider, model_id = model_spec.split(":", 1)
        if provider == "openai":
            from runner.harness_openai import OpenAIAgent as Agent
        else:
            from runner.harness_gemini import GeminiAgent as Agent
        if harness != "h3":
            raise SystemExit(f"hosted {provider} agents run under --harness h3")
        return Agent(model=model_id, cap_usd=cap_usd, spend_file=spend_file)
    return load_adapter(model_spec)


def run_execution(adapter, case_pub: PublicCase, condition: str, seed: int, temp: float) -> dict:
    t0 = time.perf_counter()
    if hasattr(adapter, "_memo"):
        adapter._memo.clear()   # memo hits only occur within one execution; bound memory over long runs
    start = len(adapter.ledger.entries)
    lbl = f"{case_pub.id}/{condition}/{seed}"
    rt = case_pub.runtime
    if simulator.HARNESS == "h3" and (rt.get("candidate_generation", "frozen") != "frozen" or (rt.get("history") or {}).get("h0_after_step")
                                      or any("include_notes" in st for st in (rt.get("history") or {}).get("steps", []))):
        raise NotImplementedError(f"{case_pub.id}: candidate_generation / h0_after_step / include_notes are implemented for h1 and h2 only")
    rec: dict = {"case": case_pub.id, "family": case_pub.family, "track": case_pub.track, "condition": condition,
                 "seed": seed, "temperature": temp, "model": adapter.name, "harness": simulator.HARNESS}

    # 1. ordinary agent (B0)
    base = run_agent(adapter, case_pub, condition, seed=seed, temperature=temp, label=f"{lbl}/b0")
    free = {k: v for k, v in (base.args or {}).items() if k not in case_pub.protected}
    rec["b0"] = {"text": base.text, "args": base.args, "status": base.status, "protected": base.protected(case_pub),
                 "candidate_index": case_pub.candidate_index(base.args) if base.args else None, "notes": base.notes,
                 "transcript": base.transcript if simulator.HARNESS in ("h2", "h3") else None, "read_ids": base.read_ids}
    if base.candidates is not None:
        rec["b0"]["candidates"], rec["b0"]["candidate_source"] = base.candidates, base.candidate_source

    # 2. scores under the original context (not available on hosted APIs)
    api_mode = simulator.HARNESS == "h3"
    rec["base_scores"] = None if api_mode else score_candidates(adapter, case_pub, condition, base, free, label=f"{lbl}/base/score", tuple_only=True)
    released_all = extract_releases(adapter, case_pub, condition, seed, f"{lbl}/release")
    rec["released"] = released_all

    # 3. interventions (contract-conditioned)
    unauth = case_pub.unauthorized_sources()
    all_ext = [s["id"] for s in case_pub.sources()]
    hist = case_pub.runtime.get("history")
    inter: list[dict] = []
    # user-request LOO (CausalArmor reference attribution: remove the user request, score only)
    if not api_mode:
      inter.append(_run_and_score(adapter, case_pub, condition, seed, temp, free, intervention="loo:user",
                                drop={"user"}, replace={}, closure=False, reuse_notes=base.notes,
                                label=f"{lbl}/loo:user", regenerate=False, released_all=released_all, reuse_run=base))
    # single-source LOO (in place) over EVERY external item: contract-agnostic attribution defenses
    # (CausalArmor-style) treat all external content as untrusted spans; contract-conditioned
    # controls only use the unauthorized subset (valid flag distinguishes them)
    for sid in ([] if api_mode else all_ext):
        inter.append(_run_and_score(adapter, case_pub, condition, seed, temp, free, intervention=f"loo:{sid}",
                                    drop={sid}, replace={}, closure=False, reuse_notes=base.notes,
                                    label=f"{lbl}/loo:{sid}", regenerate=False, released_all=released_all, reuse_run=base))
    # joint deletion in place (naive last-turn deletion), with regeneration
    if unauth:
        inter.append(_run_and_score(adapter, case_pub, condition, seed, temp, free, intervention="joint",
                                    drop=set(unauth), replace={}, closure=False, reuse_notes=base.notes,
                                    label=f"{lbl}/joint", regenerate=True, released_all=released_all, tuple_only=not hist, reuse_run=base))
        # structure-preserving replacement (authored neutral rewrite as oracle replacement)
        inter.append(_run_and_score(adapter, case_pub, condition, seed, temp, free, intervention="neutral",
                                    drop=set(), replace={s: "neutral" for s in unauth}, closure=False,
                                    reuse_notes=base.notes, label=f"{lbl}/neutral", regenerate=True, released_all=released_all, tuple_only=not hist, reuse_run=base))
    if hist:
        # clean-checkpoint closure: regenerate derived state from h0 under the intervention
        for sid in ([] if api_mode else unauth):
            inter.append(_run_and_score(adapter, case_pub, condition, seed, temp, free, intervention=f"closure:loo:{sid}",
                                        drop={sid}, replace={}, closure=True, reuse_notes=None,
                                        label=f"{lbl}/closure:loo:{sid}", regenerate=False, released_all=released_all, reuse_run=base))
        if unauth:
            inter.append(_run_and_score(adapter, case_pub, condition, seed, temp, free, intervention="closure:joint",
                                        drop=set(unauth), replace={}, closure=True, reuse_notes=None,
                                        label=f"{lbl}/closure:joint", regenerate=True, released_all=released_all, tuple_only=True, reuse_run=base))
            inter.append(_run_and_score(adapter, case_pub, condition, seed, temp, free, intervention="closure:neutral",
                                        drop=set(), replace={s: "neutral" for s in unauth}, closure=True, reuse_notes=None,
                                        label=f"{lbl}/closure:neutral", regenerate=True, released_all=released_all, tuple_only=True, reuse_run=base))
    # non-contract-conditioned control: delete ALL external items (may be invalid). When every external
    # item is unauthorized this is byte-identical to the joint intervention and is recorded as such.
    if set(all_ext) == set(unauth):
        inter.append({"intervention": "all_external", "identical_to": "closure:joint" if hist else "joint", "drop": sorted(all_ext),
                      "replace": {}, "closure": bool(hist), "valid": True, "validity_reason": "ok", "released": []})
    else:
        inter.append(_run_and_score(adapter, case_pub, condition, seed, temp, free, intervention="all_external",
                                    drop=set(all_ext), replace={}, closure=bool(hist), reuse_notes=base.notes,
                                    label=f"{lbl}/all_external", regenerate=True, released_all=released_all, reuse_run=base))
    rec["interventions"] = inter

    # 4. B2 trusted reconstruction (field isolation + typed releases)
    rec["reconstruction"] = _reconstruct(adapter, case_pub, condition, seed, temp, f"{lbl}/b2", released=released_all, base=base)

    rec["cost"] = _ledger_slice(adapter, start)
    rec["wall_seconds"] = time.perf_counter() - t0
    rec["peak_memory_gb"] = adapter.peak_memory_gb()
    return rec


COLLECTION_CODE = ("runner/schema.py", "runner/prompting.py", "runner/simulator.py", "runner/experiment.py", "runner/recording.py",
                   "runner/harness_react.py", "runner/paths.py", "models/adapter.py", "models/torch_adapter.py", "configs/models.json")


def _check_plan(plan: dict, a, case_ids: list[str], specs: list) -> list[str]:
    """A frozen run plan pins the schedule of its run ids; refuse any deviation."""
    role = next((r for r in plan["runs"] if r["run_id"] == a.run_id), None)
    if role is None:
        return [f"run id {a.run_id} is not in the plan"]
    want = {"model": role["model_spec"], "harness": role["harness"], "conditions": role["conditions"],
            "seeds": role["seeds"], "cases": role["cases"]}
    have = {"model": a.model, "harness": a.harness, "conditions": a.conditions, "seeds": [s for s, _ in specs], "cases": case_ids}
    return [f"{k}: plan {want[k]} != invocation {have[k]}" for k in want if want[k] != have[k]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="local key from configs/models.json, claude[:id], openai:<id> or gemini:<id> (hosted => --harness h3)")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--cases", nargs="*")
    ap.add_argument("--conditions", nargs="*", default=list(CONDITIONS))
    ap.add_argument("--seeds", nargs="*", type=int)
    ap.add_argument("--harness", default="h1", choices=["h1", "h2", "h3"])
    ap.add_argument("--cap-usd", type=float, default=50.0, help="spend cap for hosted API runs (per run id)")
    ap.add_argument("--plan", help="frozen run plan (JSON); the invocation must match its entry for --run-id")
    ap.add_argument("--checkpoint-every", type=int, default=0, help="checksum + verified copy of the run dir every N committed executions")
    ap.add_argument("--checkpoint-dest", default="evidence/run-checkpoints")
    ap.add_argument("--abort-after-calls", type=int, help=argparse.SUPPRESS)   # fault injection for the resume check
    a = ap.parse_args()
    simulator.set_harness(a.harness)

    cases = load_all(a.cases)
    bad = {c.id: validate_case(c) for c in cases}
    bad = {k: v for k, v in bad.items() if v}
    if bad:
        print("invalid fixtures:", json.dumps(bad, indent=1))
        return 2
    specs = [(s, t) for s, t in RUN_SPECS if not a.seeds or s in a.seeds]
    plan_sha = None
    if a.plan:
        plan_path = resolve_out(a.plan)
        plan_sha = recording.sha256_file(plan_path)
        errs = _check_plan(json.loads(plan_path.read_text()), a, [c.id for c in cases], specs)
        if errs:
            print("invocation does not match the frozen plan:\n  " + "\n  ".join(errs))
            return 2

    out_dir = resolve_out(f"runs/{a.run_id}", mkdir=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    adapter = build_adapter(a.model, a.harness, a.cap_usd, str(out_dir / "spend.json"))
    code_files = COLLECTION_CODE + ((("runner/harness_claude.py",) + (("runner/harness_hosted.py", f"runner/harness_{adapter.family}.py")
                                     if adapter.family in ("openai", "gemini") else ())) if a.harness == "h3" else ())
    manifest = {
        "run_id": a.run_id, "model_spec": a.model, "model": adapter.describe(), "harness": a.harness, "run_specs": specs,
        "conditions": a.conditions,
        "cases": {c.id: runtime_hash(c.runtime) for c in cases},
        "fixture_files": {c.id: {f: recording.sha256_file(c.path / f) for f in ("runtime.json", "evaluator.json")} for c in cases},
        "code": {p: recording.sha256_file(CATEGORY / p) for p in code_files},
        "plan": a.plan, "plan_sha256": plan_sha,
        "started": recording.now(),
    }
    session, mismatch = recording.check_resume(out_dir, manifest)
    if mismatch:
        print(f"refusing to resume runs/{a.run_id}: configuration differs from its immutable manifest:\n  " + "\n  ".join(mismatch))
        return 3
    source = recording.source_state(list(code_files), out_dir, session)
    if session == 0:
        recording.create_manifest(out_dir, {**manifest, "host": recording.host_facts(), "source": source})
    torn = [r for r in (recording.repair_torn_tail(out_dir / f, session) for f in
                        ("executions.jsonl", "attempts.jsonl", "trace.jsonl", "inputs.jsonl", "ledger.jsonl")) if r]
    out = out_dir / "executions.jsonl"
    prior = recording.read_jsonl(out)
    done = {(r["case"], r["condition"], r["seed"]) for r in prior}
    att_events = recording.read_jsonl(out_dir / "attempts.jsonl")
    committed = {e["attempt"] for e in att_events if e["event"] == "commit"}
    recovered = [r["attempt"] for r in prior if r.get("attempt") and r["attempt"] not in committed]   # killed between record and commit event
    incomplete = [e for e in att_events if e["event"] == "start" and e["attempt"] not in committed and e["attempt"] not in recovered]
    if recovered:
        log = recording.AppendLog(out_dir / "attempts.jsonl")
        for att_id in recovered:
            log.write({"event": "commit", "attempt": att_id, "recovered_on_resume": session, "at": recording.now()})
        log.close()
    if session > 0:
        recording.AppendLog(out_dir / "resumes.jsonl").write({
            "session": session, "at": recording.now(), "host": recording.host_facts(), "source": source, "model": manifest["model"],
            "committed_before": len(done), "incomplete_attempts": incomplete, "torn_tails": torn})

    rad = recording.RecordingAdapter(adapter, out_dir, session, abort_after_calls=a.abort_after_calls)
    attempts, execs = recording.AppendLog(out_dir / "attempts.jsonl"), recording.AppendLog(out)
    ck_log = recording.AppendLog(resolve_out(f"{a.checkpoint_dest}/checkpoints.jsonl", mkdir=True)) if a.checkpoint_every else None
    total = len(cases) * len(a.conditions) * len(specs)
    n = new = 0
    for case in cases:
        pub = PublicCase(case)
        for cond in a.conditions:
            for seed, temp in specs:
                n += 1
                if (case.id, cond, seed) in done:
                    continue
                att = f"s{session}-{case.id}-{cond}-{seed}"
                rad.attempt = att
                started = recording.now()
                attempts.write({"event": "start", "attempt": att, "case": case.id, "condition": cond, "seed": seed, "at": started})
                rec = run_execution(rad, pub, cond, seed, temp)
                rec.update({"attempt": att, "started": started, "finished": recording.now()})
                line = json.dumps(rec, ensure_ascii=False)
                execs.write(rec)
                done.add((case.id, cond, seed))
                attempts.write({"event": "commit", "attempt": att, "record_sha256": recording.sha256_bytes(line.encode("utf-8")),
                                "at": recording.now()})
                new += 1
                b0 = rec["b0"]
                print(f"[{n}/{total}] {case.id} {cond} seed={seed} status={b0['status']} cand={b0['candidate_index']} "
                      f"{rec['wall_seconds']:.0f}s passes={rec['cost']['total']['forward_passes']}", flush=True)
                if ck_log and new % a.checkpoint_every == 0:
                    ck_log.write(recording.checkpoint(out_dir, resolve_out(f"{a.checkpoint_dest}/{a.run_id}")))
    rad.close()
    # cumulative ledger snapshot (all sessions) for legacy consumers; ledger.jsonl stays the durable record
    (out_dir / "ledger.json").write_text(json.dumps(recording.read_jsonl(out_dir / "ledger.jsonl")))
    if ck_log:
        ck_log.write(recording.checkpoint(out_dir, resolve_out(f"{a.checkpoint_dest}/{a.run_id}")))
    print("done", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
