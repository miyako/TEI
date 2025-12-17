var $TEI : cs:C1710.TEI

If (False:C215)
	$TEI:=cs:C1710.TEI.new()  //default
Else 
	var $homeFolder : 4D:C1709.Folder
	$homeFolder:=Folder:C1567(fk home folder:K87:24).folder(".TEI")
	var $file : 4D:C1709.File
	var $URL : Text
	var $port : Integer
	
	var $event : cs:C1710.TEIEvent
	$event:=cs:C1710.TEIEvent.new()
/*
Function onError($params : Object; $error : cs._error)
Function onSuccess($params : Object; $models : cs._models)
*/
	$event.onError:=Formula:C1597(ALERT:C41($2.message))
	$event.onSuccess:=Formula:C1597(ALERT:C41($2.models.extract("name").join(",")+" loaded!"))
	$event.onData:=Formula:C1597(onData)  //onData@4D.HTTPRequest
	$event.onResponse:=Formula:C1597(onResponse)  //onResponse@4D.HTTPRequest
	
/*
embeddings
*/
	
	$folder:=$homeFolder.folder("answerdotai/ModernBERT-base")
	$URL:="answerdotai/ModernBERT-base"
	
	$folder:=$homeFolder.folder("nomic-ai/modernbert-embed-base")
	$URL:="nomic-ai/modernbert-embed-base"
	
	If (False:C215)  //Hugging Face mode (recommended)
		$folder:=$homeFolder.folder("dangvantuan/sentence-camembert-base")
		$URL:="dangvantuan/sentence-camembert-base"
	Else   //HTTP mode
		$folder:=$homeFolder.folder("dangvantuan/sentence-camembert-base")
		$URL:="dangvantuan/sentence-camembert-base"
	End if 
	
	$port:=8080
	$TEI:=cs:C1710.TEI.new($port; $folder; $URL; {\
		max_concurrent_requests: 512}; $event)
	
End if 