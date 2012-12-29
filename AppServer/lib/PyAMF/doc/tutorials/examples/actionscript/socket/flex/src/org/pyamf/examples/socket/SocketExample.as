package org.pyamf.examples.socket
{
	/**
	 * Copyright (c) 2007-2009 The PyAMF Project.
	 * See LICENSE.txt for details.
	 */

	import flash.events.Event;
	
	import mx.controls.Button;
	import mx.core.Application;
	import mx.events.FlexEvent;
	
	/**
	 * This examples shows how to use Socket class in ActionScript 3,
	 * that allows you to make socket connections and to read and write
	 * raw binary data.
	 * 
	 * @author Thijs Triemstra (info@collab.nl)
	 */
	public class SocketExample extends Application
	{
		public var start_btn: Button;
		public var stop_btn	: Button;
		
		private var _server	: PythonSocket;
		
		[Bindable]
		public var log		: String;
		
		public function SocketExample()
		{
			super();
			
			addEventListener( FlexEvent.APPLICATION_COMPLETE, initApp );
		}
		
		private function initApp(event:FlexEvent):void
		{
			// Connect to server
			_server = new PythonSocket();
			
			// Listen for log updates
			_server.addEventListener( PythonSocket.CONNECTED, startState );
			_server.addEventListener( PythonSocket.DISCONNECTED, startState );
			_server.addEventListener( PythonSocket.LOG_UPDATE, logUpdate );
		}
		
		private function logUpdate( event:Event ):void
		{
			// Display log
			log = _server.log;
		}
		
		public function startFeed():void
		{
			stopState();
			
			// Start feed
			_server.write( "start" );
		}
		
		public function stopFeed():void
		{
			startState();
			
			// Stop feed
			_server.write( "stop" );
		}
		
		private function startState( event:Event=null ):void
		{
			start_btn.enabled = true;
			stop_btn.enabled = false;
		}
		
		private function stopState( event:Event=null ):void
		{
			start_btn.enabled = false;
			stop_btn.enabled = true;
		}
		
	}
}