// document ready function
$(document).ready(function() { 	

	var divElement = $('div'); //log all div elements

	//Boostrap modal
	$('#myModal').modal({ show: false});
	
	//add event to modal after closed
	$('#myModal').on('hidden', function () {
	  	console.log('modal is closed');
	})

	//Simple chart 
    if (divElement.hasClass('simple-chart')) {
	$(function () {
		var sin = [], cos = [];
	    for (var i = 0; i < 14; i += 0.5) {
	        sin.push([i, Math.sin(i)]);
	        cos.push([i, Math.cos(i)]);
	    }
	    //graph options
		var options = {
				grid: {
					show: true,
				    aboveData: true,
				    color: "#3f3f3f" ,
				    labelMargin: 5,
				    axisMargin: 0, 
				    borderWidth: 0,
				    borderColor:null,
				    minBorderMargin: 5 ,
				    clickable: true, 
				    hoverable: true,
				    autoHighlight: true,
				    mouseActiveRadius: 20
				},
		        series: {
		        	grow: {active: false},
		            lines: {
	            		show: true,
	            		fill: false,
	            		lineWidth: 4,
	            		steps: false
		            	},
		            points: {
		            	show:true,
		            	radius: 5,
		            	symbol: "circle",
		            	fill: true,
		            	borderColor: "#fff"
		            }
		        },
		        legend: { position: "se" },
		        colors: chartColours,
		        shadowSize:1,
		        tooltip: true, //activate tooltip
				tooltipOpts: {
					content: "%s : %y.3",
					shifts: {
						x: -30,
						y: -50
					}
				}
		};  
		var plot = $.plot($(".simple-chart"),
           [{
    			label: "Sin", 
    			data: sin,
    			lines: {fillColor: "#f2f7f9"},
    			points: {fillColor: "#88bbc8"}
    		}, 
    		{	
    			label: "Cos", 
    			data: cos,
    			lines: {fillColor: "#fff8f2"},
    			points: {fillColor: "#ed7a53"}
    		}], options);
	});
	}//end if

	//Donut simple chart
    if (divElement.hasClass('simple-donut')) {
	$(function () {
		var data = [
		    { label: "USA",  data: 38, color: "#88bbc8"},
		    { label: "Brazil",  data: 23, color: "#ed7a53"},
		    { label: "India",  data: 15, color: "#9FC569"},
		    { label: "Turkey",  data: 9, color: "#bbdce3"},
		    { label: "France",  data: 7, color: "#9a3b1b"},
		    { label: "China",  data: 5, color: "#5a8022"},
		    { label: "Germany",  data: 3, color: "#2c7282"}
		];

	    $.plot($(".simple-donut"), data, 
		{
			series: {
				pie: { 
					show: true,
					innerRadius: 0.4,
					highlight: {
						opacity: 0.1
					},
					radius: 1,
					stroke: {
						color: '#fff',
						width: 8
					},
					startAngle: 2,
				    combine: {
	                    color: '#353535',
	                    threshold: 0.05
	                },
	                label: {
	                    show: true,
	                    radius: 1,
	                    formatter: function(label, series){
	                        return '<div class="pie-chart-label">'+label+'&nbsp;'+Math.round(series.percent)+'%</div>';
	                    }
	                }
				},
				grow: {	active: false}
			},
			legend:{show:false},
			grid: {
	            hoverable: true,
	            clickable: true
	        },
	        tooltip: true, //activate tooltip
			tooltipOpts: {
				content: "%s : %y.1"+"%",
				shifts: {
					x: -30,
					y: -50
				}
			}
		});
	});
	}//end if

	//Pie simple chart
    if (divElement.hasClass('simple-pie')) {
	$(function () {
		var data = [
		    { label: "USA",  data: 38, color: "#88bbc8"},
		    { label: "Brazil",  data: 23, color: "#ed7a53"},
		    { label: "India",  data: 15, color: "#9FC569"},
		    { label: "Turkey",  data: 9, color: "#bbdce3"},
		    { label: "France",  data: 7, color: "#9a3b1b"},
		    { label: "China",  data: 5, color: "#5a8022"},
		    { label: "Germany",  data: 3, color: "#2c7282"}
		];

	    $.plot($(".simple-pie"), data, 
		{
			series: {
				pie: { 
					show: true,
					highlight: {
						opacity: 0.1
					},
					radius: 1,
					stroke: {
						color: '#fff',
						width: 2
					},
					startAngle: 2,
				    combine: {
	                    color: '#353535',
	                    threshold: 0.05
	                },
	                label: {
	                    show: true,
	                    radius: 1,
	                    formatter: function(label, series){
	                        return '<div class="pie-chart-label">'+label+'&nbsp;'+Math.round(series.percent)+'%</div>';
	                    }
	                }
				},
				grow: {	active: false}
			},
			legend:{show:false},
			grid: {
	            hoverable: true,
	            clickable: true
	        },
	        tooltip: true, //activate tooltip
			tooltipOpts: {
				content: "%s : %y.1"+"%",
				shifts: {
					x: -30,
					y: -50
				}
			}
		});
	});
	}//end if


	//Ordered bars chart
    if (divElement.hasClass('order-bars-chart')) {
	$(function () {
		//some data
		var d1 = [];
	    for (var i = 0; i <= 10; i += 1)
	        d1.push([i, parseInt(Math.random() * 30)]);
	 
	    var d2 = [];
	    for (var i = 0; i <= 10; i += 1)
	        d2.push([i, parseInt(Math.random() * 30)]);
	 
	    var d3 = [];
	    for (var i = 0; i <= 10; i += 1)
	        d3.push([i, parseInt(Math.random() * 30)]);
	 
	    var ds = new Array();
	 
	     ds.push({
	     	label: "Data One",
	        data:d1,
	        bars: {order: 1}
	    });
	    ds.push({
	    	label: "Data Two",
	        data:d2,
	        bars: {order: 2}
	    });
	    ds.push({
	    	label: "Data Three",
	        data:d3,
	        bars: {order: 3}
	    });

		var options = {
				bars: {
					show:true,
					barWidth: 0.2,
					fill:1
				},
				grid: {
					show: true,
				    aboveData: false,
				    color: "#3f3f3f" ,
				    labelMargin: 5,
				    axisMargin: 0, 
				    borderWidth: 0,
				    borderColor:null,
				    minBorderMargin: 5 ,
				    clickable: true, 
				    hoverable: true,
				    autoHighlight: false,
				    mouseActiveRadius: 20
				},
		        series: {
		        	grow: {active:false}
		        },
		        legend: { position: "ne" },
		        colors: chartColours,
		        tooltip: true, //activate tooltip
				tooltipOpts: {
					content: "%s : %y.0",
					shifts: {
						x: -30,
						y: -50
					}
				}
		};

		$.plot($(".order-bars-chart"), ds, options);
	});
	}//end if

	//Stacked bars chart
    if (divElement.hasClass('stacked-bars-chart')) {
	$(function () {
		//some data
		var d1 = [];
	    for (var i = 0; i <= 10; i += 1)
	        d1.push([i, parseInt(Math.random() * 30)]);
	 
	    var d2 = [];
	    for (var i = 0; i <= 10; i += 1)
	        d2.push([i, parseInt(Math.random() * 30)]);
	 
	    var d3 = [];
	    for (var i = 0; i <= 10; i += 1)
	        d3.push([i, parseInt(Math.random() * 30)]);
	 
	    var ds = new Array();
	 
	     ds.push({
	     	label: "Data One",
	        data:d1
	    });
	    ds.push({
	    	label: "Data Two",
	        data:d2
	    });
	    ds.push({
	    	label: "Data Tree",
	        data:d3
	    });

		var stack = 0, bars = true, lines = false, steps = false;

		var options = {
				grid: {
					show: true,
				    aboveData: false,
				    color: "#3f3f3f" ,
				    labelMargin: 5,
				    axisMargin: 0, 
				    borderWidth: 0,
				    borderColor:null,
				    minBorderMargin: 5 ,
				    clickable: true, 
				    hoverable: true,
				    autoHighlight: true,
				    mouseActiveRadius: 20
				},
		        series: {
		        	grow: {active:false},
		        	stack: stack,
	                lines: { show: lines, fill: true, steps: steps },
	                bars: { show: bars, barWidth: 0.5, fill:1}
			    },
		        xaxis: {ticks:11, tickDecimals: 0},
		        legend: { position: "se" },
		        colors: chartColours,
		        shadowSize:1,
		        tooltip: true, //activate tooltip
				tooltipOpts: {
					content: "%s : %y.0",
					shifts: {
						x: -30,
						y: -50
					}
				}
		};

		$.plot($(".stacked-bars-chart"), ds, options);
	});
	}//end if



	//Lines chart without points
    if (divElement.hasClass('lines-chart')) {
	$(function () {

		//some data
		var d1 = [[1, 3+randNum()], [2, 6+randNum()], [3, 9+randNum()], [4, 12+randNum()],[5, 15+randNum()],[6, 18+randNum()],[7, 21+randNum()],[8, 15+randNum()],[9, 18+randNum()],[10, 21+randNum()],[11, 24+randNum()],[12, 27+randNum()],[13, 30+randNum()],[14, 33+randNum()],[15, 24+randNum()],[16, 27+randNum()],[17, 30+randNum()],[18, 33+randNum()],[19, 36+randNum()],[20, 39+randNum()],[21, 42+randNum()],[22, 45+randNum()],[23, 36+randNum()],[24, 39+randNum()],[25, 42+randNum()],[26, 45+randNum()],[27,38+randNum()],[28, 51+randNum()],[29, 55+randNum()], [30, 60+randNum()]];
		var d2 = [[1, randNum()-5], [2, randNum()-4], [3, randNum()-4], [4, randNum()],[5, 4+randNum()],[6, 4+randNum()],[7, 5+randNum()],[8, 5+randNum()],[9, 6+randNum()],[10, 6+randNum()],[11, 6+randNum()],[12, 2+randNum()],[13, 3+randNum()],[14, 4+randNum()],[15, 4+randNum()],[16, 4+randNum()],[17, 5+randNum()],[18, 5+randNum()],[19, 2+randNum()],[20, 2+randNum()],[21, 3+randNum()],[22, 3+randNum()],[23, 3+randNum()],[24, 2+randNum()],[25, 4+randNum()],[26, 4+randNum()],[27,5+randNum()],[28, 2+randNum()],[29, 2+randNum()], [30, 3+randNum()]];
		//define placeholder class
		var placeholder = $(".lines-chart");
		//graph options
		var options = {
				grid: {
					show: true,
				    aboveData: true,
				    color: "#3f3f3f" ,
				    labelMargin: 5,
				    axisMargin: 0, 
				    borderWidth: 0,
				    borderColor:null,
				    minBorderMargin: 5 ,
				    clickable: true, 
				    hoverable: true,
				    autoHighlight: true,
				    mouseActiveRadius: 20
				},
		        series: {
		        	grow: {active:false},
		            lines: {
	            		show: true,
	            		fill: true,
	            		lineWidth: 2,
	            		steps: false
		            	},
		            points: {show:false}
		        },
		        legend: { position: "se" },
		        yaxis: { min: 0 },
		        xaxis: {ticks:11, tickDecimals: 0},
		        colors: chartColours,
		        shadowSize:1,
		        tooltip: true, //activate tooltip
				tooltipOpts: {
					content: "%s : %y.0",
					shifts: {
						x: -30,
						y: -50
					}
				}
		    };   
	
        	$.plot(placeholder, [ 

        		{
        			label: "Visits", 
        			data: d1,
        			lines: {fillColor: "#f2f7f9"},
        			points: {fillColor: "#88bbc8"}
        		}, 
        		{	
        			label: "Unique Visits", 
        			data: d2,
        			lines: {fillColor: "#fff8f2"},
        			points: {fillColor: "#ed7a53"}
        		} 

        	], options);

	});
	}//end if

	//Horizontal bars chart
    if (divElement.hasClass('horizontal-bars-chart')) {
	$(function () {
		//some data
		//Display horizontal graph
    var d1_h = [];
    for (var i = 0; i <= 5; i += 1)
        d1_h.push([parseInt(Math.random() * 30),i ]);

    var d2_h = [];
    for (var i = 0; i <= 5; i += 1)
        d2_h.push([parseInt(Math.random() * 30),i ]);

    var d3_h = [];
    for (var i = 0; i <= 5; i += 1)
        d3_h.push([ parseInt(Math.random() * 30),i]);
                
    var ds_h = new Array();
    ds_h.push({
        data:d1_h,
        bars: {
            horizontal:true, 
            show: true, 
            barWidth: 0.2, 
            order: 1
        }
    });
	ds_h.push({
	    data:d2_h,
	    bars: {
	        horizontal:true, 
	        show: true, 
	        barWidth: 0.2, 
	        order: 2
	    }
	});
	ds_h.push({
	    data:d3_h,
	    bars: {
	        horizontal:true, 
	        show: true, 
	        barWidth: 0.2, 
	        order: 3
	    }
	});


		var options = {
				grid: {
					show: true,
				    aboveData: false,
				    color: "#3f3f3f" ,
				    labelMargin: 5,
				    axisMargin: 0, 
				    borderWidth: 0,
				    borderColor:null,
				    minBorderMargin: 5 ,
				    clickable: true, 
				    hoverable: true,
				    autoHighlight: false,
				    mouseActiveRadius: 20
				},
		        series: {
		        	grow: {active:false},
			        bars: {
			        	show:true,
						horizontal: true,
						barWidth:0.2,
						fill:1
					}
		        },
		        legend: { position: "ne" },
		        colors: chartColours,
		        tooltip: true, //activate tooltip
				tooltipOpts: {
					content: "%s : %y.0",
					shifts: {
						x: -30,
						y: -50
					}
				}
		};

		$.plot($(".horizontal-bars-chart"), ds_h, options);
	});
	}//end if

	//Auto update chart
    if (divElement.hasClass('auto-update-chart')) {
	$(function () {
		// we use an inline data source in the example, usually data would
	    // be fetched from a server
	    var data = [], totalPoints = 300;
	    function getRandomData() {
	        if (data.length > 0)
	            data = data.slice(1);

	        // do a random walk
	        while (data.length < totalPoints) {
	            var prev = data.length > 0 ? data[data.length - 1] : 50;
	            var y = prev + Math.random() * 10 - 5;
	            if (y < 0)
	                y = 0;
	            if (y > 100)
	                y = 100;
	            data.push(y);
	        }

	        // zip the generated y values with the x values
	        var res = [];
	        for (var i = 0; i < data.length; ++i)
	            res.push([i, data[i]])
	        return res;
	    }

	    // Update interval
	    var updateInterval = 200;

	    // setup plot
	    var options = {
	        series: { 
	        	grow: {active:false}, //disable auto grow
	        	shadowSize: 0, // drawing is faster without shadows
	        	lines: {
            		show: true,
            		fill: true,
            		lineWidth: 2,
            		steps: false
	            }
	        },
	        grid: {
				show: true,
			    aboveData: false,
			    color: "#3f3f3f" ,
			    labelMargin: 5,
			    axisMargin: 0, 
			    borderWidth: 0,
			    borderColor:null,
			    minBorderMargin: 5 ,
			    clickable: true, 
			    hoverable: true,
			    autoHighlight: false,
			    mouseActiveRadius: 20
			}, 
			colors: chartColours,
	        tooltip: true, //activate tooltip
			tooltipOpts: {
				content: "Value is : %y.0",
				shifts: {
					x: -30,
					y: -50
				}
			},	
	        yaxis: { min: 0, max: 100 },
	        xaxis: { show: true}
	    };
	    var plot = $.plot($(".auto-update-chart"), [ getRandomData() ], options);

	    function update() {
	        plot.setData([ getRandomData() ]);
	        // since the axes don't change, we don't need to call plot.setupGrid()
	        plot.draw();
	        
	        setTimeout(update, updateInterval);
	    }

	    update();
	});
	}//end if

});//End document ready functions

//generate random number for charts
randNum = function(){
	//return Math.floor(Math.random()*101);
	return (Math.floor( Math.random()* (1+40-20) ) ) + 20;
}

var chartColours = ['#88bbc8', '#ed7a53', '#9FC569', '#bbdce3', '#9a3b1b', '#5a8022', '#2c7282'];

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