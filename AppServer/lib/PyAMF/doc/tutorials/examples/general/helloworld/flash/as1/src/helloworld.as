/* Hello World example client for Actionscript 1.0 that can
   be used with the PyAMF helloworld server.
   See http://pyamf.org/wiki/HelloWorld/AS1 for more info. */

// Imports the NetServices ActionScript file
#include "NetServices.as"

// Create the connection to the remote service
if ( inited == null ) {
	inited = true;
	// Setup connection
	NetServices.setDefaultGatewayURL("http://localhost:8000");
	gateway = NetServices.createGatewayConnection();
	
	// Create service objects to access the remote service called 'echo'
	service = gateway.getService("echo", this);
	
	// This var holds the data we want to pass to the remote service.
	var param = "Hello World!";
	
	// Call remote service method called "echo" to fetch data
	service.echo( param );
}

// If the service function is successful, the _Result function of the same name executes 
function echo_Result( result ) {
	trace( result ); // prints "Hello World!"
	status_txt.text = result;
}

// If the service function is unsucessful, the _Status function of the same name executes
function echo_Status( error ) {
	// Notify the user of the problem
	status_txt.text = "Remoting error: \n";
	for (var d in error) {
		status_txt.text += error[d] + "\n";
	}
}