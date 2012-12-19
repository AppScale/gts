/**
 * Copyright (c) 2007-2009 The PyAMF Project.
 * See LICENSE.txt for details.
*/
package org.pyamf.examples.addressbook.components
{
	import mx.containers.TitleWindow;
	import mx.controls.TextInput;
	import mx.events.FlexEvent;
	import mx.managers.PopUpManager;
	
	import org.pyamf.examples.addressbook.models.Email;

	public class EditEmailDlgClass extends TitleWindow
	{
		[Bindable]
		public var email			: Email;
		
		public var emailLabel		: TextInput;
		public var emailText		: TextInput;
		
		/**
		 * Constructor. 
		 */		
		public function EditEmailDlgClass()
		{
			super();
			
			addEventListener(FlexEvent.CREATION_COMPLETE, creationCompleteHandler);
		}
		
		protected function creationCompleteHandler( event:FlexEvent ):void
		{
			PopUpManager.centerPopUp(this);
		}
		
		protected function close():void
		{
			email.label = emailLabel.text;
			email.email = emailText.text;
			PopUpManager.removePopUp(this);	
		}
		
	}
}