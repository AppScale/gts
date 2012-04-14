// Copyright 2010 Google Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

/**
 * @fileoverview Render form appropriate for RPC method.
 * @author rafek@google.com (Rafe Kaplan)
 */


var FORM_VISIBILITY = {
  SHOW_FORM: 'Show Form',
  HIDE_FORM: 'Hide Form'
};


var LABEL = {
  OPTIONAL: 'OPTIONAL',
  REQUIRED: 'REQUIRED',
  REPEATED: 'REPEATED'
};


var objectId = 0;


/**
 * Variants defined in protorpc/messages.py.
 */
var VARIANT = {
  DOUBLE: 'DOUBLE',
  FLOAT: 'FLOAT',
  INT64: 'INT64',
  UINT64: 'UINT64',
  INT32: 'INT32',
  BOOL: 'BOOL',
  STRING: 'STRING',
  MESSAGE: 'MESSAGE',
  BYTES: 'BYTES',
  UINT32: 'UINT32',
  ENUM: 'ENUM',
  SINT32: 'SINT32',
  SINT64: 'SINT64'
};


/**
 * Data structure used to represent a form to data element.
 * @param {Object} field Field descriptor that form element represents.
 * @param {Object} container Element that contains field.
 * @return {FormElement} New object representing a form element.  Element
 *     starts enabled.
 * @constructor
 */
function FormElement(field, container) {
  this.field = field;
  this.container = container;
  this.enabled = true;
}


/**
 * Display error message in error panel.
 * @param {string} message Message to display in panel.
 */
function error(message) {
  $('<div>').appendTo($('#error-messages')).text(message);
}


/**
 * Display request errors in error panel.
 * @param {object} XMLHttpRequest object.
 */
function handleRequestError(response) {
  var contentType = response.getResponseHeader('content-type');
  if (contentType == 'application/json') {
      var response_error = $.parseJSON(response.responseText);
      var error_message = response_error.error_message;
      if (error.state == 'APPLICATION_ERROR' && error.error_name) {
          error_message = error_message + ' (' + error.error_name + ')';
      }
  } else {
      error_message = '' + response.status + ': ' + response.statusText;
  }

  error(error_message);
}


/**
 * Send JSON RPC to remote method.
 * @param {string} path Path of service on originating server to send request.
 * @param {string} method Name of method to invoke.
 * @param {Object} request Message to send as request.
 * @param {function} on_success Function to call upon successful request.
 */
function sendRequest(path, method, request, onSuccess) {
  $.ajax({url: path + '.' + method,
          type: 'POST',
          contentType: 'application/json',
          data: $.toJSON(request),
          dataType: 'json',
          success: onSuccess,
          error: handleRequestError
         });
}


/**
 * Create callback that enables and disables field element when associated
 * checkbox is clicked.
 * @param {Element} checkbox Checkbox that will be clicked.
 * @param {FormElement} form Form element that will be toggled for editing.
 * @param {Object} disableMessage HTML element to display in place of element.
 * @return Callback that is invoked every time checkbox is clicked.
 */
function toggleInput(checkbox, form, disableMessage) {
  return function() {
    var checked = checkbox.checked;
    if (checked) {
      buildIndividualForm(form);
      form.enabled = true;
      disableMessage.hide();
    } else {
      form.display.empty();
      form.enabled = false;
      disableMessage.show();
    }
  };
}


/**
 * Build an enum field.
 * @param {FormElement} form Form to build element for.
 */
function buildEnumField(form) {
  form.descriptor = enumDescriptors[form.field.type_name];
  form.input = $('<select>').
      appendTo(form.display);

  $('<option>').
      appendTo(form.input).attr('value', '').
      text('Select enum');
  $.each(form.descriptor.values, function(index, enumValue) {
      option = $('<option>');
      option.
          appendTo(form.input).
          attr('value', enumValue.name).
          text(enumValue.name);
      if (enumValue.number == form.field.default_value) {
        option.attr('selected', 1);
      }
  });
}


/**
 * Build nested message field.
 * @param {FormElement} form Form to build element for.
 */
function buildMessageField(form) {
  form.table = $('<table border="1">').appendTo(form.display);
  buildMessageForm(form, messageDescriptors[form.field.type_name]);
}


/**
 * Build boolean field.
 * @param {FormElement} form Form to build element for.
 */
function buildBooleanField(form) {
  form.input = $('<input type="checkbox">');
  form.input[0].checked = Boolean(form.field.default_value);
}


/**
 * Build text field.
 * @param {FormElement} form Form to build element for.
 */
function buildTextField(form) {
  form.input = $('<input type="text">');
  form.input.
      attr('value', form.field.default_value || '');
}


/**
 * Build individual input element.
 * @param {FormElement} form Form to build element for.
 */
function buildIndividualForm(form) {
  form.required = form.label == LABEL.REQUIRED;

  if (form.field.variant == VARIANT.ENUM) {
    buildEnumField(form);
  } else if (form.field.variant == VARIANT.MESSAGE) {
    buildMessageField(form);
  } else if (form.field.variant == VARIANT.BOOL) {
    buildBooleanField(form);
  } else {
    buildTextField(form);
  }

  form.display.append(form.input);

  // TODO: Handle base64 encoding for BYTES field.
  if (form.field.variant == VARIANT.BYTES) {
    $("<i>use base64 encoding</i>").appendTo(form.display);
  }
}


/**
 * Add repeated field.  This function is called when an item is added
 * @param {FormElement} form Repeated form element to create item for.
 */
function addRepeatedFieldItem(form) {
  var row = $('<tr>').appendTo(form.display);
  subForm = new FormElement(form.field, row);
  form.fields.push(subForm);
  buildFieldForm(subForm, false);
}


/**
 * Build repeated field.  Contains a button that can be used for adding new
 * items.
 * @param {FormElement} form Form to build element for.
 */
function buildRepeatedForm(form) {
  form.fields = [];
  form.display = $('<table border="1" width="100%">').
      appendTo(form.container);
  var header_row = $('<tr>').appendTo(form.display);
  var header = $('<td colspan="3">').appendTo(header_row);
  var add_button = $('<button>').text('+').appendTo(header);

  add_button.click(function() {
    addRepeatedFieldItem(form);
  });
}


/**
 * Build a form field.  Populates form content with values required by
 * all fields.
 * @param {FormElement} form Repeated form element to create item for.
 * @param allowRepeated {Boolean} Allow display of repeated field.  If set to
 *     to true, will treat repeated fields as individual items of a repeated
 *     field and render it as an individual field.
 */
function buildFieldForm(form, allowRepeated) {
  // All form fields are added to a row of a table.
  var inputData = $('<td>');

  // Set name.
  if (allowRepeated) {
    var nameData = $('<td>');
    nameData.text(form.field.name + ':');
    form.container.append(nameData);
  }

  // Set input.
  form.repeated = form.field.label == LABEL.REPEATED;
  if (allowRepeated && form.repeated) {
    inputData.attr('colspan', '2');
    buildRepeatedForm(form);
  } else {
    if (!allowRepeated) {
        inputData.attr('colspan', '2');
    }

    form.display = $('<div>');

    var controlData = $('<td>');
    if (form.field.label != LABEL.REQUIRED && allowRepeated) {
        form.enabled = false;
      var checkbox_id = 'checkbox-' + objectId;
      objectId++;
      $('<label for="' + checkbox_id + '">Enabled</label>').appendTo(controlData);
      var checkbox = $('<input id="' + checkbox_id + '" type="checkbox">').appendTo(controlData);
      var disableMessage = $('<div>').appendTo(inputData);
      checkbox.change(toggleInput(checkbox[0], form, disableMessage));
    } else {
      buildIndividualForm(form);
    }

    if (form.repeated) {
      // TODO: Implement deletion of repeated items.  Needs to delete
      // from DOM and also delete from form model.
    }

    form.container.append(controlData);
  }

  inputData.append(form.display);
  form.container.append(inputData);
}


/**
 * Top level function for building an entire message form.  Called once at form
 * creation and may be called again for nested message fields.  Constructs a
 * a table and builds a row for each sub-field.
 * @params {FormElement} form Form to build message form for.
 */
function buildMessageForm(form, messageType) {
  form.fields = [];
  form.descriptor = messageType;
  if (messageType.fields) {
    $.each(messageType.fields, function(index, field) {
      var row = $('<tr>').appendTo(form.table);
      var fieldForm = new FormElement(field, row);
      fieldForm.parent = form;
      buildFieldForm(fieldForm, true);
      form.fields.push(fieldForm);
    });
  }
}


/**
 * HTML Escape a string
 */
function htmlEscape(value) {
  if (typeof(value) == "string") {
    return value
      .replace(/&/g, '&amp;')
      .replace(/>/g, '&gt;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
      .replace(/ /g, '&nbsp;');
  } else {
    return value;
  }
}


/**
 * JSON formatted in HTML for display to users.  This method recursively calls
 * itself to render sub-JSON objects.
 * @param {Object} value JSON object to format for display.
 * @param {Integer} indent Indentation level for object being displayed.
 * @return {string} Formatted JSON object.
 */
function formatJSON(value, indent) {
  var indentation = '';
  for (var index = 0; index < indent; ++index) {
    indentation = indentation + '&nbsp;&nbsp;';
  }
  var type = typeof(value);

  var result = '';

  if (type == 'object') {
    if (value.constructor === Array) {
      result += '[<br>';
      $.each(value, function(index, item) {
        result += indentation + formatJSON(item, indent + 1) + ',<br>';
      });
      result += indentation + ']';
    } else {
      result += '{<br>';
      $.each(value, function(name, item) {
        result += (indentation + htmlEscape(name) + ': ' +
                   formatJSON(item, indent + 1) + ',<br>');
      });
      result += indentation + '}';
    }
  } else {
    result += htmlEscape(value);
  }

  return result;
}


/**
 * Construct array from repeated form element.
 * @param {FormElement} form Form element to build array from.
 * @return {Array} Array of repeated elements read from input form.
 */
function fromRepeatedForm(form) {
  var values = [];
  $.each(form.fields, function(index, subForm) {
    values.push(fromIndividualForm(subForm));
  });
  return values;
}


/**
 * Construct value from individual form element.
 * @param {FormElement} form Form element to get value from.
 * @return {string, Float, Integer, Boolean, object} Value extracted from
 *     individual field.  The type depends on the field variant.
 */
function fromIndividualForm(form) {
  switch(form.field.variant) {
  case VARIANT.MESSAGE:
    return fromMessageForm(form);
    break;

  case VARIANT.DOUBLE:
  case VARIANT.FLOAT:
    return parseFloat(form.input.val());

  case VARIANT.BOOL:
    return form.input[0].checked;
    break;

  case VARIANT.ENUM:
  case VARIANT.STRING:
  case VARIANT.BYTES:
    return form.input.val();

  default:
    break;
  }
  return parseInt(form.input.val(), 10);
}


/**
 * Extract entire message from a complete form.
 * @param {FormElement} form Form to extract message from.
 * @return {Object} Fully populated message object ready to transmit
 *     as JSON message.
 */
function fromMessageForm(form) {
  var message = {};
  $.each(form.fields, function(index, subForm) {
    if (subForm.enabled) {
      var subMessage = undefined;
      if (subForm.field.label == LABEL.REPEATED) {
        subMessage = fromRepeatedForm(subForm);
      } else {
        subMessage = fromIndividualForm(subForm);
      }

      message[subForm.field.name] = subMessage;
    }
  });

  return message;
}


/**
 * Send form as an RPC.  Extracts message from root form and transmits to
 * originating ProtoRPC server.  Response is formatted as JSON and displayed
 * to user.
 */
function sendForm() {
  $('#error-messages').empty();
  $('#form-response').empty();
  message = fromMessageForm(root_form);
  if (message === null) {
    return;
  }

  sendRequest(servicePath, methodName, message, function(response) {
    $('#form-response').html(formatJSON(response, 0));
    hideForm();
  });
}


/**
 * Reset form to original state.  Deletes existing form and rebuilds a new
 * one from scratch.
 */
function resetForm() {
  var panel = $('#form-panel');
  var serviceType = serviceMap[servicePath];
  var service = serviceDescriptors[serviceType];

  panel.empty();

  function formGenerationError(message) {
    error(message);
    panel.html('<div class="error-message">' +
               'There was an error generating the service form' +
               '</div>');
  }

    // Find method.
  var requestTypeName = null;
  $.each(service.methods, function(index, method) {
    if (method.name == methodName) {
        requestTypeName = method.request_type;
    }
  });

  if (!requestTypeName) {
    formGenerationError('No such method definition for: ' + methodName);
    return;
  }

  requestType = messageDescriptors[requestTypeName];
  if (!requestType) {
    formGenerationError('No such message-type: ' + requestTypeName);
    return;
  }

  var root = $('<table border="1">').
      appendTo(panel);

  root_form = new FormElement(null, null);
  root_form.table = root;
  buildMessageForm(root_form, requestType);
  $('<button>').appendTo(panel).text('Send Request').click(sendForm);
  $('<button>').appendTo(panel).text('Reset').click(resetForm);
}


/**
 * Hide main RPC form from user.  The information in the form is preserved.
 * Called after RPC to server is completed.
 */
function hideForm() {
  var expander = $('#form-expander');
  var formPanel = $('#form-panel');
  formPanel.hide();
  expander.text(FORM_VISIBILITY.SHOW_FORM);
}


/**
 * Toggle the display of the main RPC form.  Called when form expander button
 * is clicked.
 */
function toggleForm() {
  var expander = $('#form-expander');
  var formPanel = $('#form-panel');
  if (expander.text() == FORM_VISIBILITY.HIDE_FORM) {
    hideForm();
  } else {
    formPanel.show();
    expander.text(FORM_VISIBILITY.HIDE_FORM);
  }
}


/**
 * Create form.  Called after all service information and file sets have been
 * loaded.
 */
function createForm() {
  $('#form-expander').click(toggleForm);
  resetForm();
}


/**
 * Display available services and their methods.
 */
function showMethods() {
  var methodSelector = $('#method-selector');
  if (serviceMap) {
    $.each(serviceMap, function(serviceName) {
      var descriptor = serviceDescriptors[serviceMap[serviceName]];
      methodSelector.append(descriptor.name);
      var block = $('<blockquote>').appendTo(methodSelector);
      $.each(descriptor.methods, function(index, method) {
        var url = (formPath + '?path=' + serviceName +
                   '&method=' + method.name);
        var label = serviceName + '.' + method.name;
        $('<a>').attr('href', url).text(label).appendTo(block);
        $('<br>').appendTo(block);
      });
    });
  }
}


/**
 * Populate map of fully qualified message names to descriptors.  This method
 * is called recursively to populate message definitions nested within other
 * message definitions.
 * @param {Object} messages Array of message descriptors as returned from the
 *     RegistryService.get_file_set call.
 * @param {string} container messages may be an Array of messages nested within
 *     either a FileDescriptor or a MessageDescriptor.  The container is the
 *     fully qualified name of the file descriptor or message descriptor so
 *     that the fully qualified name of the messages in the list may be
 *     constructed.
 */
function populateMessages(messages, container) {
  if (messages) {
    $.each(messages, function(messageIndex, message) {
      var messageName = container + '.' + message.name;
      messageDescriptors[messageName] = message;

      if (message.message_types) {
        populateMessages(message.message_types, messageName);
      }

      if (message.enum_types) {
        $.each(message.enum_types, function(enumIndex, enumerated) {
          var enumName = messageName + '.' + enumerated.name;
          enumDescriptors[enumName] = enumerated;
        });
      }
    });
  }
}


/**
 * Populates all descriptors from a FileSet descriptor.  Each of the three
 * descriptor collections (service, message and enum) map the fully qualified
 * name of a definition to it's descriptor.
 */
function populateDescriptors(file_set) {
  serviceDescriptors = {};
  messageDescriptors = {};
  enumDescriptors = {};
  $.each(file_set.files, function(index, file) {
    if (file.service_types) {
      $.each(file.service_types, function(serviceIndex, service) {
        var serviceName = file['package'] + '.' + service.name;
        serviceDescriptors[serviceName] = service;
      });
    }

    populateMessages(file.message_types, file['package']);
  });
}


/**
 * Load all file sets from ProtoRPC registry service.
 * @param {function} when_done Called after all file sets are loaded.
 */
function loadFileSets(when_done) {
  var paths = [];
  $.each(serviceMap, function(serviceName) {
    paths.push(serviceName);
  });

  sendRequest(
      registryPath,
      'get_file_set',
      {'names': paths},
      function(response) {
          populateDescriptors(response.file_set, when_done);
          when_done();
  });
}


/**
 * Load all services from ProtoRPC registry service.  When services are
 * loaded, will then load all file_sets from the server.
 * @param {function} when_done Called after all file sets are loaded.
 */
function loadServices(when_done) {
  sendRequest(
      registryPath,
      'services',
      {},
      function(response) {
        serviceMap = {};
        $.each(response.services, function(index, service) {
          serviceMap[service.name] = service.definition;
        });
        loadFileSets(when_done);
      });
}
