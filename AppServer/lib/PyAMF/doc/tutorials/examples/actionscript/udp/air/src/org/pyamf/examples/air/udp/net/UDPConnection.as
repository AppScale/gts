package org.pyamf.examples.air.udp.net
{
	import flash.events.DatagramSocketDataEvent;
	import flash.events.Event;
	import flash.events.EventDispatcher;
	import flash.events.TimerEvent;
	import flash.net.DatagramSocket;
	import flash.net.InterfaceAddress;
	import flash.net.registerClassAlias;
	import flash.utils.ByteArray;
	import flash.utils.Timer;
	import flash.utils.getQualifiedClassName;
	
	import org.pyamf.examples.air.udp.events.LogEvent;
	import org.pyamf.examples.air.udp.vo.HelloWorld;
	
	public class UDPConnection extends EventDispatcher
	{
		private var datagramSocket	: DatagramSocket;
        private var repeatTimer		: Timer = new Timer( 4000 ); //ms
        
        // The IP and port for this computer
        private var localIP			: String;
        private var localPort		: int = 55554;
        
        // The IP and port for the target computer
        private var targetIP		: String;
        private var targetPort		: int = 55555;
        
		/**
		 * Constructor.
		 *  
		 * @param localAddress
		 * @param serverAddress
		 * @param serverPort
		 */        
		public function UDPConnection( localAddress:InterfaceAddress,
									serverAddress:String=null,
									serverPort:int=0 )
		{
			if (localAddress)
			{
				localIP = localAddress.address;
			}
			else
			{
				throw new Error("Can't bind to interface: " + localAddress);
			}
			
			if (serverAddress == null)
			{
				targetIP = localIP;
			}
			
			if (serverPort == 0)
			{
				targetPort = localPort + 1;
			}
		}
		
		public function connect():void
		{
			// Create the socket for sending and receiving UDP datagram packets
            datagramSocket = new DatagramSocket();
            datagramSocket.addEventListener( DatagramSocketDataEvent.DATA, dataReceived,
            								 false, 0, true );
            
            // Bind the socket to the local network interface and port
            
			var msg:String = "\nConnection\n";
			msg += "----------------\n";
			log( msg );

			try
            {
            	datagramSocket.bind( localPort, localIP );
            	printAddress( "Bound to", datagramSocket.localAddress,
            							  datagramSocket.localPort );
            }
            catch (e:Error)
            {
            	log( e.toString() + "\n" );
            }
            
            // Listen for incoming datagrams
            datagramSocket.receive();
            printAddress( "Listening to", targetIP, targetPort );
            
            // Register the strongly typed class we will send over udp
            registerAlias( HelloWorld );
            
            // Send initial datagram
            log("\n");
            send();
            
            // Send a datagram at every timer event
            repeatTimer.addEventListener( TimerEvent.TIMER, send, false, 0, true );
            repeatTimer.start();
		}
		
		private function printAddress( msg:String, ip:String, port:int ) : void
		{
			log( msg + ":\t\t" + ip + ":" + port + "\n");
		}
		
		private function registerAlias( klass:Class ) : void
		{
			var pckage:Array = getQualifiedClassName( klass ).split('::');
			var alias:String = pckage.join(".");
			
			registerClassAlias( alias, klass );
			
			log( "\nRegistered alias '" + alias + "' for class '" + pckage[1] + "'" );
		}
		
        private function send( event:Event=null ):void
        {
            // Create a message in a ByteArray
            var msg:HelloWorld = new HelloWorld();
            var data:ByteArray = new ByteArray();
            data.writeObject( msg );
            
			log( "Sending: " + msg + "\n",
				 LogEvent.NETWORK_TRAFFIC );
			
            // Send a datagram to the target
            try
            {
	            datagramSocket.send( data, 0, 0, targetIP, targetPort );
            }
            catch (e:Error)
            {
				log( "Connection was closed.\n",
					 LogEvent.NETWORK_TRAFFIC );
            }
        }
		
		private function dataReceived( event:DatagramSocketDataEvent ):void
		{
			// Read the data from the datagram
			log( "Received: " + event.data.readObject() + "\n",
				 LogEvent.NETWORK_TRAFFIC );
		}
        
		/**
		 * Notify others.
		 * 
		 * @param msg
		 * @param evt
		 */		
		private function log( msg:String,
							  evt:String=LogEvent.NETWORK_INFO ):void
		{
			var log:LogEvent = new LogEvent(evt, msg);
			dispatchEvent( log );
		}

	}
}