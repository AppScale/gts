package org.pyamf.examples.sharedobject.vo
{
	[RemoteClass(alias="org.pyamf.examples.sharedobject.vo.App")]
	public class App
	{
		public var name:String;
		public var path:String;
		public var domain:String;
		public var files:Array;
			
		public function App( name:String="",
									  path:String="",
									  domain:String="",
									  files:Array=undefined)
		{
			this.name = name;
			this.path = path;
			this.domain = domain;
			this.files = files;
		}

	}
}