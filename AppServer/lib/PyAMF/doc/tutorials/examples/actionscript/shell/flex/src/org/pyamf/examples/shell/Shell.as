package org.pyamf.examples.shell
{
	/**
	 * Copyright (c) 2007-2009 The PyAMF Project.
	 * See LICENSE.txt for details.
	*/
	
	import flash.events.*;
	import flash.net.NetConnection;
	import flash.net.Responder;
	import flash.ui.Keyboard;
	
	import mx.controls.ComboBox;
	import mx.controls.TextArea;
	import mx.core.Application;
	import mx.events.FlexEvent;
	import mx.utils.URLUtil;

	/**
	 * Interactive Python shell for Flex.
	 * 
	 * @since 0.3.0
	 */	
	public class Shell extends Application
	{
		public var shell_txt	: TextArea;
		public var input_txt	: TextArea;
		public var submitMethod	: ComboBox;
		
		private var gateway		: NetConnection;
		private var submit		: Boolean;
		private var history		: Array = new Array();
		private var cursor		: int = 0;
		
		public function Shell()
		{
			super();
			
			addEventListener( FlexEvent.CREATION_COMPLETE, init );
		}
		
		private function init( event:Event ):void
		{
			// Listener for key stroke detection
			input_txt.addEventListener( KeyboardEvent.KEY_DOWN, inputKeyDownHandler );
			input_txt.addEventListener( KeyboardEvent.KEY_UP, inputKeyUpHandler );

			// setup connection
            gateway = new NetConnection();
			
			// Setup urls
			var host:String;
            var http_port:uint = mx.utils.URLUtil.getPort(this.url);
            var serverName:String = mx.utils.URLUtil.getServerName(this.url);

            if ( serverName.length == 0 || serverName == "localhost" ) {
                serverName = "localhost";
                http_port = 8000;
            }
            
            host = serverName;
            
            if (http_port > 0) {
                host += ":" + http_port.toString();
            }
            
            // Connect to gateway
            gateway.connect( 'http://' + host + '/gateway/shell/' );
            
            // Listeners for remoting errors
            gateway.addEventListener( IOErrorEvent.IO_ERROR, ioErrorHandler );
            gateway.addEventListener( NetStatusEvent.NET_STATUS, netStatusHandler );
            
            // Set responder property to the object and methods that will receive the 
            // result or fault condition that the service returns.
            var responder:Responder = new Responder( onStartupResult, onFault );
            
            // Call remote service to fetch startup data
            gateway.call( "shell.startup", responder );
		}
		
		private function inputKeyDownHandler( event:KeyboardEvent=null ):void
		{
			if ( submitMethod.selectedItem.data == "ctrlenter" &&
				 ( event.keyCode == Keyboard.ENTER && event.ctrlKey )) {
				evalCode();
			}
			
			if ( submitMethod.selectedItem.data == "altenter" &&
				 ( event.keyCode == Keyboard.ENTER && event.altKey )) {
				evalCode();
			}
			
			if ( submitMethod.selectedItem.data == "enter" && event.keyCode == Keyboard.ENTER &&
				 !event.altKey && !event.ctrlKey ) {
				evalCode();
			}
			
			if ( event.ctrlKey && event.keyCode == Keyboard.UP ) {
				changeHistory(Keyboard.UP);
			}
			
			if ( event.ctrlKey && event.keyCode == Keyboard.DOWN ) {
				changeHistory(Keyboard.DOWN);
			}
		}
		
		private function changeHistory( direction:uint ): void
		{
			if ( direction == Keyboard.UP ) {
				if (cursor < history.length ) {
					cursor++;
				}
			} else if ( direction == Keyboard.DOWN ) {
				if (cursor > 0 ) {
					cursor--;
				}
			}
			input_txt.text = history[ history.length - cursor ];
		}
		
		public function inputKeyUpHandler( event:KeyboardEvent=null ):void
		{
			if (submit) {
				input_txt.text = "";
				submit = false;
			}
		}
		
		public function evalCode():void
		{
			// get input text
			var input:String = input_txt.text;
			
			// Set responder property to the object and methods that will receive the 
            // result or fault condition that the service returns.
            var responder:Responder = new Responder( onEvalCodeResult, onFault );
            
            // Call remote service to evalute script and return result
            gateway.call( "shell.evalCode", responder, input );
            
            // Add to history
            history.push( input );
            cursor = 0;
            submit = true;
		}
		
		// Reset to start text
		public function clear():void
		{
			// Set responder property to the object and methods that will receive the 
            // result or fault condition that the service returns.
            var responder:Responder = new Responder( onStartupResult, onFault );
            
            // Call remote service to fetch startup data
            gateway.call( "shell.startup", responder );
		}
		
		private function onStartupResult( result:* ): void
        {
        	shell_txt.text = result;
        }
        
        private function onEvalCodeResult( result:* ): void
        {
            if (result == null)
                return;
        	shell_txt.text += result;
        }
        
        private function onFault( error:* ): void
        {
            // notify the user of the problem
            shell_txt.text = "Remoting error: \n";
            for ( var d:String in error ) {
               shell_txt.text += error[d] + "\n";
            }
        }
		
		private function netStatusHandler( event:NetStatusEvent ):void
		{
			if ( event.info.level == "error" )
			{
				// notify the user of the problem
                shell_txt.text = "Remoting error: \n";
                for ( var d:String in event.info ) {
                   shell_txt.text += event.info[d] + "\n";
                }
			}
		}
		
		private function ioErrorHandler( error:IOErrorEvent ):void
		{
			// notify the user of the problem
            shell_txt.text = "IO error: \n";
            for ( var d:String in error ) {
               shell_txt.text += error[d] + "\n";
            }
			shell_txt.verticalScrollPosition = shell_txt.maxVerticalScrollPosition;
		}
		
	}
}