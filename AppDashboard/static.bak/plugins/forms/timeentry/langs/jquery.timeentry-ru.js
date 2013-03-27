/* http://keith-wood.name/timeEntry.html
   Russian (UTF-8) initialisation for the jQuery $.timeEntry extension.
   Written by Andrew Stromnov (stromnov@gmail.com). */
(function($) {
	$.timeEntry.regional['ru'] = {show24Hours: true, separator: ':',
		ampmPrefix: '', ampmNames: ['AM', 'PM'],
		spinnerTexts: ['Сейчас', 'Предыдущее поле', 'Следующее поле', 'Больше', 'Меньше']};
	$.timeEntry.setDefaults($.timeEntry.regional['ru']);
})(jQuery);
