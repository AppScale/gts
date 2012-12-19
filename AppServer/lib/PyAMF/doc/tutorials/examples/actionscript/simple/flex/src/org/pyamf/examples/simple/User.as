/**
 * Copyright (c) 2009 The PyAMF Project.
 * See LICENSE.txt for details.
*/
package org.pyamf.examples.simple
{
	[Bindable]
	[RemoteClass(alias='org.pyamf.examples.simple.User')]
	public class User
	{
		public var username	: String;
		public var password	: String;
		public var email	: String;
		
		public function User()
		{
			super();
		}
		
	}
}