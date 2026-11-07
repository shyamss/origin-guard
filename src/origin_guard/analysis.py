from __future__ import annotations

import json
import itertools
import random
import statistics
from collections import defaultdict
from pathlib import Path
from collections.abc import Iterable
from typing import Any


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def bootstrap_mean_ci(
    values: list[float], *, seed: int = 20261107, samples: int = 10_000
) -> tuple[float, float]:
    if not values:
        raise ValueError("cannot bootstrap an empty sample")
    rng = random.Random(seed)
    means = [
        statistics.mean(rng.choice(values) for _ in values)
        for _ in range(samples)
    ]
    return _percentile(means, 0.025), _percentile(means, 0.975)


def exact_sign_flip_pvalue(
    values: list[float], *, alternative: str = "two-sided"
) -> float:
    """Exact randomization test under independent sign symmetry.

    Zero effects are removed because flipping their sign adds duplicate outcomes.
    This is appropriate for the tiny exploratory strata here, not a scalable
    permutation implementation.
    """
    nonzero = [value for value in values if value != 0]
    if not nonzero:
        return 1.0
    if len(nonzero) > 20:
        raise ValueError("exact sign-flip test is limited to 20 nonzero values")
    if alternative not in {"two-sided", "greater"}:
        raise ValueError("alternative must be 'two-sided' or 'greater'")
    observed = sum(nonzero)
    threshold = abs(observed) if alternative == "two-sided" else observed
    extreme = 0
    total = 0
    for signs in itertools.product((-1, 1), repeat=len(nonzero)):
        permuted = sum(sign * value for sign, value in zip(signs, nonzero))
        if alternative == "two-sided":
            extreme += abs(permuted) >= threshold
        else:
            extreme += permuted >= threshold
        total += 1
    return extreme / total


def _effect_summary(values: list[float]) -> dict[str, Any]:
    low, high = bootstrap_mean_ci(values)
    return {
        "n_cases": len(values),
        "n_nonzero": sum(value != 0 for value in values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "bootstrap_95pct_ci_mean": [low, high],
        "exact_sign_flip_pvalue_two_sided": exact_sign_flip_pvalue(values),
    }


def summarize_results(paths: Path | Iterable[Path]) -> dict[str, Any]:
    source_paths = [paths] if isinstance(paths, Path) else list(paths)
    if not source_paths:
        raise ValueError("at least one results path is required")
    latest: dict[str, dict[str, Any]] = {}
    errors = 0
    for path in source_paths:
        for raw in path.read_text().splitlines():
            if not raw.strip():
                continue
            row = json.loads(raw)
            if row.get("status") == "ok":
                latest[row["item_id"]] = row
            else:
                errors += 1

    cells: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    for row in latest.values():
        cells[(row["case_id"], row["stratum"], row["condition"])][
            row["variant"]
        ] = float(row["score"])

    cases: list[dict[str, Any]] = []
    for (case_id, stratum, condition), variants in sorted(cells.items()):
        if {"attack", "benign"} <= variants.keys():
            cases.append(
                {
                    "case_id": case_id,
                    "stratum": stratum,
                    "condition": condition,
                    "attack": variants["attack"],
                    "benign": variants["benign"],
                    "margin": variants["attack"] - variants["benign"],
                }
            )

    by_case: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in cases:
        by_case[(row["case_id"], row["stratum"])][row["condition"]] = row

    effects: list[dict[str, Any]] = []
    for (case_id, stratum), conditions in sorted(by_case.items()):
        if {"provenance", "placebo"} <= conditions.keys():
            prov = conditions["provenance"]
            placebo = conditions["placebo"]
            effects.append(
                {
                    "case_id": case_id,
                    "stratum": stratum,
                    "provenance_margin": prov["margin"],
                    "placebo_margin": placebo["margin"],
                    "margin_effect": prov["margin"] - placebo["margin"],
                    "attack_score_effect": prov["attack"] - placebo["attack"],
                    "benign_score_effect": prov["benign"] - placebo["benign"],
                }
            )

    factorial_effects: list[dict[str, Any]] = []
    factorial_conditions = {
        "placebo",
        "neutral_provenance",
        "policy_only",
        "provenance",
    }
    for (case_id, stratum), conditions in sorted(by_case.items()):
        if factorial_conditions <= conditions.keys():
            neither = conditions["placebo"]["margin"]
            origin_only = conditions["neutral_provenance"]["margin"]
            policy_only = conditions["policy_only"]["margin"]
            both = conditions["provenance"]["margin"]
            factorial_effects.append(
                {
                    "case_id": case_id,
                    "stratum": stratum,
                    "neither_margin": neither,
                    "origin_only_margin": origin_only,
                    "policy_only_margin": policy_only,
                    "both_margin": both,
                    "origin_main_effect": (
                        (origin_only - neither) + (both - policy_only)
                    )
                    / 2,
                    "policy_main_effect": (
                        (policy_only - neither) + (both - origin_only)
                    )
                    / 2,
                    "interaction_effect": (
                        both - origin_only - policy_only + neither
                    ),
                }
            )

    strata: dict[str, Any] = {}
    for stratum in sorted({row["stratum"] for row in effects}):
        selected = [row for row in effects if row["stratum"] == stratum]
        margins = [row["margin_effect"] for row in selected]
        attacks = [row["attack_score_effect"] for row in selected]
        benign = [row["benign_score_effect"] for row in selected]
        low, high = bootstrap_mean_ci(margins)
        strata[stratum] = {
            "n_cases": len(selected),
            "n_nonzero_margin_effects": sum(value != 0 for value in margins),
            "mean_margin_effect": statistics.mean(margins),
            "median_margin_effect": statistics.median(margins),
            "bootstrap_95pct_ci_mean_margin_effect": [low, high],
            "exact_sign_flip_pvalue_two_sided": exact_sign_flip_pvalue(margins),
            "exact_sign_flip_pvalue_greater": exact_sign_flip_pvalue(
                margins, alternative="greater"
            ),
            "mean_attack_score_effect": statistics.mean(attacks),
            "mean_benign_score_effect": statistics.mean(benign),
        }

    factorial_strata: dict[str, Any] = {}
    for stratum in sorted({row["stratum"] for row in factorial_effects}):
        selected = [
            row for row in factorial_effects if row["stratum"] == stratum
        ]
        factorial_strata[stratum] = {
            name: _effect_summary([float(row[name]) for row in selected])
            for name in (
                "origin_main_effect",
                "policy_main_effect",
                "interaction_effect",
            )
        }

    input_tokens = sum(int(row.get("input_tokens", 0)) for row in latest.values())
    output_tokens = sum(int(row.get("output_tokens", 0)) for row in latest.values())
    return {
        "schema": "origin-guard/pilot-summary/v1",
        "source": (
            str(source_paths[0])
            if len(source_paths) == 1
            else [str(path) for path in source_paths]
        ),
        "successful_cells": len(latest),
        "prior_error_rows": errors,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_actual_cost_usd_at_5_25_per_mtok": (
            input_tokens * 5 + output_tokens * 25
        )
        / 1_000_000,
        "case_effects": effects,
        "strata": strata,
        "factorial_case_effects": factorial_effects,
        "factorial_strata": factorial_strata,
        "limitations": [
            "exploratory pilot; one model call per cell",
            "five target cases, including two structurally similar handoff cases",
            "bootstrap interval resamples cases and does not capture model-call variance",
            "exact sign-flip tests have very low power in these tiny strata",
            "scores are ordinal monitor outputs, not calibrated probabilities",
            "no fixed-FPR threshold can be estimated from eleven benign cases",
        ],
    }
