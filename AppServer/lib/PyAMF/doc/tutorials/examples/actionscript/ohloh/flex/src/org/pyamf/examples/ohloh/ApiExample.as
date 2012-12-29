package org.pyamf.examples.ohloh
{
	/**
	 * Copyright (c) 2007-2009 The PyAMF Project.
	 * See LICENSE.txt for details.
	*/
	
	import flash.events.Event;
	import flash.events.EventDispatcher;
	import flash.events.NetStatusEvent;
	import flash.net.NetConnection;
	import flash.net.Responder;
	
	import mx.controls.Alert;
	import mx.utils.ObjectUtil;
	
	[Event(name="response", type="flash.events.Event")]
	[Event(name="error", type="flash.events.Event")]
	/**
	 * This is an example of using the Ohloh API from Actionscript 3.0.
     * Detailed information can be found at the Ohloh website:
     * http://www.ohloh.net/api
     * 
     * This examples retrieves a account and shows the profile associated.
	 */	
	public class ApiExample extends EventDispatcher
	{
		public static const RESPONSE:	String = "response";
		public static const ERROR:		String = "error";
		
		private var userEmail: 			String;
		private var gateway:			NetConnection;
		
		public var info:				XMLList;
		
		public function ApiExample( userEmail:String )
		{
			super();
			
			this.userEmail = userEmail;
		}
		
		public function connect( host:String ):void
	    {
	    	gateway = new NetConnection();
	    	gateway.addEventListener( NetStatusEvent.NET_STATUS, onFault );
	    	gateway.connect(host);
	    	
	    	var responder:Responder = new Responder( onResult, onFault );
	    	gateway.call( 'ohloh.account', responder, userEmail );
	    }
	    
	    private function onFault( event:* ):void
	    {
	    	Alert.show( ObjectUtil.toString(event), 'Remoting Error' );
	    	
	    	dispatchEvent( new Event(ERROR) );
	    }
	    
	    private function onResult(event:*):void
	    {
			info = new XMLList(event).result.account;
			
	    	dispatchEvent( new Event(RESPONSE) );
	    }
	    
	}
}