/* http://keith-wood.name/timeEntry.html
   Vietnamese template for the jQuery time entry extension
   Written by Le Thanh Huy (lthanhhuy@cit.ctu.edu.vn). */
(function($) {
	$.timeEntry.regional['vi'] = {show24Hours: false, separator: ':',
		ampmPrefix: '', ampmNames: ['AM', 'PM'],
		spinnerTexts: ['Hiện tại', 'Mục trước', 'Mục sau', 'Tăng', 'Giảm']};
	$.timeEntry.setDefaults($.timeEntry.regional['vi']);
})(jQuery);

