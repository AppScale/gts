// Create the AMF Channel
var channel:AMFChannel = new AMFChannel( "pyamf-channel", "http://localhost:8080/services" );

// Create a channel set and add your channel(s) to it
var channels:ChannelSet = new ChannelSet();
channels.addChannel( channel );

// Create a new remote object and add listener(s)
var remoteObject:RemoteObject = new RemoteObject( "EchoService" ); // this is the service id
remoteObject.channelSet = channels;
remoteObject.echo.addEventListener( ResultEvent.RESULT, onEchoComplete );

// Make a call to the remote object
remoteObject.echo( "Hello World" );


// Here is the result event listener
private function onEchoComplete( event:ResultEvent ):void 
{
  Alert.show( event.result.toString() );
}
