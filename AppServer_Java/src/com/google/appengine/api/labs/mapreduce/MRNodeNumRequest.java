package com.google.appengine.api.labs.mapreduce;

import java.io.Serializable;

import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolSink;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolSource;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolType;


//***** by Yiming *****
//a wrapper of ...nothing, just a request
//***** end 01-26-2010 *****

public class MRNodeNumRequest extends ProtocolMessage<MRNodeNumRequest> implements Serializable{


	/**
	 * 
	 */
	private static final long serialVersionUID = 7088956625147480383L;

	@Override
	public void clear() {
		System.out.println("stub in MRNodeNumRequest: clear");
		
	}

	@Override
	public int encodingSize() {
		System.out.println("stub in MRNodeNumRequest: encodingSize");
		return 0;
	}

	@Override
	public boolean equals(Object arg0) {
		System.out.println("stub in MRNodeNumRequest: equals_object");
		return false;
	}

	@Override
	public boolean equals(MRNodeNumRequest arg0) {
		System.out.println("stub in MRNodeNumRequest: equals");
		return false;
	}

	@Override
	public boolean equals(MRNodeNumRequest arg0, boolean arg1) {
		System.out.println("stub in MRNodeNumRequest: equals arg1, arg0");
		return false;
	}

	@Override
	public boolean equalsIgnoreUninterpreted(MRNodeNumRequest arg0) {
		System.out.println("stub in MRNodeNumRequest: ignore");
		return false;
	}

	@Override
	public String findInitializationError() {
		System.out.println("stub in MRNodeNumRequest: finderror");
		return null;
	}

	@Override
	public ProtocolType getProtocolType() {
		System.out.println("stub in MRNodeNumRequest: getProtocolType");
		return null;
	}

	@Override
	public int hashCode() {
		System.out.println("stub in MRNodeNumRequest: hashcode");
		return 0;
	}

	@Override
	public int maxEncodingSize() {
		System.out.println("stub in MRNodeNumRequest: maxEncodingSize");
		return 0;
	}

	@Override
	protected boolean merge(ProtocolSource arg0) {
		System.out.println("stub in MRNodeNumRequest: merge sourc");
		return false;
	}

	@Override
	public MRNodeNumRequest mergeFrom(MRNodeNumRequest arg0) {
		System.out.println("stub in MRNodeNumRequest: mergefrom");
		return null;
	}

	@Override
	public MRNodeNumRequest newInstance() {
		System.out.println("stub in MRNodeNumRequest: new instance");
		return null;
	}

	@Override
	public void outputTo(ProtocolSink arg0) {
		System.out.println("stub in MRNodeNumRequest: output to");
		
	}

	@Override
	public boolean isInitialized() {
		return true;
	}

}
