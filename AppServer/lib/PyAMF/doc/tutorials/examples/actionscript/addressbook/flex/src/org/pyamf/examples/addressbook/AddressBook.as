/**
 * Copyright (c) 2007-2009 The PyAMF Project.
 * See LICENSE.txt for details.
*/
package org.pyamf.examples.addressbook
{
	import flash.display.DisplayObject;
	import flash.net.registerClassAlias;

	import mx.collections.ArrayCollection;
	import mx.controls.Alert;
	import mx.controls.DataGrid;
	import mx.controls.TextInput;
	import mx.core.Application;
	import mx.events.FlexEvent;
	import mx.managers.PopUpManager;
	import mx.messaging.ChannelSet;
	import mx.messaging.channels.AMFChannel;
	import mx.rpc.AbstractOperation;
	import mx.rpc.events.FaultEvent;
	import mx.rpc.events.ResultEvent;
	import mx.rpc.remoting.mxml.RemoteObject;

	import org.pyamf.examples.addressbook.components.EditUserDlg;
	import org.pyamf.examples.addressbook.models.Email;
	import org.pyamf.examples.addressbook.models.PhoneNumber;
	import org.pyamf.examples.addressbook.models.User;

	public class AddressBook extends Application
	{
		[Bindable]
		protected var users		: ArrayCollection;

		public var server		: TextInput;
		public var port			: TextInput;
		public var userGrid		: DataGrid;

		/**
		 * Constructor.
		 */
		public function AddressBook()
		{
			super();

			// These mappings must use the same aliases defined with the PyAMF
			// function 'pyamf.register_class'.
			registerClassAlias(User.ALIAS, User);
			registerClassAlias(Email.ALIAS, Email);
			registerClassAlias(PhoneNumber.ALIAS, PhoneNumber);

			addEventListener(FlexEvent.CREATION_COMPLETE, creationCompleteHandler);
		}

		protected function creationCompleteHandler(event:FlexEvent):void
		{
			// Load users at startup
			loadUsers();
		}

		/**
		 * Insert default data.
		 */
		public function insertDefaultData():void
		{
			var remoteObj:RemoteObject = getService();
			var operation:AbstractOperation = remoteObj.getOperation('insertDefaultData');
            operation.addEventListener(ResultEvent.RESULT, insertDefaultData_resultHandler);
            operation.send();
		}

		protected function insertDefaultData_resultHandler(event:Event):void
		{
			event.target.removeEventListener(ResultEvent.RESULT,
											 insertDefaultData_resultHandler);
			loadUsers();
		}

		/**
		 * Load list of persistent users from server.
		 */
		public function loadUsers(event:FlexEvent=null):void
		{
			var remoteObj:RemoteObject = getService();
			var operation:AbstractOperation = remoteObj.getOperation('loadAll');
            operation.addEventListener(ResultEvent.RESULT, loadAll_resultHandler);
            operation.send(User.ALIAS);
		}

		protected function loadAll_resultHandler(event:Event):void
		{
			enabled = true;
			event.target.removeEventListener(ResultEvent.RESULT, loadAll_resultHandler);
			users = ArrayCollection(ResultEvent(event).result);
		}

		/**
		 * Create a RemoteObject with url from user input.
		 */
		public function getService():RemoteObject
		{
			// Create the AMF Channel
			var url:String = 'http://' + server.text + ':' + port.text;
			var channel:AMFChannel = new AMFChannel("pyamf-channel", url);

			// Create a channel set and add your channel(s) to it
			var channels:ChannelSet = new ChannelSet();
			channels.addChannel(channel);

			// Create a new remote object and set channels
			var remoteObject:RemoteObject = new RemoteObject("ExampleService");
			remoteObject.showBusyCursor = true;
			remoteObject.channelSet = channels;
			remoteObject.addEventListener(FaultEvent.FAULT, onServiceFault);

			return remoteObject;
		}

		/**
		 * Edit a user record.
		 */
		protected function editUser():void
		{
			if (userGrid.selectedItem == null)
			{
				return;
			}

			var dlg:EditUserDlg = new EditUserDlg();
			dlg.user = User(userGrid.selectedItem);
			PopUpManager.addPopUp(dlg, DisplayObject(this), true);
		}

		/**
		 * Add a new user.
		 */
		protected function addUser():void
		{
			var user:User = new User();
			var dlg:EditUserDlg = new EditUserDlg();
			dlg.user = user;
			PopUpManager.addPopUp(dlg, DisplayObject(this), true);
		}

		/**
		 * Remove an existing user.
		 */
		protected function removeUser():void
		{
			if (userGrid.selectedItems == null || userGrid.selectedItems.length < 1)
			{
				return;
			}

			var removeKeys:Array = [];
			for each (var item:Object in userGrid.selectedItems)
			{
				removeKeys.push(item.sa_key);
			}

			var remoteObj:RemoteObject = getService();
			var operation:AbstractOperation = remoteObj.getOperation('removeList');
            operation.addEventListener(ResultEvent.RESULT, remove_resultHandler);
            operation.send(User.ALIAS, removeKeys);
		}

		protected function remove_resultHandler(event:Event):void
		{
			event.target.removeEventListener(ResultEvent.RESULT, remove_resultHandler);
			loadUsers();
		}

		/**
		 * Service reported an error.
		 *
		 * @param event Event containing error information.
		 */
		protected function onServiceFault(event:FaultEvent):void
		{
			var errorMsg:String = 'Service error: ' + event.fault.faultCode;
			Alert.show(event.fault.faultDetail, errorMsg);
		}

	}
}