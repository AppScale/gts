/* http://keith-wood.name/timeEntry.html
   Simplified Chinese initialisation for the jQuery time entry extension.
   By Cloudream(cloudream@gmail.com) */
(function($) {
	$.timeEntry.regional['zh-CN'] = {show24Hours: false, separator: ':',
		ampmPrefix: '', ampmNames: ['AM', 'PM'],
		spinnerTexts: ['当前', '左移', '右移', '加一', '减一']};
	$.timeEntry.setDefaults($.timeEntry.regional['zh-CN']);
})(jQuery);
