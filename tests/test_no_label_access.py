import unittest
from pathlib import Path


class LabelIsolationTests(unittest.TestCase):
    def test_transformer_source_does_not_reference_benchmark_labels(self):
        root = Path(__file__).parents[1] / "src" / "origin_guard"
        source = "\n".join(path.read_text() for path in root.glob("*.py"))
        forbidden = (
            "metadata.json",
            "description.md",
            'get("outcome")',
            'get("tags")',
            "suspiciousness",
            "attack_metadata",
        )
        for needle in forbidden:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, source)


if __name__ == "__main__":
    unittest.main()
