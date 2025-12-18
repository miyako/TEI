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

TEI is the industry standard for serving embeddings in the Hugging Face ecosystem and is widely deployed in enterprise RAG stacks. It expects NVIDIA GPUs and aims to process thousands of concurrent requests per second.

**Note**: The component's CLI is compiled with Metal support for Apple Silicon and CPU-only settings for Windows and Mac Intel.

For 4D developers looking for a local LLM engine to support semantic search, TEI might be an overkill. Unlike llama.cpp which expects weights in quantised custom GGUF format, TEI works with full precision weights. 4D memory consumption may jump up while loading the model before returning to regular levels.

#### Usage

Instantiate `cs.TEI.TEI` in your *On Startup* database method:

```4d
var $TEI : cs.TEI.TEI

If (False)
    $TEI:=cs.TEI.TEI.new()  //default
Else 
    var $homeFolder : 4D.Folder
    $homeFolder:=Folder(fk home folder).folder(".TEI")
    var $file : 4D.File
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
        Function onStdOut($worker : 4D.SystemWorker; $params : Object)
        Function onStdErr($worker : 4D.SystemWorker; $params : Object)
    */
    
    $event.onError:=Formula(ALERT($2.message))
    $event.onSuccess:=Formula(ALERT($2.models.extract("name").join(",")+" loaded!"))
    $event.onData:=Formula(LOG EVENT(Into 4D debug message; "download:"+String((This.range.end/This.range.length)*100; "###.00%")))
    $event.onResponse:=Formula(LOG EVENT(Into 4D debug message; "download complete"))
    $event.onStdOut:=Formula(LOG EVENT(Into 4D debug message; "out:"+$2.data))
    $event.onStdErr:=Formula(LOG EVENT(Into 4D debug message; "err:"+$2.data))
    $event.onTerminate:=Formula(LOG EVENT(Into 4D debug message; (["process"; $1.pid; "terminated!"].join(" "))))
    
    /*
        embeddings
    */
    
    If (False)  //Hugging Face mode (recommended)
        $folder:=$homeFolder.folder("dangvantuan/sentence-camembert-base")
        $URL:="dangvantuan/sentence-camembert-base"
    Else   //HTTP mode (must be .zip)
        $folder:=$homeFolder.folder("dangvantuan/sentence-camembert-base")
        $URL:="https://github.com/miyako/TEI/releases/download/models/sentence-camembert-base.zip"
    End if 
    
    $port:=8085
    $TEI:=cs.TEI.TEI.new($port; $folder; $URL; {\
    max_concurrent_requests: 512}; $event)
    
End if  
```

Unless the server is already running (in which case the costructor does nothing), the following procedure runs in the background:

1. The specified model is downloaded via HTTP
2. The `text-embeddings-router` program is started

Now you can test the server:

```
curl -X POST http://127.0.0.1:8080/v1/embeddings \
     -H "Content-Type: application/json" \
     -d '{"input":"The quick brown fox jumps over the lazy dog."}'
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
var $llama : cs.TEI.TEI
$llama:=cs.TEI.TEI.new()
$llama.terminate()
```

#### AI Kit compatibility

The API is compatibile with [Open AI](https://platform.openai.com/docs/api-reference/embeddings). 

|Class|API|Availability|
|-|-|:-:|
|Models|`/v1/models`|✅|
|Chat|`/v1/chat/completions`||
|Images|`/v1/images/generations`||
|Moderations|`/v1/moderations`||
|Embeddings|`/v1/embeddings`|✅|
|Files|`/v1/files`||
