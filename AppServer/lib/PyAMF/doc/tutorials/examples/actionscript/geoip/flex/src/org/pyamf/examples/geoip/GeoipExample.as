package org.pyamf.examples.geoip
{
	/**
	 * Copyright (c) 2007-2009 The PyAMF Project.
	 * See LICENSE.txt for details.
	*/
	
	import flash.events.NetStatusEvent;
	import flash.net.NetConnection;
	import flash.net.Responder;
	
	import mx.controls.Alert;
	import mx.controls.Image;
	import mx.controls.Label;
	import mx.core.Application;
	import mx.events.FlexEvent;
	
	import org.pyamf.examples.geoip.vo.GeoInfo;

	/**
	 * This examples shows how to use the GeoIP Python API
	 * with Flex and PyAMF.
	 * 
	 * @since 0.1
	 */
	public class GeoipExample extends Application
	{
		public var cc_txt			: Label;
		public var status_txt		: Label;
		public var flag				: Image;
		
		private var _gateway		: NetConnection;
		private var _status			: String;
		private var _myComputer		: GeoInfo;
		private var _countryCode	: String;
		private var _flag			: String;
		
		public function GeoipExample()
		{
			super();
			_flag = "unknown";
			addEventListener(FlexEvent.APPLICATION_COMPLETE, onInitApp);
		}
		
		private function onInitApp(event:FlexEvent): void
		{
			// setup connection
            _gateway = new NetConnection();
            _gateway.addEventListener(NetStatusEvent.NET_STATUS, onNetstatusError);
			
            // Connect to gateway
            _gateway.connect("http://demo.pyamf.org/gateway/geoip");
            
            // Set responder property to the object and methods that will receive the 
            // result or fault condition that the service returns.
            var responder:Responder = new Responder( onGeoInfoResult, onFault );
            
            // Call remote service to fetch geolocation data
            _gateway.call("geoip.getGeoInfo", responder);
            status_txt.text = "Loading...";
		}
		
		private function onGeoInfoResult(result:*): void
        {
        	_myComputer = result as GeoInfo;
        	
           	setInfo();
        }
        
        private function onNetstatusError(event:NetStatusEvent): void
        {
        	setInfo(event.info.code);
        }
        
        private function setInfo(errorText:String=""): void
        {
        	if (errorText.length == 0) {
        		if ( _myComputer.country.code != null ) {
	           		 _countryCode = _myComputer.country.code;
	           		 cc_txt.text = _countryCode;
	           		 _status = _myComputer.country.name + " (" + _myComputer.ip + ")";
	           		 _flag = _countryCode.toLowerCase();
	           	} else {
	           		_status = "Unknown Location";
	           		cc_txt.text = _myComputer.ip;
	           		cc_txt.setStyle('fontSize', 10);
	           	}
        	} else {
        		cc_txt.text = "Error!";
        		_status = errorText;
        	}
        	
        	status_txt.text = _status;
        	flag.load('http://demo.pyamf.org/icons/flags/' + _flag + '.png');
        }
        
        private function onFault( error:* ): void
        {
            // notify the user of the problem
            var errorStr:String = "";
            for (var d:String in error) {
               errorStr += error[d] + "\n";
            }
            
            mx.controls.Alert.show(errorStr, "Remoting error");
        }
		
	}
}