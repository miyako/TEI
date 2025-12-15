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
Function onSuccess($params : Object)
*/
	$event.onError:=Formula:C1597(ALERT:C41($2.message))
	$event.onSuccess:=Formula:C1597(ALERT:C41(This:C1470.file.name+" loaded!"))
	
/*
embeddings
*/
	
	//3.13 GB
	$folder:=$homeFolder.folder("answerdotai/ModernBERT-base")
	$URL:="answerdotai/ModernBERT-base"
	$port:=8080
	$TEI:=cs:C1710.TEI.new($port; $folder; $URL; {\
		max_concurrent_requests: 512}; $event)
	
End if 