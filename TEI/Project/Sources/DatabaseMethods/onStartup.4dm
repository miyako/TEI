var $TEI : cs:C1710.TEI

If (False:C215)
	$TEI:=cs:C1710.TEI.new()  //default
Else 
	var $homeFolder : 4D:C1709.Folder
	$homeFolder:=Folder:C1567(fk home folder:K87:24).folder(".TEI")
	var $file : 4D:C1709.File
	var $URL : Text
	var $port : Integer
	
	var $event : cs:C1710.event.event
	$event:=cs:C1710.event.event.new()
/*
Function onError($params : Object; $error : cs.event.error)
Function onSuccess($params : Object; $models : cs.event.models)
Function onData($request : 4D.HTTPRequest; $event : Object)
Function onResponse($request : 4D.HTTPRequest; $event : Object)
Function onTerminate($worker : 4D.SystemWorker; $params : Object)
Function onStdOut($worker : 4D.SystemWorker; $params : Object)
Function onStdErr($worker : 4D.SystemWorker; $params : Object)
*/
	
	$event.onError:=Formula:C1597(ALERT:C41($2.message))
	$event.onSuccess:=Formula:C1597(ALERT:C41($2.models.extract("name").join(",")+" loaded!"))
	$event.onData:=Formula:C1597(LOG EVENT:C667(Into 4D debug message:K38:5; "download:"+String:C10((This:C1470.range.end/This:C1470.range.length)*100; "###.00%")))
	$event.onResponse:=Formula:C1597(LOG EVENT:C667(Into 4D debug message:K38:5; "download complete"))
	$event.onStdOut:=Formula:C1597(LOG EVENT:C667(Into 4D debug message:K38:5; "out:"+$2.data))
	$event.onStdErr:=Formula:C1597(LOG EVENT:C667(Into 4D debug message:K38:5; "err:"+$2.data))
	$event.onTerminate:=Formula:C1597(LOG EVENT:C667(Into 4D debug message:K38:5; (["process"; $1.pid; "terminated!"].join(" "))))
	
/*
embeddings
*/
	
	If (False:C215)  //Hugging Face mode (recommended)
		$folder:=$homeFolder.folder("dangvantuan/sentence-camembert-base")
		$URL:="dangvantuan/sentence-camembert-base"
	Else   //HTTP mode (must be .zip)
		$folder:=$homeFolder.folder("dangvantuan/sentence-camembert-base")
		$URL:="https://github.com/miyako/TEI/releases/download/models/sentence-camembert-base.zip"
	End if 
	
	$port:=8085
	$TEI:=cs:C1710.TEI.new($port; $folder; $URL; {\
		max_concurrent_requests: 512}; $event)
	
End if 