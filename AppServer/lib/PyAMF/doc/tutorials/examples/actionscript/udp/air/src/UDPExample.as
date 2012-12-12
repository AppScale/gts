package 
{
	import flash.desktop.NativeApplication;
	import flash.display.Sprite;
	import flash.events.Event;
	
	import org.pyamf.examples.air.udp.events.LogEvent;
	import org.pyamf.examples.air.udp.net.NetworkConnection;
	import org.pyamf.examples.air.udp.net.UDPConnection;
	import org.pyamf.examples.air.udp.view.TextWindow;

	public class UDPExample extends Sprite
	{
		private var connection			: UDPConnection;
		private var network				: NetworkConnection;
		private var logEvent			: LogEvent;
		
		private static var window		: TextWindow;
		
		/**
		 * Constructor.
		 */		
		public function UDPExample()
		{
			super();
			
			// setup AIR
			NativeApplication.nativeApplication.autoExit = true;
			
			// create text window
			window = new TextWindow();
			stage.nativeWindow.close();
			
			// listen for events
			addEventListener( Event.ADDED_TO_STAGE, onWindowComplete,
							  false, 0, true );
		}
		
		private function onWindowComplete( event:Event ) : void
		{
			removeEventListener( event.type, onWindowComplete );

			// get local network info
			network = new NetworkConnection();
			network.addEventListener( LogEvent.NETWORK_INFO, log, false, 0, true );
			network.addEventListener( Event.NETWORK_CHANGE, onNetworkChange,
									  false, 0, true );
			try
			{
				// connect to UDP server using IPv4 address because
				// Twisted doesn't support IPv6
				connection = new UDPConnection( network.activeIP4Address );
				connection.addEventListener( LogEvent.NETWORK_INFO, log, false, 0, true );
				connection.addEventListener( LogEvent.NETWORK_TRAFFIC, log, false, 0, true );
				connection.connect();
			}
			catch ( error:Error )
			{
				logEvent = new LogEvent( LogEvent.NETWORK_INFO, error.toString() );
				log( logEvent );
			}
		}
		
		private function onNetworkChange( event:Event ) : void
		{
			logEvent = new LogEvent( LogEvent.NETWORK_INFO, event.toString() );
			log( logEvent );
		}
		
		private static function log( event:LogEvent ) : void
		{
			switch ( event.type )
			{
				case LogEvent.NETWORK_INFO:
					window.connection += event.message;
					break;
				
				case LogEvent.NETWORK_TRAFFIC:
					window.text += event.message;
					break;
			}
		}
		
	}
}