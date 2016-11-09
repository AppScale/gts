$(document).ready(function(){
    /*enable sortable areas*/
    $(".sortable").sortable({
        cursor:"move",
        helper:"clone",
        placeholder: "ui-state-highlight",
        update: function (event,ui) {
            $("#save-layout").html("Save Current Layout");
            $("#reset-layout").html("Reset Current Layout");
        }
    });

    /*enable tooltips*/
    $('[data-toggle="tooltip"]').tooltip();

    /*add panel functionality*/
    $(".add-panel").click(function() {
        var newPanelID = "#" + $(this).attr("data-target");
        if(!$(newPanelID).length){
            $.ajax({
                method: "get",
                url: "/ajax/render/panel",
                async: false,
                data: {
                    page_content: $(this).siblings("a").first().attr("href") + ".html",
                    key_val: $(this).attr("data-target")
                },
                success: function (result) {
                    $("#dash-panels").append(result);
                }
            });
            var offset = $(newPanelID).offset();
            $("html, body").animate({scrollTop:offset.top});
        }
        $("#save-layout").html("Save Current Layout");
        $("#reset-layout").html("Reset Current Layout");
    });

    /*save layout functionality*/
    $("#save-layout").click(function() {
        var nav_array = [];
        $(".nav-heading-collapse").each(function(){
            nav_array.push($(this).attr("href").match("\#(.*)")[1]);
        });
        var panel_array = [];
        $("#dash-panels .panel-collapse").each(function(){
            panel_array.push($(this).attr("id"));
        });
        $.ajax({
            method: "post",
            url:"/ajax/layout/save",
            data:{
                nav:JSON.stringify(nav_array),
                panel:JSON.stringify(panel_array)},
            success: function(result) {
                if(result) {
                    $("#save-layout").html(result);
                    location.reload();
                }
            },
            error: function (result) {
                $("#save-layout").html(result);
            }
        });
    });
    /*reset layout functionality*/
    $("#reset-layout").click(function() {
        $.ajax({
            method:"post",
            url:"/ajax/layout/reset",
            success: function(result) {
                if(result) {
                    $("#reset-layout").html("Reset");
                    location.reload();
                }
            },
            error: function (result) {
                $("#reset-layout").html("Try Again");
            }
        })
    })
});
