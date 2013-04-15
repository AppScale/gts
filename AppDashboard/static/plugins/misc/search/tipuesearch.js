
/*
Tipue Search 1.1.1
Tipue Search Copyright (c) 2012 Tri-State Consultants
Tipue Search is free for both both commercial and non-commercial use and released under the MIT License.
For the latest release, documentation and licence see http://www.tipue.com/search
*/


var tipue_search_w = '';
if (tipuesearch_new_window == 1)
{
     tipue_search_w = ' target="_blank"';      
}

var tipue_search_q = window.location.search;
if (tipue_search_q)
{
     var tipue_search_l_q = tipue_search_q.indexOf('?q=');
     var tipue_search_q = tipue_search_q.substring(tipue_search_l_q + 3);
     tipue_search_q = tipue_search_q.replace(/\+/g, ' ');
     tipue_search_q = decodeURIComponent(tipue_search_q);
     $('#tipue_search_input').val(tipue_search_q);
     
     getTipueSearch(0, 1);
}

$('#tipue_search_button').click(function()
{
     getTipueSearch(0, 1);
});

$('#tipue_search_input').keyup(function(event)
{
     if(event.keyCode == '13')
     {
          getTipueSearch(0, 1);
     }
});

function getTipueSearch(start, replace)
{
     $('#tipue_search_content').hide();     
     var out = '';
     var results = '';
     var show_replace = 0;
     var show_stop = 0;
     
     var d = $('#tipue_search_input').val().toLowerCase();
     d = $.trim(d);
     var d_w = d.split(' ');
          
     for (var i = 0; i < d_w.length; i++)
     {
          for (var f = 0; f < tipuesearch_stop_words.length; f++)
          {
               if (d_w[i] == tipuesearch_stop_words[f])
               {
                    d = d.replace(d_w[i], '');
                    show_stop = 1;
               }
          }
     }
     d = $.trim(d);
     d = d.replace(/\s+/g, ' ');
     d_w = d.split(' ');
          
     if (d.length >= tipuesearch_minimum_length)
     {
          if (replace == 1)
          {
               var d_r = d;
               for (var i = 0; i < d_w.length; i++)
               {
                    for (var f = 0; f < tipuesearch_replace.words.length; f++)
                    {
                         if (d_w[i] == tipuesearch_replace.words[f].word)
                         {
                              d = d.replace(d_w[i], tipuesearch_replace.words[f].replace_with);
                              show_replace = 1;
                         }
                    }
               }
               d_w = d.split(' ');
          }
          
          var d_t = d;
          for (var i = 0; i < d_w.length; i++)
          {
               for (var f = 0; f < tipuesearch_stem.words.length; f++)
               {
                    if (d_w[i] == tipuesearch_stem.words[f].word)
                    {
                         d_t = d_t + ' ' + tipuesearch_stem.words[f].stem;
                    }
               }
          }
          d_w = d_t.split(' ');
         
          var c = 0;
          found = new Array();
          for (var i = 0; i < tipuesearch.pages.length; i++)
          {
               var score = 10000000;
               for (var f = 0; f < d_w.length; f++)
               {
                    var pat = new RegExp(d_w[f], 'i');
                    if (tipuesearch.pages[i].title.search(pat) != -1)
                    {
                         score -= (2000 - i);
                    }
                    if (tipuesearch.pages[i].text.search(pat) != -1)
                    {
                         score -= (1500 - i);
                    }
                    if (tipuesearch.pages[i].tags.search(pat) != -1)
                    {
                         score -= (1000 - i);
                    }                    
               }
               if (score < 10000000)
               {
                    found[c++] = score + '^' + tipuesearch.pages[i].title + '^' + tipuesearch.pages[i].text + '^' + tipuesearch.pages[i].loc;
               }
          }
                   
          if (c != 0)
          {
               if (show_replace == 1)
               {
                    out += '<div id="tipue_search_warning_head">Showing results for ' + d + '</div>';
                    out += '<div id="tipue_search_warning">Show results for <a href="#" onclick="getTipueSearch(0, 0)">' + d_r + '</a></div>'; 
               }
               if (c == 1)
               {
                    out += '<div id="tipue_search_results_count">1 result</div>';
               }
               else
               {
                    c_c = c.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
                    out += '<div id="tipue_search_results_count">' + c_c + ' results</div>';
               }
               
               found.sort();
               var l_o = 0;
               for (var i = 0; i < found.length; i++)
               {
                    var fo = found[i].split('^');
                    if (l_o >= start && l_o < tipuesearch_show + start)
                    {
                         out += '<div class="tipue_search_content_title"><a href="' + fo[3] + '"' + tipue_search_w + '>' +  fo[1] + '</a></div>';
  
                         var t = fo[2];
                         var t_d = '';
                         var t_w = t.split(' ');
                         if (t_w.length < tipuesearch_descriptive_words)
                         {
                              t_d = t;
                         }
                         else
                         {
                              for (var f = 0; f < tipuesearch_descriptive_words; f++)
                              {
                                   t_d += t_w[f] + ' '; 	
                              }
                         }
                         t_d = $.trim(t_d);
                         if (t_d.charAt(t_d.length - 1) != '.')
                         {
                              t_d += ' ...';
                         }
                         out += '<div class="tipue_search_content_text">' + t_d + '</div>';
                         
                         if (tipuesearch_show_url == 1)
                         {
                              out += '<div class="tipue_search_content_loc"><a href="' + fo[3] + '"' + tipue_search_w + '>' + fo[3] + '</a></div>';
                         }
                    }
                    l_o++;     
               }
                              
               if (c > tipuesearch_show)
               {
                    var pages = Math.ceil(c / tipuesearch_show);
                    var page = (start / tipuesearch_show);
                    out += '<div id="tipue_search_foot"><ul id="tipue_search_foot_boxes">';
                    
                    if (start > 0)
                    {
                        out += '<li><a href="#" onclick="getTipueSearch(' + (start - tipuesearch_show) + ', ' + replace + ')">&#171; Previous</a></li>'; 
                    }
                                        
                    if (page <= 4)
                    {
                         var p_b = pages;
                         if (pages > 5)
                         {
                              p_b = 5;
                         }                    
                         for (var f = 0; f < p_b; f++)
                         {
                              if (f == page)
                              {
                                   out += '<li class="current">' + (f + 1) + '</li>';
                              }
                              else
                              {
                                   out += '<li><a href="#" onclick="getTipueSearch(' + (f * tipuesearch_show) + ', ' + replace + ')">' + (f + 1) + '</a></li>';
                              }
                         }
                    }
                    else
                    {
                         var p_b = pages + 4;
                         if (p_b > pages)
                         {
                              p_b = pages; 
                         }
                         for (var f = page; f < p_b; f++)
                         {
                              if (f == page)
                              {
                                   out += '<li class="current">' + (f + 1) + '</li>';
                              }
                              else
                              {
                                   out += '<li><a href="#" onclick="getTipueSearch(' + (f * tipuesearch_show) + ', ' + replace + ')">' + (f + 1) + '</a></li>';
                              }
                         }                         
                    }
                                       
                    if (page + 1 != pages)
                    {
                        out += '<li><a href="#" onclick="getTipueSearch(' + (start + tipuesearch_show) + ', ' + replace + ')">Next &#187;</a></li>'; 
                    }                    
                    
                    out += '</ul></div>';
               }
          }
          else
          {
               out += '<div id="tipue_search_warning_head">Nothing found</div>'; 
          }          
     }
     else
     {
          if (show_stop == 1)
          {
               out += '<div id="tipue_search_warning_head">Nothing found</div><div id="tipue_search_warning">Common words are largely ignored</div>';     
          }
          else
          {
               out += '<div id="tipue_search_warning_head">Search too short</div>';
               if (tipuesearch_minimum_length == 1)
               {
                    out += '<div id="tipue_search_warning">Should be one character or more</div>';
               }
               else
               {
                    out += '<div id="tipue_search_warning">Should be ' + tipuesearch_minimum_length + ' characters or more</div>';
               }
          }
     }
     
     $('#tipue_search_content').html(out);
     $('#tipue_search_content').slideDown(200);
}


