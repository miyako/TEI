---
layout: default
---

![version](https://img.shields.io/badge/version-20%2B-E23089)
![platform](https://img.shields.io/static/v1?label=platform&message=mac-intel%20|%20mac-arm%20|%20win-64&color=blue)
[![license](https://img.shields.io/github/license/miyako/TEI)](LICENSE)
![downloads](https://img.shields.io/github/downloads/miyako/TEI/total)

# Use Text Embeddings Inference from 4D

#### Abstract

[Text Embeddings Inference](https://github.com/huggingface/text-embeddings-inference) is a high-performance extraction framework and server that supports a wide variety of embedding models such as Nomic, BERT, CamemBERT, XLM-RoBERTa models with absolute positions; JinaBERT model with Alibi positions; Mistral, Alibaba GTE, Qwen2 models with Rope positions; MPNet, ModernBERT, Qwen3, and Gemma3.

TEI supports native Metal and CPU backends as well as upstream GPU deployments.
This component does not require an NVIDIA GPU.

## Native server distributions

The source build defaults to upstream **v1.9.4**, commit
[`e80ef225ed0e6cb1717ce632a6a84b6cf211bb67`](https://github.com/huggingface/text-embeddings-inference/commit/e80ef225ed0e6cb1717ce632a6a84b6cf211bb67),
with upstream Rust **1.92.0** and locked Cargo dependencies. These are build targets;
publication requires all native jobs to pass, not just a successful source resolution.

| Platform | Backend | Native release asset |
|---|---|---|
| Apple Silicon, macOS 14+ | Candle + Metal | `tei-v1.9.4-macos-universal.zip` |
| Intel Mac, macOS 14+ | Candle + Accelerate CPU | Same universal ZIP |
| Windows 10/11 x64 | Candle CPU, static MSVC CRT | `tei-v1.9.4-windows-x64.zip` |

Linux, Windows ARM64, CUDA/ROCm, ONNX Runtime, Python and gRPC are not packaged here.
These builds load compatible Safetensors models, not GGUF or ONNX model files.
No non-system runtime DLLs or Homebrew libraries are permitted by the packaging checks.

Install the 4D component from `TEI.zip` or `TEI.dmg` on the
[Releases page](https://github.com/miyako/TEI/releases). These component asset names
and resource paths remain unchanged. Standalone native ZIPs appear only after a
successful authorized native publication; existing older releases are not rebuilt
retroactively. Standalone tags use `native-vX.Y.Z-<builder commit>` and do not replace
the latest `20.x` component release used by dependency consumers.

Verify the archive against the release's `SHA256SUMS`, then extract it. Each ZIP
contains the actual `text-embeddings-router` (or `.exe`), `build-info.json` with
source/build provenance, and `UPSTREAM-LICENSE`. Standalone Mac servers are ad-hoc
signed, **not notarized**; Gatekeeper may require approval under your organization's
policy. Component publication instead requires Developer ID signing and Accepted
Apple notarization.

### Standalone usage

On macOS:

```sh
chmod +x ./text-embeddings-router
./text-embeddings-router --model-id sentence-transformers/all-MiniLM-L6-v2 \
  --hostname 127.0.0.1 --port 8080 --dtype float32
```

In PowerShell:

```powershell
.\text-embeddings-router.exe --model-id sentence-transformers/all-MiniLM-L6-v2 `
  --hostname 127.0.0.1 --port 8080 --dtype float32
```

The first start downloads the model from Hugging Face. For offline use, give
`--model-id` a complete compatible local model directory. Use the `HF_TOKEN`
environment variable for gated models. Binding to `127.0.0.1` keeps the server local.

```sh
curl --fail http://127.0.0.1:8080/health
curl --fail http://127.0.0.1:8080/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"sentence-transformers/all-MiniLM-L6-v2","input":"The quick brown fox."}'
```

### Rebuilds and release provenance

The [Build native CLI workflow](https://github.com/miyako/TEI/actions/workflows/build-native.yml)
resolves `pinned`, `latest` stable, or a published `vX.Y.Z` release once to an exact
commit/toolchain, builds on native Apple Silicon, Intel Mac and Windows x64 runners,
checks `--version` / `--help` and runtime dependencies, and combines the Mac slices.
CI does not download a model or claim model-inference coverage. It uploads Actions
artifacts only. Standalone publishing requires an explicit dispatch of
[Publish native CLI](https://github.com/miyako/TEI/actions/workflows/publish-native.yml)
on `main`, which builds the selected source through the same read-only workflow.

The component [Publish workflow](https://github.com/miyako/TEI/actions/workflows/publish.yml)
builds the pinned server from source before compiling the 4D component, rather than
releasing historical checked-in executables. `TEI.4dbase/Resources/bin/macOS` and
`Resources/bin/Windows` still contain the executable names expected by the component.
The [GitHub README](https://github.com/miyako/TEI#build-and-publish) documents local
build prerequisites, exact features/flags, release permissions and unimplemented
bug-fix/feature proposals.

For 4D developers looking for a local LLM engine to support semantic search, TEI might be an overkill. Unlike llama.cpp which expects weights in quantised custom GGUF format, TEI works with full precision weights. The separate server process needs memory for model loading and inference; allow for
startup peaks as well as the model's steady-state working set.

#### Usage

Instantiate `cs.TEI.TEI` in your *On Startup* database method:

```4d
var $TEI : cs.TEI.TEI

If (False)
    $TEI:=cs.TEI.TEI.new()  //default
Else 
    var $homeFolder : 4D.Folder
    $homeFolder:=Folder(fk home folder).folder(".TEI")
    var $URL : Text
    var $port : Integer
    
    var $event : cs.event.event
    $event:=cs.event.event.new()
    /*
        Function onError($params : Object; $error : cs.event.error)
        Function onSuccess($params : Object; $models : cs.event.models)
        Function onData($request : 4D.HTTPRequest; $event : Object)
        Function onResponse($request : 4D.HTTPRequest; $event : Object)
        Function onTerminate($worker : 4D.SystemWorker; $params : Object)
    */
    
    $event.onError:=Formula(ALERT($2.message))
    $event.onSuccess:=Formula(ALERT($2.models.extract("name").join(",")+" loaded!"))
    $event.onData:=Formula(LOG EVENT(Into 4D debug message; This.file.fullName+":"+String((This.range.end/This.range.length)*100; "###.00%")))
    $event.onData:=Formula(MESSAGE(This.file.fullName+":"+String((This.range.end/This.range.length)*100; "###.00%")))
    $event.onResponse:=Formula(LOG EVENT(Into 4D debug message; This.file.fullName+":download complete"))
    $event.onResponse:=Formula(MESSAGE(This.file.fullName+":download complete"))
    $event.onTerminate:=Formula(LOG EVENT(Into 4D debug message; (["process"; $1.pid; "terminated!"].join(" "))))
    
    $port:=8080
    
    $model:=$homeFolder.folder("dangvantuan/sentence-camembert-base")
    $path:=""
    $URL:="dangvantuan/sentence-camembert-base"
    $embedding:=cs.event.huggingface.new($model; $URL; $path; "embedding")
    
    $options:={max_concurrent_requests: 512}
    var $huggingfaces : cs.event.huggingfaces
    $huggingfaces:=cs.event.huggingfaces.new([$embedding])
    
    $TEI:=cs.TEI.TEI.new($port; $huggingfaces; $homeFolder; $options; $event)
    
End if 
```

Unless the server is already running (in which case the constructor does nothing), the following procedure runs in the background:

1. The specified model is downloaded via HTTP
2. The `text-embeddings-router` program is started

Now you can test the server:

```
curl -X POST http://127.0.0.1:8080/v1/embeddings \
     -H "Content-Type: application/json" \
     -d '{"model":"dangvantuan/sentence-camembert-base","input":"The quick brown fox jumps over the lazy dog."}'
```

Or, use AI Kit:

```4d
var $AIClient : cs.AIKit.OpenAI
$AIClient:=cs.AIKit.OpenAI.new()
$AIClient.baseURL:="http://127.0.0.1:8080/v1"

var $text : Text
$text:="The quick brown fox jumps over the lazy dog."

var $responseEmbeddings : cs.AIKit.OpenAIEmbeddingsResult
$responseEmbeddings:=$AIClient.embeddings.create($text)
```

Finally to terminate the server:

```4d
var $TEI : cs.TEI.TEI
$TEI:=cs.TEI.TEI.new()
$TEI.terminate()
```

#### AI Kit compatibility

The API is compatible with [Open AI](https://platform.openai.com/docs/api-reference/embeddings). 

|Class|API|Availability|
|-|-|:-:|
|Models|`/v1/models`||
|Chat|`/v1/chat/completions`||
|Images|`/v1/images/generations`||
|Moderations|`/v1/moderations`||
|Embeddings|`/v1/embeddings`|✅|
|Files|`/v1/files`||

Upstream v1.9.4 exposes model metadata at `/info`, not `/v1/models`. Configure the
model explicitly in clients that would otherwise discover it through that endpoint.
