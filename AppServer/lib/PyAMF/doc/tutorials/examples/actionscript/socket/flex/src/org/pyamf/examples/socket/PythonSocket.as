package org.pyamf.examples.socket
{
	/**
	 * Copyright (c) 2007-2009 The PyAMF Project.
	 * See LICENSE.txt for details.
	 */
	 
	import flash.errors.IOError;
	import flash.events.Event;
	import flash.events.IOErrorEvent;
	import flash.events.ProgressEvent;
	import flash.events.SecurityErrorEvent;
	import flash.net.ObjectEncoding;
	import flash.net.Socket;
	import flash.system.Capabilities;
	
	[Event(name="connected", type="flash.events.Event")]
	[Event(name="disconnected", type="flash.events.Event")]
	[Event(name="logUpdate", type="flash.events.Event")]
	/**
	 * Socket connection to read and write raw binary data.
	 * 
	 * @see http://livedocs.adobe.com/flex/3/langref/flash/net/Socket.html
	 * @since 0.1.0
	 */	
	public class PythonSocket extends Socket
	{
		private var _response			: String;
		private var _log				: String;
		private var _host				: String;
		private var _port				: int;
		
		public static const CONNECTED	: String = "connected";
		public static const DISCONNECTED: String = "disconnected";
		public static const LOG_UPDATE	: String = "logUpdate";
		
		public function PythonSocket(host:String='localhost', port:int=8000)
		{
			super(host, port);
			
			_host = host;
			_port = port;
			_log = "Using Flash Player " + Capabilities.version + "\n";
			
			objectEncoding = ObjectEncoding.AMF0;
			configureListeners();
			
			logger("Connecting to socket server on " + _host + ":" + _port);
		}
		
		public function get log():String
		{
			return _log;
		}
		
		public function set log(val:String):void
		{
			_log = val;
		}
		
		private function configureListeners():void 
		{
	        addEventListener(Event.CLOSE, closeHandler);
	        addEventListener(Event.CONNECT, connectHandler);
	        addEventListener(IOErrorEvent.IO_ERROR, ioErrorHandler);
	        addEventListener(SecurityErrorEvent.SECURITY_ERROR, securityErrorHandler);
	        addEventListener(ProgressEvent.SOCKET_DATA, readResponse);
	    }
	
		public function write(msg:String): void
		{
			sendRequest(msg);
		}
		
	    private function writeln(str:String):void 
	    {
	        str += "\n";
	        
	        try {
	            writeUTFBytes(str);
	        }
	        catch(e:IOError) {
	        	switch (e.errorID) {
	        		case 2002:
	        			// reconnect when connection timed out
	        			if (!connected) {
	        				logger("Reconnecting...");
	        				connect( _host, _port );
	        			}
	        			break;
	        			
	        		default:
	        			logger(e.toString());
	        			break;
	        	}
	        }
	    }
	
	    private function sendRequest(str:String):void 
	    {
	        logger("sendRequest: " + str);
	        _response = "";
	        writeln(str);
	        flush();
	    }
	
	    private function readResponse(event:ProgressEvent):void 
	    {
			var result:Object = this.readObject();

	        _response += result;
	        logger(result.toString());
	    }
		
	    private function logger(msg:String):void
		{
			var newMsg:String = msg + "\n";
			_log += newMsg;
			
			dispatchEvent(new Event(LOG_UPDATE));
		}
		
	    private function connectHandler(event:Event):void 
	    {
	        logger("Connected to server.\n");
	        
	        dispatchEvent(new Event(CONNECTED));
	    }
	    
	    private function closeHandler(event:Event):void 
	    {
	        logger("Connection closed.");
	        
	        dispatchEvent(new Event(DISCONNECTED));
	    }
	
	    private function ioErrorHandler(event:IOErrorEvent):void 
	    {
	        logger("ioErrorHandler: " + event.text);
	    }
	
	    private function securityErrorHandler(event:SecurityErrorEvent):void 
	    {
	        logger("securityErrorHandler: " + event.text);
	    }
			
	}
}