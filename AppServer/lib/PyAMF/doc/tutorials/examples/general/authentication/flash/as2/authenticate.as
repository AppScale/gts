// Authentication with setCredentials example.

// Imports the Remoting classes
import mx.remoting.Service;
import mx.rpc.RelayResponder;
import mx.rpc.FaultEvent;
import mx.rpc.ResultEvent;
import mx.remoting.PendingCall;

// These vars hols the data we want to pass to the remote service.
var a = 1;
var b = 2;
	
// Create service object to access the remote service called 'calc'
var service = new Service( "http://localhost:8000", null, "calc", null, null );

// Submit button click handler
submit_btn.onRelease = function () {
	login();
}

// Login
function login() {
	
	var username:String = username_txt.text;
	var password:String = password_txt.text;
	
	// Add authentication
	service.connection.setCredentials(username, password);

	// Call remote method 'sum' to fetch data and receive PendingCall object in return
	var pc:PendingCall = service.sum( a, b );
	
	// Set responder property to the object and methods that will receive the 
	// result or fault condition that the service returns.
	pc.responder = new RelayResponder( this, "onResult", "onFault" );
}

// Result handler method 
function onResult( re:ResultEvent ): Void {
	myData = re.result;
	trace( myData ); // prints "3"
	status_txt.text = a +"+"+ b + "=" + myData;
}

// Fault handler method displays error message 
function onFault( fault:FaultEvent ): Void {
	// Notify the user of the problem
	status_txt.text = "Remoting error:";
	for ( var d in fault.fault ) {
		status_txt.text += fault.fault[d] + "\n";
	}
}
