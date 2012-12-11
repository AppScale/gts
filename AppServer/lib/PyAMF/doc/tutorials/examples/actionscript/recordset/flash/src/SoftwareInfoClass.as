// Copyright (c) 2007-2009 The PyAMF Project.
// See LICENSE.txt for details.

import mx.remoting.Service;
import mx.remoting.PendingCall;
import mx.remoting.RecordSet;
import mx.remoting.DataGlue;
import mx.rpc.RelayResponder;
import mx.rpc.FaultEvent;
import mx.rpc.ResultEvent;

import mx.controls.DataGrid;
import mx.controls.gridclasses.DataGridColumn;
import mx.controls.ComboBox;
import mx.controls.TextArea;
import mx.controls.TextInput;
import mx.controls.Alert;

var softwareService :	Service;
var software_grd :		DataGrid;
var softwareCat_cmbo :	ComboBox;
var softwareInfo_txt :	TextArea;
var totalRec_txt :		TextInput;
var initialized :		Boolean;

function init()
{
	// initialize the NCD
	mx.remoting.debug.NetDebug.initialize();
	initialized = false;
	softwareService = new Service(
							  "http://localhost:8000",
							  null,
							  "service",
							  null,
							  null);
	// setup ui
	onReveal();
	// load language combo
	var pc:PendingCall = softwareService.getLanguages();
	pc.responder = new RelayResponder( this, "onLanguageData", "onLanguageDataFault" );
}

// initializes the display
function onReveal():Void 
{
	if( !initialized ) {
		var col:DataGridColumn = new DataGridColumn( "ID" );
		software_grd.addColumn( col );
		col = new DataGridColumn( "Active" );
		col.width = 70;
		software_grd.addColumn( col );
		col = new DataGridColumn( "Name" );
		col.width = 100;
		software_grd.addColumn( col );
		col = new DataGridColumn( "Url" );
		col.width = 300;
		software_grd.addColumn( col );
		software_grd.addEventListener( "change", onSoftwareGrid_Change );
		// setup remaining
		totalRec_txt.setStyle( "textAlign", "right" );
		initialized = true;
	}
}

// updateDetails will update the details TextArea and textInput present on the screen.
// Changes will be updated when the selection in DataGrid changes.
function updateDetails():Void 
{
	var curItem:Object = software_grd.selectedItem;
	softwareInfo_txt.text = curItem.Details;
}
	
// gets the software data for the current language selected
function refreshSoftwareData():Void 
{
	var lang:String = softwareCat_cmbo.selectedItem.data;
	var pc:PendingCall = softwareService.getSoftware( lang );
	pc.responder = new RelayResponder( this, "onSoftwareData", "onSoftwareDataFault" );
}

// updates the detail section when a new item is selected in the grid
function onSoftwareGrid_Change( eventObj: Object ):Void 
{
	mx.remoting.debug.NetDebug.trace({ level:"Debug", message:"onSoftwareGrid_Change" });
	eventObj.target._parent.updateDetails();
}

// updates the grid with the new software projects based on the category selected
function onSoftwareCat_Change( eventObj: Object ):Void 
{
	eventObj.target._parent.refreshSoftwareData();
}

// handles the results from the getLanguages() call
function onLanguageData( re:ResultEvent ):Void 
{
	mx.remoting.debug.NetDebug.trace({level:"Debug", message:"onLanguageData" });
	// use data glue to remap the fields so that label = name field and data = id field
	DataGlue.bindFormatStrings( softwareCat_cmbo, re.result, "#Name#", "#ID#" );
	softwareCat_cmbo.addEventListener( "change", onSoftwareCat_Change );
	refreshSoftwareData();
}

// handles the results from the request to getSoftware() method of the service
function onSoftwareData( re:ResultEvent ):Void 
{
	// update customer grid
	var rs:mx.remoting.RecordSet = mx.remoting.RecordSet( re.result );
	rs.setDeliveryMode("page", 25, 2);
	totalRec_txt.text = String( rs.length );
	software_grd.dataProvider = rs;
	software_grd.selectedIndex = 0;
	updateDetails();
}

// handles the display of the fault information related to the software data request 
// to the user
function onSoftwareDataFault( fault:FaultEvent ):Void 
{
	var error:String = "Couldn't retrieve software data: \n";
	for (var d in fault.fault) {
		error += fault.fault[d] + "\n";
	}
	trace(error);
	// notify the user of the problem
	Alert.show( fault.fault.description, "Couldn't retrieve software data", Alert.OK, this );
}

// handles the display of the fault information related to the language data request
// to the user
function onLanguageDataFault( fault:FaultEvent ):Void 
{
	var error:String = "Couldn't retrieve language data: \n";
	for (var d in fault.fault) {
		error += d + ": " + fault.fault[d] + "\n";
	}
	trace(error);
	// notify the user of the problem
	Alert.show( fault.fault.description, "Couldn't retrieve language data", Alert.OK, this );
}