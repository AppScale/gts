package org.pyamf.examples.bytearray
{
	/**
	 * Copyright (c) 2007-2009 The PyAMF Project.
	 * See LICENSE.txt for details.
	*/

	import flash.media.Camera;
	import flash.media.Video;
	import flash.net.NetConnection;
	import flash.net.Responder;
	
	import flash.events.IOErrorEvent;
	import flash.events.NetStatusEvent;
	import flash.events.SecurityErrorEvent;
	
	import mx.collections.ArrayCollection;
	import mx.controls.Button;
	import mx.controls.ComboBox;
	import mx.controls.DataGrid;
	import mx.controls.Image;
	import mx.controls.TextArea;
	import mx.core.Application;
	import mx.core.UIComponent;
	import mx.events.FlexEvent;
	
	/**
	 * This examples shows how to use the ByteArray class in
	 * ActionScript 3. Requires Flex 3 (for JPG/PNG encoders).
	 */
	public class ByteArrayExample extends Application
	{
		private var _cam			: Camera;
		private var _snapshot	: Snapshot;
		private var _gateway		: NetConnection;
		private var _video			: Video;
		private var _width			: int;
		private var _height			: int;
		private var _fps			: int;
		private var _fileTypes			: Array;
		private var _imageBaseUrl		: String;
		
		public var status_txt		: TextArea;
		public var videoWindow		: UIComponent;
		public var img				: Image;
		public var btn				: Button;
		public var dg				: DataGrid;
		public var img_type			: ComboBox;
		
		[Bindable]
		public var snapshots		: ArrayCollection;
		
		public function ByteArrayExample()
		{
			super();
			addEventListener(FlexEvent.APPLICATION_COMPLETE, onInitApp);
		}
		
		private function onInitApp(event:FlexEvent): void
		{
			// setup video properties
			_width = 320;
			_height = 240;
			_fps = 15;
			
			// setup ui
			btn.enabled = img_type.enabled = false;
	 		img_type.dataProvider = ['Loading...'];

			// Setup snapshot feature
            		if ( Camera.names.length == 0 ) 
            		{
            			status_txt.text = "No camera devices found on this system.\n";
           		} 
            		else
            		{
            			// Enable camera and video
	            		_cam = Camera.getCamera();
	            		_cam.setMode(_width, _height, _fps);
	            		_video = new Video(_width, _height);
	            		_video.attachCamera(_cam);
	            		videoWindow.width = _width;
				videoWindow.height = _height;
	            		videoWindow.addChild(_video);
	            
	           		status_txt.text = "Started " + _cam.name + "\n";
            		}

			// setup connection
            _gateway = new NetConnection();
			
            // Connect to gateway (Django needs trailing slash)
            _gateway.connect("http://localhost:8000/");
            
            // addEventListeners for IOErrors and gateway script errors
            _gateway.addEventListener(IOErrorEvent.IO_ERROR, onFault);
	    _gateway.addEventListener(SecurityErrorEvent.SECURITY_ERROR, onFault);
            _gateway.addEventListener(NetStatusEvent.NET_STATUS, onFault);
            
            // Set responder property to the object and methods that will receive the 
            // result or fault condition that the service returns.
            var responder:Responder = new Responder( onSnapshotsResult, onFault );

            // Call remote service to fetch data
	    status_txt.text += "Loading snapshots...\n";
            _gateway.call("getSnapshots", responder);
            
            
		}
		
		public function showPhoto(): void 
		{
			if (dg.selectedItem != null)
			{
				img.load(_imageBaseUrl + dg.selectedItem.name);
			}
		}
		
		public function createSnapshot(): void
		{
			btn.enabled = img_type.enabled = false;
			// create snapshot
			_snapshot = new Snapshot(_video, _video.width, _video.height,
						 img_type.selectedLabel);
			
			// save snapshot
			saveSnapshot();
		}
		
		private function saveSnapshot(): void
		{
            // set responder property to the object and methods that will receive the 
            // result or fault condition that the service returns.
            var responder:Responder = new Responder( onSaveResult, onFault );
            
            // call remote service to save image wrapped in ByteArray.
            _gateway.call( "ByteArray.saveSnapshot", responder, _snapshot.image.data,
			   img_type.selectedLabel );
            
            // wait for result.
            status_txt.text += "\nSaving snapshot...\n";
            btn.enabled = img_type.enabled = false;
		}
		
		private function onSnapshotsResult( result:Object ): void
        {
        	_imageBaseUrl = result[0];
		_fileTypes = result[1];
		img_type.dataProvider = _fileTypes;

		// add snapshots to list
           	snapshots = result[2];

		var total:int = snapshots.length;
		var status:String = "Loaded " + total + " snapshot";
		if (total == 0)
                {
		    status = "No snapshots found";
		} else if (total > 1)
                {
                    status += 's';
		}

           	status_txt.text += status + ".\n";		
		btn.enabled = img_type.enabled = true;
        }
        
	public function updateScroll(event:FlexEvent=null):void
	{
		status_txt.verticalScrollPosition = status_txt.maxVerticalScrollPosition;
	}
	
        private function onSaveResult( res:Object ): void
        {
            var snapshot:Object = res;
            status_txt.text += "Saved as " + snapshot.name + "\n";
	    
            // add url to list
            snapshots.addItemAt(snapshot, 0);
            btn.enabled = img_type.enabled = true;
        }
        
        private function onFault( error:* ): void
        {
            // notify the user of the problem
            status_txt.text = "Error!\n";
            for ( var d:String in error ) {
               status_txt.text += error[d] + "\n";
            }
            btn.enabled = img_type.enabled = false;
        }
		
	}
}