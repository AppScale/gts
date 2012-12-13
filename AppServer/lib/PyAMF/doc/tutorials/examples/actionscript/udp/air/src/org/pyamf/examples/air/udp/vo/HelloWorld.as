package org.pyamf.examples.air.udp.vo
{
	import flash.utils.getQualifiedClassName;
	
	/**
	 * Sample typed object for testing.
	 */	
	public class HelloWorld
	{
		public var msg			: String;
		public var time			: Date;
		
		/**
		 * Constructor.
		 * 
		 * @param msg
		 * @param time
		 */		
		public function HelloWorld( msg:String="UDP message",
									time:Date=null )
		{
			this.msg = msg;
			this.time = time;
			
			if (this.time == null)
			{
				this.time = new Date();
			}
		}
		
		public function toString() : String
		{
			var className:String = getQualifiedClassName( this ).split( "::" )[ 1 ];
			
			return "<class='" + className + "' msg='" + msg + "' time='" + time + "' />";
		}

	}
}