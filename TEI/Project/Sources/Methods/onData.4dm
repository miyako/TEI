//%attributes = {"invisible":true,"preemptive":"capable"}
#DECLARE($request : 4D:C1709.HTTPRequest; $event : Object)

//var $size; $total : Real
//$size:=This.range.end
//$total:=This.range.length
//var $progress : Real
//$progress:=$size/$total

MESSAGE:C88(String:C10((This:C1470.range.end/This:C1470.range.length)*100; "###.00%"))