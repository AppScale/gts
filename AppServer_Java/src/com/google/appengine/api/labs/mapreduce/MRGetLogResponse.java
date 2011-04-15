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
//a wrapper of log
//***** end 01-26-2010 *****
public class MRGetLogResponse extends ProtocolMessage<MRGetLogResponse> implements Serializable{

	/**
	 * 
	 */
	private static final long serialVersionUID = 4154031759217070052L;
	private String log;
	
	public String getLog() {
		return log;
	}

	public void setLog(String log) {
		this.log = log;
	}

	@Override
	public void clear() {
		System.out.println("stub in MRGetOututResponse: clear");
		
	}

	@Override
	public int encodingSize() {
		System.out.println("stub in MRGetOututResponse: encodingSize");
		return 0;
	}

	@Override
	public boolean equals(Object arg0) {
		System.out.println("stub in MRGetOututResponse: equals_object");
		return false;
	}

	@Override
	public boolean equals(MRGetLogResponse arg0) {
		System.out.println("stub in MRGetOututResponse: equals");
		return false;
	}

	@Override
	public boolean equals(MRGetLogResponse arg0, boolean arg1) {
		System.out.println("stub in MRGetOututResponse: equals arg1, arg0");
		return false;
	}

	@Override
	public boolean equalsIgnoreUninterpreted(MRGetLogResponse arg0) {
		System.out.println("stub in MRGetOututResponse: ignore");
		return false;
	}

	@Override
	public String findInitializationError() {
		System.out.println("stub in MRGetOututResponse: finderror");
		return null;
	}

	@Override
	public ProtocolType getProtocolType() {
		System.out.println("stub in MRGetOututResponse: getProtocolType");
		return null;
	}

	@Override
	public int hashCode() {
		System.out.println("stub in MRGetOututResponse: hashcode");
		return 0;
	}

	@Override
	public int maxEncodingSize() {
		System.out.println("stub in MRGetOututResponse: maxEncodingSize");
		return 0;
	}

	@Override
	protected boolean merge(ProtocolSource arg0) {		
        try {
        	byte[] buf = arg0.array();
        	ObjectInputStream in = new ObjectInputStream(new ByteArrayInputStream(buf));
    		MRGetLogResponse resp = (MRGetLogResponse)in.readObject();
    		this.log = resp.getLog();
			in.close();
		} catch (IOException e) {
			System.out.println("error in deserializing log response");
			e.printStackTrace();
			return false;
		} catch (ClassNotFoundException e) {
			System.out.println("error in deserializing log response, class not found");
			e.printStackTrace();
			return false;
		}
		
		
		return true;
	}

	@Override
	public MRGetLogResponse mergeFrom(MRGetLogResponse arg0) {
		System.out.println("stub in MRGetOututResponse: mergefrom");
		return null;
	}

	@Override
	public MRGetLogResponse newInstance() {
		System.out.println("stub in MRGetOututResponse: new instance");
		return null;
	}

	@Override
	public void outputTo(ProtocolSink arg0) {
		System.out.println("stub in MRGetOututResponse: output to");
		
	}

	@Override
	public boolean isInitialized() {
		return true;
	}
}
