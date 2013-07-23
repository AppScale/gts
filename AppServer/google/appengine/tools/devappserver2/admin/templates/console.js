/**
 * @fileoverview Supporting Javascript for the code.
 * @author bquinlan@google.com (Brian Quinlan)
 */

/**
 * @private
 */
var DEFAULT_PYTHON_SOURCE_ = 'import os\n' +
    'import pprint\n' +
    '\n' +
    'from google.appengine.api import memcache\n' +
    'from google.appengine.api import mail\n' +
    'from google.appengine.api import urlfetch\n' +
    'from google.appengine.ext import db\n' +
    '\n' +
    'pprint.pprint(os.environ.copy())\n';

/**
 * @private
 */
var SERVER_NAME_TO_RUNTIME_NAME_ = {
{% for server in servers %}
  '{{ server.name }}': '{{ server.server_configuration.runtime }}',
{% endfor %}
};

/**
 * Return the interactive code for the given server. This code is saved using
 * HTML localStorage and is unique per application.
 * @param {string} serverName The name of the server whose code should be
 *     returned.
 * @return {string} The code for the given server. If no code was previously
 *     saved for this server then some example code is returned.
 */
function getCode(serverName) {
  var text = localStorage.getItem('{{ app_id }}:' + serverName);
  if (text == null) {
    if (SERVER_NAME_TO_RUNTIME_NAME_[serverName] == 'python' ||
        SERVER_NAME_TO_RUNTIME_NAME_[serverName] == 'python27') {
      return DEFAULT_PYTHON_SOURCE_;
    } else {
      return '';
    }
  }
  return text;
}

/**
 * Set the interactive code for the given server. This code is saved using
 * HTML localStorage and is unique per application.
 * @param {string} serverName The name of the server to save the code for.
 * @param {string} code The code to save.
 */
function setCode(serverName, code) {
  localStorage.setItem('{{ app_id }}:' + serverName, code);
}

function enableExecuteButton() {
  $('#execute_button').removeAttr('disabled');
  $('#execute_button').removeClass('disabled');
}

function disableExecuteButton() {
  $('#execute_button').attr('disabled', 'disabled');
  $('#execute_button').addClass('disabled');
}

function enableRestartButton() {
  $('#restart_button').removeAttr('disabled');
  $('#restart_button').removeClass('disabled');
}

function disableRestartButton() {
  $('#restart_button').attr('disabled', 'disabled');
  $('#restart_button').addClass('disabled');
}

$(window).unload(function() {
  // Save the current code text.
  setCode($('#server_name').val(), $('#code_text').val());
});

$(document).ready(function() {
  $('#server_name').data('previous_value', $('#server_name').val());
  $('#code_text').val(getCode($('#server_name').val()));

  $('#server_name').change(function() {
    var $this = $(this);
    setCode($this.data('previous_value'), $('#code_text').val());
    $('#code_text').val(getCode($this.val()));
    $('#server_name').data('previous_value', $('#server_name').val());
  });

  $('#code_text').change(function() {
    // Save the current code text.
    setCode($('#server_name').val(), $('#code_text').val());
  });

  $('#restart_button').click(function() {
    $('#output').text('Restarting...');
    disableExecuteButton();
    disableRestartButton();

    var request = $.ajax({
      url: '{{ request.uri }}/restart/' +
           encodeURIComponent($('#server_name').val()),
      type: 'POST'
    })
    .done(function(data) {
      $('#output').text('Restarting...complete');
      enableExecuteButton();
      enableRestartButton();
    })
    .fail(function(xhr, textStatus) {
      $('#output').text('Restarting...failed');
      enableExecuteButton();
      enableRestartButton();
    });
    return false;
  });

  $('#console-form').submit(function() {
    $('#output').text('...');
    disableExecuteButton();

    var data = {'code': $('#code_text').val(),
                'server_name': $('#server_name').val(),
                'xsrf_token': '{{ xsrf_token }}'};

    var request = $.ajax({
      url: '{{ request.uri }}',
      type: 'POST',
      data: data
    })
    .done(function(data) {
      $('#output').text(data);
      enableExecuteButton();
    })
    .fail(function(xhr, textStatus) {
      $('#output').text('Request failed');
      enableExecuteButton();
    });
    return false;
  });
});
