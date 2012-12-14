package org.pyamf.examples.guestbook
{
	/**
	 * Copyright (c) 2007-2009 The PyAMF Project.
	 * See LICENSE.txt for details.
	*/

	import flash.events.NetStatusEvent;
	import flash.events.SecurityErrorEvent;
	import flash.net.NetConnection;
	import flash.net.Responder;
	
	import mx.collections.ArrayCollection;
	import mx.core.Application;
	import mx.events.FlexEvent;
	
	import org.pyamf.examples.guestbook.components.SubmitBox;
	import org.pyamf.examples.guestbook.events.SubmitEvent;
	import org.pyamf.examples.guestbook.vo.Message;
	
	/**
	 * Simple guestbook using PyAMF, Twisted and Flash.
	 * 
	 * @since 0.3.0
	 */
	public class GuestbookExample extends Application
	{
		private var _gateway		: NetConnection;
		
		[Bindable]
		public var messages			: ArrayCollection;
		
		[Bindable]
		public var totalMessages	: String = "Loading...";
		
		[Bindable]
		public var loading			: Boolean = true;
		
		public var submit			: SubmitBox;

		public function GuestbookExample()
		{
			super();
			
			addEventListener( FlexEvent.APPLICATION_COMPLETE, onInitApp );
		}
		
		private function onInitApp( event:FlexEvent ): void
		{
			// setup connection
            _gateway = new NetConnection();
			_gateway.addEventListener( NetStatusEvent.NET_STATUS, 			onStatus );
			_gateway.addEventListener( SecurityErrorEvent.SECURITY_ERROR, 	onError );
			
            // Connect to gateway
            _gateway.connect( "http://localhost:8080/gateway" );
            
            // Set responder property to the object and methods that will receive the 
            // result or fault condition that the service returns.
            var responder:Responder = new Responder( onLoadResult, onFault );
            
            // Call remote service to fetch data
            _gateway.call( "guestbook.getMessages", responder);
		}
		
		public function addMessage( event:SubmitEvent ): void
		{
			var message:Message = event.message;
			loading = true;
			
            // set responder property to the object and methods that will receive the 
            // result or fault condition that the service returns.
            var responder:Responder = new Responder( onSaveResult, onFault );
            
            // call remote service to save guestbook message.
            _gateway.call( "guestbook.addMessage", responder, new ObjectProxy(event.message) );
            
            // wait for result.
            totalMessages = "Saving message...";
		}
		
		private function onLoadResult( result:* ): void
        {
        	loading = false;
        	
        	// update list
           	messages = result;
           	totalMessages = "Loaded " + messages.length + " message(s).";
        }
        
        private function onSaveResult( result:* ): void
        {
            var message:Message = result;
            
            loading = false;
            
            // add message to list
            messages.addItemAt( message, 0 );
            totalMessages = "Loaded " + messages.length + " message(s).";
        }
        
        private function onStatus( event:NetStatusEvent ): void
		{
                        submit.status = event.info.description + "!";
		}
		
		private function onError( event:* ): void
		{
              		submit.status = event.error + "!";

		}
		
        private function onFault( error:* ): void
        {
            // notify the user of the problem
            //trace("Remoting error:");
            for ( var d:String in error ) {
               //trace("   " + d + ": " + error[d]);
            }
            
            totalMessages = "Loaded " + messages.length + " message(s).";
            
            if ( error.fault.description != null ) {
            	submit.status = error.fault.description + "!";
            } else {
            	submit.status = error + "!";
            }
        }
		
	}
}
