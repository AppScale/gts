/**
 * Copyright (c) 2007-2009 The PyAMF Project.
 * See LICENSE.txt for details.
*/
package org.pyamf.examples.addressbook.models
{
	[Bindable]
	public class PhoneNumber extends SAObject
	{
		public static var ALIAS	: String = 'org.pyamf.examples.addressbook.models.PhoneNumber';
		
		public var id			: Object;
		public var user_id		: Object;
		public var label		: String;
		public var number		: String;
	}
}