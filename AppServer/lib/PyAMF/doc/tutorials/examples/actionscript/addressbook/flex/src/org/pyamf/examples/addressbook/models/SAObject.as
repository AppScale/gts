/**
 * Copyright (c) 2007-2009 The PyAMF Project.
 * See LICENSE.txt for details.
*/
package org.pyamf.examples.addressbook.models
{
	import flash.events.Event;
	import flash.utils.getDefinitionByName;
	import flash.utils.getQualifiedClassName;
	
	import mx.collections.ArrayCollection;
	import mx.core.Application;
	import mx.rpc.AbstractOperation;
	import mx.rpc.events.AbstractEvent;
	import mx.rpc.events.ResultEvent;
	import mx.rpc.remoting.RemoteObject;
		
   /**
	* A base-class for classes mapped with SQLAlchemy on the server side.
	*/
	public class SAObject
	{
		protected const LOAD_ERROR_MSG		: String = 'Cannot load attribute of un-persisted object.';
		protected const SAVE_ERROR_MSG		: String = 'Cannot save attribute of un-persisted object.';
		protected const REMOVE_ERROR_MSG	: String = 'Cannot remove un-persisted object.';
		
		public const ALIAS					: String = '';
		
		/**
		 * Primary key of the persistent object.
		 */
		public var sa_key					: ArrayCollection = new ArrayCollection();
		
		/**
		 * Attributes that are lazy-loaded.
		 */
		public var sa_lazy					: ArrayCollection = new ArrayCollection();
		
		/**
		 * Attributes that are in the process of being loaded.
		 */
		public var sa_loading				: ArrayCollection = new ArrayCollection();
		
		/**
		 * Constructor. 
		 */		
		public function SAObject()
		{
			super();
		}
		
		public function get alias():String
		{
			var className:String = getQualifiedClassName(this);
			var klass:Class = getDefinitionByName(className) as Class;
			
			return klass.ALIAS;
		}

		/**
         * Returns true if object is persistent.
         */
		public function isPersistent():Boolean
		{
			if (sa_key == null || sa_key.length < 1)
			{
				return false;
			}
			        
			for each(var item:Object in sa_key)
			{
				if (item == null)
				{
			    	return false;
				}
			}
			        
			return true;
		}
		
		/**
		 * Returns true if the attribute has not been loaded from the database.
		 */
		public function isAttrLazy(attr:String):Boolean
		{
			if (!isPersistent())
			{
				return false;
			}
			
			for each (var item:String in sa_lazy)
			{
				if (item == attr)
				{
					return true;
				}
			}
			
			return false
		}
		
		/**
		 * Sets an attribute so that it is no-longer considered lazy-loaded.
		 */
		public function setAttr(attr:String, value:*):void
		{
			var i:int = sa_lazy.getItemIndex(attr);
			if (i > -1)
			{
				sa_lazy.removeItemAt(i);
			}
			this[attr] = value;
		}
		
		/**
		 * Sets an attribute to null so that it can be lazy-loaded.
		 */
		public function unSetAttr(attr:String):void
		{
			this[attr] = null;
			
			var i:int = sa_lazy.getItemIndex(attr);
			if (i > -1)
			{
				return;
			}
			else
			{
				sa_lazy.addItem(attr);
			}
		}
		
		/**
		 * Returns true if the attribute is being loaded from the server.
		 */
		public function isAttrLoading(attr:String):Boolean
		{	
			for each (var item:String in sa_loading)
			{
				if (item == attr)
				{
					return true;
				}
			}
			
			return false
		}
		
		/**
		 * Sets an attribute so that it is considered to be loading.
		 */
		public function setAttrLoading(attr:String):void
		{
			var i:int = sa_loading.getItemIndex(attr);
			if (i > -1)
			{
				return;
			}
			else
			{
				sa_loading.addItem(attr);
			}
		}
		
		/**
		 * Sets an attribute to not-loading
		 */
		public function unSetAttrLoading(attr:String):void
		{
			var i:int = sa_loading.getItemIndex(attr);
			if (i > -1)
			{
				sa_loading.removeItemAt(i);
			}
		}	

		/**
		 * Loads a single attribute from the server.
		 */
		public function loadAttr(attr:String):void
		{
			if (!isPersistent())
			{
				throw new Error(LOAD_ERROR_MSG);
			}
			
			// Make sure not to call the same RPC multiple times.
			if (isAttrLoading(attr))
			{
				return;
			}
			
			setAttrLoading(attr);
			var remoteObj:RemoteObject = Application.application.getService();
			var operation:AbstractOperation = remoteObj.getOperation('loadAttr');
			operation.addEventListener(ResultEvent.RESULT, loadAttr_resultHandler);
			operation.send(alias, sa_key, attr);
		}

		/**
		 * Set remotely loaded attribute.
		 */
		protected function loadAttr_resultHandler(event:Event):void
		{
			event.target.removeEventListener(ResultEvent.RESULT,
											 loadAttr_resultHandler);
						
			var attr:String = AbstractEvent(event).token.message.body[2];
			setAttr(attr, ResultEvent(event).result);
			unSetAttrLoading(attr);
		}
				
		/**
		  * Save a single persistent attribute.
		 */
		public function saveAttr(attr:String):void
		{
			if (!isPersistent())
			{
				throw new Error(SAVE_ERROR_MSG);
			}
				
			var remoteObj:RemoteObject = Application.application.getService();
			remoteObj.saveAttr(sa_key, attr, this[attr]);
		}
				
		/**
		 * Persist the entire object.
		 */
		public function save():void
		{
			var remoteObj:RemoteObject = Application.application.getService();
			remoteObj.save(this);
		}
				
		/**
		 * Delete persistent object.
		 */
		public function remove():void
		{
			if (!isPersistent())
			{
				throw new Error(REMOVE_ERROR_MSG);
			}

			var remoteObj:RemoteObject = Application.application.getService();
			var operation:AbstractOperation = remoteObj.getOperation('remove');
            operation.send(alias, sa_key);
		}
		
	}
}