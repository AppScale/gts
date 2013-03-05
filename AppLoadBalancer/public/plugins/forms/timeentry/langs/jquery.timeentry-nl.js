/* http://keith-wood.name/timeEntry.html
   Dutch initialisation written for the jQuery time entry extension.
   Glenn plas (glenn.plas@telenet.be) March 2008. */
(function($) {
	$.timeEntry.regional['nl'] = {show24Hours: true, separator: ':',
		ampmPrefix: '', ampmNames: ['AM', 'PM'],
		spinnerTexts: ['Nu', 'Vorig veld', 'Volgend veld','Verhoog', 'Verlaag']};
	$.timeEntry.setDefaults($.timeEntry.regional['nl']);
})(jQuery);
