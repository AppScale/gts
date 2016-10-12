$(document).ready(function(){
    //in case there's any later special implementations with multiple areas that can be dragged
    //$( ".selector" ).droppable({accept: ".special"});

    $(".sortable").sortable({cursorAt:{top:3}, cursor:"move", helper:"clone"});
});