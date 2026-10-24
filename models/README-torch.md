# Torch/transformers adapter — CPU-verified, Spark steps

`models/torch_adapter.py::TorchAdapter` mirrors `MLXAdapter` (same `generate` / `score` / `CostLedger`
/ `_memo` / `describe()` / `peak_memory_gb()`). `load_adapter(spec)` dispatches on
`"backend": "torch"` in `configs/models.json` (default stays MLX). Torch specs take overrides:
`name@batch_candidates=true,dtype=4bit,device=cuda`.

Semantics that matter for MLX parity:

- Scoring EOS = `tokenizer.eos_token_id` (`<|im_end|>` = 151645 for Qwen2.5 Instruct), the same id the
  MLX 14B adapter uses. Do **not** copy MLX's `sorted(eos_token_ids)[0]` rule: on an HF checkpoint whose
  `generation_config.json` lists `[151645, 151643]` it would pick `<|endoftext|>`. You can override it
  with `"eos_id"` in models.json. `--compare-with` reports `eos_id_match`.
- Sampling: every transformers knob is set explicitly to its neutral value (top_k=0, top_p=1,
  repetition_penalty=1, …). Otherwise transformers fills `None` from the checkpoint's
  generation_config (Qwen ships top_k=20/top_p=0.8/rep 1.1). The harmless warning
  "generation flags are not valid … ['min_p','top_k']" comes from those explicit neutral values.
- Log-softmax is accumulated in float64 (float32 on MPS). A float32 CPU log-softmax over the 152k
  vocabulary was off by 1.5e-4 nats, which failed the 1e-4 numpy check.
- `batch_candidates=True` right-pads the missing candidates into one uncached forward. Each candidate
  gets one ledger entry with `forward_passes=1` and the batch wall time split evenly.
- Determinism: `torch.use_deterministic_algorithms(True, warn_only=True)`,
  `CUBLAS_WORKSPACE_CONFIG=:4096:8` (set before CUDA init), TF32 off, `cudnn.benchmark=False`.
  `describe()` records all of these along with the torch/transformers versions and the attention
  implementation.

## CPU verification (done 2026-10-03, Apple M4 Pro, no CUDA)

```bash
cd w3
UV_CACHE_DIR=$PWD/cache/uv uv venv --python /opt/homebrew/opt/python@3.12/bin/python3.12 envs/torch
UV_CACHE_DIR=$PWD/cache/uv uv pip install --python envs/torch/bin/python torch transformers==5.18.0 numpy safetensors huggingface_hub accelerate
# model: Qwen/Qwen2.5-0.5B-Instruct @ 7ae557604adf67be50417f59c2c2f167def9a775 under cache/hf (HF_HOME)
TMPDIR=$PWD/tmp envs/torch/bin/python models/verify_adapter.py qwen05b-cpu
TMPDIR=$PWD/tmp envs/torch/bin/python models/verify_adapter.py qwen05b-cpu \
    --compare-with 'qwen05b-cpu@batch_candidates=true' --cases S01,P01,H02 --dump-scores
```

Versions: `configs/env-torch-cpu.json`. Reports: `reports/model-readiness/verify-qwen05b-cpu.json`,
`compare-qwen05b-cpu--*.json`.

## Spark (DGX Spark: GB10, aarch64, Blackwell, unified memory) — steps

All paths are relative to `w3/`. Everything stays under `w3/` (`HF_HOME=cache/hf`,
`UV_CACHE_DIR=cache/uv`, `TMPDIR=tmp`); `runner/paths.apply_env()` sets `HF_HUB_OFFLINE=1`, so
download the models first.

1. **Host facts → `configs/env-cuda.json`**
   ```bash
   uname -m; cat /etc/os-release | head -3; nvidia-smi; nvidia-smi --query-gpu=name,compute_cap,driver_version,memory.total --format=csv
   nvcc --version || true
   ```
2. **Torch CUDA wheel for aarch64.** Check the wheel first, then install it:
   ```bash
   export UV_CACHE_DIR=$PWD/cache/uv TMPDIR=$PWD/tmp
   uv venv --python 3.12 envs/torch-cuda
   # pick the newest CUDA index that has an aarch64 wheel matching the driver (try cu130, then cu129, then cu128)
   uv pip install --python envs/torch-cuda/bin/python torch --index-url https://download.pytorch.org/whl/cu130
   uv pip install --python envs/torch-cuda/bin/python transformers==5.18.0 numpy safetensors huggingface_hub accelerate
   envs/torch-cuda/bin/python -c "import torch;print(torch.__version__,torch.version.cuda,torch.cuda.is_available(),torch.cuda.get_device_name(0),torch.cuda.get_device_capability(0),torch.cuda.get_arch_list())"
   envs/torch-cuda/bin/python -c "import torch;x=torch.randn(4096,4096,device='cuda',dtype=torch.bfloat16);print((x@x).float().abs().mean())"
   ```
   The GPU's capability must appear in `get_arch_list()`, or be covered by PTX JIT, and the bf16
   matmul must run without a "no kernel image" error. If no aarch64 CUDA wheel works, fall back to
   NVIDIA's PyTorch container (`nvcr.io/nvidia/pytorch:<yy.mm>-py3`) with `w3/` bind-mounted. Record
   the route in `torch_index_url`/`notes`.
3. **bitsandbytes (4-bit pilots):**
   ```bash
   uv pip install --python envs/torch-cuda/bin/python bitsandbytes
   envs/torch-cuda/bin/python -c "import bitsandbytes as b, torch; print(b.__version__); import bitsandbytes.functional as F; q,s=F.quantize_4bit(torch.randn(64,64,device='cuda',dtype=torch.bfloat16)); print('4bit ok')"
   ```
   If this fails on aarch64/Blackwell, set `bitsandbytes_4bit_works=false`. Then measure 14B in
   bf16 only (it fits in unified memory) and note it in the env file.
4. **vLLM availability check.** This only records the result. The adapter does not use vLLM.
   ```bash
   uv venv --python 3.12 envs/vllm && uv pip install --python envs/vllm/bin/python vllm   # aarch64 wheel?
   envs/vllm/bin/python -c "import vllm, torch; print(vllm.__version__, torch.version.cuda)"
   # alternative: NVIDIA's vLLM container (nvcr.io/nvidia/vllm) if the pip wheel lacks aarch64/sm_12x
   ```
   **Fallback if vLLM is unavailable:** use `TorchAdapter` for everything. Scoring is one uncached
   forward per candidate, or `batch_candidates=true`, which verify_adapter checks for equivalence.
   vLLM would only speed up generation. If vLLM is ever used for scoring, it has to pass the same
   numpy, incremental and batched checks first.
5. **Models.** Download them with network on, at these pins (revisions resolved via the HF API on 2026-10-03):
   ```bash
   HF_HOME=$PWD/cache/hf envs/torch-cuda/bin/python -c "from huggingface_hub import snapshot_download as d; d('Qwen/Qwen2.5-14B-Instruct', revision='cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8'); d('Qwen/Qwen2.5-32B-Instruct', revision='5ede1c97bbab6ce5cda5812749b4c0bdf79b18dd')"
   ```
   Add these entries to `configs/models.json`:
   ```json
   "qwen14b-torch": {"backend": "torch", "hf_repo": "Qwen/Qwen2.5-14B-Instruct", "family": "qwen2.5", "dtype": "bf16", "device": "cuda", "attn_implementation": "sdpa", "revision": "cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8"},
   "qwen32b-torch": {"backend": "torch", "hf_repo": "Qwen/Qwen2.5-32B-Instruct", "family": "qwen2.5", "dtype": "bf16", "device": "cuda", "attn_implementation": "sdpa", "revision": "5ede1c97bbab6ce5cda5812749b4c0bdf79b18dd"}
   ```
6. **Verify.** All four checks must pass, and for torch the batched-equals-single check as well.
   ```bash
   P=envs/torch-cuda/bin/python
   TMPDIR=$PWD/tmp $P models/verify_adapter.py qwen14b-torch
   TMPDIR=$PWD/tmp $P models/verify_adapter.py 'qwen14b-torch@dtype=4bit'
   TMPDIR=$PWD/tmp $P models/verify_adapter.py qwen32b-torch
   ```
   Each report has `throughput.s_per_1k_token_score_pass`, `throughput.gen90_seconds` and
   `peak_memory_gb` (`torch.cuda.max_memory_allocated`). Copy them into `configs/env-cuda.json`.
   In bf16 on GPU, the 1e-4 numpy tolerance compares the adapter against the *same* logits, so it
   should still hold. The incremental check allows 0.5 nats. If batched-vs-single goes above 1e-3
   in bf16, report it and leave `batch_candidates` off.
7. **MLX ↔ Torch (same 14B) comparison.** MLX cannot run on Linux, so compare against the MLX
   scores dumped on the Mac (`reports/model-readiness/scores-qwen14b.json`, S01/P01/H02 clean+attack,
   MLX 4-bit):
   ```bash
   TMPDIR=$PWD/tmp $P models/verify_adapter.py qwen14b-torch --compare-with reports/model-readiness/scores-qwen14b.json --cases S01,P01,H02 --dump-scores
   TMPDIR=$PWD/tmp $P models/verify_adapter.py 'qwen14b-torch@dtype=4bit' --compare-with reports/model-readiness/scores-qwen14b.json --cases S01,P01,H02
   ```
   Acceptance: `argmax_agreement == 1.0` and `spearman_rel_logodds >= 0.9`, with an empty
   `tokenization_mismatch_contexts` and `eos_id_match: true`. The MLX side is 4-bit affine
   (group 64) and torch is bf16 or NF4, so absolute log-probs will differ by quantization. Expect
   only ranks and relative log-odds to agree. Explain any disagreement in `mlx_vs_torch.explanation_if_disagree`.
8. Freeze the env: `uv pip freeze --python $P` → `pip_freeze` in `configs/env-cuda.json`.

## H100 chain (m10/t004) — prepared 2026-10-05, not yet run

`scripts/run_h100.sh probe` runs a 3-template H1 probe per bf16 family (`qwen32b-bf16`, `gemma27b-bf16`, `mistral24b-bf16`; revisions pinned in
`configs/models.json`, `google/gemma-3-27b-it` is gated → `HF_TOKEN` with granted access) and writes `reports/h100-projection.{md,json}` via
`runner/h100_projection.py` (schedule: dev 216 + conf 72 + F 24 + H2 96 + generated test split 1323 executions per family; `approved` only under
`W3_GPU_CAP_USD`, default $450 at `W3_GPU_USD_PER_HOUR` = 2.5). `scripts/run_h100.sh run` refuses without an approved projection, then runs the
chain sequentially and resumably (thresholds calibrated on each family's dev run *before* its confirmation/test analysis). The torch adapter
now has the same adjacent-turn merge fallback as MLX for strict-alternation templates (Gemma, Mistral). Rehearse on the Spark first with
`W3_PY=envs/torch-cuda/bin/python W3_FAMILIES=qwen32b-bf16 scripts/run_h100.sh probe` (the Spark's 128 GB unified memory holds all three in bf16,
but its throughput is ~1/6 of an H100, so use it for the probe and the CUDA verification only).
