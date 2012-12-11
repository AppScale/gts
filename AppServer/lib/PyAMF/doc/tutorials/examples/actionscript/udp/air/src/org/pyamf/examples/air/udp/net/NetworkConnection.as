package org.pyamf.examples.air.udp.net
{
	import flash.events.Event;
	import flash.events.EventDispatcher;
	import flash.net.IPVersion;
	import flash.net.InterfaceAddress;
	import flash.net.NetworkInfo;
	import flash.net.NetworkInterface;
	
	import org.pyamf.examples.air.udp.events.LogEvent;
	
	public class NetworkConnection extends EventDispatcher
	{
		private var _info		: NetworkInfo;
		private var _interfaces	: Vector.<NetworkInterface>;
		
		/**
		 * Get active and inactive interfaces from this machine.
		 *  
		 * @return Vector of NetworkInterfaces
		 */		
		public function get interfaces() : Vector.<NetworkInterface>
		{
			return _interfaces;
		}
		
		/**
		 * Get all active interfaces.
		 *  
		 * @return Vector of NetworkInterfaces
		 */		
		public function get activeInterfaces() : Vector.<NetworkInterface>
		{
			var active:Vector.<NetworkInterface> = new Vector.<NetworkInterface>();
			var inet:NetworkInterface;
			var localhost:NetworkInterface;
			
			for each ( inet in _interfaces )
			{
				// any active connected interfaces
				if ( inet.active )
				{
					active.push( inet );
				}
				else if ( inet.addresses.length > 0 )
				{
					// inactive but contains localhost address
					localhost = inet;
				}
			}
			
			// add localhost
			active.push( localhost );
			
			return active;
		}
		
		/**
		 * Get primary active interface IPv4 address.
		 *  
		 * @return InterfaceAddress of type IPVersion.IPV4.
		 */		
		public function get activeIP4Address() : InterfaceAddress
		{
			return getActiveInterfaceAddress();
		}
		
		/**
		 * Get primary active interface IPv6 address.
		 *  
		 * @return InterfaceAddress of type IPVersion.IPv6.
		 */		
		public function get activeIP6Address() : InterfaceAddress
		{
			return getActiveInterfaceAddress( IPVersion.IPV6 );
		}
		
		/**
		 * Constructor. 
		 */		
		public function NetworkConnection()
		{
			super();
			
			_info = NetworkInfo.networkInfo;
			_info.addEventListener( Event.NETWORK_CHANGE, onNetworkChange, false,
								    0, true );
			
			listInterfaces();
		}
		
		private function onNetworkChange( event:Event ) : void
		{
			log("One of the network interfaces has changed.\n");
			
			listInterfaces();
			
			dispatchEvent( new Event(event.type, true, true) );
		}
		
		private function listInterfaces() : void
		{
			_interfaces = _info.findInterfaces();
			
			log("Total network interfaces: " + _interfaces.length + "\n");
			
			for each ( var inet:NetworkInterface in _interfaces )
			{
				//printInterface( inet );
			}
		}
		
		private function printInterface( inet:NetworkInterface ) : void
		{
			var msg:String = "-------------------------------\n";
			msg += "Name: " + inet.name + "\n";
			msg += "Displayname: " + inet.displayName + "\n";
			msg += "Active: " + inet.active + "\n";
			msg += "Hardware Address: " + inet.hardwareAddress + "\n";
			msg += "MTU: " + inet.mtu + "\n";
			
			log( msg );
			
			if (inet.addresses.length > 0)
			{
				printAddresses( inet.addresses );
			}
		}

		private function printAddresses( addresses:Vector.<InterfaceAddress> ):void
		{
			var msg:String = "Addresses:\n";
			
			for each (var address:InterfaceAddress in addresses)
			{
				msg += " - " + address.ipVersion + ": \t\t\t" + address.address + "\n";
				if (address.broadcast)
				{
					msg += " - Broadcast:\t\t" + address.broadcast + "\n";
				}
			}
			
			log( msg );
		}
		
		/**
		 * Get active interface address by IP version
		 * 
		 * @param type
		 * @return 
		 */		
		private function getActiveInterfaceAddress( type:String=null ):InterfaceAddress
		{
			var address:InterfaceAddress;
			
			if ( type == null )
			{
				type = IPVersion.IPV4;
			}
			
			if (activeInterfaces.length > 0 && activeInterfaces[0].addresses.length > 0)
			{
				log("Primary active interface\n");
				
				printInterface( activeInterfaces[0] );
				
				for each ( address in activeInterfaces[0].addresses )
				{
					if ( address.ipVersion == type )
					{
						break;
					}
				}
			}
			
			return address;
		}
		
		/**
		 * Log a message.
		 *  
		 * @param msg
		 */		
		private function log( msg:String ):void
		{
			var log:LogEvent = new LogEvent( LogEvent.NETWORK_INFO, msg );
			dispatchEvent( log );
		}
		
	}
}