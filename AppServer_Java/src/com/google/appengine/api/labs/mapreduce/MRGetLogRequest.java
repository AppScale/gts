package com.google.appengine.api.labs.mapreduce;

import java.io.Serializable;

import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolSink;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolSource;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolType;


//***** by Yiming *****
// a wrapper of outputPath
//***** end 01-26-2010 *****
public class MRGetLogRequest extends ProtocolMessage<MRGetLogRequest> implements Serializable{

	/**
	 * 
	 */
	/**
	 * 
	 */
	private static final long serialVersionUID = -3276693369944868771L;
	private String outputPath;
	
	public String getData() {
		return this.outputPath;
	}


	public MRGetLogRequest(String outputPath){
		this.outputPath = outputPath;
	}
	
	@Override
	public MRGetLogRequest clear() {
		System.out.println("stub in MRGetLogRequest: clear");
		
		return null;
	}

	@Override
	public int encodingSize() {
		System.out.println("stub in MRGetLogRequest: encodingSize");
		return 0;
	}

	@Override
	public boolean equals(Object arg0) {
		System.out.println("stub in MRGetLogRequest: equals_object");
		return false;
	}

	@Override
	public boolean equals(MRGetLogRequest arg0) {
		System.out.println("stub in MRGetLogRequest: equals");
		return false;
	}

	@Override
	public boolean equals(MRGetLogRequest arg0, boolean arg1) {
		System.out.println("stub in MRGetLogRequest: equals arg1, arg0");
		return false;
	}

	@Override
	public boolean equalsIgnoreUninterpreted(MRGetLogRequest arg0) {
		System.out.println("stub in MRGetLogRequest: ignore");
		return false;
	}

	@Override
	public String findInitializationError() {
		System.out.println("stub in MRGetLogRequest: finderror");
		return null;
	}

	@Override
	public ProtocolType getProtocolType() {
		System.out.println("stub in MRGetLogRequest: getProtocolType");
		return null;
	}

	@Override
	public int hashCode() {
		System.out.println("stub in MRGetLogRequest: hashcode");
		return 0;
	}

	@Override
	public int maxEncodingSize() {
		System.out.println("stub in MRGetLogRequest: maxEncodingSize");
		return 0;
	}

	@Override
	protected boolean merge(ProtocolSource arg0) {
		System.out.println("stub in MRGetLogRequest: merge sourc");
		return false;
	}

	@Override
	public MRGetLogRequest mergeFrom(MRGetLogRequest arg0) {
		System.out.println("stub in MRGetLogRequest: mergefrom");
		return null;
	}

	@Override
	public MRGetLogRequest newInstance() {
		System.out.println("stub in MRGetLogRequest: new instance");
		return null;
	}

	@Override
	public void outputTo(ProtocolSink arg0) {
		System.out.println("stub in MRGetLogRequest: output to");
		
	}


	@Override
	public boolean isInitialized() {
		return true;
	}

}
