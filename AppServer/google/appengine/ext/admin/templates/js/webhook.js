// Copyright 2009 Google Inc.  All Rights Reserved.

function Webhook(formId) {
  this.formId = formId;
  this.action = null;
  this.headers = {};
  this.method = null;
  this.payload = null;
};

Webhook.prototype.HEADER_KEY = 'header:';

Webhook.prototype.parse = function() {
  var form = document.getElementById(this.formId);
  if (form == null) {
    return 'could not find form with id "' + this.formId + '"';
  }
  this.action = form.action;
  this.method = form.method;
  for (var i = 0, n = form.elements.length; i < n; i++) {
    var currentElement = form.elements[i];
    if (currentElement.tagName != 'INPUT' ||
        currentElement.type.toUpperCase() != 'HIDDEN') {
      continue;
    }
    var key = currentElement.name;
    var value = currentElement.value;
    var headerIndex = key.indexOf(this.HEADER_KEY);
    if (headerIndex == 0) {
      var header = key.substr(this.HEADER_KEY.length);
      if (this.headers[header] === undefined) {
        this.headers[header] = [value];
      } else {
        this.headers[header].push(value);
      }
    } else if (key == 'payload') {
      this.payload = value;
    }
  }

  if (this.action == '') {
    return 'action not found';
  }
  if (this.method == '') {
    return 'method not found';
  }
  return '';
};

Webhook.prototype.send = function(callback) {
  var req = null;
  if (window.XMLHttpRequest) {
    req = new XMLHttpRequest();
  } else if (window.ActiveXObject) {
    req = new ActiveXObject('MSXML2.XMLHTTP.3.0');
  }

  try {
    req.open(this.method, this.action, false);
    for (var key in this.headers) {
      // According to the W3C, multiple calls to setRequestHeader should result
      // in a single header with comma-seperated values being set (see
      // http://www.w3.org/TR/2009/WD-XMLHttpRequest-20090820/). Unfortunately,
      // both FireFox 3 and Konqueror 3.5 set the header value to the value in
      // the last call to setRequestHeader so the joined header is generated
      // manually. The equivalence of headers with comma-separated values and
      // repeated headers is described here:
      // http://www.w3.org/Protocols/rfc2616/rfc2616-sec4.html#sec4.2
      req.setRequestHeader(key, this.headers[key].join(', '));
    }
    req.send(this.payload);
  } catch (e) {
    callback(this, req, e);
    return;
  }

  // If the responseText matches our <form action="/_ah/login then the
  // user is not logged in as an Administrator so we'll fake the request.
  if (req.responseText.match(/<form[^>]+_ah\/login/)) {
    var fakeReq = {
      'status': 403,
      'responseText': 'Current logged in user is not authorized ' +
                      'to view this page'
    }
    fakeReq.getAllResponseHeaders = function(){};
    callback(this, fakeReq, null);
  } else {
    callback(this, req, null);
  }
};

Webhook.prototype.run = function(callback) {
  var error = this.parse();
  if (error != '') {
    callback(this, null, error);
  } else {
    this.send(callback);
  }
};
