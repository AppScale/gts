package 
{
	// Copyright (c) 2007-2009 The PyAMF Project.
	// See LICENSE.txt for details.

	import flash.events.MouseEvent;
	import flash.display.SimpleButton;
	import flash.display.MovieClip;
	import flash.text.TextField;
	import flash.net.NetConnection;
	import flash.net.Responder;

	public class Authentication extends MovieClip 
	{	
		// These vars hols the data we want to pass to the remote service.
		private var a:int = 1;
		private var b:int = 2;
		
		// Gateway connection object
		private var gateway:NetConnection;

		public function Authentication() 
		{
			submit_btn.addEventListener( "click", login );
		}

		private function login( event:MouseEvent ): void 
		{
			var username:String = username_txt.text;
			var pass:String = password_txt.text;
			
			// Setup connection
			gateway = new NetConnection();

			// Connect to gateway
			gateway.connect( "http://localhost:8000" );

			// Authentication
			gateway.addHeader( "Credentials", false, {userid: username, password: pass} );
			
			// Set responder property to the object and methods that will receive the 
			// result or fault condition that the service returns.
			var responder:Responder = new Responder( onResult, onFault );

			// Call remote service.method 'calc.sum' to fetch data
			gateway.call( "calc.sum", responder, a, b );
		}
		
		// Result handler method 
		private function onResult( result:Object ): void 
		{
			var myData:String = result.toString();
			trace( result );// prints "3"
			status_txt.text = a +"+"+ b + "=" + myData;
		}
		
		// Fault handler method displays error message 
		private function onFault( error:Object ): void 
		{
			// Notify the user of the problem
			status_txt.text = "Remoting error: ";
			for ( var d:String in error ) {
				status_txt.appendText( error[d] + "\n" );
			}
		}

	}
}