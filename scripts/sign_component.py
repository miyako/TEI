import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile


MACHO_MAGICS = {
    b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca",
}


def discover(product):
    binaries = []
    bundles = []
    for path in sorted(product.rglob("*")):
        if path.is_symlink():
            if not path.resolve(strict=True).is_relative_to(product):
                raise ValueError(f"Component symlink escapes product: {path}")
            continue
        if path.is_file():
            with path.open("rb") as stream:
                if stream.read(4) in MACHO_MAGICS:
                    binaries.append(path)
        elif path.suffix in {".app", ".framework", ".xpc", ".bundle", ".plugin", ".kext"}:
            for relative in ("Contents/Info.plist", "Resources/Info.plist", "Info.plist"):
                info = path / relative
                if info.is_file():
                    if plistlib.loads(info.read_bytes()).get("CFBundleExecutable"):
                        bundles.append(path)
                    break
    if not binaries:
        raise ValueError(f"No Mach-O binaries found in {product}")
    return binaries, sorted(bundles, key=lambda path: (-len(path.parts), str(path)))


def run(*arguments):
    print("+", *map(str, arguments), flush=True)
    result = subprocess.run(arguments, text=True, capture_output=True)
    if result.returncode:
        print(result.stdout, end="", flush=True)
        print(result.stderr, end="", flush=True)
        result.check_returncode()
    return result


def verify(path, team, architecture=None):
    arguments = ["codesign", "--display", "--verbose=4"]
    if architecture:
        arguments += ["--architecture", architecture]
    result = run(*arguments, str(path))
    details = result.stdout + result.stderr
    print(details, flush=True)
    if not any(line.startswith("Authority=Developer ID Application:") for line in details.splitlines()):
        raise ValueError(f"Missing Developer ID Application authority: {path}")
    if f"TeamIdentifier={team}" not in details.splitlines():
        raise ValueError(f"Unexpected Developer ID team: {path}")
    if not any(line.startswith("Timestamp=") and line not in {"Timestamp=", "Timestamp=none"}
               for line in details.splitlines()):
        raise ValueError(f"Missing secure timestamp: {path}")
    if not any(line.startswith("CodeDirectory ") and "(runtime)" in line
               for line in details.splitlines()):
        raise ValueError(f"Missing hardened runtime: {path}")


def entitlements(path):
    try:
        result = run("codesign", "--display", "--entitlements", "-", "--xml", str(path))
    except subprocess.CalledProcessError as error:
        if error.returncode == 1 and "code object is not signed at all" in (error.stderr or ""):
            return {}
        raise
    return plistlib.loads(result.stdout.encode()) if result.stdout.strip() else {}


def sign_component(product, identity, keychain, team):
    product = product.resolve(strict=True)
    binaries, bundles = discover(product)
    for path in binaries + bundles:
        existing = entitlements(path)
        with tempfile.TemporaryDirectory() as temporary:
            arguments = []
            if existing:
                entitlement_file = Path(temporary) / "entitlements.plist"
                entitlement_file.write_bytes(plistlib.dumps(existing))
                arguments = ["--entitlements", str(entitlement_file)]
            run("codesign", "--force", "--options", "runtime", "--timestamp",
                "--force-library-entitlements", "--generate-entitlement-der",
                "--sign", identity, "--keychain", keychain, *arguments, str(path))
        if entitlements(path) != existing:
            raise ValueError(f"Entitlements changed during signing: {path}")
    inventory = []
    for path in binaries:
        run("codesign", "--verify", "--strict", "--all-architectures", str(path))
        architectures = run("lipo", "-archs", str(path)).stdout.split()
        if not architectures:
            raise ValueError(f"No Mach-O architectures: {path}")
        for architecture in architectures:
            verify(path, team, architecture)
        inventory.append({
            "path": path.relative_to(product).as_posix(),
            "architectures": architectures,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    for path in bundles:
        run("codesign", "--verify", "--strict", "--all-architectures", str(path))
        verify(path, team)
    return inventory


def main():
    parser = argparse.ArgumentParser(description="Sign and audit every component Mach-O, inside out.")
    parser.add_argument("product", type=Path)
    parser.add_argument("--inventory", type=Path, default=Path("component-signing.json"))
    args = parser.parse_args()
    inventory = sign_component(args.product, os.environ["SIGNING_IDENTITY"],
                               os.environ["KEYCHAIN_PATH"], os.environ["TEAM_ID"])
    args.inventory.write_text(json.dumps(inventory, indent=2) + "\n")


if __name__ == "__main__":
    main()
