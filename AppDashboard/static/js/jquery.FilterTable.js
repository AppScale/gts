/**
 * jquery.filterTable
 *
 * This plugin will add a search filter to tables. When typing in the filter,
 * any rows that do not contain the filter will be hidden.
 *
 * Utilizes bindWithDelay() if available. https://github.com/bgrins/bindWithDelay
 *
 * @version v1.3
 * @author Sunny Walker, swalker@hawaii.edu
 */
(function($){
	$.expr[':'].filterTableFind = function(a,i,m) {
		return $(a).text().toUpperCase().indexOf(m[3].toUpperCase())>=0;
	}; //case insensitive searching
	$.fn.filterTable = function(options) {
		var defaults = {
				hideTFootOnFilter: false,               //if true, the table's tfoot(s) will be hidden when the table is filtered
				containerClass:    'filter-table',      //class to apply to the container
				containerTag:      'p',                 //tag name of the container
				highlightClass:    'alt',               //class applied to cells containing the filter term
				inputType:         'search',            //tag name of the filter input tag
				label:             'Filter:',           //text to precede the filter input tag
				minRows:           8,                   //don't show the filter on tables with less than this number of rows
				placeholder:       'search this table', //HTML5 placeholder text for the filter field
				quickList:         [],                  //list of phrases to quick fill the search
				quickListClass:    'quick',             //class of each quick list item
				callback:          null                 //callback function: function(term, table){}
			},
			hsc = function(text) { return text.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); },
			settings = $.extend({}, defaults, options);

		var doFiltering = function(table, q) {
				var tbody=table.find('tbody');
				if (q==='') {
					tbody.find('tr').show().addClass('visible');
					tbody.find('td').removeClass(settings.highlightClass);
					if (settings.hideTFootOnFilter) table.find('tfoot').show(); //show footer when not filtered
				} else {
					tbody.find('tr').hide().removeClass('visible').filter(':filterTableFind("'+q.replace(/(['"])/g,'\\$1')+'")').show().addClass('visible');
					if (settings.hideTFootOnFilter) table.find('tfoot').hide(); //hide footer when filtered
					tbody.find('td').removeClass(settings.highlightClass).filter(':filterTableFind("'+q.replace(/(['"])/g,'\\$1')+'")').addClass(settings.highlightClass); //highlight (class=alt) cells with the content
					if (settings.callback) settings.callback(q, table);
				}
			};

		return this.each(function(){
			var t=$(this), tbody=t.find('tbody'), container=null, filter=null;
			if (t[0].nodeName==='TABLE' && tbody.length>0 && (settings.minRows===0 || (settings.minRows>0 && tbody.find('tr').length>settings.minRows)) && !t.prev().hasClass(settings.containerClass)) { //only if object is a table and there's a tbody and at least minRows trs and hasn't already had a filter added
				container = $('<'+settings.containerTag+' />');
				if (settings.containerClass!=='') container.addClass(settings.containerClass);
				container.prepend(settings.label+' ');
				filter = $('<input type="'+settings.inputType+'" placeholder="'+settings.placeholder+'" />');
				if ($.fn.bindWithDelay) {
					filter.bindWithDelay('keyup', function(){
						doFiltering(t, $(this).val());
					}, 200);
				} else {
					filter.bind('keyup', function(){
						doFiltering(t, $(this).val());
					});
				}
				filter.bind('click search', function(){
					doFiltering(t, $(this).val());
				});
				container.append(filter);
				if (settings.quickList.length>0) {
					$.each(settings.quickList, function(i, v) {
						var q = $('<a href="#" class="'+settings.quickListClass+'">'+hsc(v)+'</a>');
						q.bind('click',function(e){
							e.preventDefault();
							filter.val(v).focus().trigger('click');
						});
						container.append(q);
					});
				}
				t.before(container);
			}
		});
	};
})(jQuery);