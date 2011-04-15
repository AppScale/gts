package com.google.appengine.api.labs.mapreduce;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.ObjectOutput;
import java.io.ObjectOutputStream;

import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolSource;
import com.google.apphosting.api.ApiProxy;

//***** by Yiming *****
//this class handle the local rpc call to implementation of mapreduce
//I was trying to mimic what Google does, but it is too difficult to guess how to make
//real pbs of all requests and responses(basically because of the encodings), so I just use 
//standard Java serialization for thses objects.
//so in summary, this class is the proxy class for all requests and responses who needs make rpc calls
//also this class handles the serialization of them(converting objects to byte array)
//***** end 01-26-2010 *****
public class MapReduceApiHelper {
	static final String PACKAGE = "mapreduce";

	public static <T extends ProtocolMessage<T>, V extends ProtocolMessage<V>> void makeSyncCall(
			String method, ProtocolMessage<T> request,
			ProtocolMessage<V> response) {
		try {
			
	//		System.out.println("-----request----- ");
	//		System.out.println(request.toFlatString());
	//		System.out.println("-----request ends----- ");
			
			 // Serialize to a byte array
			ByteArrayOutputStream bos = new ByteArrayOutputStream() ;
			ObjectOutput  out = new ObjectOutputStream(bos) ;
		    out.writeObject(request);
		    out.close();

		    // Get the bytes of the serialized object
		    byte[] buf = bos.toByteArray();
			
			byte[] responseBytes = ApiProxy.makeSyncCall(PACKAGE,
					method, buf);
			System.out.println("call ok, need to parse object!");
			if (responseBytes != null)
				response.mergeFrom(new ProtocolSource(responseBytes));
			
			
//			System.out.println("-----response----- ");
//			System.out.println(response.toFlatString());
//			System.out.println("-----response ends----- ");
			System.out.println("response is ok");
		} catch (ApiProxy.ApplicationException exception) {
			throw exception;
		}
		catch (IOException e){
			System.out.println("serialization error!");
		}
	}
}
