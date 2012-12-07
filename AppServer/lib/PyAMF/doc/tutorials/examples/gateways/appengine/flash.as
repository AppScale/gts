import flash.net.*;

var netConnection:NetConnection = new NetConnection();
netConnection.connect("http://localhost:8080/");

var responder:Responder = new Responder(onComplete, onFail);
netConnection.call("myservice.echo", responder, "Flash talked to PyAMF.  They both say hello.");

function onComplete(results)
{
        output.htmlText = results;
}

function onFail(results)
{
        for each (var thisResult in results)
        {
                output.text += thisResult;
        }
}