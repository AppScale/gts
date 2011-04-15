package com.google.appengine.api.labs.mapreduce;

import java.io.Serializable;
import java.util.Map;

import com.google.appengine.repackaged.com.google.io.protocol.ProtocolMessage;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolSink;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolSource;
import com.google.appengine.repackaged.com.google.io.protocol.ProtocolType;

//***** by Yiming *****
//a wrapper of mapper and reducer file, together with the input and output path
//***** end 01-26-2010 *****

public class MRRunRequest extends ProtocolMessage<MRRunRequest> implements Serializable{

	/**
	 * 
	 */
	private static final long serialVersionUID = -6479825807961532531L;
	private String mapper;
	private String reducer;
	
	private String inputPath;
	private String outputPath;
	private Map<String, String> configs;

	public MRRunRequest(String mapper, String reducer, String inputPath, String outputPath, Map<String,String> configs){
		this.mapper = mapper;
		this.reducer = reducer;
		this.inputPath = inputPath;
		this.outputPath = outputPath;
		this.configs = configs;
	}
	
	public String getMapper() {
		return mapper;
	}

	public String getReducer() {
		return reducer;
	}

	public String getInputPath() {
		return inputPath;
	}

	public String getOutputPath() {
		return outputPath;
	}

	public Map<String, String> getConfigs() {
		return configs;
	}

	@Override
	public void clear() {
		System.out.println("stub in MRRunRequest: clear");
		
	}

	@Override
	public int encodingSize() {
		System.out.println("stub in MRRunRequest: encodingSize");
		return 0;
	}

	@Override
	public boolean equals(Object arg0) {
		System.out.println("stub in MRRunRequest: equals_object");
		return false;
	}

	@Override
	public boolean equals(MRRunRequest arg0) {
		System.out.println("stub in MRRunRequest: equals");
		return false;
	}

	@Override
	public boolean equals(MRRunRequest arg0, boolean arg1) {
		System.out.println("stub in MRRunRequest: equals arg1, arg0");
		return false;
	}

	@Override
	public boolean equalsIgnoreUninterpreted(MRRunRequest arg0) {
		System.out.println("stub in MRRunRequest: ignore");
		return false;
	}

	@Override
	public String findInitializationError() {
		System.out.println("stub in MRRunRequest: finderror");
		return null;
	}

	@Override
	public ProtocolType getProtocolType() {
		System.out.println("stub in MRRunRequest: getProtocolType");
		return null;
	}

	@Override
	public int hashCode() {
		System.out.println("stub in MRRunRequest: hashcode");
		return 0;
	}

	@Override
	public int maxEncodingSize() {
		System.out.println("stub in MRRunRequest: maxEncodingSize");
		return 0;
	}

	@Override
	protected boolean merge(ProtocolSource arg0) {
		System.out.println("stub in MRRunRequest: merge sourc");
		return false;
	}

	@Override
	public MRRunRequest mergeFrom(MRRunRequest arg0) {
		System.out.println("stub in MRRunRequest: mergefrom");
		return null;
	}

	@Override
	public MRRunRequest newInstance() {
		System.out.println("stub in MRRunRequest: new instance");
		return null;
	}

	@Override
	public void outputTo(ProtocolSink arg0) {
		System.out.println("stub in MRRunRequest: output to");
		
	}

	@Override
	public boolean isInitialized() {
		return true;
	}

}
