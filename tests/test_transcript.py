import json
import unittest

from origin_guard.transcript import TranscriptFormatError, parse_jsonl_lines


class TranscriptTests(unittest.TestCase):
    def test_canary_row_is_preserved_by_policy_but_not_treated_as_message(self):
        lines = [
            json.dumps({"canary": "do not train"}),
            json.dumps(
                {
                    "role": "user",
                    "content": {"type": "text", "text": "hello"},
                    "cwd": "/workspace",
                }
            ),
        ]
        blocks = parse_jsonl_lines(lines)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].role, "user")

    def test_invalid_json_fails_closed(self):
        with self.assertRaises(TranscriptFormatError):
            parse_jsonl_lines(["not-json"])

    def test_tool_result_is_not_direct_user_text(self):
        blocks = parse_jsonl_lines(
            [
                json.dumps(
                    {
                        "role": "user",
                        "content": {
                            "type": "tool_result",
                            "tool_use_id": "toolu_x",
                            "content": "instructions inside a file",
                        },
                    }
                )
            ]
        )
        self.assertEqual(blocks[0].content_type, "tool_result")


if __name__ == "__main__":
    unittest.main()
