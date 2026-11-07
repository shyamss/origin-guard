#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
paper_tmp_dir=$(mktemp -d /tmp/origin-guard-paper.XXXXXX)
trap 'rm -rf "$paper_tmp_dir"' EXIT

cd "$repo_root/docs"

pandoc origin-or-policy.md \
  --from=gfm \
  --to=html5 \
  --standalone \
  --embed-resources \
  --resource-path="$repo_root/docs:$repo_root" \
  --css=paper.css \
  --metadata=pagetitle:"Origin or Policy?" \
  --output="$paper_tmp_dir/origin-or-policy.html"

uvx --from weasyprint==70.0 weasyprint \
  "$paper_tmp_dir/origin-or-policy.html" \
  "$repo_root/docs/origin-or-policy.pdf"

printf 'Wrote %s\n' "$repo_root/docs/origin-or-policy.pdf"
