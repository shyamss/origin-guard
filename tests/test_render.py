import json
import unittest

from origin_guard.model import ProvenanceEvent
from origin_guard.render import render_json


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.event = ProvenanceEvent(
            event_id=1,
            session_id="s2",
            transcript_index=4,
            actor="agent",
            operation="read",
            objects=("/workspace/handoff.md",),
            object_origins=("agent_written_prior_session",),
            authority="observation_not_authorization",
            depends_on=(2,),
        )

    def test_neutral_keeps_facts_but_withholds_authority_policy(self):
        result = json.loads(render_json([self.event], neutral=True))
        record = result["events"][0]
        self.assertEqual(
            record["object_origins"], ["agent_written_prior_session"]
        )
        self.assertEqual(record["depends_on"], [2])
        self.assertEqual(record["authority"], "not_evaluated")

    def test_placebo_removes_origin_and_dependencies(self):
        result = json.loads(render_json([self.event], placebo=True))
        record = result["events"][0]
        self.assertEqual(record["object_origins"], ["unresolved"])
        self.assertEqual(record["depends_on"], [])
        self.assertEqual(record["authority"], "unresolved")

    def test_policy_only_keeps_authority_but_removes_origin(self):
        result = json.loads(render_json([self.event], policy_only=True))
        record = result["events"][0]
        self.assertEqual(record["object_origins"], ["unresolved"])
        self.assertEqual(record["depends_on"], [])
        self.assertEqual(record["authority"], "observation_not_authorization")

    def test_modes_are_mutually_exclusive(self):
        with self.assertRaises(ValueError):
            render_json([self.event], placebo=True, neutral=True)
        with self.assertRaises(ValueError):
            render_json([self.event], neutral=True, policy_only=True)


if __name__ == "__main__":
    unittest.main()
