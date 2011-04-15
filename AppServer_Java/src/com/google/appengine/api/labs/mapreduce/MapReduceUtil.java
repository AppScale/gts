package com.google.appengine.api.labs.mapreduce;

import java.util.Map;


//***** by Yiming *****
//this class contains the mapreduce apis to perform a Map-Reduce job
//namely, putMRInput, runMRJob, getNumOfNodes, getMROutput, getMROutput, getMRLog
//and they are consistent with the python version
//***** end 01-26-2010 *****
public class MapReduceUtil {
	
	//gen a local input file
	public static boolean putMRInput(String data, String inputLoc){
		MRPutRequest request = new MRPutRequest(data, inputLoc);
		MRPutResponse response = new MRPutResponse();
		MapReduceApiHelper.makeSyncCall("MRPut", request,response);
		return response.isSucceeded();
	}
	
	//run mr job
	public static void runMRJob(String mapper, String reducer, String inputPath, String outputPath, Map<String,String> configs){
		MRRunRequest request = new MRRunRequest(mapper, reducer, inputPath, outputPath, configs);
		MRRunResponse response = new MRRunResponse();
		MapReduceApiHelper.makeSyncCall("MRRun", request,response);
	}
	
	//get the number of nodes available 
	public static int getNumOfNodes(){
		MRNodeNumRequest request = new MRNodeNumRequest();
		MRNodeNumResponse response = new MRNodeNumResponse();
		MapReduceApiHelper.makeSyncCall("MRNodeNum", request,response);
		
		System.out.println("resulting num: "+ response.getNum());
		return response.getNum();		    	
	}

	//relative path to hadoop root
	public static String getMROutput(String outputPath){
		MRGetOutputRequest request = new MRGetOutputRequest(outputPath);
		MRGetOutputResponse response = new MRGetOutputResponse();
		MapReduceApiHelper.makeSyncCall("MRGetOutput", request,response);
		return response.getOutput();
	}
	
	public static String getMRLog(String outputPath){
		MRGetLogRequest request = new MRGetLogRequest(outputPath);
		MRGetLogResponse response = new MRGetLogResponse();
		MapReduceApiHelper.makeSyncCall("MRGetLog", request,response);
		return response.getLog();
	}
	

}
