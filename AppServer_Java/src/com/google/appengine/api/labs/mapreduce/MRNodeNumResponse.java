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
//a wrapper of number available
//***** end 01-26-2010 *****

public class MRNodeNumResponse extends ProtocolMessage<MRNodeNumResponse> implements Serializable{

	/**
	 * 
	 */
	private static final long serialVersionUID = 5768542089455133568L;
	private int num;
	
	
	public int getNum() {
		return num;
	}

	public void setOutput(int num) {
		this.num = num;
	}

	@Override
	public MRNodeNumResponse clear() {
		System.out.println("stub in MRNodeNum: clear");
		
		return null;
	}

	@Override
	public int encodingSize() {
		System.out.println("stub in MRNodeNum: encodingSize");
		return 0;
	}

	@Override
	public boolean equals(Object arg0) {
		System.out.println("stub in MRNodeNum: equals_object");
		return false;
	}

	@Override
	public boolean equals(MRNodeNumResponse arg0) {
		System.out.println("stub in MRNodeNum: equals");
		return false;
	}

	@Override
	public boolean equals(MRNodeNumResponse arg0, boolean arg1) {
		System.out.println("stub in MRNodeNum: equals arg1, arg0");
		return false;
	}

	@Override
	public boolean equalsIgnoreUninterpreted(MRNodeNumResponse arg0) {
		System.out.println("stub in MRNodeNum: ignore");
		return false;
	}

	@Override
	public String findInitializationError() {
		System.out.println("stub in MRNodeNum: finderror");
		return null;
	}

	@Override
	public ProtocolType getProtocolType() {
		System.out.println("stub in MRNodeNum: getProtocolType");
		return null;
	}

	@Override
	public int hashCode() {
		System.out.println("stub in MRNodeNum: hashcode");
		return 0;
	}

	@Override
	public int maxEncodingSize() {
		System.out.println("stub in MRNodeNum: maxEncodingSize");
		return 0;
	}

	@Override
	protected boolean merge(ProtocolSource arg0) {
		try {
	        	byte[] buf = arg0.array();
	        	ObjectInputStream in = new ObjectInputStream(new ByteArrayInputStream(buf));
	        	MRNodeNumResponse resp = (MRNodeNumResponse)in.readObject();
	    		this.num = resp.getNum();
				in.close();
			} catch (IOException e) {
				System.out.println("error in deserializing NodeNum response");
				e.printStackTrace();
				return false;
			} catch (ClassNotFoundException e) {
				System.out.println("error in deserializing NodeNum response, class not found");
				e.printStackTrace();
				return false;
			}
			
			System.out.println("so far so good!");
			return true;
	}

	@Override
	public MRNodeNumResponse mergeFrom(MRNodeNumResponse arg0) {
		System.out.println("stub in MRNodeNum: mergefrom");
		return null;
	}

	@Override
	public MRNodeNumResponse newInstance() {
		System.out.println("stub in MRNodeNum: new instance");
		return null;
	}

	@Override
	public void outputTo(ProtocolSink arg0) {
		System.out.println("stub in MRNodeNum: output to");
		
	}

	@Override
	public boolean isInitialized() {
		return true;
	}
}
