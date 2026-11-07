# Reproducibility record

## Frozen external dependency

- Repository: `https://github.com/safety-research/sleight-bench.git`
- Commit: `218c58315cc01ff0dc5a100e906c27d82d259521`
- Upstream commit date: 2026-05-16
- Monitor prompt: `prompts/control_arena.md` at that commit
- Benchmark data: obtained and decrypted separately under the upstream
  instructions; never copied into this repository

The case manifest was frozen on 2026-11-07 before provenance/placebo treatment
outputs were viewed. It records the relative upstream attack directories.

## Local environment

The verified build used CPython 3.12 through `uv`. Recreate it with:

```bash
uv sync --extra api --group dev --python 3.12
uv run python -m unittest discover -s tests -v
uv build
```

The current suite contains 29 tests plus 6 subtests. The deterministic
transformer, public-result sanitizer, analysis, and figure generation require no
API calls.

## Structural audit

```bash
uv run origin-guard audit-sleight \
  --root /path/to/sleight-bench/attacks
```

Recorded audit: 87 files, 1,909 transcript blocks, 634 tool events, zero parse
errors, and 343 tool events with incompletely interpreted shell effects.

## Plan before paid execution

Always run the cost estimator with the intended model's current prices:

```bash
uv run origin-guard plan \
  --root /path/to/sleight-bench/attacks \
  --manifest config/pilot-cases.json \
  --base-prompt /path/to/sleight-bench/prompts/control_arena.md \
  --state-prompt /path/to/sleight-bench/prompts/state_tracking.md \
  --condition provenance \
  --condition placebo \
  --max-output-tokens 1200 \
  --input-price 5 \
  --output-price 25 \
  --shuffle-seed 20261107
```

The API runner requires an explicit spend cap and writes append-only raw results
to the caller-selected path. Put raw output under `results/private/`.

The unrun factorial follow-up replaces the two completed conditions above with
`neutral_provenance` and `policy_only`. Its frozen no-call cost record is
`config/factorial-followup-plan.json`: 44 calls and a $3.10 worst-case estimate
at the standard global API prices verified on 2026-11-07, with a proposed $3.25
hard cap pending approval. Anthropic's Opus 4.6 announcement records $5 per
million input tokens and $25 per million output tokens:
`https://www.anthropic.com/news/claude-opus-4-6`.

The frozen seed produces execution-order SHA-256
`f692836ab487ca7224c61472485488d9ccba9c8e4617d2a778663b8341ed0406` for the
44 missing cells. Abort rather than run if the runner prints a different value.

Only after author approval, the frozen execution shape is:

```bash
uv run origin-guard run \
  --root /path/to/sleight-bench/attacks \
  --manifest config/pilot-cases.json \
  --base-prompt /path/to/sleight-bench/prompts/control_arena.md \
  --state-prompt /path/to/sleight-bench/prompts/state_tracking.md \
  --condition neutral_provenance \
  --condition policy_only \
  --model claude-opus-4-6 \
  --max-output-tokens 1200 \
  --input-price 5 \
  --output-price 25 \
  --shuffle-seed 20261107 \
  --spend-cap-usd 3.25 \
  --api-key-file /secure/path/to/anthropic-key \
  --results results/private/factorial-opus46-raw.jsonl
```

The key file must remain outside the repository. The raw result path is ignored
by Git and must be sanitized before any public analysis artifact is created.

## Public-safe analysis

```bash
uv run origin-guard sanitize \
  --source results/private/pilot-opus46-raw.jsonl \
  --output results/pilot-opus46.jsonl

uv run origin-guard summarize \
  --results results/pilot-opus46.jsonl \
  --output results/pilot-opus46-summary.json

uv run python scripts/render_pilot_figure.py \
  --summary results/pilot-opus46-summary.json \
  --output results/pilot-margin-effects.svg
```

The public JSONL intentionally omits raw model prose and provider error messages.
Its score, condition, token, and status fields reproduce the checked-in summary.

After a factorial follow-up, sanitize its raw file separately and pass both
public-safe paths to `summarize`; the command merges latest successful rows by
item ID without manually concatenating benchmark-adjacent files:

```bash
uv run origin-guard summarize \
  --results results/pilot-opus46.jsonl results/factorial-opus46.jsonl \
  --output results/factorial-opus46-summary.json
```

## Irreducible variation

The provider API did not expose a seed and the run used one call per cell. A
fresh run can therefore differ from the cached scores even with the same model
identifier and prompt. The cached public-safe output reproduces the reported
analysis, not future model behavior. Current model availability and pricing can
also change.
