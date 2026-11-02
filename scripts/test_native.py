import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import native


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.lock = {
            "repository": native.REPOSITORY, "tag": "v1.9.4",
            "sha": "a" * 40, "rust": "1.92.0",
        }
        native.write_json(self.root / "native-source.json", self.lock)

    def resolve(self, selection="pinned", sha=None, rust="1.92.0", prerelease=False):
        release = {"tag_name": "v1.9.4", "draft": False, "prerelease": prerelease}
        with patch.object(native, "ROOT", self.root), \
                patch.object(native, "api", side_effect=[release, {"sha": sha or self.lock["sha"]}]), \
                patch.object(native, "run", return_value=f'[toolchain]\nchannel = "{rust}"'), \
                patch.dict(os.environ, {"GITHUB_OUTPUT": str(self.root / "outputs")}), \
                contextlib.redirect_stdout(io.StringIO()):
            native.resolve(selection, self.root / "resolved.json")

    def test_pinned_source_and_outputs(self):
        self.resolve()
        self.assertEqual(json.loads((self.root / "resolved.json").read_text()), self.lock)
        self.assertIn(f"sha={self.lock['sha']}\n", (self.root / "outputs").read_text())

    def test_latest_resolves_to_concrete_release(self):
        self.resolve("latest", sha="b" * 40)
        self.assertEqual(json.loads((self.root / "resolved.json").read_text())["sha"], "b" * 40)

    def test_reject_moved_pin_unpinned_toolchain_and_prerelease(self):
        for kwargs in ({"sha": "b" * 40}, {"rust": "stable"}, {"prerelease": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.resolve(**kwargs)

    def test_reject_branch_or_injection_as_source(self):
        for selection in ("main", "../tags/v1.9.4", "v1.9.4\nsha=bad", "$(whoami)"):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                self.resolve(selection)

    def test_smoke_checks_version_and_required_server_options(self):
        options = "--model-id --hostname --port --max-concurrent-requests"
        with patch.object(native, "run", side_effect=["text-embeddings-router 1.9.4", options]):
            native.smoke(self.root / "server", "1.9.4")
        for responses in (["text-embeddings-router 1.8.0"], ["1.9.4", "--help"]):
            with patch.object(native, "run", side_effect=responses), self.assertRaises(ValueError):
                native.smoke(self.root / "server", "1.9.4")

    def test_dependencies_fail_closed(self):
        with patch.object(native, "run", return_value="binary:\n\t/usr/lib/libSystem.B.dylib (version)"):
            native.mac_dependencies("binary")
        with patch.object(native, "run", return_value="binary:\n\t/opt/homebrew/lib/libssl.dylib (version)"):
            with self.assertRaisesRegex(ValueError, "Unpackaged"):
                native.mac_dependencies("binary")
        with patch.object(native, "run", return_value="    KERNEL32.dll\n    bcrypt.dll"):
            self.assertEqual(native.windows_dependencies("binary"), ["KERNEL32.dll", "bcrypt.dll"])
        for imports in ("    vcruntime140.dll", "    libcrypto-3-x64.dll", "unparseable"):
            with patch.object(native, "run", return_value=imports), self.assertRaises(ValueError):
                native.windows_dependencies("binary")

    def make_slices(self):
        slices = self.root / "slices"
        for target, (features, _) in native.TARGETS.items():
            folder = slices / target
            folder.mkdir(parents=True)
            name = "text-embeddings-router" + (".exe" if "windows" in target else "")
            (folder / name).write_bytes(target.encode())
            (folder / "UPSTREAM-LICENSE").write_text("Apache-2.0")
            (folder / "Cargo.lock").write_text("version = 4\n")
            native.write_json(folder / "build-info.json", {
                **self.lock, "target": target, "features": features,
                "binary_sha256": native.digest(folder / name), "builder_sha": "b" * 40,
                "cargo_lock_sha256": native.digest(folder / "Cargo.lock"),
            })
        return slices

    def test_incomplete_or_corrupt_assets_never_package(self):
        slices = self.make_slices()
        binary = slices / "x86_64-pc-windows-msvc" / "text-embeddings-router.exe"
        binary.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "Corrupted"):
            native.assemble(slices, self.lock, self.root / "dist")
        binary.unlink()
        with self.assertRaises(FileNotFoundError):
            native.assemble(slices, self.lock, self.root / "dist")
        self.assertFalse((self.root / "dist").exists())

    def test_mixed_source_or_builder_never_packages(self):
        slices = self.make_slices()
        info_path = slices / "aarch64-apple-darwin" / "build-info.json"
        info = json.loads(info_path.read_text())
        info["sha"] = "c" * 40
        native.write_json(info_path, info)
        with self.assertRaisesRegex(ValueError, "Inconsistent source"):
            native.assemble(slices, self.lock, self.root / "dist")
        info["sha"] = self.lock["sha"]
        info["builder_sha"] = "c" * 40
        native.write_json(info_path, info)
        with self.assertRaisesRegex(ValueError, "different builder"):
            native.assemble(slices, self.lock, self.root / "dist")

    def test_archive_has_executable_mode_and_no_extra_top_directory(self):
        folder = self.root / "package"
        folder.mkdir()
        binary = folder / "text-embeddings-router"
        binary.write_bytes(b"server")
        binary.chmod(0o755)
        native.archive(folder, self.root / "package.zip")
        with zipfile.ZipFile(self.root / "package.zip") as zipped:
            self.assertEqual(zipped.namelist(), ["text-embeddings-router"])
            self.assertEqual((zipped.getinfo(binary.name).external_attr >> 16) & 0o777, 0o755)

    def test_complete_distribution_layout_hashes_and_permissions(self):
        slices = self.make_slices()
        output = self.root / "dist"

        def fake_run(*args):
            if args[:2] == ("lipo", "-create"):
                Path(args[-1]).write_bytes(b"universal-server")
            if args[0] == "otool":
                return "binary:\n\t/usr/lib/libSystem.B.dylib (version)"
            return ""

        with patch.object(native, "run", side_effect=fake_run), patch.object(native, "smoke"):
            native.assemble(slices, self.lock, output)
        archives = sorted(output.glob("*.zip"))
        self.assertEqual([path.name for path in archives], [
            "tei-v1.9.4-macos-universal.zip", "tei-v1.9.4-windows-x64.zip"])
        for path in archives:
            with zipfile.ZipFile(path) as zipped:
                self.assertIn("UPSTREAM-LICENSE", zipped.namelist())
                self.assertIn("Cargo.lock", zipped.namelist())
                manifest = json.loads(zipped.read("build-info.json"))
                name = "text-embeddings-router" + (".exe" if "windows" in path.name else "")
                self.assertEqual(manifest["packaged_binary_sha256"],
                                 native.hashlib.sha256(zipped.read(name)).hexdigest())
                if "macos" in path.name:
                    self.assertEqual((zipped.getinfo(name).external_attr >> 16) & 0o777, 0o755)
            self.assertIn(f"{native.digest(path)}  {path.name}",
                          (output / "SHA256SUMS").read_text())

    def test_build_rejects_wrong_host_and_moved_checkout(self):
        with patch.object(native.platform, "system", return_value="Linux"), \
                patch.object(native.platform, "machine", return_value="x86_64"), \
                self.assertRaisesRegex(ValueError, "native host"):
            native.build(self.root, "aarch64-apple-darwin", self.lock, self.root / "slice")
        with patch.object(native.platform, "system", return_value="Darwin"), \
                patch.object(native.platform, "machine", return_value="arm64"), \
                patch.object(native, "run", return_value="c" * 40), \
                self.assertRaisesRegex(ValueError, "resolved commit"):
            native.build(self.root, "aarch64-apple-darwin", self.lock, self.root / "slice")


if __name__ == "__main__":
    unittest.main()
