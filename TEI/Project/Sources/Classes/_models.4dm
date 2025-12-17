property models : Collection

Class constructor($models : Collection)
	
	This:C1470.models:=[]
	var $model : Object
	For each ($model; $models)
		If (OB Instance of:C1731($model; cs:C1710._model))
			This:C1470.models.push($model)
		End if 
	End for each 