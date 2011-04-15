// Copyright 2009 Google Inc.  All Rights Reserved.

/**
 * A multipart form data construction class for XHR.
 * @see http://www.w3.org/Protocols/rfc1341/7_2_Multipart.html
 * @constructor
 */
var MultipartFormData = function() {
  /**
   * @type {Array}
   */
  this.headers = [];

  /**
   * @type {Array}
   */
  this.parts = [];

  /**
   * A random string for the boundary.
   * @type {string}
   */
  this.boundary = MultipartFormData.getRandomBoundary();
};


/**
 * @type {string}
 */
MultipartFormData.CRLF = '\r\n';


/**
 * @type {string}
 * @private
 */
MultipartFormData.TEN_CHARS_ =


/**
 * Generates a random number and some random characters from it.
 */
MultipartFormData.getRandomBoundary = function() {
  var anyTenCharacters = 'DiStRIcT10';
  var randomNumber = Math.floor(Math.random() * 10000000);
  var nums = randomNumber.toString().split('');
  var randomChars = '';
  for (var i = 0, num; num = nums[i]; i++) {
    randomChars += anyTenCharacters[num];
  }
  return randomChars + '-' + randomNumber;
};


/**
 * @param {string} name The name for this header.
 * @param {string} value The value for this header.
 */
MultipartFormData.prototype.addHeader = function(name, value) {
  this.headers.push({
    'name': name,
    'value': value
  });
};


/**
 * @param {?string} name The name for this part.
 * @param {string} value The value for this part.
 * @param {string} opt_contentType Content-type for this part.
 * @param {string} opt_contentDisposition Content disposition for this part.
 * @param {string} opt_filename The filename for this part
 */
MultipartFormData.prototype.addPart = function(name, value, opt_contentType,
    opt_contentDisposition, opt_filename) {
  var contentType = opt_contentType || null;
  var contentDisposition = opt_contentDisposition || null;
  var filename = opt_filename || null;
  this.parts.push({
    'name': name,
    'value': value,
    'contentType': contentType,
    'contentDisposition': contentDisposition,
    'filename': filename
  });
};

/**
 * @return {string} The string to set as a payload.
 */
MultipartFormData.prototype.toString = function() {
  var lines = [];

  for (var i = 0, header; header = this.headers[i]; i++) {
    lines.push(header['name'] + ': ' + header['value']);
  }
  if (this.headers.length > 0) {
    lines.push('');
  }

  for (var i = 0, part; part = this.parts[i]; i++) {
    lines.push('--' + this.boundary);

    if (part['contentDisposition']) {
      var contentDisposition = 'Content-Disposition: form-data; ';
      contentDisposition += 'name="' + part['name'] + '"';
      if (part['filename']) {
        contentDisposition += '; filename="' + part['filename'] + '"';
      }
      lines.push(contentDisposition);
    }

    if (part['contentType']) {
      lines.push('Content-Type: ' + part['contentType']);
    }

    lines.push('');
    lines.push(part['value']);
  }

  lines.push('--' + this.boundary + '--');

  return lines.join(MultipartFormData.CRLF) + MultipartFormData.CRLF;
};

