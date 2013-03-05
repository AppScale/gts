// document ready function
$(document).ready(function() { 	

	//--------------- Data tables ------------------//

	if($('table').hasClass('emailTable')){
		$('.emailTable').dataTable({
			"bJQueryUI": false,
			"bAutoWidth": false,
			"bLengthChange": false,
			"oLanguage": {
				"sSearch": "",
		        "sInfo": "Got a total of _TOTAL_ emails to show (_START_ to _END_)"
		    },
		    "fnDrawCallback": function(){
    			$("input[type=checkbox]").uniform();
            },
		    "aoColumns": [
			    { 
			    	"sWidth": "10px",
			    	"bSortable": false
			    },
			    { 
			    	"sWidth": "10px", 
			    	"bSortable": false
			    },
				{ 
			    	"bSortable": false
			    },
				{ 
			    	"bSortable": false
			    },
			    { 
			    	"sWidth": "20px",
			    	"bSortable": false
			    },
				{ 
			    	"sWidth": "80px", 
			    	"bSortable": false
		    	}
		    ]
		});
	}		

	//------------- Email page  -------------//
	
	var emailTable = $('.emailTable');
	var emailStar = emailTable.find('td.star>span.icon16');

	//setup the star in click
	emailStar.click(function() {
		if($(this).hasClass('icomoon-icon-star-3')) {
			$(this).removeClass('icomoon-icon-star-3').addClass('icomoon-icon-star');
			//make callback here

		} else {
			$(this).removeClass('icomoon-icon-star').addClass('icomoon-icon-star-3');
			//make callback here
		}
	});

	//auto complete for compose To form field
	$('#to').typeahead({
		source: ['jonh@yahoo.com','silva@yahoo.com','carlos@gmail.com','sugge@gmail.com']
	})

	//check all checkboxes in email table
	$(".checkAll").click(function() {
		var $this = $(this);
		var checkedStatus = $this.find('span').hasClass('checked');
		$(".emailTable tr .check input:checkbox").each(function() {
			this.checked = checkedStatus;
				if (checkedStatus == this.checked) {
					$(this).closest('.checker > span').removeClass('checked');
				}
				if (this.checked) {
					$(this).closest('.checker > span').addClass('checked');
				}
		});
	});

	//show compose form
	$('.composeBtn>.btn').click(function() {
		$('.email-content>.box.plain').fadeOut(200);
		$('.compose').fadeIn();
	});

	//close compose form on discard click
	$('#discard').click(function() {
		$('.compose').fadeOut(200);
		$('.email-content>.box.plain').fadeIn(300);
	});

	//save click event
	$('#save').click(function() {
		$('.compose').fadeOut(200);
		$('.email-content>.box.plain').fadeIn(300);
		$.pnotify({
			type: 'success',
		    title: 'Done',
    		text: 'Email is saved',
		    icon: 'picon icon16 iconic-icon-check-alt white',
		    opacity: 0.95,
		    history: false,
		    sticker: false
		});
		//save callback here
	});

	//on send msg click
	$('#send').click(function() {
		$('.compose').fadeOut(200);
		$('.email-content>.box.plain').fadeIn(300);
		//add some notification
		$.pnotify({
			type: 'success',
		    title: 'Done',
    		text: 'Email send successfull',
		    icon: 'picon icon16 iconic-icon-check-alt white',
		    opacity: 0.95,
		    history: false,
		    sticker: false
		});
		//calback function here
	});

	//on send msg click
	$('#backToInbox').click(function() {
		$('.read-email').fadeOut(200);
		$('.email-content>.box.plain').fadeIn(300);
		//calback function here
	});

	emailTable.find('td a.link').click(function() {
		$('.email-content>.box.plain').fadeOut(200);
		$('.read-email').fadeIn(300);
		//calback function here
	});


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