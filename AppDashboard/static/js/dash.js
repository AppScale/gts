$(document).ready(function(){
    //in case there's any later special implementations with multiple areas that can be dragged
    //$( ".selector" ).droppable({accept: ".special"});

    $(".sortable").sortable({
        cursor:"move",
        helper:"clone",
        placeholder: "ui-state-highlight",
        update: function (event,ui) {
            $("#save-layout").html("Save Current Layout");
        }
    });
    $(".add-panel").click(function() {
        var newPanelID = "#" + $(this).attr("data-target");
        if(!$(newPanelID).length){
            $.ajax({
                method: "post",
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
            url:"/ajax/save/layout",
            data:{
                nav:JSON.stringify(nav_array),
                panel:JSON.stringify(panel_array)},
            success: function(result) {
                if(result) {
                    $("#save-layout").html(result);
                }
            },
            error: function (result) {
                $("#save-layout").html(result);
            }
        });
    });
    $("#reset-layout").click(function() {
        $.ajax({
            method:"post",
            url:"/ajax/reset/layout"
        })
    })
});
