property embedding_model : 4D:C1709.Folder
property _started : Boolean

Class extends _models

Class constructor($port : Integer; $huggingfaces : cs:C1710.event.huggingfaces; $options : Object; $formula : 4D:C1709.Function; $event : cs:C1710.event.event)
	
	Super:C1705($port; $huggingfaces; $options; $formula; $event)
	
	If (Not:C34(This:C1470.offline))
		This:C1470.download()
	End if 
	
Function models() : cs:C1710.event.models
	
	var $models : Collection
	$models:=[]
	
	var $_model : Text
	For each ($_model; This:C1470._models)
		$models.push(cs:C1710.event.model.new($_model; True:C214))
	End for each 
	
	return cs:C1710.event.models.new($models)
	
Function onDownload($oid : Text)
	
	var $downloaded : cs:C1710.event.huggingface
	$downloaded:=This:C1470.files.query("oid == :1"; $oid).first()
	
	If ($downloaded#Null:C1517)
		var $model : Object
		//the destination folder is the model root even when the file is in a subfolder (e.g. 1_Pooling/config.json)
		$model:=$downloaded.folder
		
		Case of 
			: (This:C1470.options.embedding_model=Null:C1517)
				This:C1470.options.embedding_model:=$model
		End case 
	End if 
	
	Super:C1706.onDownload($oid)
	
Function _selectFiles($files : Collection) : Collection
	
	//the candle backend loads safetensors (or pytorch_model.bin as a fallback); skip other formats
	var $excluded : Collection
	$excluded:=[".onnx"; ".onnx_data"; ".h5"; ".msgpack"; ".ot"; ".tflite"; ".mlmodel"; ".gguf"]
	var $hasSafetensors : Boolean
	$hasSafetensors:=$files.query("path in :1"; ["model.safetensors"; "model.safetensors.index.json"]).length#0
	var $selected : Collection
	$selected:=[]
	var $file : Object
	var $path : Text
	ARRAY LONGINT:C221($pos; 0)
	ARRAY LONGINT:C221($len; 0)
	For each ($file; $files)
		$path:=String:C10($file.path)
		If (["onnx"; "openvino"; "coreml"].includes(Split string:C1554($path; "/").first()))
			continue
		End if 
		If (Match regex:C1019("\\.[^./]+$"; $path; 1; $pos; $len))
			If ($excluded.includes(Substring:C12($path; $pos{0}; $len{0})))
				continue
			End if 
		End if 
		If ($hasSafetensors) && (Position:C15("pytorch_model"; $path)=1)
			continue
		End if 
		$selected.push($file)
	End for each 
	return $selected
	
Function start()
	
	If (This:C1470._started)
		return 
	End if 
	//text-embeddings-router needs --model-id: a local model folder
	If (Not:C34(OB Instance of:C1731(This:C1470.options.embedding_model; 4D:C1709.Folder))) || (Not:C34(This:C1470.options.embedding_model.exists))
		var $message : Text
		$message:="no model to load: options.embedding_model is not an existing folder"
		If (OB Instance of:C1731(This:C1470.options.embedding_model; 4D:C1709.Folder)) || (OB Instance of:C1731(This:C1470.options.embedding_model; 4D:C1709.File))
			$message+=": "+This:C1470.options.embedding_model.path
		End if 
		LOG EVENT:C667(Into 4D debug message:K38:5; "TEI: "+$message)
		If (This:C1470.event#Null:C1517) && (OB Instance of:C1731(This:C1470.event; cs:C1710.event.event))
			This:C1470.event.onError.call(This:C1470; This:C1470.options; cs:C1710.event.error.new(2; $message; This:C1470.models()))
		End if 
		return 
	End if 
	This:C1470._started:=True:C214
	var $TEI : cs:C1710.workers.worker
	$TEI:=cs:C1710.workers.worker.new(cs:C1710._server)
	$TEI.start(This:C1470.options.port; This:C1470.options)
	
	If (This:C1470.event#Null:C1517) && (OB Instance of:C1731(This:C1470.event; cs:C1710.event.event))
		This:C1470.event.onSuccess.call(This:C1470; This:C1470.options; This:C1470.models())
	End if 