package com.google.appengine.api.labs.mapreduce;

import java.io.Serializable;

import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolSink;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolSource;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolType;


//***** by Yiming *****
//a wrapper of user-provided data and the path of input
//***** end 01-26-2010 *****

public class MRPutRequest extends ProtocolMessage<MRPutRequest> implements Serializable{

	/**
	 * 
	 */
	private static final long serialVersionUID = 9055931606376414508L;
	private String data;
	private String inputLoc;
	
	public String getData() {
		return data;
	}

	public String getInputLoc() {
		return inputLoc;
	}

	public MRPutRequest(String data, String inputLoc){
		this.data = data;
		this.inputLoc = inputLoc;
	}
	
	@Override
	public void clear() {
		System.out.println("stub in MRPutRequest: clear");
		
	}

	@Override
	public int encodingSize() {
		System.out.println("stub in MRPutRequest: encodingSize");
		return 0;
	}

	@Override
	public boolean equals(Object arg0) {
		System.out.println("stub in MRPutRequest: equals_object");
		return false;
	}

	@Override
	public boolean equals(MRPutRequest arg0) {
		System.out.println("stub in MRPutRequest: equals");
		return false;
	}

	@Override
	public boolean equals(MRPutRequest arg0, boolean arg1) {
		System.out.println("stub in MRPutRequest: equals arg1, arg0");
		return false;
	}

	@Override
	public boolean equalsIgnoreUninterpreted(MRPutRequest arg0) {
		System.out.println("stub in MRPutRequest: ignore");
		return false;
	}

	@Override
	public String findInitializationError() {
		System.out.println("stub in MRPutRequest: finderror");
		return null;
	}

	@Override
	public ProtocolType getProtocolType() {
		System.out.println("stub in MRPutRequest: getProtocolType");
		return null;
	}

	@Override
	public int hashCode() {
		System.out.println("stub in MRPutRequest: hashcode");
		return 0;
	}

	@Override
	public int maxEncodingSize() {
		System.out.println("stub in MRPutRequest: maxEncodingSize");
		return 0;
	}

	@Override
	protected boolean merge(ProtocolSource arg0) {
		System.out.println("stub in MRPutRequest: merge sourc");
		return false;
	}

	@Override
	public MRPutRequest mergeFrom(MRPutRequest arg0) {
		System.out.println("stub in MRPutRequest: mergefrom");
		return null;
	}

	@Override
	public MRPutRequest newInstance() {
		System.out.println("stub in MRPutRequest: new instance");
		return null;
	}

	@Override
	public void outputTo(ProtocolSink arg0) {
		System.out.println("stub in MRPutRequest: output to");
		
	}

	@Override
	public boolean isInitialized() {
		return true;
	}

}
