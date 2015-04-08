package com.google.appengine.api.labs.mapreduce;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.Serializable;

import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolSink;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolSource;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolType;

//***** by Yiming *****
//a wrapper of running result, just a response
//***** end 01-26-2010 *****

public class MRRunResponse extends ProtocolMessage<MRRunResponse> implements Serializable{

	/**
	 * 
	 */
	private static final long serialVersionUID = 6671061287673019327L;

	@Override
	public MRRunResponse clear() {
		System.out.println("stub in MRPutResponse: clear");
		return null;
	}

	@Override
	public int encodingSize() {
		System.out.println("stub in MRPutResponse: encodingSize");
		return 0;
	}

	@Override
	public boolean equals(Object arg0) {
		System.out.println("stub in MRPutResponse: equals_object");
		return false;
	}

	@Override
	public boolean equals(MRRunResponse arg0) {
		System.out.println("stub in MRPutResponse: equals");
		return false;
	}

	@Override
	public boolean equals(MRRunResponse arg0, boolean arg1) {
		System.out.println("stub in MRPutResponse: equals arg1, arg0");
		return false;
	}

	@Override
	public boolean equalsIgnoreUninterpreted(MRRunResponse arg0) {
		System.out.println("stub in MRPutResponse: ignore");
		return false;
	}

	@Override
	public String findInitializationError() {
		System.out.println("stub in MRPutResponse: finderror");
		return null;
	}

	@Override
	public ProtocolType getProtocolType() {
		System.out.println("stub in MRPutResponse: getProtocolType");
		return null;
	}

	@Override
	public int hashCode() {
		System.out.println("stub in MRPutResponse: hashcode");
		return 0;
	}

	@Override
	public int maxEncodingSize() {
		System.out.println("stub in MRPutResponse: maxEncodingSize");
		return 0;
	}

	@Override
	protected boolean merge(ProtocolSource arg0) {
		try {
        	byte[] buf = arg0.array();
        	ObjectInputStream in = new ObjectInputStream(new ByteArrayInputStream(buf));
        	MRRunResponse resp = (MRRunResponse)in.readObject();    	
        	//should set corresponding variables in resp to local variables, but this class doesn't need 
			in.close();
		} catch (IOException e) {
			System.out.println("error in deserializing run response");
			e.printStackTrace();
			return false;
		} catch (ClassNotFoundException e) {
			System.out.println("error in deserializing run response, class not found");
			e.printStackTrace();
			return false;
		}
		
		
		return true;
	}

	@Override
	public MRRunResponse mergeFrom(MRRunResponse arg0) {
		System.out.println("stub in MRPutResponse: mergefrom");
		return null;
	}

	@Override
	public MRRunResponse newInstance() {
		System.out.println("stub in MRPutResponse: new instance");
		return null;
	}

	@Override
	public void outputTo(ProtocolSink arg0) {
		System.out.println("stub in MRPutResponse: output to");
		
	}

	@Override
	public boolean isInitialized() {
		return true;
	}
}
