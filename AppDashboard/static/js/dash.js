$(document).ready(function(){
    //in case there's any later special implementations with multiple areas that can be dragged
    //$( ".selector" ).droppable({accept: ".special"});

    $(".sortable").sortable({cursor:"move", helper:"clone",placeholder: "ui-state-highlight"});
    $(".add-panel").click(function() {
        $.ajax({
            method: "post",
            url:"/ajax/render/panel",
            data:{page_content:$(this).siblings("a").first().attr("href")+".html"},
            success: function(result) {
                $("#dash-panels").append(result);
            }
        });
    });
});