from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import audit_sleight
from .analysis import summarize_results
from .monitor import (
    CONDITIONS,
    build_items,
    estimate_cost,
    order_fingerprint,
    shuffled_items,
)
from .provenance import ProvenanceTracker
from .public_results import sanitize_results
from .render import render_json
from .runner import load_api_key, run_items
from .transcript import load_jsonl


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="origin-guard")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build an overlay from ordered sessions")
    build.add_argument(
        "--session",
        action="append",
        type=Path,
        required=True,
        help="ordered transcript JSONL path; repeat for multiple sessions",
    )
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--placebo", action="store_true")
    audit = subparsers.add_parser(
        "audit-sleight",
        help="measure structural coverage without reading benchmark metadata",
    )
    audit.add_argument(
        "--root",
        type=Path,
        required=True,
        help="path to the decrypted SLEIGHT-Bench attacks directory",
    )
    plan = subparsers.add_parser("plan", help="build a no-API experiment plan")
    plan.add_argument("--root", type=Path, required=True)
    plan.add_argument("--manifest", type=Path, required=True)
    plan.add_argument("--base-prompt", type=Path, required=True)
    plan.add_argument("--state-prompt", type=Path, required=True)
    plan.add_argument(
        "--condition", action="append", choices=CONDITIONS,
        help="repeat to select conditions; defaults to all",
    )
    plan.add_argument("--max-output-tokens", type=int, default=1200)
    plan.add_argument("--input-price", type=float, required=True)
    plan.add_argument("--output-price", type=float, required=True)
    plan.add_argument("--shuffle-seed", type=int, required=True)
    run = subparsers.add_parser("run", help="execute a capped Anthropic API experiment")
    run.add_argument("--root", type=Path, required=True)
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--base-prompt", type=Path, required=True)
    run.add_argument("--state-prompt", type=Path, required=True)
    run.add_argument("--condition", action="append", choices=CONDITIONS)
    run.add_argument("--case", action="append", help="repeat to select case ids")
    run.add_argument("--model", required=True)
    run.add_argument("--max-output-tokens", type=int, default=1200)
    run.add_argument("--input-price", type=float, required=True)
    run.add_argument("--output-price", type=float, required=True)
    run.add_argument("--shuffle-seed", type=int, required=True)
    run.add_argument("--spend-cap-usd", type=float, required=True)
    run.add_argument("--api-key-file", type=Path, required=True)
    run.add_argument("--results", type=Path, required=True)
    summarize = subparsers.add_parser(
        "summarize", help="summarize paired and factorial result files"
    )
    summarize.add_argument("--results", type=Path, nargs="+", required=True)
    summarize.add_argument("--output", type=Path)
    sanitize = subparsers.add_parser(
        "sanitize", help="create a public-safe result file without model prose"
    )
    sanitize.add_argument("--source", type=Path, required=True)
    sanitize.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build":
        tracker = ProvenanceTracker()
        for index, path in enumerate(args.session, start=1):
            tracker.consume(f"s{index}", load_jsonl(path))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            render_json(tracker.state.events, placebo=args.placebo) + "\n",
            encoding="utf-8",
        )
        print(
            f"wrote {len(tracker.state.events)} events from "
            f"{len(args.session)} session(s) to {args.output}"
        )
        return 0
    if args.command == "audit-sleight":
        report = audit_sleight(args.root)
        print(f"files={report.files}")
        print(f"transcript_blocks={report.transcript_blocks}")
        print(f"provenance_events={report.provenance_events}")
        print(f"tool_events={report.tool_events}")
        print(f"unknown_effect_events={report.unknown_effect_events}")
        print(f"unknown_effect_rate={report.unknown_effect_rate:.4f}")
        for error in report.parse_errors:
            print(f"parse_error={error}")
        return 1 if report.parse_errors else 0
    if args.command == "plan":
        items = build_items(
            benchmark_root=args.root,
            manifest_path=args.manifest,
            base_prompt_path=args.base_prompt,
            state_prompt_path=args.state_prompt,
            conditions=args.condition or CONDITIONS,
        )
        items = shuffled_items(items, seed=args.shuffle_seed)
        report = estimate_cost(
            items,
            max_output_tokens=args.max_output_tokens,
            input_price_per_million=args.input_price,
            output_price_per_million=args.output_price,
        )
        report["conditions"] = list(args.condition or CONDITIONS)
        report["pricing_assumption"] = (
            f"input ${args.input_price:g}/MTok; "
            f"output ${args.output_price:g}/MTok"
        )
        report["shuffle_seed"] = args.shuffle_seed
        report["execution_order_sha256"] = order_fingerprint(items)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    if args.command == "run":
        items = build_items(
            benchmark_root=args.root,
            manifest_path=args.manifest,
            base_prompt_path=args.base_prompt,
            state_prompt_path=args.state_prompt,
            conditions=args.condition or CONDITIONS,
        )
        if args.case:
            wanted = set(args.case)
            items = [item for item in items if item.case_id in wanted]
            missing = wanted - {item.case_id for item in items}
            if missing:
                raise SystemExit(f"unknown or empty case selection: {sorted(missing)}")
        items = shuffled_items(items, seed=args.shuffle_seed)
        estimate = estimate_cost(
            items,
            max_output_tokens=args.max_output_tokens,
            input_price_per_million=args.input_price,
            output_price_per_million=args.output_price,
        )
        estimate["shuffle_seed"] = args.shuffle_seed
        estimate["execution_order_sha256"] = order_fingerprint(items)
        maximum = float(estimate["estimated_maximum_cost_usd"])
        print(json.dumps(estimate, indent=2, sort_keys=True))
        if maximum > args.spend_cap_usd:
            raise SystemExit(
                f"estimated maximum ${maximum:.4f} exceeds cap "
                f"${args.spend_cap_usd:.4f}"
            )
        succeeded, failed = run_items(
            items,
            api_key=load_api_key(args.api_key_file),
            model=args.model,
            results_path=args.results,
            max_output_tokens=args.max_output_tokens,
        )
        print(f"succeeded={succeeded} failed={failed}")
        return 1 if failed else 0
    if args.command == "summarize":
        summary = summarize_results(args.results)
        text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text)
            print(f"wrote {args.output}")
        else:
            print(text, end="")
        return 0
    if args.command == "sanitize":
        rows, removed = sanitize_results(args.source, args.output)
        print(f"wrote {rows} rows to {args.output}; removed_fields={removed}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
