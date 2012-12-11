package org.pyamf.examples.guestbook.vo
{
	/**
	 * Copyright (c) 2007-2009 The PyAMF Project.
	 * See LICENSE.txt for details.
	*/
	
	[RemoteClass(alias="org.pyamf.examples.guestbook.Message")] 
	/**
	 * Guestbook message.
	 * 
	 * @author Thijs Triemstra (info@collab.nl)
	 */
	public class Message
	{
		public var name		: String;
		public var url		: String;
		public var email 	: String;
		public var created	: Date;
		public var message	: String;
		
		public function Message(name:String="", url:String="", email:String="",
								created:Date=undefined, message:String="")
		{
			this.name = name;
			this.url = url;
			this.email = email;
			this.created = created;
			this.message = message;
		}

	}
}