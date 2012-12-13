// Copyright (c) 2007-2009 The PyAMF Project.
// See LICENSE.txt for details.

import mx.remoting.Service;
import mx.rpc.RelayResponder;
import mx.rpc.FaultEvent;
import mx.rpc.ResultEvent;
import mx.remoting.PendingCall;

// Create service object to access the remote service called 'echo'
service = new Service( "http://localhost:8000", null, "echo", null, null );

// This var holds the data we want to pass to the remote service.
var param = "Hello World!";

// Call remote service to fetch data and receive PendingCall object in return
var pc:PendingCall = service.echo( param );

// Set responder property to the object and methods that will receive the 
// result or fault condition that the service returns.
pc.responder = new RelayResponder( this, "onResult", "onFault" );

// Result handler method 
function onResult( re:ResultEvent ): Void {
	myData = re.result;
	trace( myData ); // prints "Hello World!"
	status_txt.text = myData;
}

// Fault handler method displays error message 
function onFault( fault:FaultEvent ): Void {
	// Notify the user of the problem
	status_txt.text = "Remoting error: \n";
	for ( var d in fault.fault ) {
		status_txt.text += fault.fault[d] + "\n";
	}
}
