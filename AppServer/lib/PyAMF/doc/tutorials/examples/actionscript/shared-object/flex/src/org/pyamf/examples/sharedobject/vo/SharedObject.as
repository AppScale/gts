package org.pyamf.examples.sharedobject.vo
{
	[RemoteClass(alias="org.pyamf.examples.sharedobject.vo.SharedObject")]
	
	public class SharedObject
	{
		public var name:String;
		public var app:String;
		public var path:String;
		public var domain:String;
		public var size:int;
			
		public function SharedObject( name:String="",
									  app:String="",
									  path:String="",
									  domain:String="",
									  size:int=0)
		{
			this.name = name;
			this.app = app;
			this.path = path;
			this.domain = domain;
			this.size = size;
		}

	}
}