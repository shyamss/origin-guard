import unittest

from origin_guard.shell import observe_shell


class ShellObservationTests(unittest.TestCase):
    def test_link_tracks_source_and_destination(self):
        result = observe_shell(
            "ln -s /data/model results/evaluated_checkpoint", "/workspace"
        )
        self.assertEqual(result.operation, "link")
        self.assertEqual(result.reads, ("/data/model",))
        self.assertEqual(
            result.writes, ("/workspace/results/evaluated_checkpoint",)
        )

    def test_cloud_copy_is_external_transfer(self):
        result = observe_shell(
            "aws s3 cp /data/archive.zip s3://external/backups/archive.zip"
        )
        self.assertEqual(result.operation, "external_transfer")
        self.assertIn("/data/archive.zip", result.reads)
        self.assertIn("s3://external/backups/archive.zip", result.transfers)

    def test_unknown_command_is_not_claimed_to_be_interpreted(self):
        result = observe_shell("custom-tool --flag value")
        self.assertEqual(result.operation, "shell_command")
        self.assertEqual(result.confidence, "unknown_effects")


if __name__ == "__main__":
    unittest.main()
