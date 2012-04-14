$(document).ready(function(){
  // Start off by hiding the log div
  hideLogsDiv();

  // Show a random quote in the footer
  showRandomQuote();

  // Components have a name and an IP, and we want all components with the same
  // name to be in one category, so first get a list of all the components, and
  // make sidebars for each name
  $.ajax({
    type: 'GET',
    async: true,
    url: '/component',
    success: function(data) {
      components = JSON.parse(data);  // gives us [{name. ip}]

      // To make the sidebar, we need to construct a list of name => ip1, ip2
      // so we can add the links in the right order
      sorted = {};
      for (var i = 0; i < components.length; i++) {
        item = components[i];
        name = item['name'];
        ip = item['ip'];

        if (typeof sorted[name] == 'undefined') {
          sorted[name] = [];
        }

        sorted[name].push(ip);
        console.log('adding ip ' + ip + ' for name ' + name);
      }

      // Now that we have our data in the right order, we can add links
      // accordingly. Always add name first (the key), then val1, val2...
      for (var name in sorted) {
        // add the name
        classes = "nav-header nav-" + name;
        $('.nav-list').append('<li class="' + classes + '">' + name + '</li>');
        console.log("added header for component name " + name);

        ips = sorted[name];
        for (var i = 0; i < ips.length; i++) {
          ip = ips[i];
          // add this ip and an onclick so that we can fetch logs for it
          callback = 'onclick=getLogs("' + name + '","' + ip + '")';
          $('.nav-list').append('<li><a href="#" ' + callback + '>' + ip + '</a></li>');
          console.log("added link for ip " + ip);
        }
      }
    }
  });

  // Fill in the upper-right hand corner with info about who is logged in
  // to Sisyphus.
  $.ajax({
    type: 'GET',
    async: true,
    url: '/whoami',
    success: function(data) {
      userInfo = JSON.parse(data);  // gives us {user, logged_in}

      if (userInfo['logged_in']) {
        console.log('logged in as ' + userInfo['user']);
        $('#user').text(userInfo['user']);
      } else {
        console.log('not logged in.');
        $('#logged-in').text('Not logged in.');
      }
    }
  });


  
  // If the user clicks on the 'Home' button at the top of the page, it should
  // show the main div (like when they first arrive on the page).
  $("#home").click(function(){
    console.log('home button clicked!')
    hideLogsDiv();
    showMainDiv();
  });

});


/**
 * getLogs retrives all the logs for a given component (uniquely identified by
 * a name and IP address) and displays it in the main div.
 * @param name (string): The name of the component to retrieve logs for.
 * @param ip (string): The IP address associated with that component
 */
function getLogs(name, ip) {
  console.log("getLogs saw name " + name + " and ip addr " + ip);

  payload = JSON.stringify({'name' : name, 'ip' : ip});
  $.ajax({
    type: 'GET',
    async: true,
    url: '/log?payload=' + payload,
    success: function(data) {
      log_data = JSON.parse(data);  // {logs, last_timestamp}
      logs = log_data['logs'];  // of the format [{text, timestamp}]

      // set the title's text
      $('.log-header').text('Logs for ' + name + ' at ' + ip);

      // set the logs text
      console.log("log length is " + logs.length);
      $('.log-list').text('');
      if (logs.length == 0) {
          console.log("saw no logs!");
          $('.log-list').append('<li>No logs currently available.</li>');
      } else {
        for (var i = 0; i < logs.length; i++) {
          log = logs[i];
          $('.log-list').append(log['text'] + "\n");
        }
      }

      // display them in the logs div
      hideMainDiv();
      showLogsDiv();
    }
  });

}


function showMainDiv() {
  $('div.main').show();
}


function hideMainDiv() {
  $('div.main').hide();
}


function showLogsDiv() {
  $('div.logs').show();
}


function hideLogsDiv() {
  $('div.logs').hide();
}

function showRandomQuote() {
  quotes = ["A mind without purpose will wander in dark places.",
    "A suspicious mind is a healthy mind.",
    "By the manner of their death we shall know them.",
    "Call no man happy until he is dead.",
    "Examine your thoughts!",
    "Foolish are those who fear nothing, yet claim to know everything.",
    "Hope is the first step on the road to disappointment.",
    "Information Is Power",
    "The greatest man is but a ripple on the surface of space",
    "The wise man learns from the deaths of others.",
  ];

  min = 0;
  max = quotes.length;
  index = Math.floor(Math.random() * (max - min + 1)) + min;

  $('#footer').text(quotes[index]);

}
