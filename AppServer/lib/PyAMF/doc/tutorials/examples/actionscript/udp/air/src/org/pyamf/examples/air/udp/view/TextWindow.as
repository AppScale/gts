package org.pyamf.examples.air.udp.view
{
	import flash.desktop.NativeApplication;
	import flash.display.NativeWindow;
	import flash.display.NativeWindowInitOptions;
	import flash.display.NativeWindowResize;
	import flash.display.NativeWindowSystemChrome;
	import flash.display.Sprite;
	import flash.display.StageAlign;
	import flash.display.StageDisplayState;
	import flash.display.StageScaleMode;
	import flash.events.ContextMenuEvent;
	import flash.events.Event;
	import flash.events.FullScreenEvent;
	import flash.events.MouseEvent;
	import flash.events.NativeWindowBoundsEvent;
	import flash.geom.Point;
	import flash.text.TextField;
	import flash.text.TextFieldAutoSize;
	import flash.text.TextFormat;
	import flash.text.TextFormatAlign;
	import flash.ui.ContextMenu;
	import flash.ui.ContextMenuItem;

	public class TextWindow extends NativeWindow
	{
		private static const GRIPPER_SIZE	: uint = 20;
		private static const PADDING_LEFT	: Number = 10;
		private static const PADDING_RIGHT	: Number = 10;
		private static const PADDING_TOP	: Number = 10;
		private static const PADDING_BOTTOM	: Number = 10;
		private static const VERTICAL_GAP	: Number = 10;
		
		private var background				: Sprite;
		private var traffic					: TextField;
		private var output					: TextField;

		private var fullScreenMenuItem		: ContextMenuItem;
		private var onTopMenuItem			: ContextMenuItem;
		private var exitMenuItem			: ContextMenuItem;
		
		public function get connection():String
		{
			return output.text;
		}
		
		public function set connection( val:String ):void
		{
			if (val)
			{
				output.text = val;
			}
		}
		
		public function get text():String
		{
			return traffic.text;
		}
		
		public function set text( val:String ):void
		{
			if (val)
			{
				traffic.text = val;
				updateScroll();
			}
		}
		
		/**
		 * Constructor.
		 *  
		 * @param width
		 * @param height
		 * @param x
		 * @param y
		 */		
		public function TextWindow( width:uint=580, height:uint=350, x:uint=50, y:uint=50 )
		{
			// setup AIR
			var winArgs:NativeWindowInitOptions = new NativeWindowInitOptions();
			winArgs.systemChrome = NativeWindowSystemChrome.NONE;
			winArgs.transparent = true;
			super( winArgs );
			
			title = "UDP Example for PyAMF";
			activate();

			// Configure the window
			alwaysInFront = false;
			minSize = new Point( 30,30 );
			maxSize = new Point( 2000, 2000 );
			
			this.x = x;
			this.y = y;
			this.width = width;
			this.height = height;

			// Create the background
			background = new Sprite();
			draw();

			// Configure the context menu
			configureContextMenu();

			// Configure the stage
			stage.align = StageAlign.TOP_LEFT;
			stage.scaleMode = StageScaleMode.NO_SCALE;
			stage.addChild( background );

			// Set up event listeners
			addEventListener(Event.RESIZE, onWindowResize);
			background.addEventListener(MouseEvent.MOUSE_DOWN, onMouseDown);
			stage.addEventListener(FullScreenEvent.FULL_SCREEN, onFullScreen);
			
			// add textfields
			traffic = createTextField( TextFieldAutoSize.NONE,
									   TextFormatAlign.RIGHT );
			traffic.height = 300;
			output = createTextField();
			background.addChild( output );
			background.addChild( traffic );
			
			updateDimensions(width, height);
			visible = true;
		}
		
		private function draw():void
		{
			// UI
			background.graphics.clear();
			background.alpha = .83;
			background.useHandCursor = true;
			background.buttonMode = true;
			background.graphics.beginFill(0x000000);
			background.graphics.drawRoundRect(0,0,this.width,this.height, 20, 20);
			background.graphics.endFill();
		}
		
		private function configureContextMenu():void
		{
			stage.showDefaultContextMenu = true;
			var cm:ContextMenu = new ContextMenu();
			cm.hideBuiltInItems();
			
			fullScreenMenuItem = new ContextMenuItem("Full Screen");
			onTopMenuItem = new ContextMenuItem("Keep On Top");
			exitMenuItem = new ContextMenuItem("Exit");
			
			fullScreenMenuItem.addEventListener(ContextMenuEvent.MENU_ITEM_SELECT, onFullScreenMenuItem);
			onTopMenuItem.addEventListener(ContextMenuEvent.MENU_ITEM_SELECT, toggleAlwaysInFront);
			exitMenuItem.addEventListener(ContextMenuEvent.MENU_ITEM_SELECT, onExitMenuItem);
			cm.customItems.push(fullScreenMenuItem);
			cm.customItems.push(onTopMenuItem);
			cm.customItems.push(exitMenuItem);
			background.contextMenu = cm;
		}
		
		/**
		 * @param autoSize
		 * @param align
		 * @return 
		 */		
		private function createTextField( autoSize:String=null,
										  align:String=TextFormatAlign.LEFT):TextField
		{
			var fmt:TextFormat = new TextFormat();
			fmt.font = "Arial";
			fmt.color = 0x3366ff;
			fmt.align = align;
			fmt.size = 12;
			fmt.bold = false;
			
			if (autoSize == null)
			{
				autoSize = TextFieldAutoSize.LEFT;
				fmt.color = 0xFFFFFF;
			}
			
			var txt:TextField = new TextField();
			txt.mouseEnabled = false;
			txt.embedFonts = false;
			txt.autoSize = autoSize;
			txt.border = false;
			txt.borderColor = 0xff0000;
			txt.selectable = false;
			txt.multiline = true;
			txt.wordWrap = true;
			txt.defaultTextFormat = fmt;
			
			return txt;
		}
		
		private function updateScroll( event:Event=null ):void
		{
			traffic.y = output.y + output.height + VERTICAL_GAP;
			traffic.scrollV = traffic.maxScrollV;
		}
		
		private function toggleAlwaysInFront( e:Event ):void
		{
			this.alwaysInFront = !this.alwaysInFront;
			this.onTopMenuItem.checked = this.alwaysInFront;
		}
		
		/**
		 * Handle the fullscreen mode toggle command in the context menu.
		 *  
		 * @param e
		 */		
		private function onFullScreenMenuItem(e:ContextMenuEvent):void
		{
			stage.displayState = (stage.displayState == StageDisplayState.NORMAL) ? StageDisplayState.FULL_SCREEN : StageDisplayState.NORMAL;
		}

		/**
		 * Handle the fullscreen event
		 *  
		 * @param e
		 */		
		private function onFullScreen(e:FullScreenEvent):void
		{
			fullScreenMenuItem.caption = (e.fullScreen) ? "Full Screen Off" : "Full Screen";
		}
		
		/**
		 * Handle the exit command in the context menu
		 *  
		 * @param e
		 */		
		private function onExitMenuItem(e:ContextMenuEvent):void
		{
			NativeApplication.nativeApplication.exit();
		}
		
		/**
		 * Update the label for the window dimensions
		 *  
		 * @param _width
		 * @param _height
		 */		
		private function updateDimensions(_width:int, _height:int):void
		{
			traffic.width = _width - (PADDING_RIGHT + PADDING_LEFT);
			traffic.height = _height - (300 - (PADDING_BOTTOM + PADDING_TOP));
			traffic.x = (_width / 2) - (traffic.width / 2);
			
			output.width = traffic.width;
			output.height = _height - (PADDING_BOTTOM + traffic.height);
			output.x = traffic.x;
			output.y = PADDING_TOP;
			
			updateScroll();
			draw();
		}
		
		/**
		 * Handle window mouse down events.
		 *  
		 * @param e
		 */		
		private function onMouseDown(e:Event):void
		{
			if (stage.mouseX >= 0 && stage.mouseX <= GRIPPER_SIZE &&
				stage.mouseY >= 0 && stage.mouseY <= GRIPPER_SIZE)
			{
				startResize(NativeWindowResize.TOP_LEFT);
			}
			else if (stage.mouseX <= this.width &&
					 stage.mouseX >= this.width - GRIPPER_SIZE &&
					 stage.mouseY >= 0 && stage.mouseY <= GRIPPER_SIZE)
			{
				startResize(NativeWindowResize.TOP_RIGHT);					
			}
			else if (stage.mouseX >= 0 &&
					 stage.mouseX <= GRIPPER_SIZE &&
					 stage.mouseY <= this.height &&
					 stage.mouseY >= this.height - GRIPPER_SIZE)
			{
				startResize(NativeWindowResize.BOTTOM_LEFT);					
			}
			else if (stage.mouseX <= this.width &&
					 stage.mouseX >= this.width - GRIPPER_SIZE &&
					 stage.mouseY <= this.height &&
					 stage.mouseY >= this.height - GRIPPER_SIZE)
			{
				startResize(NativeWindowResize.BOTTOM_RIGHT);					
			}
			else if (stage.mouseX >= 0 && stage.mouseX <= GRIPPER_SIZE)
			{
				startResize(NativeWindowResize.LEFT);					
			}
			else if (stage.mouseX >= this.width - GRIPPER_SIZE &&
					 stage.mouseX <= this.width)
			{
				startResize(NativeWindowResize.RIGHT);					
			}
			else if (stage.mouseY >= 0 && stage.mouseY <= GRIPPER_SIZE)
			{
				startResize(NativeWindowResize.TOP);					
			}
			else if (stage.mouseY >= this.height - GRIPPER_SIZE &&
				     stage.mouseY <= this.height)
			{
				startResize(NativeWindowResize.BOTTOM);					
			}
			else
			{
				startMove();
			}
		}
		
		/**
		 * Redraw the window when a resize event is dispatched.
		 *  
		 * @param e
		 */		
		private function onWindowResize(e:NativeWindowBoundsEvent):void
		{
			updateDimensions(e.afterBounds.width, e.afterBounds.height);
		}
		
	}
}