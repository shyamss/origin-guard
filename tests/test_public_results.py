import json
import tempfile
import unittest
from pathlib import Path

from origin_guard.public_results import sanitize_record, sanitize_results


class PublicResultsTests(unittest.TestCase):
    def test_model_prose_and_provider_error_are_removed(self):
        result = sanitize_record(
            {
                "schema": "origin-guard/monitor-result/v1",
                "item_id": "case--attack--provenance",
                "status": "error",
                "error_type": "ProviderError",
                "error": "request quoted benchmark transcript and secret detail",
                "response": "model paraphrased the private transcript",
            }
        )
        self.assertNotIn("response", result)
        self.assertNotIn("error", result)
        self.assertEqual(result["error_type"], "ProviderError")
        self.assertEqual(result["redacted_fields"], ["error", "response"])

    def test_sanitized_rows_remain_analysis_compatible(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "raw.jsonl"
            output = Path(directory) / "public.jsonl"
            source.write_text(
                json.dumps(
                    {
                        "schema": "origin-guard/monitor-result/v1",
                        "item_id": "c--attack--placebo",
                        "case_id": "c",
                        "stratum": "target",
                        "variant": "attack",
                        "condition": "placebo",
                        "model": "m",
                        "status": "ok",
                        "score": 7,
                        "input_tokens": 10,
                        "output_tokens": 20,
                        "response": "private prose",
                    }
                )
                + "\n"
            )
            rows, removed = sanitize_results(source, output)
            result = json.loads(output.read_text())
            self.assertEqual(rows, 1)
            self.assertEqual(removed, 1)
            self.assertEqual(result["score"], 7)
            self.assertNotIn("response", result)


if __name__ == "__main__":
    unittest.main()
