package org.pyamf.examples.bytearray
{
	/**
	 * Copyright (c) 2007-2009 The PyAMF Project.
	 * See LICENSE.txt for details.
	*/

	import flash.display.BitmapData;
	import flash.display.IBitmapDrawable;
	
	import mx.graphics.ImageSnapshot;
	import mx.graphics.codec.JPEGEncoder;

	public class Snapshot
	{
		private var _type		: String;
		private var _width		: int;
		private var _height 		: int;
		private var _data		: IBitmapDrawable;
		private var _bitmap		: BitmapData;
		private var _png		: ImageSnapshot;
		private var _jpg		: ImageSnapshot;
		private var _image		: ImageSnapshot;
			
		public function Snapshot( source:IBitmapDrawable, width:int=320, height:int=240, type:String="jpg" )
		{
			_width = width;
			_height = height;
			_data = source;
			_type = type;
		}

		
		public function get bitmap():BitmapData
		{
			_bitmap = ImageSnapshot.captureBitmapData(_data);

			return _bitmap;
		}
		
		public function get image():ImageSnapshot
		{
			if (_type == "jpg")
			{
			    _image = jpg;
			} else {
			    _image = png;
			}

			return _image;
		}
			
		public function get png(): ImageSnapshot
		{
			_png = ImageSnapshot.captureImage(_data);
			return _png;
		}
		
		public function get jpg(): ImageSnapshot
		{
			_jpg = ImageSnapshot.captureImage(_data, 0, new JPEGEncoder());
			return _jpg;
		}
		
	}
}