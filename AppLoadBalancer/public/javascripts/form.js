function setFocus() {
    if(document.forms.length > 0) {
	form = document.forms[0];
	if (form["user_email"]){
	    form["user_email"].focus();
	}
    }
}
