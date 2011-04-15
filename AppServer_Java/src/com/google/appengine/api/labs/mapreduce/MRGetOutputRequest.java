package com.google.appengine.api.labs.mapreduce;

import java.io.Serializable;

import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolSink;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolSource;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolType;


//***** by Yiming *****
//a wrapper of outputPath
//***** end 01-26-2010 *****
public class MRGetOutputRequest extends ProtocolMessage<MRGetOutputRequest> implements Serializable{

	/**
	 * 
	 */
	private static final long serialVersionUID = -788984698269703933L;
	private String outputPath;
	
	public String getData() {
		return this.outputPath;
	}


	public MRGetOutputRequest(String outputPath){
		this.outputPath = outputPath;
	}
	
	@Override
	public void clear() {
		System.out.println("stub in MRGetOutputRequest: clear");
		
	}

	@Override
	public int encodingSize() {
		System.out.println("stub in MRGetOutputRequest: encodingSize");
		return 0;
	}

	@Override
	public boolean equals(Object arg0) {
		System.out.println("stub in MRGetOutputRequest: equals_object");
		return false;
	}

	@Override
	public boolean equals(MRGetOutputRequest arg0) {
		System.out.println("stub in MRGetOutputRequest: equals");
		return false;
	}

	@Override
	public boolean equals(MRGetOutputRequest arg0, boolean arg1) {
		System.out.println("stub in MRGetOutputRequest: equals arg1, arg0");
		return false;
	}

	@Override
	public boolean equalsIgnoreUninterpreted(MRGetOutputRequest arg0) {
		System.out.println("stub in MRGetOutputRequest: ignore");
		return false;
	}

	@Override
	public String findInitializationError() {
		System.out.println("stub in MRGetOutputRequest: finderror");
		return null;
	}

	@Override
	public ProtocolType getProtocolType() {
		System.out.println("stub in MRGetOutputRequest: getProtocolType");
		return null;
	}

	@Override
	public int hashCode() {
		System.out.println("stub in MRGetOutputRequest: hashcode");
		return 0;
	}

	@Override
	public int maxEncodingSize() {
		System.out.println("stub in MRGetOutputRequest: maxEncodingSize");
		return 0;
	}

	@Override
	protected boolean merge(ProtocolSource arg0) {
		System.out.println("stub in MRGetOutputRequest: merge sourc");
		return false;
	}

	@Override
	public MRGetOutputRequest mergeFrom(MRGetOutputRequest arg0) {
		System.out.println("stub in MRGetOutputRequest: mergefrom");
		return null;
	}

	@Override
	public MRGetOutputRequest newInstance() {
		System.out.println("stub in MRGetOutputRequest: new instance");
		return null;
	}

	@Override
	public void outputTo(ProtocolSink arg0) {
		System.out.println("stub in MRGetOutputRequest: output to");
		
	}


	@Override
	public boolean isInitialized() {
		return true;
	}

}
