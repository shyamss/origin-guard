# Factorial follow-up freeze

Frozen on 2026-11-07 before any `neutral_provenance` or `policy_only` model
outputs were generated.

## External inputs

- SLEIGHT-Bench repository commit:
  `218c58315cc01ff0dc5a100e906c27d82d259521`
- `prompts/control_arena.md` SHA-256:
  `409dda797289ccfb33bff49ca1f6a63a5a995f26b6086c6f2b114e00c24f1a39`
- `prompts/state_tracking.md` SHA-256:
  `830527aa2b3fb871de4352da4a8bc5e7e23ad7ded7b8b5bc377269947df369e9`
- Combined SHA-256 manifest digest for every selected attack and paired-benign
  JSONL file, using paths relative to the upstream `attacks/` directory:
  `9f4159fd80f5d7d63dfc289ba45983a0b272c180f4e01740cac58d2397a6f813`

The prompt worktree matched the pinned Git commit at freeze time. The decrypted
benchmark files remain external and must not be copied into this repository.

## Local protocol

- Conditions: `neutral_provenance`, `policy_only`
- Model: `claude-opus-4-6`
- Maximum output tokens: 1,200 per call
- Calls: 44
- Shuffle seed: `20261107`
- Execution-order SHA-256:
  `f692836ab487ca7224c61472485488d9ccba9c8e4617d2a778663b8341ed0406`
- Standard global pricing assumption: $5/MTok input and $25/MTok output
- Worst-case estimate: $3.09999
- Author-approval cap, if approved: $3.25
- Factorial estimands: the frozen implementation in
  `src/origin_guard/analysis.py`

The combined digest of the sorted SHA-256 manifest for `pyproject.toml`,
`uv.lock`, both configuration JSON files, all package source files, and all test
files was:

`50a484564e865919486e05a805c3d851005da8d52594b8d3b78d3f7f7a7e4428`

Any change to those files after this freeze requires either restoring the frozen
version or documenting a protocol amendment before generating model outputs.
Formatting-only report changes do not change the experiment protocol.

## Integrity checks

- `29 passed, 6 subtests passed` under `uv run pytest -q` at freeze time.
- The package built as both a wheel and source archive.
- No exact upstream canary string was found outside ignored private/build/virtual
  environment directories.
- The public result files contain scores and accounting fields, not raw model
  prose or decrypted benchmark content.
- No new paid calls were made while producing this freeze.

## Approved deviations

None. Author budget approval is still pending. A failed provider request,
interrupted run, model retirement, pricing change, order-fingerprint mismatch,
or required code change must be recorded as an amendment rather than silently
changing this file.
