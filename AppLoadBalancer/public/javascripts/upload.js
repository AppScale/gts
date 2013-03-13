function displaySpinner(){
    elem = document.getElementById('spinner');
    if(elem) {
	elem.style.display="inline";
    }
}

function disableButton(){
    elem = document.getElementById('upload-button');
    if(elem) {
	elem.disabled="true";
    }
}

function showHelp(){
    elem = document.getElementById('help-text');
    if(elem) {
	elem.style.display="block";
    }
}

function uploading(){
    displaySpinner();
}
