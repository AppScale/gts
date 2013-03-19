// document ready function
$(document).ready(function() { 	

	//------------- Full calendar  -------------//

	$(function () {
		var date = new Date();
		var d = date.getDate();
		var m = date.getMonth();
		var y = date.getFullYear();
		
		//front page calendar
		$('#calendar').fullCalendar({
			//isRTL: true,
			//theme: true,
			header: {
				left: 'title,today',
				center: 'prev,next',
				right: 'month,agendaWeek,agendaDay'
			},
			buttonText: {
	        	prev: '<span class="icon24 icomoon-icon-arrow-left-2"></span>',
	        	next: '<span class="icon24 icomoon-icon-arrow-right-2"></span>'
	    	},
			editable: true,
			events: [
				{
					title: 'All Day Event',
					start: new Date(y, m, 1)
				},
				{
					title: 'Long Event',
					start: new Date(y, m, d-5),
					end: new Date(y, m, d-2)
				},
				{
					id: 999,
					title: 'Repeating Event',
					start: new Date(y, m, d-3, 16, 0),
					allDay: false
				},
				{
					id: 999,
					title: 'Repeating Event',
					start: new Date(y, m, d+4, 16, 0),
					allDay: false
				},
				{
					title: 'Meeting',
					start: new Date(y, m, d, 10, 30),
					allDay: false
				},
				{
					title: 'Lunch',
					start: new Date(y, m, d, 12, 0),
					end: new Date(y, m, d, 14, 0),
					allDay: false,
					color: '#9FC569'
				},
				{
					title: 'Birthday Party',
					start: new Date(y, m, d+1, 19, 0),
					end: new Date(y, m, d+1, 22, 30),
					allDay: false,
					color: '#ED7A53'
				},
				{
					title: 'Click for Google',
					start: new Date(y, m, 28),
					end: new Date(y, m, 29),
					url: 'http://google.com/'
				}
			]
		});
	});

	/* initialize the external events
	-----------------------------------------------------------------*/
	
	$('#external-events div.external-event').each(function() {
	
		// create an Event Object (http://arshaw.com/fullcalendar/docs/event_data/Event_Object/)
		// it doesn't need to have a start or end
		var eventObject = {
			title: $.trim($(this).text()) // use the element's text as the event title
		};
		
		// store the Event Object in the DOM element so we can get to it later
		$(this).data('eventObject', eventObject);
		
		// make the event draggable using jQuery UI
		$(this).draggable({
			zIndex: 999,
			revert: true,      // will cause the event to go back to its
			revertDuration: 0  //  original position after the drag
		});
		
	});


	/* initialize the calendar
	-----------------------------------------------------------------*/
	
	$('#calendar-events').fullCalendar({
		header: {
			left: 'title,today',
			center: 'prev,next',
			right: 'month,agendaWeek,agendaDay'
		},
		buttonText: {
        	prev: '<span class="icon24 icomoon-icon-arrow-left-2"></span>',
        	next: '<span class="icon24 icomoon-icon-arrow-right-2"></span>'
    	},
		editable: true,
		droppable: true, // this allows things to be dropped onto the calendar !!!
		drop: function(date, allDay) { // this function is called when something is dropped
		
			// retrieve the dropped element's stored Event Object
			var originalEventObject = $(this).data('eventObject');
			
			// we need to copy it, so that multiple events don't have a reference to the same object
			var copiedEventObject = $.extend({}, originalEventObject);
			
			// assign it the date that was reported
			copiedEventObject.start = date;
			copiedEventObject.allDay = allDay;
			
			// render the event on the calendar
			// the last `true` argument determines if the event "sticks" (http://arshaw.com/fullcalendar/docs/event_rendering/renderEvent/)
			$('#calendar-events').fullCalendar('renderEvent', copiedEventObject, true);
			$(this).remove();
			
		}
	});

	//--------------- Tabs ------------------//

    //activate calendar ot tab click
    $('#myTab a[data-toggle="tab"]').on('shown', function (e) {
		$('#calendar').fullCalendar('render');
	})

	//Boostrap modal
	$('#myModal').modal({ show: false});
	
	//add event to modal after closed
	$('#myModal').on('hidden', function () {
	  	console.log('modal is closed');
	})

});//End document ready functions

//sparkline in sidebar area
var positive = [1,5,3,7,8,6,10];
var negative = [10,6,8,7,3,5,1]
var negative1 = [7,6,8,7,6,5,4]

$('#stat1').sparkline(positive,{
	height:15,
	spotRadius: 0,
	barColor: '#9FC569',
	type: 'bar'
});
$('#stat2').sparkline(negative,{
	height:15,
	spotRadius: 0,
	barColor: '#ED7A53',
	type: 'bar'
});
$('#stat3').sparkline(negative1,{
	height:15,
	spotRadius: 0,
	barColor: '#ED7A53',
	type: 'bar'
});
$('#stat4').sparkline(positive,{
	height:15,
	spotRadius: 0,
	barColor: '#9FC569',
	type: 'bar'
});
//sparkline in widget
$('#stat5').sparkline(positive,{
	height:15,
	spotRadius: 0,
	barColor: '#9FC569',
	type: 'bar'
});

$('#stat6').sparkline(positive, { 
	width: 70,//Width of the chart - Defaults to 'auto' - May be any valid css width - 1.5em, 20px, etc (using a number without a unit specifier won't do what you want) - This option does nothing for bar and tristate chars (see barWidth)
	height: 20,//Height of the chart - Defaults to 'auto' (line height of the containing tag)
	lineColor: '#88bbc8',//Used by line and discrete charts to specify the colour of the line drawn as a CSS values string
	fillColor: '#f2f7f9',//Specify the colour used to fill the area under the graph as a CSS value. Set to false to disable fill
	spotColor: '#e72828',//The CSS colour of the final value marker. Set to false or an empty string to hide it
	maxSpotColor: '#005e20',//The CSS colour of the marker displayed for the maximum value. Set to false or an empty string to hide it
	minSpotColor: '#f7941d',//The CSS colour of the marker displayed for the mimum value. Set to false or an empty string to hide it
	spotRadius: 3,//Radius of all spot markers, In pixels (default: 1.5) - Integer
	lineWidth: 2//In pixels (default: 1) - Integer
});