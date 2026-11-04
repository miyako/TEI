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
		$model:=OB Instance of:C1731($downloaded.folder; 4D:C1709.Folder)\
			 ? $downloaded.folder.folder($downloaded.path).parent : $downloaded.folder
		
		Case of 
			: (This:C1470.options.embedding_model=Null:C1517)
				This:C1470.options.embedding_model:=$model
		End case 
	End if 
	
	Super:C1706.onDownload($oid)
	
Function _onNothingToDownload()
	
	If (OB Instance of:C1731(This:C1470.options.embedding_model; 4D:C1709.Folder))
		If (This:C1470.options.embedding_model.exists)
			This:C1470.start()
			return 
		End if 
	End if 
	var $message : Text
	$message:="no model to load: nothing to download and options.embedding_model is not an existing folder"
	If (OB Instance of:C1731(This:C1470.options.embedding_model; 4D:C1709.Folder)) || (OB Instance of:C1731(This:C1470.options.embedding_model; 4D:C1709.File))
		$message+=": "+This:C1470.options.embedding_model.path
	End if 
	LOG EVENT:C667(Into 4D debug message:K38:5; "TEI: "+$message)
	If (This:C1470.event#Null:C1517) && (OB Instance of:C1731(This:C1470.event; cs:C1710.event.event))
		This:C1470.event.onError.call(This:C1470; This:C1470.options; cs:C1710.event.error.new(2; $message; cs:C1710.event.models.new()))
	End if 
	
Function start()
	
	If (This:C1470._started)
		return 
	End if 
	This:C1470._started:=True:C214
	var $TEI : cs:C1710.workers.worker
	$TEI:=cs:C1710.workers.worker.new(cs:C1710._server)
	$TEI.start(This:C1470.options.port; This:C1470.options)
	
	If (This:C1470.event#Null:C1517) && (OB Instance of:C1731(This:C1470.event; cs:C1710.event.event))
		This:C1470.event.onSuccess.call(This:C1470; This:C1470.options; This:C1470.models())
	End if 