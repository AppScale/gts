// Aurora Menu v1.0
// Design and conception by Aurora Studio http://www.aurora-studio.co.uk
// Plugin development by Invent Partners http://www.inventpartners.com
// Copyright Invent Partners & Aurora Studio 2009

var auroraMenuSpeed = 150;

$(document).ready(function(){
	$.cookie('testcookie' , 'expanded')
	var auroramenucount = 0;
	$('.auroramenu').each(function(){
		var auroramenuitemcount = 0;
		$(this).children('li').children('ul').each(function(){
			if($.cookie('arMenu_' + auroramenucount + '_arItem_' + auroramenuitemcount) == 1){
				$(this).siblings('a').attr('onClick' , 'auroraMenuItem(\'' + auroramenucount + '\' , \'' + auroramenuitemcount + '\' , \'0\'); return false;');
				$(this).parent().children('.aurorahide').css("display","inline");
				$(this).parent().children('.aurorashow').css("display","none");
			} else {
				$(this).css("display","none");
				$(this).siblings('a').attr('onClick' , 'auroraMenuItem(\'' + auroramenucount + '\' , \'' + auroramenuitemcount + '\' , \'1\'); return false;');
				$(this).parent().children('.aurorahide').css("display","none");
				$(this).parent().children('.aurorashow').css("display","inline");
			}
			auroramenuitemcount ++;
		});
		auroramenucount ++;
	});
});
function auroraMenuItem(menu , item , show){
    $.cookie('arMenu_' + menu + '_arItem_' + item , show);
	var auroramenucount = 0;
	$('.auroramenu').each(function(){
		if(menu == auroramenucount){	
			var auroramenuitemcount = 0;
			$(this).children('li').children('ul').each(function(){
				if(item == auroramenuitemcount){
					if(show == 1){
						$(this).slideDown(auroraMenuSpeed);
						//$(this).click(auroraMenuItemHide(menu , item));
						$(this).siblings('a').attr('onClick' , 'auroraMenuItem(\'' + menu + '\' , \'' + item + '\' , \'0\'); return false;');
						$(this).parent().children('.aurorahide').css("display","inline");
						$(this).parent().children('.aurorashow').css("display","none");
					} else {
						$(this).slideUp(auroraMenuSpeed);
						$(this).siblings('a').attr('onClick' , 'auroraMenuItem(\'' + menu + '\' , \'' + item + '\' , \'1\'); return false;');
						$(this).parent().children('.aurorahide').css("display","none");
						$(this).parent().children('.aurorashow').css("display","inline");
					}
				}
				auroramenuitemcount ++;
			});
		}
		auroramenucount ++;
	});
}