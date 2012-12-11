/**
 * Copyright (c) 2009 The PyAMF Project.
 * See LICENSE.txt for details.
*/
package org.pyamf.examples.simple
{
	import flash.events.MouseEvent;
	import flash.events.SecurityErrorEvent;
	
	import mx.controls.Alert;
	import mx.controls.Text;
	import mx.controls.TextArea;
	import mx.controls.TextInput;
	import mx.core.Application;
	import mx.messaging.ChannelSet;
	import mx.messaging.channels.AMFChannel;
	import mx.rpc.AbstractOperation;
	import mx.rpc.events.FaultEvent;
	import mx.rpc.events.ResultEvent;
	import mx.rpc.remoting.mxml.RemoteObject;
	
	public class SimpleView extends Application
	{
		private static const URL	: String = "http://localhost:8000";
		
		private var _service		: RemoteObject;

		public var txtUsername		: TextInput;
		public var txtUserInfo		: TextArea;
		public var txtInput			: TextInput;
		public var txtResult		: Text;
		
		public function SimpleView()
		{
			super();
			_service = initializeService();
		}

		private function initializeService():RemoteObject
		{
			var channel:AMFChannel = new AMFChannel("pyamf-channel", URL);
			var channels:ChannelSet = new ChannelSet();
			channels.addChannel(channel);
			
			var remoteObject:RemoteObject = new RemoteObject("user");  
			remoteObject.showBusyCursor = true;
			remoteObject.channelSet = channels;
			remoteObject.addEventListener(FaultEvent.FAULT, onRemoteServiceFault);
			remoteObject.addEventListener(SecurityErrorEvent.SECURITY_ERROR, onRemoteServiceFault);
			
			return remoteObject;
		}

		public function getUser(event:MouseEvent):void
		{
  			var operation:AbstractOperation = _service.getOperation('get_user');
			operation.addEventListener(ResultEvent.RESULT, resultHandler);
			operation.send(txtUsername.text);
		}

		protected function resultHandler(event:ResultEvent):void
		{
			var usr:User = event.result as User;
			if (usr) 
			{
				txtUserInfo.text = "User: " + usr.username + 
					"\nEmail: " + usr.email + "\n";
			}
			else
			{
				txtUserInfo.text = event.result.toString();
			}
		}
		
		private function onRemoteServiceFault(event:FaultEvent):void
		{
			var errorMsg:String = "Service error:\n" + event.fault.faultCode;
			Alert.show(event.fault.faultDetail, errorMsg);	
		}
		
		private function onRemoteServiceSecurityError(event:SecurityErrorEvent):void
		{
			var errorMsg:String = "Service security error";
			Alert.show(event.text, errorMsg);	
		}
	}
}