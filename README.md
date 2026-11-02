# TEI

[Hugging Face Text Embeddings Inference](https://github.com/huggingface/text-embeddings-inference)
as a native HTTP server and a 4D 20+ component. The executable is
**`text-embeddings-router`**, not a model downloader or a Python wrapper.
See the [4D usage guide](https://miyako.github.io/TEI/).

## Source and supported builds

The default source is upstream **v1.9.4**, commit
[`e80ef225ed0e6cb1717ce632a6a84b6cf211bb67`](https://github.com/huggingface/text-embeddings-inference/commit/e80ef225ed0e6cb1717ce632a6a84b6cf211bb67)
(latest stable release checked 2026-11-02). [native-source.json](native-source.json)
pins the release, commit and upstream Rust **1.92.0** toolchain. Cargo uses
upstream's checked-in `Cargo.lock` with `--locked`; no upstream source patches are applied.
CI checks out upstream with `core.autocrlf=false` and `core.eol=lf` on every
platform so dependency-lock and license bytes stay identical across targets.
The regression suite runs on all three native runners before compilation; it
checks CRLF conversion explicitly and tests executable permissions according to
the host's filesystem semantics.

| Distribution | Native build target | Backend / explicit Cargo features | Minimum runtime |
|---|---|---|---|
| macOS universal | `aarch64-apple-darwin` | Candle + Metal: `http,candle,metal` | Apple Silicon, macOS 14+ |
| macOS universal | `x86_64-apple-darwin` | Candle + Accelerate CPU: `http,candle,accelerate` | Intel Mac, macOS 14+ |
| Windows x64 | `x86_64-pc-windows-msvc` | Candle CPU: `http,candle` | Windows 10/11 x64 |

These are this repository's **build targets**, not a claim that every platform has
already passed CI for this change. Each native runner must build and pass CLI and
dependency checks before a distribution can be published. Both Mac slices are
combined with `lipo`, preserving the existing universal-binary consumer path.
CPU flags are explicit (`apple-m1` / baseline `x86-64`), never runner-specific
`target-cpu=native`. Windows uses the static MSVC CRT; only allowlisted Windows
system DLL imports are accepted. Mac binaries may link only Apple system libraries
and frameworks. No Homebrew libraries, CUDA DLLs or ONNX Runtime downloads are needed.
The Windows allowlist includes OS-provided `bcryptprimitives.dll` for
[random-number generation](https://learn.microsoft.com/en-us/windows/win32/seccng/processprng)
and `combase.dll` for the
[Windows Runtime](https://learn.microsoft.com/en-us/windows/win32/api/roapi/nf-roapi-roinitialize).
These must not be bundled as application runtime dependencies. Inspection logs
the full import list and reports all unexpected DLLs together, without relaxing
the exact system-DLL allowlist.

Linux, Windows ARM64, CUDA, ROCm, ONNX Runtime, Python and gRPC are **not packaged**
here. Upstream supports other deployment options; see its
[documentation](https://huggingface.co/docs/text-embeddings-inference/index).
The selected Candle backends load compatible Safetensors models, not GGUF or ONNX
models. GPU-specific features and model/dtype combinations are not interchangeable
with these native builds; choose a model supported by upstream's Candle backend.

## Install and run

Download from [Releases](https://github.com/miyako/TEI/releases):

| Asset | Contents / consumer |
|---|---|
| `tei-v1.9.4-macos-universal.zip` | Universal `text-embeddings-router`, provenance and upstream license |
| `tei-v1.9.4-windows-x64.zip` | `text-embeddings-router.exe`, provenance and upstream license |
| `SHA256SUMS`, `native-source.json` | Archive integrity and resolved upstream source |
| `TEI.zip`, `TEI.dmg` | Existing 4D component distribution names, unchanged |

The native assets become available **after a successful authorized native release**;
older component releases do not retroactively contain these files. Asset versions
follow the selected upstream release, not the component's independent `20.x` version.
Native release tags are `native-vX.Y.Z-<12-character builder commit>` and do **not**
replace GitHub's latest component release (used by 4D dependency consumers).

Verify the archive before extraction: `shasum -a 256 -c SHA256SUMS` on macOS, or
`Get-FileHash .\tei-v1.9.4-windows-x64.zip -Algorithm SHA256` on Windows and compare
with `SHA256SUMS`. The checksum file lists both archives; download both to check all
entries, or check only the line for the archive you downloaded.

Extract the standalone archive into a directory of your choice. On macOS:

```sh
chmod +x ./text-embeddings-router
./text-embeddings-router --version
./text-embeddings-router --model-id sentence-transformers/all-MiniLM-L6-v2 \
  --hostname 127.0.0.1 --port 8080 --dtype float32
```

In PowerShell:

```powershell
.\text-embeddings-router.exe --model-id sentence-transformers/all-MiniLM-L6-v2 `
  --hostname 127.0.0.1 --port 8080 --dtype float32
```

The first start downloads model files from Hugging Face; allow disk space, memory
and network access. For offline use, supply a local model directory containing the
complete compatible model/tokenizer/configuration. Use `HF_TOKEN` in the environment
for gated models; do not put tokens in source control. The explicit loopback bind
avoids exposing the server on the network.

```sh
curl --fail http://127.0.0.1:8080/health
curl --fail http://127.0.0.1:8080/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"sentence-transformers/all-MiniLM-L6-v2","input":"The quick brown fox."}'
```

Standalone Mac binaries are **ad-hoc signed, not Developer ID signed or notarized**;
Gatekeeper may block downloaded executables. Follow your organization's approval
policy; do not disable Gatekeeper globally. The component Publish workflow requires
Developer ID signing and an **Accepted** Apple notarization result.
Component publication preserves Apple's submission response and detailed issue
log as the `component-notarization` Actions artifact even when Apple rejects the
image. A locally valid signature alone does not establish notarization acceptance.

For 4D, install `TEI.zip` using the existing component/dependency mechanism. Its
resource paths remain `TEI.4dbase/Resources/bin/macOS/text-embeddings-router` and
`TEI.4dbase/Resources/bin/Windows/text-embeddings-router.exe`. To replace a server
manually, copy the matching archive's contents into the corresponding `Resources/bin`
platform directory; keep the provenance and license alongside the executable.
The checked-in historical binaries are not replaced by running CI: Publish overlays
fresh artifacts before compiling the component. Merely downloading this repository's
source ZIP is **not** an installation of the newly built server.

## Build and publish

[Build native CLI](.github/workflows/build-native.yml) builds on pull requests and
relevant pushes, and can be dispatched manually. Its `source` input accepts:
`pinned` (default), `latest` (latest stable published upstream release), or a published
stable `vX.Y.Z` tag. Branches, arbitrary commits and prereleases are rejected. The
resolver freezes the commit and exact upstream toolchain once, then shares that
resolution across every job. A newer release still has to pass the complete matrix;
resolution alone does not assert compatibility. To adopt a newer default, update
`native-source.json` from the resolved record and review the build results.

By default this workflow **only uploads Actions artifacts**, including
`native-packages` and `native-component`. To publish standalone ZIPs, an authorized
maintainer must explicitly dispatch [Publish native CLI](.github/workflows/publish-native.yml)
on `main` with the desired `source`. It calls the same read-only build workflow. All three
native builds and universal assembly must succeed first. Releases are uploaded as
drafts and exposed only after all assets have been uploaded. Reusing an existing
release tag fails rather than silently replacing assets.

[Publish](.github/workflows/publish.yml) retains its existing component-source push
triggers and manual patch/minor/major and self-hosted options; resource changes also
trigger it. It calls the native workflow with the **pinned** source, downloads the
complete resource artifact, builds the 4D component, signs its Mac server, notarizes
the DMG, and publishes `TEI.zip` / `TEI.dmg`. Apple signing/notarization secrets and
the existing tool4d setup are required. Self-hosted mode applies to component
compilation/signing only; native source builds still run on the hosted matrix.
Concurrent component publications are serialized. Publication refuses a stale
`main` checkout instead of rebasing onto source that was not built; a concurrent
push later in the run causes the version push to fail, not overwrite newer commits.
Only `package.json` is committed, after successful packaging; binaries are not
committed and no separate workflow dispatch token is required.

Native jobs have read-only repository permissions; only publication jobs have
`contents: write`. Standalone releases never dispatch component publication and use
a separate tag namespace. No workflow publishes from a pull request.

Every native archive includes `build-info.json`: upstream tag/SHA/toolchain, builder
commit, Actions run ID, target/features/flags, Cargo.lock hash, dependency inspection
and binary/build-script hashes. The upstream `Cargo.lock` is included in each ZIP.
Mac assembly changes the binary hash through `lipo` and ad-hoc
signing, so the manifest records both slice and packaged hashes. Component signing
updates the packaged hash again. `UPSTREAM-LICENSE` is upstream's Apache-2.0 license;
this repository's component code remains under [MIT](LICENSE).

### Local source build

Use Python 3.12+, Git, GitHub CLI (authenticated for the resolver), Rust/rustup,
CMake and a native C/C++ toolchain. macOS requires full Xcode with Metal tools and
command-line tools selected. Windows requires Visual Studio **2022** C++ build
tools, the Windows SDK, NASM on `PATH`, and an x64 Developer PowerShell (the CI pins
`windows-2022`; it does not depend on VS 2026). Protobuf is only needed if adding
gRPC, which these builds disable. The HTTP/Candle build does not require OpenSSL
on Mac or Windows; TLS uses OS libraries and statically built Rust dependencies.

```sh
python3 scripts/native.py resolve --source pinned --output resolved-source.json
git clone --branch v1.9.4 https://github.com/huggingface/text-embeddings-inference.git upstream
git -C upstream checkout --detach e80ef225ed0e6cb1717ce632a6a84b6cf211bb67
rustup toolchain install 1.92.0 --profile minimal
python3 scripts/native.py build --source-dir upstream --target aarch64-apple-darwin \
  --resolved resolved-source.json --output arm64-slice
```

Use the corresponding target from the table on **each native host**; cross-built
slices are deliberately rejected because they cannot be smoke-tested there.
The script selects the exact router package/binary with `--no-default-features`,
sets portability flags, runs `--version` / `--help`, and fails on unexpected runtime
dependencies. It refuses to reuse an output folder. To assemble, collect the three
slice folders under a directory named by their exact target triples, then on an
Apple Silicon Mac run:

```sh
python3 scripts/native.py assemble --slices slices --resolved resolved-source.json --output dist
python3 -m unittest discover -s scripts -p 'test_*.py'
actionlint .github/workflows/build-native.yml .github/workflows/publish-native.yml .github/workflows/publish.yml
```

Model inference, memory/performance benchmarks and Apple notarization require
separate runtime/credentialed checks; CLI smoke tests do not prove model quality.

## Follow-up proposals (not implemented)

* **Correct File-valued server arguments:** [`_server.4dm`](TEI/Project/Sources/Classes/_server.4dm)
  tests `$arg.value` as a `4D.File` but serializes `$option.model` instead. Use the
  actual argument value and cover paths containing spaces on both operating systems.
* **Make callback/stream options explicit:** the same class forwards arbitrary
  options to the CLI and references `$isStream` without declaring it there.
  Separate wrapper-only callbacks from server arguments and add generated-command
  tests before changing existing 4D behavior.
* **Add a small-model integration gate:** start the built server against a pinned
  model revision and test `/health`, `/info`, `/v1/embeddings` dimensions and
  invalid-input responses on all native backends. Current CI deliberately tests
  CLI/dependency contracts without downloading a model. Upstream v1.9.4 has no
  `/v1/models` route; a compatibility adapter would be a separate feature.
* **Add standalone Developer ID notarization and dependency SBOMs:** standalone
  archives currently use ad-hoc signing and record the lock hash, but do not claim
  notarization or provide a complete third-party license inventory.

Related fixes implemented here: fresh source builds replace stale-resource
publication, corrected resource triggers, portable CPU flags, strict dependency
checks, isolated release tags, serialized versioning, and fail-closed signing and
notarization (rather than the former helper's `continue-on-error` signing step).
