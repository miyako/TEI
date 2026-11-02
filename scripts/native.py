#!/usr/bin/env python3
"""Resolve, build and package the native TEI server without modifying upstream."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "huggingface/text-embeddings-inference"
TARGETS = {
    "aarch64-apple-darwin": ("http,candle,metal", "apple-m1"),
    "x86_64-apple-darwin": ("http,candle,accelerate", "x86-64"),
    "x86_64-pc-windows-msvc": ("http,candle", "x86-64"),
}


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def api(path):
    return json.loads(run("gh", "api", f"repos/{REPOSITORY}/{path}"))


def resolve(selection, output):
    lock = json.loads((ROOT / "native-source.json").read_text())
    if lock["repository"] != REPOSITORY:
        raise ValueError("Unexpected upstream repository")
    tag = lock["tag"] if selection == "pinned" else selection
    if tag == "latest":
        release = api("releases/latest")
    else:
        if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
            raise ValueError("Select pinned, latest, or a published vX.Y.Z release")
        release = api(f"releases/tags/{tag}")
    tag = release["tag_name"]
    if release["draft"] or release["prerelease"] or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError("Only stable published upstream releases are supported")
    sha = api(f"commits/{tag}")["sha"]
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("Invalid upstream commit")
    toolchain = run("gh", "api", "-H", "Accept: application/vnd.github.raw+json",
                    f"repos/{REPOSITORY}/contents/rust-toolchain.toml?ref={sha}")
    rust = tomllib.loads(toolchain)["toolchain"]["channel"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", rust):
        raise ValueError("Upstream must specify an exact Rust toolchain")
    source = {"repository": REPOSITORY, "tag": tag, "sha": sha, "rust": rust}
    if selection == "pinned" and source != lock:
        raise ValueError("Pinned release moved or its toolchain differs from native-source.json")
    write_json(output, source)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            for key, value in source.items():
                stream.write(f"{key}={value}\n")
    print(json.dumps(source, indent=2))


def smoke(binary, version):
    binary = str(Path(binary).resolve())
    actual = run(binary, "--version")
    if not re.search(rf"\b{re.escape(version)}\b", actual):
        raise ValueError(f"Unexpected server version: {actual}")
    help_text = run(binary, "--help")
    for option in ("--model-id", "--hostname", "--port", "--max-concurrent-requests"):
        if option not in help_text:
            raise ValueError(f"Server CLI is missing {option}")
    print(actual)


def mac_dependencies(binary):
    for line in run("otool", "-L", str(binary)).splitlines()[1:]:
        dependency = line.strip().split(" (", 1)[0]
        if not dependency.startswith(("/usr/lib/", "/System/Library/")):
            raise ValueError(f"Unpackaged macOS dependency: {dependency}")


def windows_dependencies(binary):
    # The CRT is static; only OS DLLs are allowed. Fail closed on new dependencies.
    allowed = {
        "advapi32.dll", "bcrypt.dll", "bcryptprimitives.dll", "crypt32.dll",
        "dbghelp.dll", "iphlpapi.dll",
        "kernel32.dll", "msvcrt.dll", "ncrypt.dll", "ntdll.dll", "ole32.dll",
        "oleaut32.dll", "psapi.dll", "secur32.dll", "shell32.dll", "shlwapi.dll",
        "user32.dll", "userenv.dll", "version.dll", "ws2_32.dll",
    }
    imports = run("dumpbin", "/dependents", str(binary))
    dlls = re.findall(r"^\s+([A-Za-z0-9_.-]+\.dll)\s*$", imports, re.MULTILINE | re.IGNORECASE)
    if not dlls:
        raise ValueError("Could not inspect Windows runtime dependencies")
    for dll in dlls:
        if dll.lower() not in allowed and not dll.lower().startswith("api-ms-win-"):
            raise ValueError(f"Unpackaged Windows dependency: {dll}")
    return dlls


def build(source, target, resolved, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError(f"Output must be fresh: {output}")
    expected_host = {
        "aarch64-apple-darwin": ("Darwin", "arm64"),
        "x86_64-apple-darwin": ("Darwin", "x86_64"),
        "x86_64-pc-windows-msvc": ("Windows", "AMD64"),
    }[target]
    if (platform.system(), platform.machine()) != expected_host:
        raise ValueError(f"{target} must be built and smoke-tested on a native host")
    if run("git", "-C", str(source), "rev-parse", "HEAD") != resolved["sha"]:
        raise ValueError("Upstream checkout does not match resolved commit")
    if run("git", "-C", str(source), "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Upstream checkout has tracked modifications")
    workspace = tomllib.loads((source / "Cargo.toml").read_text())
    toolchain = tomllib.loads((source / "rust-toolchain.toml").read_text())
    version = resolved["tag"].removeprefix("v")
    if workspace["workspace"]["package"]["version"] != version:
        raise ValueError("Upstream version differs from release tag")
    if toolchain["toolchain"]["channel"] != resolved["rust"]:
        raise ValueError("Upstream toolchain differs from resolved toolchain")
    features, cpu = TARGETS[target]
    flags = f"-C target-cpu={cpu}"
    if platform.system() == "Windows":
        flags += " -C target-feature=+crt-static"
    env = os.environ.copy()
    # Override upstream target-cpu=native and Intel's AVX disabling config.
    env.pop("CARGO_ENCODED_RUSTFLAGS", None)
    env.update(RUSTFLAGS=flags, MACOSX_DEPLOYMENT_TARGET="14.0",
               CARGO_TARGET_DIR=str(source / "target"), CARGO_INCREMENTAL="0")
    lock_hash = digest(source / "Cargo.lock")
    command = ["cargo", f"+{resolved['rust']}", "build", "--locked", "--release",
               "--target", target, "--package", "text-embeddings-router",
               "--bin", "text-embeddings-router", "--no-default-features", "--features", features]
    subprocess.run(command, cwd=source, env=env, check=True)
    if digest(source / "Cargo.lock") != lock_hash:
        raise ValueError("Cargo.lock changed during the build")
    name = "text-embeddings-router" + (".exe" if platform.system() == "Windows" else "")
    binary = source / "target" / target / "release" / name
    smoke(binary, version)
    if platform.system() == "Darwin":
        mac_dependencies(binary)
        dependencies = run("otool", "-L", str(binary))
    else:
        dependencies = windows_dependencies(binary)
    output.mkdir(parents=True)
    shutil.copy2(binary, output / name)
    shutil.copy2(source / "LICENSE", output / "UPSTREAM-LICENSE")
    shutil.copy2(source / "Cargo.lock", output / "Cargo.lock")
    write_json(output / "build-info.json", {
        **resolved, "target": target, "features": features, "rustflags": flags,
        "cargo_lock_sha256": lock_hash, "binary_sha256": digest(binary),
        "rustc": run("rustc", f"+{resolved['rust']}", "--version"),
        "builder_sha": run("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        "build_script_sha256": digest(Path(__file__)),
        "workflow_run": os.environ.get("GITHUB_RUN_ID"),
        "macos_deployment_target": "14.0" if platform.system() == "Darwin" else None,
        "dependencies": dependencies,
    })


def archive(root, destination):
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(Path(root).rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(root))


def assemble(slices, resolved, output):
    slices, output = Path(slices).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError(f"Output must be fresh: {output}")
    manifests = {}
    for target in TARGETS:
        folder = slices / target
        info = json.loads((folder / "build-info.json").read_text())
        name = "text-embeddings-router" + (".exe" if "windows" in target else "")
        if any(info[key] != value for key, value in resolved.items()):
            raise ValueError(f"Inconsistent source provenance for {target}")
        if info["target"] != target or info["features"] != TARGETS[target][0]:
            raise ValueError(f"Inconsistent target/features for {target}")
        if info["binary_sha256"] != digest(folder / name):
            raise ValueError(f"Corrupted binary for {target}")
        if info["cargo_lock_sha256"] != digest(folder / "Cargo.lock"):
            raise ValueError(f"Corrupted Cargo.lock for {target}")
        manifests[target] = info
    if len({info["builder_sha"] for info in manifests.values()}) != 1:
        raise ValueError("Slices came from different builder commits")
    if len({info["cargo_lock_sha256"] for info in manifests.values()}) != 1:
        raise ValueError("Slices used different dependency locks")
    output.mkdir(parents=True)
    mac = output / "component" / "macOS"
    windows = output / "component" / "Windows"
    mac.mkdir(parents=True)
    windows.mkdir()
    binary = mac / "text-embeddings-router"
    run("lipo", "-create",
        str(slices / "aarch64-apple-darwin" / binary.name),
        str(slices / "x86_64-apple-darwin" / binary.name), "-output", str(binary))
    run("lipo", str(binary), "-verify_arch", "arm64", "x86_64")
    binary.chmod(0o755)
    run("codesign", "--force", "--sign", "-", str(binary))
    run("codesign", "--verify", "--strict", str(binary))
    smoke(binary, resolved["tag"].removeprefix("v"))
    for arch in ("arm64", "x86_64"):
        for line in run("otool", "-arch", arch, "-L", str(binary)).splitlines()[1:]:
            dependency = line.strip().split(" (", 1)[0]
            if not dependency.startswith(("/usr/lib/", "/System/Library/")):
                raise ValueError(f"Unpackaged universal dependency: {dependency}")
    shutil.copy2(slices / "x86_64-pc-windows-msvc" / "text-embeddings-router.exe", windows)
    for folder, targets in (
        (mac, ["aarch64-apple-darwin", "x86_64-apple-darwin"]),
        (windows, ["x86_64-pc-windows-msvc"]),
    ):
        shutil.copy2(slices / targets[0] / "UPSTREAM-LICENSE", folder)
        shutil.copy2(slices / targets[0] / "Cargo.lock", folder)
        write_json(folder / "build-info.json", {
            "source": resolved, "builds": [manifests[target] for target in targets],
            "packaged_binary_sha256": digest(folder / ("text-embeddings-router.exe"
                                                      if folder == windows else binary.name)),
            "macos_signing": "ad-hoc; not notarized" if folder == mac else None,
        })
    for folder, suffix in ((mac, "macos-universal"), (windows, "windows-x64")):
        archive(folder, output / f"tei-{resolved['tag']}-{suffix}.zip")
    checksums = [f"{digest(path)}  {path.name}\n" for path in sorted(output.glob("*.zip"))]
    (output / "SHA256SUMS").write_text("".join(checksums), encoding="utf-8")
    write_json(output / "native-source.json", resolved)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    resolver = commands.add_parser("resolve")
    resolver.add_argument("--source", default="pinned")
    resolver.add_argument("--output", default="resolved-source.json")
    builder = commands.add_parser("build")
    builder.add_argument("--source-dir", required=True)
    builder.add_argument("--target", choices=TARGETS, required=True)
    builder.add_argument("--resolved", required=True)
    builder.add_argument("--output", required=True)
    packager = commands.add_parser("assemble")
    packager.add_argument("--slices", required=True)
    packager.add_argument("--resolved", required=True)
    packager.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "resolve":
        resolve(args.source, args.output)
    else:
        resolved = json.loads(Path(args.resolved).read_text())
        if args.command == "build":
            build(args.source_dir, args.target, resolved, args.output)
        else:
            assemble(args.slices, resolved, args.output)


if __name__ == "__main__":
    main()
