import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class NotarizationTests(unittest.TestCase):
    def exercise(self, status, submit_exit=0):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tool = root / "xcrun"
            tool.write_text(
                "#!/bin/bash\n"
                'echo "$1 $2" >> calls\n'
                'if [[ "$1 $2" == "notarytool submit" ]]; then\n'
                f'  echo \'{{"id":"submission-id","status":"{status}"}}\'\n'
                f"  exit {submit_exit}\n"
                'elif [[ "$1 $2" == "notarytool log" ]]; then\n'
                '  echo \'{"issues":[]}\' > "${@: -1}"\n'
                "fi\n"
            )
            tool.chmod(0o755)
            env = dict(os.environ, PATH=f"{root}:{os.environ['PATH']}",
                       APPLE_ID="fixture", TEAM_ID="fixture", NOTARY_PASSWORD="fixture")
            script = Path(__file__).with_name("notarize.sh").resolve()
            result = subprocess.run(["bash", str(script), "fixture.dmg"],
                                    cwd=root, env=env, capture_output=True, text=True)
            return result, (root / "calls").read_text(), (root / "notarization-log.json").exists()

    @unittest.skipIf(os.name == "nt", "Bash signing helper runs only on macOS")
    def test_rejection_retains_log_and_never_staples(self):
        for submit_exit in (0, 65):
            with self.subTest(submit_exit=submit_exit):
                result, calls, retained = self.exercise("Invalid", submit_exit)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(retained)
                self.assertIn("notarytool log", calls)
                self.assertNotIn("stapler", calls)

    @unittest.skipIf(os.name == "nt", "Bash signing helper runs only on macOS")
    def test_acceptance_staples_and_validates(self):
        result, calls, retained = self.exercise("Accepted")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(retained)
        self.assertIn("stapler staple", calls)
        self.assertIn("stapler validate", calls)
