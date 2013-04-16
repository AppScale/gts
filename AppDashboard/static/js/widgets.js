// document ready function
$(document).ready(function() { 	

	//------------- Check all checkboxes  -------------//
	
	$("#masterCh").click(function() {
		var checkedStatus = $(this).find('span').hasClass('checked');
		$("#checkAll tr .chChildren input:checkbox").each(function() {
			this.checked = checkedStatus;
				if (checkedStatus == this.checked) {
					$(this).closest('.checker > span').removeClass('checked');
				}
				if (this.checked) {
					$(this).closest('.checker > span').addClass('checked');
				}
		});
	});

	//------------- I button  -------------//
	$(".ibuttonCheck").iButton({
		 labelOn: "<span class='icon16 icomoon-icon-checkmark-2 white'></span>",
		 labelOff: "<span class='icon16 icomoon-icon-cancel-3 white'></span>",
		 enableDrag: false
	});

	//------------- Custom scroll in widget box  -------------//
	if($(".scroll").length) {
		$(".scroll").niceScroll({
			cursoropacitymax: 0.7,
			cursorborderradius: 6,
			cursorwidth: "7px"
		});
	}
	if($(".scrolled").length) {
		$(".scrolled").niceScroll({
			cursoropacitymax: 0.7,
			cursorborderradius: 6,
			cursorwidth: "4px"
		});
	}

	//--------------- Typeahead ------------------//
	$('.typeahead').typeahead({
		source: ['jonh','carlos','arcos','stoner']
	})

	$('.findUser').typeahead({
		source: ['Sammy','Jonny','Sugge Elson','Elenna','Rayan','Dimitrios','Sidarh','Jana','Daniel','Morerira','Stoichkov']
	})

	//------------- Datepicker -------------//

	if($('#datepicker-inline').length) {
		$('#datepicker-inline').datepicker({
	        inline: true,
			showOtherMonths:true
	    });
	}

	//--------------- carousel ------------------//
	$('.carousel').carousel({
	  interval: 5000
	})

	//--------------- Prettyphoto ------------------//
	$("a[rel^='prettyPhoto']").prettyPhoto({
		default_width: 800,
		default_height: 600,
		theme: 'facebook',
		social_tools: false,
		show_title: false
	});
	//--------------- Gallery & lazzy load & jpaginate ------------------//
	$(function() {
		//hide the action buttons
		$('.actionBtn').hide();
		//show action buttons on hover image
		$('.galleryView>li').hover(
			function () {
			   $(this).find('.actionBtn').stop(true, true).show();
			},
			function () {
			    $(this).find('.actionBtn').stop(true, true).hide();
			}
		);
		//remove the gallery item after press delete
		$('.actionBtn>.delete').click(function(){
			$(this).closest('li').remove();
			/* destroy and recreate gallery */
		    $("div.holder").jPages("destroy").jPages({
		        containerID : "itemContainer",
		        animation   : "fadeInUp",
		        perPage		: 16,
		        scrollBrowse   : true, //use scroll to change pages
		        keyBrowse   : true,
		        callback    : function( pages ,items ){
		            /* lazy load current images */
		            items.showing.find("img").trigger("turnPage");
		            /* lazy load next page images */
		            items.oncoming.find("img").trigger("turnPage");
		        }
		    });
		    // add notificaton 
			$.pnotify({
				type: 'success',
			    title: 'Done',
	    		text: 'You just delete this picture.',
			    icon: 'picon icon16 brocco-icon-info white',
			    opacity: 0.95,
			    history: false,
			    sticker: false
			});

		});

	    /* initiate lazyload defining a custom event to trigger image loading  */
	    $("ul#itemContainer li img").lazyload({
	        event : "turnPage",
	        effect : "fadeIn"
	    });
	    /* initiate plugin */
	    $("div.holder").jPages({
	        containerID : "itemContainer",
	        animation   : "fadeInUp",
	        perPage		: 16,
	        scrollBrowse   : true, //use scroll to change pages
	        keyBrowse   : true,
	        callback    : function( pages ,items ){
	            /* lazy load current images */
	            items.showing.find("img").trigger("turnPage");
	            /* lazy load next page images */
	            items.oncoming.find("img").trigger("turnPage");
	        }
	    });
	});

//------------- Smart Wizzard  -------------//	
  	$('#wizard').smartWizard({
  		transitionEffect: 'fade', // Effect on navigation, none/fade/slide/
  		onLeaveStep:leaveAStepCallback,
        onFinish:onFinishCallback
    });

    function leaveAStepCallback(obj){
        var step = obj;
        step.find('.stepNumber').stop(true, true).remove();
        step.find('.stepDesc').stop(true, true).before('<span class="stepNumber"><span class="icon16 iconic-icon-checkmark"></span></span>');
        return true;
    }
    function onFinishCallback(obj){
    	var step = obj;
    	step.find('.stepNumber').stop(true, true).remove();
        step.find('.stepDesc').stop(true, true).before('<span class="stepNumber"><span class="icon16 iconic-icon-checkmark"></span></span>');
      	$.pnotify({
			type: 'success',
		    title: 'Done',
    		text: 'You finish the wizzard',
		    icon: 'picon icon16 iconic-icon-check-alt white',
		    opacity: 0.95,
		    history: false,
		    sticker: false
		});
    }

    /*Vertical wizard*/
    $('#wizard-vertical').smartWizard({
  		transitionEffect: 'fade', // Effect on navigation, none/fade/slide/
  		onLeaveStep:leaveAStepCallback,
        onFinish:onFinishCallback
    });

    function leaveAStepCallback(obj){
        var step = obj;
        step.find('.stepNumber').stop(true, true).remove();
        step.find('.stepDesc').stop(true, true).before('<span class="stepNumber"><span class="icon16 iconic-icon-checkmark"></span></span>');
        return true;
    }
    function onFinishCallback(obj){
    	var step = obj;
    	step.find('.stepNumber').stop(true, true).remove();
        step.find('.stepDesc').stop(true, true).before('<span class="stepNumber"><span class="icon16 iconic-icon-checkmark"></span></span>');
      	$.pnotify({
			type: 'success',
		    title: 'Done',
    		text: 'You finish the wizzard',
		    icon: 'picon icon16 iconic-icon-check-alt white',
		    opacity: 0.95,
		    history: false,
		    sticker: false
		});
    }

    //--------------- Data tables ------------------//

	if($('table').hasClass('contactTable')){
		$('.contactTable').dataTable({
			"bJQueryUI": false,
			"bAutoWidth": false,
			"iDisplayLength": 5,
			"bLengthChange": false,
			"aoColumnDefs": [{ 
				"bSortable": false, "aTargets": [ 0, 1, 2, 3 ] 
			}],
		});
	}

	//------------- JQuery Autocomplete -------------//
    $(function() {
		var availableTags = [
			"ActionScript",
			"AppleScript",
			"Asp",
			"BASIC",
			"C",
			"C++",
			"Clojure",
			"COBOL",
			"ColdFusion",
			"Erlang",
			"Fortran",
			"Groovy",
			"Haskell",
			"Java",
			"JavaScript",
			"Lisp",
			"Perl",
			"PHP",
			"Python",
			"Ruby",
			"Scala",
			"Scheme"
		];
		$( "#autocomplete" ).autocomplete({
			source: availableTags
		});
	});

	//------------- File tree plugin  -------------//
	if($('#file-tree').length) {
	     $('#file-tree').fileTree({
	        root: '/images/',
	        script: 'php/filetree/jqueryFileTree.php',
	        expandSpeed: 1000,
	        collapseSpeed: 1000,
	        multiFolder: false
	    }, function(file) {
	        alert(file);
	    });
	}

	//------------- Combobox  -------------//
    (function( $ ) {
        $.widget( "ui.combobox", {
            _create: function() {
                var input,
                    self = this,
                    select = this.element.hide(),
                    selected = select.children( ":selected" ),
                    value = selected.val() ? selected.text() : "",
                    wrapper = this.wrapper = $( "<span>" )
                        .addClass( "ui-combobox" )
                        .insertAfter( select );

                input = $( "<input>" )
                    .appendTo( wrapper )
                    .val( value )
                    .addClass( "ui-state-default ui-combobox-input" )
                    .autocomplete({
                        delay: 0,
                        minLength: 0,
                        source: function( request, response ) {
                            var matcher = new RegExp( $.ui.autocomplete.escapeRegex(request.term), "i" );
                            response( select.children( "option" ).map(function() {
                                var text = $( this ).text();
                                if ( this.value && ( !request.term || matcher.test(text) ) )
                                    return {
                                        label: text.replace(
                                            new RegExp(
                                                "(?![^&;]+;)(?!<[^<>]*)(" +
                                                $.ui.autocomplete.escapeRegex(request.term) +
                                                ")(?![^<>]*>)(?![^&;]+;)", "gi"
                                            ), "<strong>$1</strong>" ),
                                        value: text,
                                        option: this
                                    };
                            }) );
                        },
                        select: function( event, ui ) {
                            ui.item.option.selected = true;
                            self._trigger( "selected", event, {
                                item: ui.item.option
                            });
                        },
                        change: function( event, ui ) {
                            if ( !ui.item ) {
                                var matcher = new RegExp( "^" + $.ui.autocomplete.escapeRegex( $(this).val() ) + "$", "i" ),
                                    valid = false;
                                select.children( "option" ).each(function() {
                                    if ( $( this ).text().match( matcher ) ) {
                                        this.selected = valid = true;
                                        return false;
                                    }
                                });
                                if ( !valid ) {
                                    // remove invalid value, as it didn't match anything
                                    $( this ).val( "" );
                                    select.val( "" );
                                    input.data( "autocomplete" ).term = "";
                                    return false;
                                }
                            }
                        }
                    })
                    .addClass( "ui-widget ui-widget-content ui-corner-left" );

                input.data( "autocomplete" )._renderItem = function( ul, item ) {
                    return $( "<li></li>" )
                        .data( "item.autocomplete", item )
                        .append( "<a>" + item.label + "</a>" )
                        .appendTo( ul );
                };

                $( "<a>" )
                    .attr( "tabIndex", -1 )
                    .attr( "title", "Show All Items" )
                    .appendTo( wrapper )
                    .button({
                        icons: {
                            primary: "ui-icon-triangle-1-s"
                        },
                        text: false
                    })
                    .removeClass( "ui-corner-all" )
                    .addClass( "ui-corner-right ui-combobox-toggle" )
                    .click(function() {
                        // close if already visible
                        if ( input.autocomplete( "widget" ).is( ":visible" ) ) {
                            input.autocomplete( "close" );
                            return;
                        }

                        // work around a bug (likely same cause as #5265)
                        $( this ).blur();

                        // pass empty string as value to search for, displaying all results
                        input.autocomplete( "search", "" );
                        input.focus();
                    });
            },

            destroy: function() {
                this.wrapper.remove();
                this.element.show();
                $.Widget.prototype.destroy.call( this );
            }
        });
    })( jQuery );

    if($("#combobox").length) {
    	$( "#combobox" ).combobox();
    }

	//Boostrap modal
	$('#myModal').modal({ show: false});
	
	//add event to modal after closed
	$('#myModal').on('hidden', function () {
	  	console.log('modal is closed');
	})

});//End document ready functions

//generate random number for charts
randNum = function(){
	//return Math.floor(Math.random()*101);
	return (Math.floor( Math.random()* (1+40-20) ) ) + 20;
}

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

//sparklines (making loop with random data for all 7 sparkline)
i=1;
for (i=1; i<8; i++) {
 	var data = [[1, 3+randNum()], [2, 5+randNum()], [3, 8+randNum()], [4, 11+randNum()],[5, 14+randNum()],[6, 17+randNum()],[7, 20+randNum()], [8, 15+randNum()], [9, 18+randNum()], [10, 22+randNum()]];
 	placeholder = '.sparkLine' + i;
	$(placeholder).sparkline(data, { 
		width: 100,//Width of the chart - Defaults to 'auto' - May be any valid css width - 1.5em, 20px, etc (using a number without a unit specifier won't do what you want) - This option does nothing for bar and tristate chars (see barWidth)
		height: 30,//Height of the chart - Defaults to 'auto' (line height of the containing tag)
		lineColor: '#88bbc8',//Used by line and discrete charts to specify the colour of the line drawn as a CSS values string
		fillColor: '#f2f7f9',//Specify the colour used to fill the area under the graph as a CSS value. Set to false to disable fill
		spotColor: '#467e8c',//The CSS colour of the final value marker. Set to false or an empty string to hide it
		maxSpotColor: '#9FC569',//The CSS colour of the marker displayed for the maximum value. Set to false or an empty string to hide it
		minSpotColor: '#ED7A53',//The CSS colour of the marker displayed for the mimum value. Set to false or an empty string to hide it
		spotRadius: 3,//Radius of all spot markers, In pixels (default: 1.5) - Integer
		lineWidth: 2//In pixels (default: 1) - Integer
	});
}