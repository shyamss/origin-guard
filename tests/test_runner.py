import tempfile
import unittest
from pathlib import Path

from origin_guard.runner import completed_item_ids, load_api_key


class RunnerTests(unittest.TestCase):
    def test_load_raw_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "key"
            path.write_text("secret-value\n")
            self.assertEqual(load_api_key(path), "secret-value")

    def test_load_assignment_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "key"
            path.write_text("ANTHROPIC_API_KEY='secret-value'\n")
            self.assertEqual(load_api_key(path), "secret-value")

    def test_completed_ids_only_include_successes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "results.jsonl"
            path.write_text(
                '{"item_id":"a","status":"ok"}\n'
                '{"item_id":"b","status":"error"}\n'
            )
            self.assertEqual(completed_item_ids(path), {"a"})


if __name__ == "__main__":
    unittest.main()
