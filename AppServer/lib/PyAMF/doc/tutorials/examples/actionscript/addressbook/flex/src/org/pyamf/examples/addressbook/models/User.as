/**
 * Copyright (c) 2007-2009 The PyAMF Project.
 * See LICENSE.txt for details.
*/
package org.pyamf.examples.addressbook.models
{
	import mx.collections.ArrayCollection;
	
	[Bindable]
	public class User extends SAObject
	{
		public static var ALIAS		: String = 'org.pyamf.examples.addressbook.models.User';
		
		public var id				: Object;
		public var first_name		: String;
		public var last_name		: String;
		public var emails			: ArrayCollection = new ArrayCollection();
		public var phone_numbers	: ArrayCollection = new ArrayCollection();
		public var created		: Date = new Date();
	}
}