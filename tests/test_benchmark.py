import json
import tempfile
import unittest
from pathlib import Path

from origin_guard.benchmark import audit_sleight


class BenchmarkAuditTests(unittest.TestCase):
    def test_audit_reads_only_transcripts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case = root / "category" / "case"
            case.mkdir(parents=True)
            row = {
                "role": "user",
                "content": {"type": "text", "text": "task"},
            }
            for name in ("transcript.jsonl", "benign.jsonl"):
                (case / name).write_text(json.dumps(row) + "\n")
            (case / "metadata.json").write_text("this is deliberately invalid")
            report = audit_sleight(root)
            self.assertEqual(report.files, 2)
            self.assertEqual(report.transcript_blocks, 2)
            self.assertFalse(report.parse_errors)


if __name__ == "__main__":
    unittest.main()
