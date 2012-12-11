package org.pyamf.examples.sharedobject
{
	import flash.events.IOErrorEvent;
	import flash.events.NetStatusEvent;
	import flash.events.SecurityErrorEvent;
	import flash.net.NetConnection;
	import flash.net.Responder;
	
	import mx.collections.ArrayCollection;
	import mx.controls.DataGrid;
	import mx.controls.TextArea;
	import mx.core.Application;
	import mx.events.FlexEvent;
	import mx.utils.ObjectUtil;

	/**
	 * Local Shared Objects browser with PyAMF.
	 * 
	 * @since: 0.3.2
	 */	
	public class SharedObjectExample extends Application
	{
		private var gateway:NetConnection;
		
		private static const gatewayURL:String = "http://localhost:8000";
		
		public var main_dg:DataGrid;
		public var sub_dg:DataGrid;
		public var details_txt:TextArea;
		
		[Bindable]
		public var apps:ArrayCollection;
		
		[Bindable]
		public var files:ArrayCollection;
		
		[Bindable]
		public var loading:Boolean = false;
		
		[Bindable]
		public var path:String = "Loading...";
		
		[Bindable]
		public var so_name:String;
		
		[Bindable]
		public var so_path:String;
		
		[Bindable]
		public var so_domain:String
		
		public function SharedObjectExample()
		{
			super();
			
			addEventListener(FlexEvent.APPLICATION_COMPLETE, onInit);
		}
		
		private function onInit(event:FlexEvent): void
		{
			// setup connection
			gateway = new NetConnection();
			
			gateway.addEventListener(SecurityErrorEvent.SECURITY_ERROR, onError);
			gateway.addEventListener(IOErrorEvent.IO_ERROR, onError);
			gateway.addEventListener(NetStatusEvent.NET_STATUS, onError);
			
			gateway.connect( gatewayURL );
			
			// get startup data
			refresh();
		}
		
		public function getTotalFiles(item:Object):String
		{
			return item.files.length;
		}
		
		public function refresh():void
		{
			loading = true;
			apps = new ArrayCollection();
			files = new ArrayCollection();
			path = "Loading...";
			so_name = so_path = so_domain = details_txt.text = "";
						
			var responder:Responder = new Responder(onGetFiles, onError);
			gateway.call('lso.getApps', responder);
		}
		
		public function showDetails():void
		{
			so_name = main_dg.selectedItem.name;
			so_path = main_dg.selectedItem.path;
			so_domain = main_dg.selectedItem.domain;
			
			files = new ArrayCollection(main_dg.selectedItem.files);
			sub_dg.selectedIndex = 0;
			viewFile();
		}
		
		public function viewFile():void
		{
			details_txt.text = "Loading...";
			
			var path:String = sub_dg.selectedItem.path;
			var responder:Responder = new Responder(onViewFile, onError);
			
			gateway.call('lso.getDetails', responder, path);
		}
         
		private function onGetFiles(event:*):void
		{
			apps = new ArrayCollection(event[1]);
			path = event[0];
			loading = false;
			
			if (apps.length > 0) {
				main_dg.selectedIndex = 0;
				showDetails();
			}
		}
		
		private function onViewFile(event:*):void
		{
			details_txt.text = ObjectUtil.toString(event);
		}
		
		private function onError(event:*):void
		{
			loading = false;
			details_txt.text = ObjectUtil.toString(event);
		}
		
	}
}