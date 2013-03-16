/*
 * jQuery UI @VERSION
 *
 * Copyright (c) 2008 Paul Bakaus (ui.jquery.com)
 * Dual licensed under the MIT (MIT-LICENSE.txt)
 * and GPL (GPL-LICENSE.txt) licenses.
 *
 * http://docs.jquery.com/UI
 *
 * $Id: ui.core.js 5587 2008-05-13 19:56:42Z scott.gonzalez $
 */
;(function($) {

$.ui = {
	plugin: {
		add: function(module, option, set) {
			var proto = $.ui[module].prototype;
			for(var i in set) {
				proto.plugins[i] = proto.plugins[i] || [];
				proto.plugins[i].push([option, set[i]]);
			}
		},
		call: function(instance, name, args) {
			var set = instance.plugins[name];
			if(!set) { return; }
			
			for (var i = 0; i < set.length; i++) {
				if (instance.options[set[i][0]]) {
					set[i][1].apply(instance.element, args);
				}
			}
		}	
	},
	cssCache: {},
	css: function(name) {
		if ($.ui.cssCache[name]) { return $.ui.cssCache[name]; }
		var tmp = $('<div class="ui-resizable-gen">').addClass(name).css({position:'absolute', top:'-5000px', left:'-5000px', display:'block'}).appendTo('body');
		
		//if (!$.browser.safari)
			//tmp.appendTo('body'); 
		
		//Opera and Safari set width and height to 0px instead of auto
		//Safari returns rgba(0,0,0,0) when bgcolor is not set
		$.ui.cssCache[name] = !!(
			(!(/auto|default/).test(tmp.css('cursor')) || (/^[1-9]/).test(tmp.css('height')) || (/^[1-9]/).test(tmp.css('width')) || 
			!(/none/).test(tmp.css('backgroundImage')) || !(/transparent|rgba\(0, 0, 0, 0\)/).test(tmp.css('backgroundColor')))
		);
		try { $('body').get(0).removeChild(tmp.get(0));	} catch(e){}
		return $.ui.cssCache[name];
	},
	disableSelection: function(e) {
		e.unselectable = "on";
		e.onselectstart = function() { return false; };
		if (e.style) { e.style.MozUserSelect = "none"; }
	},
	enableSelection: function(e) {
		e.unselectable = "off";
		e.onselectstart = function() { return true; };
		if (e.style) { e.style.MozUserSelect = ""; }
	},
	hasScroll: function(e, a) {
		var scroll = /top/.test(a||"top") ? 'scrollTop' : 'scrollLeft', has = false;
		if (e[scroll] > 0) return true; e[scroll] = 1;
		has = e[scroll] > 0 ? true : false; e[scroll] = 0;
		return has;
	}
};


/** jQuery core modifications and additions **/

var _remove = $.fn.remove;
$.fn.remove = function() {
	$("*", this).add(this).trigger("remove");
	return _remove.apply(this, arguments );
};

// $.widget is a factory to create jQuery plugins
// taking some boilerplate code out of the plugin code
// created by Scott González and Jörn Zaefferer
function getter(namespace, plugin, method) {
	var methods = $[namespace][plugin].getter || [];
	methods = (typeof methods == "string" ? methods.split(/,?\s+/) : methods);
	return ($.inArray(method, methods) != -1);
}

var widgetPrototype = {
	init: function() {},
	destroy: function() {
		this.element.removeData(this.widgetName);
	},
	
	getData: function(key) {
		return this.options[key];
	},
	setData: function(key, value) {
		this.options[key] = value;
	},
	
	enable: function() {
		this.setData('disabled', false);
	},
	disable: function() {
		this.setData('disabled', true);
	}
};

$.widget = function(name, prototype) {
	var namespace = name.split(".")[0];
	name = name.split(".")[1];
	// create plugin method
	$.fn[name] = function(options) {
		var isMethodCall = (typeof options == 'string'),
			args = Array.prototype.slice.call(arguments, 1);
		
		if (isMethodCall && getter(namespace, name, options)) {
			var instance = $.data(this[0], name);
			return (instance ? instance[options].apply(instance, args)
				: undefined);
		}
		
		return this.each(function() {
			var instance = $.data(this, name);
			if (!instance) {
				$.data(this, name, new $[namespace][name](this, options));
			} else if (isMethodCall) {
				instance[options].apply(instance, args);
			}
		});
	};
	
	// create widget constructor
	$[namespace][name] = function(element, options) {
		var self = this;
		
		this.widgetName = name;
		
		this.options = $.extend({}, $[namespace][name].defaults, options);
		this.element = $(element)
			.bind('setData.' + name, function(e, key, value) {
				return self.setData(key, value);
			})
			.bind('getData.' + name, function(e, key) {
				return self.getData(key);
			})
			.bind('remove', function() {
				return self.destroy();
			});
		this.init();
	};
	
	// add widget prototype
	$[namespace][name].prototype = $.extend({}, widgetPrototype, prototype);
};


/** Mouse Interaction Plugin **/

$.ui.mouse = {
	mouseInit: function() {
		var self = this;
	
		this.element.bind('mousedown.'+this.widgetName, function(e) {
			return self.mouseDown(e);
		});
		
		// Prevent text selection in IE
		if ($.browser.msie) {
			this._mouseUnselectable = this.element.attr('unselectable');
			this.element.attr('unselectable', 'on');
		}
		
		this.started = false;
	},
	
	// TODO: make sure destroying one instance of mouse doesn't mess with
	// other instances of mouse
	mouseDestroy: function() {
		this.element.unbind('.'+this.widgetName);
		
		// Restore text selection in IE
		($.browser.msie
			&& this.element.attr('unselectable', this._mouseUnselectable));
	},
	
	mouseDown: function(e) {
		// we may have missed mouseup (out of window)
		(this._mouseStarted && this.mouseUp(e));
		
		this._mouseDownEvent = e;
		
		var self = this,
			btnIsLeft = (e.which == 1),
			elIsCancel = ($(e.target).is(this.options.cancel));
		if (!btnIsLeft || elIsCancel) {
			return true;
		}
		
		this._mouseDelayMet = !this.options.delay;
		if (!this._mouseDelayMet) {
			this._mouseDelayTimer = setTimeout(function() {
				self._mouseDelayMet = true;
			}, this.options.delay);
		}
		
		// these delegates are required to keep context
		this._mouseMoveDelegate = function(e) {
			return self.mouseMove(e);
		};
		this._mouseUpDelegate = function(e) {
			return self.mouseUp(e);
		};
		$(document)
			.bind('mousemove.'+this.widgetName, this._mouseMoveDelegate)
			.bind('mouseup.'+this.widgetName, this._mouseUpDelegate);
		
		return false;
	},
	
	mouseMove: function(e) {
		// IE mouseup check - mouseup happened when mouse was out of window
		if ($.browser.msie && !e.button) {
			return this.mouseUp(e);
		}
		
		if (this._mouseStarted) {
			this.mouseDrag(e);
			return false;
		}
		
		if (this.mouseDistanceMet(e) && this.mouseDelayMet(e)) {
			this._mouseStarted =
				(this.mouseStart(this._mouseDownEvent, e) !== false);
			(this._mouseStarted || this.mouseUp(e));
		}
		
		return !this._mouseStarted;
	},
	
	mouseUp: function(e) {
		$(document)
			.unbind('mousemove.'+this.widgetName, this._mouseMoveDelegate)
			.unbind('mouseup.'+this.widgetName, this._mouseUpDelegate);
		
		if (this._mouseStarted) {
			this._mouseStarted = false;
			this.mouseStop(e);
		}
		
		return false;
	},
	
	mouseDistanceMet: function(e) {
		return (Math.max(
				Math.abs(this._mouseDownEvent.pageX - e.pageX),
				Math.abs(this._mouseDownEvent.pageY - e.pageY)
			) >= this.options.distance
		);
	},
	
	mouseDelayMet: function(e) {
		return this._mouseDelayMet;
	},
	
	// These are placeholder methods, to be overriden by extending plugin
	mouseStart: function(e) {},
	mouseDrag: function(e) {},
	mouseStop: function(e) {}
};

$.ui.mouse.defaults = {
	cancel: null,
	distance: 0,
	delay: 0
};

})(jQuery);

/*
 * jQuery UI Stepper
 *
 * Copyright (c) 2008 Ca Phun Ung <caphun at yelotofu dot com>
 * Dual licensed under the MIT (MIT-LICENSE.txt)
 * and GPL (GPL-LICENSE.txt) licenses.
 *
 * http://yelotofu.com/labs/jquery/UI/stepper
 *
 * Depends: 
 *	ui.core.js 
 *	jquery.mousewheel.js
 *
 */
;(function($) {

$.widget("ui.stepper", {
	plugins: {},
	
	ui: function(e) {
		return {
			instance: this,
			options: this.options,
			element: this.element
		};
	},
	
	keys: {
		BACK: 8,
		TAB: 9,
		LEFT: 37,
		UP: 38,
		RIGHT: 39,
		DOWN: 40,
		PGUP: 33,
		PGDN: 34,
		HOME: 36,
		END: 35,
		PERIOD: 190,
		MINUS: 109,
		NUMPAD_DECIMAL: 110,
		NUMPAD_SUBTRACT: 109
	},
	
	init: function() {
		var self = this;
		this.element[0].value = this.options.start;
		this.element[0].textbox = $('input[type="text"]', this.element[0]);
		
		// check for decimals in step size
		if (this.options.step.toString().indexOf('.') != -1) {
			var s = this.options.step.toString();
			this.setData('decimals', s.slice(s.indexOf('.')+1, s.length).length);
		}
		
		this.element.each(function(){
			var ns = $(this);
			var textbox = $('input[type="text"]', ns); // get the input textbox
			var bup = $('.ui-stepper-plus', ns); // plus button
			var bdn = $('.ui-stepper-minus', ns); // minus button
			
			self.element[0].value = self.value(textbox.val());
			
			if (textbox.length > 0){
				if (self.element[0].value == '' || isNaN(self.element[0].value)) {
					textbox.val(self.format(self.options.start));
					self.element[0].value = self.value(textbox.val());
				}
				
				// detect key presses and restrict to numeric values only
				textbox
					.bind("keydown.stepper", function(e) {
						if(!self.counter) self.counter = 1;
						return self.keydown(e);
					})
					.bind("keyup.stepper", function(e) {
						if (e.keyCode !== self.keys.BACK && e.keyCode !== self.keys.MINUS && e.keyCode !== self.keys.PERIOD) {
							var val = self.value(this.value);
							var dif = parseFloat(val) % parseFloat(self.options.step);
							if (dif !== 0) {
								val = parseFloat(val) + (parseFloat(self.options.step) - parseFloat(dif));
							}
							if (val < self.options.min) val = self.options.min;
							if (val > self.options.max) val = self.options.max;
							self.element[0].value = self.value(val);
							this.value = self.format(val);
						}
						self.counter = 0;
						self.propagate("change", e);
					})
					// detect when textbox loses cursor focus
					.bind('blur', function(e){
						if (this.value < self.options.min) this.value = self.options.min;
						if (this.value > self.options.max) this.value = self.options.max;
						if (this.value === '') this.value = self.options.start;
					})
					.bind('mousewheel', function(e, delta){
						if (delta > 0)
							self.spin(self.options.step);
						else if (delta < 0)
							self.spin(-self.options.step);
						return false;
					})
					.attr('autocomplete', 'off') // turns off autocomplete in opera!
				;
				
			}
			
			// convert button type to button to prevent form submission onclick
			if (bup.attr('type') == 'submit') {
				try {
					bup.removeAttr('type');
					bup.attr('type', 'button');
				} catch(ex) {
					// IE fix
					bup.each(function(){
						this.removeAttribute('type');
						this.setAttribute('type','button');
					});
				}
			}
			//bup.click(function(){stepper(self.options.step);});
			bup
				.bind('mousedown', function(){
					self.mousedown(100, self.options.step);
				})
				.bind('mouseup', function(e){
					self.mouseup(e);
				})
				.bind('click', function(e){
					self.spin(self.options.step);
				})
				.bind('keyup', function(e) {
					var keynum = (window.event ? event.keyCode : (e.which ? e.which : null));
					switch (keynum) {
						// (prev object)
						case self.keys.UP :
						case self.keys.LEFT :
							textbox.focus(); break;
						// (next object)
						case self.keys.DOWN :
						case self.keys.RIGHT :
							bdn.focus(); break;
					}
				})
			;
			
			// convert button type to button to prevent form submission onclick
			if (bdn.attr('type') == 'submit') {
				try {
					bdn.removeAttr('type');
					bdn.attr('type', 'button');
				} catch(e) {
					// IE fix
					bdn.each(function(){
						this.removeAttribute('type');
						this.setAttribute('type','button');
					});
				}
			}
			bdn
				.bind('mousedown' ,function(){
					self.mousedown(100, -self.options.step);
				})
				.bind('mouseup', function(e){
					self.mouseup(e);
				})
				.bind('click', function(e){
					self.spin(-self.options.step);
				})
				.bind('keyup', function(e){
					var keynum = (window.event ? event.keyCode : (e.which ? e.which : null));
					switch (keynum) {
						// (prev object)
						case self.keys.UP :
						case self.keys.LEFT :
							bup.focus();
							break;
						// (next object)
						case self.keys.DOWN :
						case self.keys.RIGHT :
							break;
					}
				})
			;
		});
	},

	spin: function(val){
		var textbox = this.element[0].textbox;
		if (textbox == undefined)
			return false;
		
		if (val == undefined || isNaN(val))
			val = 1;

		var textboxVal = this.value(textbox.val());
		textboxVal = parseFloat(textboxVal) + parseFloat(val);
		
		if (isNaN(textboxVal)) textboxVal = this.options.start;
		if (textboxVal < this.options.min) textboxVal = this.options.min;
		if (textboxVal > this.options.max) textboxVal = this.options.max;
		
		textbox.val(this.format(textboxVal));
		this.element[0].value = textboxVal;
	},
	
	number: function(num, dec) {
		return Math.round(parseFloat(num)*Math.pow(10, dec)) / Math.pow(10, dec);
	},
	
	currency: function(num) {
		var s = this.number(num, 2).toString();
		var dot = parseInt(s).toString().length+1;
		s = s + ((s.indexOf('.') == -1) ? '.' : '') + '0000000001';
		s = s.substr(0, dot) + s.substr(dot, 2);
		return this.options.symbol + s;
	},
	
	value: function(val) {
		val = val.toString();
		return (this.options.format == 'currency') ? val.slice(this.options.symbol.length, val.length) : val;
	},
	
	format: function(val) {
		return (this.options.format == 'currency') ? this.currency(val) : this.number(val, this.options.decimals);
	},
	
	mousedown: function(i, val) {
		var self = this;
		i = i || 100;
		if(this.timer) window.clearInterval(this.timer);
		this.timer = window.setInterval(function() {
			self.spin(val);
			if(self.counter > 20) self.mousedown(20, val);
		}, i);
	},

	mouseup: function(e) {
		this.counter = 0;
		if(this.timer) 
			window.clearInterval(this.timer);
		this.propagate("change", e);
	},

	keydown: function(e) {
		if(this.upKey(e.keyCode)) this.spin(this.options.step);
		if(this.downKey(e.keyCode)) this.spin(-this.options.step);
		return this.allowedKey(e.keyCode);
	},
	
	upKey: function(key){
		return (key === this.keys.UP || key === this.keys.PGUP) ? true : false;
	},

	downKey: function(key){
		return (key === this.keys.DOWN || key === this.keys.PGDN) ? true : false;
	},
	
	allowedKey: function(key){
		// add support for numeric keys 0-9
		if (key >= 96 && key <= 105) {
			key = 'NUMPAD';
		}
		
		switch (key) {
			case this.keys.TAB :
			case this.keys.BACK :
			case this.keys.LEFT :
			case this.keys.RIGHT :
			case this.keys.PERIOD :
			case this.keys.MINUS :
			case this.keys.NUMPAD_DECIMAL :
			case this.keys.NUMPAD_SUBTRACT :
			case 'NUMPAD' :
				return true;
			default : 
				return (/[0-9\-\.]/).test(String.fromCharCode(key));
		}
	},

	propagate: function(n,e) {
		$.ui.plugin.call(this, n, [e, this.ui()]);
		return this.element.triggerHandler(n == "step" ? n : "step"+n, [e, this.ui()], this.options[n]);
	}
	
});

$.ui.stepper.defaults = {
	min: 0,
	max: 10,
	step: 1,
	start: 0,
	decimals: 0,
	format: '',
	symbol: '$'
};

})(jQuery);