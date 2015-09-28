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
//a wrapper of output string
//***** end 01-26-2010 *****
public class MRGetOutputResponse extends ProtocolMessage<MRGetOutputResponse> implements Serializable{

	/**
	 * 
	 */
	private static final long serialVersionUID = -485142841740934569L;
	private String output;
	
	
	public String getOutput() {
		return output;
	}

	public void setOutput(String output) {
		this.output = output;
	}

	@Override
	public MRGetOutputResponse clear() {
		System.out.println("stub in MRGetLogResponse: clear");
		
		return null;
	}

	@Override
	public int encodingSize() {
		System.out.println("stub in MRGetLogResponse: encodingSize");
		return 0;
	}

	@Override
	public boolean equals(Object arg0) {
		System.out.println("stub in MRGetLogResponse: equals_object");
		return false;
	}

	@Override
	public boolean equals(MRGetOutputResponse arg0) {
		System.out.println("stub in MRGetLogResponse: equals");
		return false;
	}

	@Override
	public boolean equals(MRGetOutputResponse arg0, boolean arg1) {
		System.out.println("stub in MRGetLogResponse: equals arg1, arg0");
		return false;
	}

	@Override
	public boolean equalsIgnoreUninterpreted(MRGetOutputResponse arg0) {
		System.out.println("stub in MRGetLogResponse: ignore");
		return false;
	}

	@Override
	public String findInitializationError() {
		System.out.println("stub in MRGetLogResponse: finderror");
		return null;
	}

	@Override
	public ProtocolType getProtocolType() {
		System.out.println("stub in MRGetLogResponse: getProtocolType");
		return null;
	}

	@Override
	public int hashCode() {
		System.out.println("stub in MRGetLogResponse: hashcode");
		return 0;
	}

	@Override
	public int maxEncodingSize() {
		System.out.println("stub in MRGetLogResponse: maxEncodingSize");
		return 0;
	}

	@Override
	protected boolean merge(ProtocolSource arg0) {
		   try {
	        	byte[] buf = arg0.array();
	        	ObjectInputStream in = new ObjectInputStream(new ByteArrayInputStream(buf));
	    		MRGetOutputResponse resp = (MRGetOutputResponse)in.readObject();
	    		this.output = resp.getOutput();
				in.close();
			} catch (IOException e) {
				System.out.println("error in deserializing output response");
				e.printStackTrace();
				return false;
			} catch (ClassNotFoundException e) {
				System.out.println("error in deserializing output response, class not found");
				e.printStackTrace();
				return false;
			}
			
			
			return true;
	}

	@Override
	public MRGetOutputResponse mergeFrom(MRGetOutputResponse arg0) {
		System.out.println("stub in MRGetLogResponse: mergefrom");
		return null;
	}

	@Override
	public MRGetOutputResponse newInstance() {
		System.out.println("stub in MRGetLogResponse: new instance");
		return null;
	}

	@Override
	public void outputTo(ProtocolSink arg0) {
		System.out.println("stub in MRGetLogResponse: output to");
		
	}

	@Override
	public boolean isInitialized() {
		return true;
	}
}
