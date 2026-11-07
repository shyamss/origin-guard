import json
import tempfile
import unittest
from pathlib import Path

from origin_guard.analysis import exact_sign_flip_pvalue, summarize_results


class AnalysisTests(unittest.TestCase):
    def test_exact_sign_flip_pvalue_exposes_tiny_sample_uncertainty(self):
        values = [45, 28, 3, 0, 0]
        self.assertEqual(exact_sign_flip_pvalue(values), 0.25)
        self.assertEqual(
            exact_sign_flip_pvalue(values, alternative="greater"), 0.125
        )

    def test_paired_margin_effect(self):
        rows = []
        for condition, attack, benign in (
            ("provenance", 90, 30),
            ("placebo", 20, 5),
        ):
            for variant, score in (("attack", attack), ("benign", benign)):
                rows.append(
                    {
                        "status": "ok",
                        "item_id": f"c--{variant}--{condition}",
                        "case_id": "c",
                        "stratum": "target",
                        "variant": variant,
                        "condition": condition,
                        "score": score,
                        "input_tokens": 10,
                        "output_tokens": 2,
                    }
                )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "results.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            summary = summarize_results(path)
        effect = summary["case_effects"][0]
        self.assertEqual(effect["provenance_margin"], 60)
        self.assertEqual(effect["placebo_margin"], 15)
        self.assertEqual(effect["margin_effect"], 45)

    def test_factorial_effects_separate_origin_policy_and_interaction(self):
        rows = []
        margins = {
            "placebo": 10,
            "neutral_provenance": 16,
            "policy_only": 14,
            "provenance": 24,
        }
        for condition, margin in margins.items():
            for variant, score in (("attack", margin), ("benign", 0)):
                rows.append(
                    {
                        "status": "ok",
                        "item_id": f"c--{variant}--{condition}",
                        "case_id": "c",
                        "stratum": "target",
                        "variant": variant,
                        "condition": condition,
                        "score": score,
                    }
                )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "results.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            summary = summarize_results(path)
        effect = summary["factorial_case_effects"][0]
        self.assertEqual(effect["origin_main_effect"], 8)
        self.assertEqual(effect["policy_main_effect"], 6)
        self.assertEqual(effect["interaction_effect"], 4)

    def test_multiple_result_files_are_merged_by_item_id(self):
        placebo = {
            "status": "ok",
            "item_id": "c--attack--placebo",
            "case_id": "c",
            "stratum": "target",
            "variant": "attack",
            "condition": "placebo",
            "score": 10,
        }
        provenance = {
            **placebo,
            "item_id": "c--attack--provenance",
            "condition": "provenance",
            "score": 20,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.jsonl"
            second = root / "second.jsonl"
            first.write_text(json.dumps(placebo) + "\n")
            second.write_text(json.dumps(provenance) + "\n")
            summary = summarize_results([first, second])
        self.assertEqual(summary["successful_cells"], 2)
        self.assertEqual(summary["source"], [str(first), str(second)])


if __name__ == "__main__":
    unittest.main()
