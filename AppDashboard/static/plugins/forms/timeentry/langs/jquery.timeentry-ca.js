/* http://keith-wood.name/timeEntry.html
   Catalan initialisation for the jQuery time entry extension
   Written by Gabriel Guzman (gabriel@josoft.com.ar). */
(function($) {
	$.timeEntry.regional['ca'] = {show24Hours: true, separator: ':',
		ampmPrefix: '', ampmNames: ['AM', 'PM'],
		spinnerTexts: ['Ara', 'Camp anterior', 'Següent camp', 'Augmentar', 'Disminuir']};
	$.timeEntry.setDefaults($.timeEntry.regional['ca']);
})(jQuery);
