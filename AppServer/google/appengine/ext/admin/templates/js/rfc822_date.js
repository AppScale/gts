// Copyright 2009 Google Inc.  All Rights Reserved.

var RFC822Date = {};

/**
 * Return a DateTime in RFC822 format.
 * @see http://www.w3.org/Protocols/rfc822/#z28
 * @param {Date} date A Date object.
 * @param {string} opt_tzo The timezone offset.
 */
RFC822Date.format = function(date, opt_tzo) {
  var tzo = opt_tzo || RFC822Date.getTZO(date.getTimezoneOffset());
  var rfc822Date = RFC822Date.DAYS[date.getDay()] + ', ';
  rfc822Date += RFC822Date.padZero(date.getDate()) + ' ';
  rfc822Date += RFC822Date.MONTHS[date.getMonth()] + ' ';
  rfc822Date += date.getFullYear() + ' ';
  rfc822Date += RFC822Date.padZero(date.getHours()) + ':';
  rfc822Date += RFC822Date.padZero(date.getMinutes()) + ':';
  rfc822Date += RFC822Date.padZero(date.getSeconds()) + ' ' ;
  rfc822Date += tzo;
  return rfc822Date;
};


/**
 * @type {Array}
 */
RFC822Date.MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];


/**
 * @type {Array}
 */
RFC822Date.DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];


/**
 * Pads a value with a 0 if it is less than 10;
 * @param {number|string}
 * @return {string}
 */
RFC822Date.padZero = function(val) {
  val = val + ''; // cast into string
  if (val.length < 2) {
    val = '0' + val;
  }
  return val;
};


/**
 * Returns a timezone offset in the format +|-dddd.
 * @param {String} tzo A time zone offset from GMT in minutes.
 * @return {string} The time zone offset as a string.
 */
RFC822Date.getTZO = function(tzo) {
  var hours = Math.floor(tzo / 60);
  var tzoFormatted = hours > 0 ? '-' : '+';

  var absoluteHours = Math.abs(hours);
  tzoFormatted += absoluteHours < 10 ? '0' : '';
  tzoFormatted += absoluteHours;

  var moduloMinutes = Math.abs(tzo % 60);
  tzoFormatted += moduloMinutes == 0 ? '00' : moduloMinutes

  return tzoFormatted;
};

