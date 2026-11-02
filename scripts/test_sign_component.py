from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import sign_component


class ComponentSigningTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.product = Path(self.temporary.name) / "TEI.4dbase"
        self.paths = [
            "Libraries/lib4d-arm64.dylib",
            "Libraries/lib4d-x86_64.dylib",
            "Resources/bin/macOS/text-embeddings-router",
            "Resources/Helper.app/Contents/MacOS/Helper",
        ]
        for name in self.paths:
            path = self.product / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\xcf\xfa\xed\xfe" + b"fixture")
        (self.product / "Resources/bin/Windows").mkdir(parents=True)
        (self.product / "Resources/bin/Windows/router.exe").write_bytes(b"MZfixture")
        (self.product / "Resources/Helper.app/Contents/Info.plist").write_bytes(
            plistlib.dumps({"CFBundleExecutable": "Helper"}))

    def tool(self, *args):
        stdout, stderr = "", ""
        if args[:2] == ("lipo", "-archs"):
            stdout = "arm64 x86_64\n"
        elif args[:3] == ("codesign", "--display", "--entitlements"):
            stdout = ""
        elif args[:2] == ("codesign", "--display"):
            stderr = (
                "Authority=Developer ID Application: Fixture (TEAM)\n"
                "TeamIdentifier=TEAM\nTimestamp=Nov 2, 2026\n"
                "CodeDirectory v=20500 size=123 flags=0x10000(runtime) hashes=1\n"
            )
        return subprocess.CompletedProcess(args, 0, stdout, stderr)

    def test_signs_libraries_and_router_before_bundle_and_verifies_each_slice(self):
        with patch.object(sign_component, "run", side_effect=self.tool) as run:
            inventory = sign_component.sign_component(self.product, "identity", "keychain", "TEAM")
        self.assertEqual({row["path"] for row in inventory}, set(self.paths))
        commands = [call.args for call in run.call_args_list]
        signing = [args for args in commands if args[:2] == ("codesign", "--force")]
        self.assertEqual(len(signing), 5)
        self.assertTrue(signing[-1][-1].endswith("Helper.app"))
        for args in signing:
            self.assertIn("--timestamp", args)
            self.assertIn("runtime", args)
            self.assertIn("--force-library-entitlements", args)
            self.assertNotIn("--deep", args)
        displays = [args for args in commands if args[:3] == ("codesign", "--display", "--verbose=4")]
        self.assertEqual(len(displays), 9)
        self.assertEqual(sum("--all-architectures" in args for args in commands), 5)

    def test_sign_failure_stops_before_verification_or_inventory(self):
        def fail_sign(*args):
            if args[:2] == ("codesign", "--force"):
                raise subprocess.CalledProcessError(1, args)
            return self.tool(*args)
        with patch.object(sign_component, "run", side_effect=fail_sign) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                sign_component.sign_component(self.product, "identity", "keychain", "TEAM")
        self.assertEqual(run.call_count, 2)

    def test_only_known_unsigned_signature_error_is_allowed(self):
        error = subprocess.CalledProcessError(
            1, ["codesign"], stderr="fixture: code object is not signed at all")
        with patch.object(sign_component, "run", side_effect=error):
            self.assertEqual(sign_component.entitlements(self.product), {})
        error.stderr = "fixture: malformed signature"
        with patch.object(sign_component, "run", side_effect=error):
            with self.assertRaises(subprocess.CalledProcessError):
                sign_component.entitlements(self.product)

    def test_rejects_missing_authority_timestamp_runtime_or_wrong_team(self):
        valid = self.tool("codesign", "--display").stderr
        for bad in (
            valid.replace("Authority=Developer ID Application:", "Authority=Ad Hoc:"),
            valid.replace("Timestamp=Nov 2, 2026", "Timestamp=none"),
            valid.replace("Timestamp=Nov 2, 2026", "Timestamp="),
            valid.replace("TEAM", "OTHER"),
            valid.replace("(runtime)", ""),
        ):
            with self.subTest(details=bad):
                with patch.object(sign_component, "run",
                                  return_value=subprocess.CompletedProcess([], 0, "", bad)):
                    with self.assertRaises(ValueError):
                        sign_component.verify(self.product, "TEAM", "arm64")

    def test_signature_verification_failure_propagates(self):
        def fail_verify(*args):
            if args[:2] == ("codesign", "--verify"):
                raise subprocess.CalledProcessError(1, args)
            return self.tool(*args)
        with patch.object(sign_component, "run", side_effect=fail_verify):
            with self.assertRaises(subprocess.CalledProcessError):
                sign_component.sign_component(self.product, "identity", "keychain", "TEAM")

    def test_all_thin_and_universal_magics_are_discovered(self):
        for index, magic in enumerate(sign_component.MACHO_MAGICS):
            (self.product / f"binary-{index}").write_bytes(magic)
        binaries, _ = sign_component.discover(self.product)
        self.assertEqual(len(binaries), len(self.paths) + len(sign_component.MACHO_MAGICS))

    def test_empty_component_is_rejected(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaises(ValueError):
                sign_component.discover(Path(empty))

    @unittest.skipUnless(sys.platform == "darwin", "Requires actual macOS codesign and clang")
    def test_actual_library_entitlements_survive_resigning(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "libfixture.dylib"
            entitlements = root / "entitlements.plist"
            entitlements.write_bytes(plistlib.dumps({"com.apple.security.cs.allow-jit": True}))
            subprocess.run(
                ["clang", "-dynamiclib", "-x", "c", "-o", str(binary), "-"],
                input="int fixture(void) { return 1; }", text=True, check=True, capture_output=True)
            subprocess.run(
                ["codesign", "--force", "--sign", "-", "--force-library-entitlements",
                 "--entitlements", str(entitlements), str(binary)], check=True, capture_output=True)

            def adhoc_tool(*args):
                if args[:2] == ("codesign", "--force"):
                    args = list(args)
                    args[args.index("--timestamp")] = "--timestamp=none"
                    args[args.index("--sign") + 1] = "-"
                    index = args.index("--keychain")
                    del args[index:index + 2]
                return subprocess.run(args, check=True, text=True, capture_output=True)

            # Only the authority/timestamp audit needs credentials; real signing and
            # strict signature verification run with the production command flags.
            with patch.object(sign_component, "run", side_effect=adhoc_tool):
                with patch.object(sign_component, "verify"):
                    inventory = sign_component.sign_component(root, "fixture", "fixture", "TEAM")
            self.assertEqual(inventory[0]["path"], "libfixture.dylib")
            result = subprocess.run(
                ["codesign", "--display", "--entitlements", "-", "--xml", str(binary)],
                check=True, capture_output=True)
            self.assertTrue(plistlib.loads(result.stdout)["com.apple.security.cs.allow-jit"])
