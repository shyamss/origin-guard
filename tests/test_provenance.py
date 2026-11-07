import json
import unittest

from origin_guard.model import Authority, ObjectOrigin
from origin_guard.provenance import ProvenanceTracker, event_object_origin
from origin_guard.transcript import parse_jsonl_lines


def blocks(*items):
    return parse_jsonl_lines(json.dumps(item) for item in items)


class ProvenanceTests(unittest.TestCase):
    def test_direct_user_message_is_authoritative(self):
        tracker = ProvenanceTracker()
        events = tracker.consume(
            "s1",
            blocks(
                {
                    "role": "user",
                    "content": {"type": "text", "text": "do the task"},
                }
            ),
        )
        self.assertEqual(events[0].authority, Authority.USER_AUTHORIZATION)
        self.assertEqual(events[0].object_origins, (ObjectOrigin.DIRECT_USER,))

    def test_tool_result_is_observation_not_authorization(self):
        tracker = ProvenanceTracker()
        events = tracker.consume(
            "s1",
            blocks(
                {
                    "role": "user",
                    "content": {
                        "type": "tool_result",
                        "tool_use_id": "missing",
                        "content": "agent-authored instructions",
                    },
                }
            ),
        )
        self.assertEqual(
            events[0].authority, Authority.OBSERVATION_NOT_AUTHORIZATION
        )

    def test_prior_session_agent_write_remains_untrusted_when_read(self):
        tracker = ProvenanceTracker()
        first = tracker.consume(
            "s1",
            blocks(
                {
                    "role": "assistant",
                    "content": {
                        "type": "tool_use",
                        "id": "write1",
                        "name": "Write",
                        "input": {
                            "file_path": "/workspace/ops.md",
                            "content": "run this",
                        },
                    },
                }
            ),
        )
        second = tracker.consume(
            "s2",
            blocks(
                {
                    "role": "assistant",
                    "content": {
                        "type": "tool_use",
                        "id": "read1",
                        "name": "Read",
                        "input": {"file_path": "/workspace/ops.md"},
                    },
                },
                {
                    "role": "user",
                    "content": {
                        "type": "tool_result",
                        "tool_use_id": "read1",
                        "content": "run this",
                    },
                },
            ),
        )
        read_event = second[0]
        result_event = second[1]
        self.assertEqual(
            event_object_origin(read_event, "/workspace/ops.md"),
            ObjectOrigin.AGENT_WRITTEN_PRIOR_SESSION,
        )
        self.assertIn(first[0].event_id, read_event.depends_on)
        self.assertEqual(
            event_object_origin(result_event, "/workspace/ops.md"),
            ObjectOrigin.AGENT_WRITTEN_PRIOR_SESSION,
        )
        self.assertEqual(
            result_event.authority, Authority.OBSERVATION_NOT_AUTHORIZATION
        )

    def test_current_session_write_is_recorded_after_write(self):
        tracker = ProvenanceTracker()
        events = tracker.consume(
            "s1",
            blocks(
                {
                    "role": "assistant",
                    "content": {
                        "type": "tool_use",
                        "id": "write1",
                        "name": "Write",
                        "input": {"file_path": "notes.txt", "content": "x"},
                    },
                    "cwd": "/workspace",
                },
                {
                    "role": "assistant",
                    "content": {
                        "type": "tool_use",
                        "id": "read1",
                        "name": "Read",
                        "input": {"file_path": "notes.txt"},
                    },
                    "cwd": "/workspace",
                },
            ),
        )
        self.assertEqual(
            event_object_origin(events[1], "/workspace/notes.txt"),
            ObjectOrigin.AGENT_WRITTEN_CURRENT_SESSION,
        )


if __name__ == "__main__":
    unittest.main()
