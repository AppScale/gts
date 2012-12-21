package org.pyamf.examples.guestbook.events
{
	/**
	 * Copyright (c) 2007-2009 The PyAMF Project.
	 * See LICENSE.txt for details.
	*/

	import mx.events.FlexEvent;
	
	import org.pyamf.examples.guestbook.vo.Message;
	
	/**
	 * @since 0.3.0
	 */
	public class SubmitEvent extends FlexEvent
	{
		private var _message : Message;
		
		/**
		 * @param message
		 * @param type
		 * @param bubbles
		 * @param cancelable
		 */		
		public function SubmitEvent(message:Message, type:String="onSubmit", bubbles:Boolean=false,
									cancelable:Boolean=false)
		{
			super(type);
			this._message = message;
		}
		
		public function get message():Message
		{
			return _message;
		}
		
		public function set message(msg:Message):void
		{
			_message = msg;
		}
		
		override public function toString():String
		{
			return 'SubmitEvent(message=' + this._message + ' type="' + this.type + '" bubbles=' + 
								this.bubbles + ' cancelable=' + this.cancelable + ')';
		}
		
	}
}