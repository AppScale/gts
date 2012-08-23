package com.google.appengine.api.labs.mapreduce.dev;

import java.io.BufferedInputStream;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.DataInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.security.AccessController;
import java.security.PrivilegedAction;
import java.security.PrivilegedActionException;
import java.security.PrivilegedExceptionAction;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;

import com.google.appengine.api.labs.mapreduce.MRGetLogRequest;
import com.google.appengine.api.labs.mapreduce.MRGetLogResponse;
import com.google.appengine.api.labs.mapreduce.MRGetOutputRequest;
import com.google.appengine.api.labs.mapreduce.MRGetOutputResponse;
import com.google.appengine.api.labs.mapreduce.MRNodeNumRequest;
import com.google.appengine.api.labs.mapreduce.MRNodeNumResponse;
import com.google.appengine.api.labs.mapreduce.MRPutRequest;
import com.google.appengine.api.labs.mapreduce.MRPutResponse;
import com.google.appengine.api.labs.mapreduce.MRRunRequest;
import com.google.appengine.api.labs.mapreduce.MRRunResponse;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.appengine.tools.resources.ResourceLoader;

//***** by Yiming *****
//this class is the local rpc provider of mapreduce,
//it performs operations to run a Map-Reduce job
//basically it call hadoop shell command to run jobs
//it uses ther streaming model "http://hadoop.apache.org/common/docs/r0.15.2/streaming.html"
//***** end 01-26-2010 *****
@ServiceProvider(LocalRpcService.class)
public class LocalMapReduceService implements LocalRpcService {

	// this line is needed for rpc agent to find this class
	public static final String PACKAGE = "mapreduce";

	private static ArrayList<String> workingList = new ArrayList<String>();
	private Thread shutdownHook;

	private static String mrTmpLocation = "/tmp";
	
	private static String hadoopHome = "/opt/appscale/AppDB/hadoop-0.20.0";
	
	private final static Integer maxApiRequestSize = 33554432;

	private final static Double defaultDeadline = 30D;

	private final static Double maximumDeadline = 30D;
	
	private static Map<String, String> supportedLang = new HashMap<String, String>();

	@Override
	public String getPackage() {
		return PACKAGE;
	}

	// the languages supported for executable
	@Override
	public void init(LocalServiceContext arg0, Map<String, String> arg1) {
		supportedLang.put("rb", "ruby");
		supportedLang.put("pl", "perl");
		supportedLang.put("py", "python");
		hadoopHome = ResourceLoader.getResourceLoader().getHadoopHome();
		mrTmpLocation = ResourceLoader.getResourceLoader().getMrTmpLocation();
	}

	@Override
	public void start() {
		System.out.println("stub method in LocalMapReduceService: start");
		AccessController.doPrivileged(new PrivilegedAction<Object>() {
			public Object run() {
				LocalMapReduceService.this.start_();
				return null;
			}

		});

	}

	private void start_() {

		this.shutdownHook = new Thread() {
			public void run() {
				LocalMapReduceService.this.stop();
			}

		};
		Runtime.getRuntime().addShutdownHook(this.shutdownHook);
	}

        public Integer getMaxApiRequestSize() {
        	return maxApiRequestSize;
        }

        public Double getDefaultDeadline(boolean isOfflineRequest) {
                return defaultDeadline;
        }

        public Double getMaximumDeadline(boolean isOfflineRequest) {
                return maximumDeadline;
        }

	@Override
	public void stop() {
		System.out.println("stub method in LocalMapReduceService: stop");
		try {
			Runtime.getRuntime().removeShutdownHook(this.shutdownHook);
		} catch (IllegalStateException ex) {

		}

	}

	// (LocalRpcService.Status status, ImagesServicePb.ImagesCompositeRequest
	// request)
	public MRPutResponse mRPut(LocalRpcService.Status status,
			final MRPutRequest request) {

		MRPutResponse res = new MRPutResponse();

		try {
			boolean s = AccessController
					.doPrivileged(new PrivilegedExceptionAction<Boolean>() {
						public Boolean run() throws IOException {
							System.out
									.println("running mapreduce job in super mode!");

							return writeInput(request.getData(), request
									.getInputLoc());
						}
					});
			res.setSucceeded(s);
		} catch (PrivilegedActionException e) {
			e.printStackTrace();
		}
		return res;

		// Process process = Runtime.getRuntime().exec(cmd);
		// String s = "";
		// BufferedReader br = new BufferedReader(new InputStreamReader(process
		// .getInputStream()));
		// while ((s = br.readLine()) != null)
		// {
		// s += s + "\n";
		// }
		// System.out.println(s);
		//
		// BufferedReader br2 = new BufferedReader(new
		// InputStreamReader(process.getErrorStream()));
		// while (br2.ready() && (s = br2.readLine()) != null)
		// {
		// errOutput += s;
		// }
		// System.out.println(errOutput);

	}

	protected Boolean writeInput(String data, String inputLoc) {
		String fileLoc = mrTmpLocation+"/" + inputLoc;
		File f = new File(fileLoc);
		try {
			if (f.createNewFile()) {
				if (!f.getParent().equals(mrTmpLocation)) {
					System.out.println(f.getParent());
					System.out.println("input name is not valid!");
					return false;
				}
			}
			f.delete();
		} catch (IOException e1) {
			System.out.println("can't create input file!");
			return false;
		}

		System.out.println("write data to "+mrTmpLocation+"/" + inputLoc);
		try {
			BufferedWriter out = new BufferedWriter(new FileWriter(fileLoc));
			out.write(data);
			out.close();
		} catch (IOException e) {
			System.out.println("can't generate input");

			e.printStackTrace();
			return false;
		}
		String removeInput = hadoopHome+"/bin/hadoop fs -rmr "
				+ fileLoc;
		String removeInputCmd[] = new String[4];
		removeInputCmd[0] = hadoopHome+"/bin/hadoop";
		removeInputCmd[1] = "fs";
		removeInputCmd[2] = "-rmr";
		removeInputCmd[3] = fileLoc;
		System.out.println("remove old input in hadoop, if any");
		System.err.println(removeInput);
		try {
			Runtime.getRuntime().exec(removeInputCmd);
		} catch (IOException e) {
			System.out.println("can't remove old input");
			e.printStackTrace();
			return false;

		}

		String put = hadoopHome + "/bin/hadoop fs -put "
				+ fileLoc + " " + fileLoc;
		System.out.println("put input in hadoop");
		System.out.println(put);
		String putCmd[] = new String[5];
		putCmd[0] = hadoopHome+"/bin/hadoop";
		putCmd[1] = "fs";
		putCmd[2] = "-put";
		putCmd[3] = fileLoc;
		putCmd[4] = fileLoc;

		try {
			Process proc = Runtime.getRuntime().exec(putCmd);
			System.out.println("from std of put command!");
			InputStream inputstream = proc.getInputStream();
			InputStreamReader inputstreamreader = new InputStreamReader(
					inputstream);
			BufferedReader bufferedreader = new BufferedReader(
					inputstreamreader);

			// read the instream output

			String line;
			while ((line = bufferedreader.readLine()) != null) {
				System.out.println(line);
			}
			System.out.println("from error td");
			InputStream inputstream2 = proc.getErrorStream();
			InputStreamReader inputstreamreader2 = new InputStreamReader(
					inputstream2);
			BufferedReader bufferedreade2r = new BufferedReader(
					inputstreamreader2);

			// read the errstream output

			while ((line = bufferedreade2r.readLine()) != null) {
				System.out.println(line);
			}
			
			
		} catch (IOException e) {
			System.out.println("can't put file input dfs");
			e.printStackTrace();
			return false;
		}
		return true;
	}

	public MRNodeNumResponse mRNodeNum(LocalRpcService.Status status,
			MRNodeNumRequest request) {
		int num = 1;
		try {
			num = AccessController
					.doPrivileged(new PrivilegedExceptionAction<Integer>() {
						public Integer run() throws IOException {
						
							return getNodeNumber();
						}
					});
		} catch (PrivilegedActionException e) {
			e.printStackTrace();
		}
		MRNodeNumResponse resp = new MRNodeNumResponse();
	
		resp.setOutput(num);
		return resp;

	}

	protected Integer getNodeNumber() {
		int num = 0;
		String fileLoc = ResourceLoader.getResourceLoader().getNumOfNode();
		File file = new File(fileLoc);
		MRNodeNumResponse resp = new MRNodeNumResponse();
		if (!file.exists()) {
			System.out.println("file not exist!");
			num = 1;
			resp.setOutput(num);
			return 1;
		}
		FileInputStream fis = null;
		BufferedInputStream bis = null;
		DataInputStream dis = null;
		BufferedReader d = null;
		String data = null;
		try {
			fis = new FileInputStream(file);

			// Here BufferedInputStream is added for fast reading.
			bis = new BufferedInputStream(fis);
			dis = new DataInputStream(bis);
			d = new BufferedReader(new InputStreamReader(dis));

			// dis.available() returns 0 if the file does not have more lines.
//			while (dis.available() != 0) {
//
//				// this statement reads the line from the file and print it to
//				// the console.
//				data = dis.readLine();
//				System.out.println("got data: " + data);
//				break;
//			}
			data = d.readLine();
			System.out.println("got data: " + data);
			
			// dispose all the resources after using them.
			fis.close();
			bis.close();
			dis.close();
			d.close();

		} catch (FileNotFoundException e) {
			e.printStackTrace();
		} catch (IOException e) {
			e.printStackTrace();
		}

		if (data != null) {

			num = Integer.parseInt(data);
			System.out.println("parse data successful!");
			System.out.println("num is: " + num);
		}
		return num;
	}

//	private void putFileToHadoop(String inputLoc) {
//		System.out.println("putting local file: " + inputLoc + "to hadoop fs");
//
//		String realFilePath = System.getProperty("appRoot") + "/" + inputLoc;
//
//		String realFilePathInHd = "/tmp/" + inputLoc;
//
//		String removeInput = "/root/appscale/AppDB/hadoop-0.20.0/bin/hadoop fs -rmr "
//				+ realFilePathInHd;
//		String removeInputCmd[] = new String[4];
//		removeInputCmd[0] = "/root/appscale/AppDB/hadoop-0.20.0/bin/hadoop";
//		removeInputCmd[1] = "fs";
//		removeInputCmd[2] = "-rmr";
//		removeInputCmd[3] = realFilePathInHd;
//		System.out.println("remove old input in hadoop, if any");
//		System.err.println(removeInput);
//		try {
//			Runtime.getRuntime().exec(removeInputCmd);
//		} catch (IOException e) {
//			System.out.println("can't remove old input");
//			e.printStackTrace();
//
//		}
//
//		String put = "/root/appscale/AppDB/hadoop-0.20.0/bin/hadoop fs -put "
//				+ realFilePath + " " + realFilePathInHd;
//		System.out.println("put input in hadoop");
//		System.out.println(put);
//		String putCmd[] = new String[5];
//		putCmd[0] = "/root/appscale/AppDB/hadoop-0.20.0/bin/hadoop";
//		putCmd[1] = "fs";
//		putCmd[2] = "-put";
//		putCmd[3] = realFilePath;
//		putCmd[4] = realFilePathInHd;
//
//		try {
//			Runtime.getRuntime().exec(putCmd);
//		} catch (IOException e) {
//			System.out.println("can't put file input dfs");
//			e.printStackTrace();
//		}
//
//		// Process process = Runtime.getRuntime().exec(cmd);
//		// String s = "";
//		// BufferedReader br = new BufferedReader(new InputStreamReader(process
//		// .getInputStream()));
//		// while ((s = br.readLine()) != null)
//		// {
//		// s += s + "\n";
//		// }
//		// System.out.println(s);
//		//
//		// BufferedReader br2 = new BufferedReader(new
//		// InputStreamReader(process.getErrorStream()));
//		// while (br2.ready() && (s = br2.readLine()) != null)
//		// {
//		// errOutput += s;
//		// }
//		// System.out.println(errOutput);
//	}

	// run mr job
	public MRRunResponse mRRun(LocalRpcService.Status status,
			final MRRunRequest request) {
		try {
			AccessController
					.doPrivileged(new PrivilegedExceptionAction<Object>() {
						public Object run() throws IOException {
							System.out
									.println("begin running mapreduce job in super mode!");
							// putFileToHadoop(request.getInputPath());
							runTask(request);
							return null;
						}
					});
		} catch (PrivilegedActionException e) {
			e.printStackTrace();
		}

		MRRunResponse resp = new MRRunResponse();
		return resp;
	}

	private void runTask(MRRunRequest request) {
		
		try{
		String mapper = request.getMapper();
		String reducer = request.getReducer();
		String inputPath = request.getInputPath();
		String outputPath = request.getOutputPath();
		Map<String, String> configs = request.getConfigs();

		// check mapper and reducer
		String warDir = System.getProperty("appRoot");
		System.out.println("war dir: "+ warDir);
		File f = new File(warDir + "/" + mapper);
		File f2 = new File(warDir + "/" + reducer);
		if (f.exists()) {
			System.out.println("mapper ok");
			if (f2.exists())
				System.out.println("reducer ok");
			else {
				System.out.println("reducer not exist!");
				return;
			}
		} else{
			System.out.println("no mapper!");
			return;
		}
		System.out.println("get a app root " + System.getProperty("appRoot"));
		String mydir = System.getProperty("appRoot") + "/";
		mapper = "\"" + getLang(mapper) + " " + mydir + mapper + "\"";
		reducer = "\"" + getLang(reducer) + " " + mydir + reducer + "\"";

		String realFilePathInHd = mrTmpLocation+"/" + inputPath;

		String realOutFilePathInHd = mrTmpLocation+"/" + outputPath;

		String removeOutput = hadoopHome+"/bin/hadoop fs -rmr "
				+ realOutFilePathInHd;
		System.out.println("remove old output in hadoop");
		System.out.println(removeOutput + "\n");

		String removeOutputCmd[] = new String[4];
		removeOutputCmd[0] = hadoopHome+"/bin/hadoop";
		removeOutputCmd[1] = "fs";
		removeOutputCmd[2] = "-rmr";
		removeOutputCmd[3] = realOutFilePathInHd;

		try {
			Runtime.getRuntime().exec(removeOutputCmd);
		} catch (IOException e) {
			System.out.println("can't remove old output");
			e.printStackTrace();

		}

		// String fileLoc = "/tmp/" + outputPath;
		//
		// String rmr = "/bin/rm -rf " + fileLoc;
		//
		// System.out.println(rmr);
		// String rmrCmd[] = new String[3];
		// rmrCmd[0] = "/bin/rm";
		// rmrCmd[1] = "-rf";
		// rmrCmd[2] = fileLoc;
		//
		// try {
		// System.out.println("remove old output in /tmp/");
		//
		// Process proc = Runtime.getRuntime().exec(rmrCmd);
		// } catch (Exception e) {
		// e.printStackTrace();
		// }

		String formattedConfig = "";
		if (configs != null && configs.size() != 0) {
			for (String key : configs.keySet())
				formattedConfig = formattedConfig + " -D " + key + "="
						+ configs.get(key);
		}

		String command;
		if (!(formattedConfig == ""))
			command = hadoopHome+"/bin/hadoop jar "+ hadoopHome+"/contrib/streaming/hadoop-0.20.0-streaming.jar "
					+ formattedConfig
					+ " -input "
					+ realFilePathInHd
					+ " -output "
					+ realOutFilePathInHd
					+ " -mapper "
					+ mapper
					+ " -reducer " + reducer;
		else
			command = hadoopHome+"/bin/hadoop jar "+hadoopHome+"/contrib/streaming/hadoop-0.20.0-streaming.jar"
					+ " -input "
					+ realFilePathInHd
					+ " -output "
					+ realOutFilePathInHd
					+ " -mapper "
					+ mapper
					+ " -reducer "
					+ reducer;
		System.out.println(command);

		ArrayList<String> newCom = new ArrayList<String>();

		newCom.add(hadoopHome+"/bin/hadoop");
		newCom.add("jar");
		newCom
				.add(hadoopHome+"/contrib/streaming/hadoop-0.20.0-streaming.jar");
		if (configs != null && configs.size() != 0) {
			for (String key : configs.keySet()) {
				newCom.add("-D");
				newCom.add(key + "=" + configs.get(key));
			}
		}

		newCom.add("-input");
		newCom.add(realFilePathInHd);
		newCom.add("-output");
		newCom.add(realOutFilePathInHd);
		newCom.add("-mapper");
		newCom.add(mapper);
		newCom.add("-reducer");
		newCom.add(reducer);

		String[] a = new String[newCom.size()];
		for (int i = 0; i < a.length; i++) {
			a[i] = newCom.get(i);
		}

		long time1 = System.currentTimeMillis();
		try {
			Process proc = Runtime.getRuntime().exec(a);
			System.out.println("from std");
			InputStream inputstream = proc.getInputStream();
			InputStreamReader inputstreamreader = new InputStreamReader(
					inputstream);
			BufferedReader bufferedreader = new BufferedReader(
					inputstreamreader);

			// read the instream output

			String line;
			while ((line = bufferedreader.readLine()) != null) {
				System.out.println(line);
			}
			System.out.println("from error td");
			InputStream inputstream2 = proc.getErrorStream();
			InputStreamReader inputstreamreader2 = new InputStreamReader(
					inputstream2);
			BufferedReader bufferedreade2r = new BufferedReader(
					inputstreamreader2);

			// read the errstream output

			while ((line = bufferedreade2r.readLine()) != null) {
				System.out.println(line);
			}

			// check for failure

			// try {
			// if (proc.waitFor() != 0) {
			// System.err.println("exit value = " + proc.exitValue());
			// }
			// } catch (InterruptedException e) {
			// System.err.println(e);
			// }

		} catch (IOException e) {
			System.out.println("can't remove old output");
			e.printStackTrace();

		}
		time1 = System.currentTimeMillis() - time1;
		System.err.println("\nTime elapsed = " + time1 / 1000.0 + "seconds\n");
		}catch(Throwable t){
			t.printStackTrace();
		}
	}

	private static String getLang(String file) {

		String ext = file.substring(file.lastIndexOf(".") + 1);
		String lang = supportedLang.get(ext);
		if (lang != null)
			return lang;
		System.err.println("file is not supported: type " + ext);
		return null;
	}

	// relative path to hadoop root
	public MRGetOutputResponse mRGetOutput(LocalRpcService.Status status,
			final MRGetOutputRequest request) {
		String result = "";
		try {
			result = AccessController
					.doPrivileged(new PrivilegedExceptionAction<String>() {
						public String run() throws IOException {
							return getOutput(request.getData());
						}
					});
		} catch (PrivilegedActionException e) {
			e.printStackTrace();
		}
		System.out.println("what is returning is : " + result);
		MRGetOutputResponse resp = new MRGetOutputResponse();
		resp.setOutput(result);
		return resp;

	}

	private String getOutput(String string) {
		String outputPath = string;
		// outputLoc = urllib.unquote(outputLoc)
		String fileLoc = mrTmpLocation+"/" + outputPath;
		//
		String rmr = "/bin/rm -rf " + fileLoc;

		System.out.println(rmr);
		String rmrCmd[] = new String[3];
		rmrCmd[0] = "/bin/rm";
		rmrCmd[1] = "-rf";
		rmrCmd[2] = fileLoc;

		try {
			// not delete
			// System.out.println("result of rm!");
			// System.out.println("have me!");

			Process proc = Runtime.getRuntime().exec(rmrCmd);
			// System.out.println("after remove");
			// System.out.println("from std");
			// InputStream inputstream = proc.getInputStream();
			// InputStreamReader inputstreamreader = new InputStreamReader(
			// inputstream);
			// BufferedReader bufferedreader = new BufferedReader(
			// inputstreamreader);
			//
			// // read the instream output
			//
			// String line;
			// while ((line = bufferedreader.readLine()) != null) {
			// System.out.println(line);
			// }
			// System.out.println("from error td");
			// InputStream inputstream2 = proc.getErrorStream();
			// InputStreamReader inputstreamreader2 = new InputStreamReader(
			// inputstream2);
			// BufferedReader bufferedreade2r = new BufferedReader(
			// inputstreamreader2);
			//
			// // read the errstream output
			//
			// while ((line = bufferedreade2r.readLine()) != null) {
			// System.out.println(line);
			// }
			//
			// // check for failure
			//
			// try {
			// if (proc.waitFor() != 0) {
			// System.err.println("exit value = " + proc.exitValue());
			// }
			// } catch (InterruptedException e) {
			// System.err.println(e);
			// }
			//
		} catch (IOException e) {
			System.out.println("can't remove old output");
			e.printStackTrace();

		}

		String get = hadoopHome+"/bin/hadoop fs -get "
				+ fileLoc + " " + fileLoc;
		System.out.println(get);

		String[] getCmd = new String[5];

		getCmd[0] = hadoopHome+"/bin/hadoop";
		getCmd[1] = "fs";
		getCmd[2] = "-get";
		getCmd[3] = fileLoc;
		getCmd[4] = fileLoc;

		try {
			System.out.println("copying result...");
			Process proc = Runtime.getRuntime().exec(getCmd);

			// System.out.println("from std");
			// InputStream inputstream = proc.getInputStream();
			// InputStreamReader inputstreamreader = new
			// InputStreamReader(
			// inputstream);
			// BufferedReader bufferedreader = new BufferedReader(
			// inputstreamreader);
			//
			// // read the instream output
			//
			// String line;
			// while ((line = bufferedreader.readLine()) != null) {
			// System.out.println(line);
			// }
			// System.out.println("from error td");
			// InputStream inputstream2 = proc.getErrorStream();
			// InputStreamReader inputstreamreader2 = new
			// InputStreamReader(
			// inputstream2);
			// BufferedReader bufferedreade2r = new BufferedReader(
			// inputstreamreader2);
			//
			// // read the errstream output
			//
			// while ((line = bufferedreade2r.readLine()) != null) {
			// System.out.println(line);
			// }
			//
			// // check for failure
			//
			// try {
			// if (proc.waitFor() != 0) {
			// System.err.println("exit value = " + proc.exitValue());
			// }
			// } catch (InterruptedException e) {
			// System.err.println(e);System.out.println("what is returning is : "
			// + result.toString());
			// }

		} catch (IOException e) {
			System.out.println("can't remove old output");
			e.printStackTrace();

		}

		File f;
		System.out.println("try to get " + fileLoc);
		while (true) {
			try {
				Thread.sleep(1000);
			} catch (InterruptedException e) {
				continue;
			}
			f = new File(fileLoc);
			if (!f.exists()) {
				System.out.println("waiting out file!");
			} else
				break;
		}

		System.out.println("output " + "for " + fileLoc + " is ready!");

		StringBuilder result = new StringBuilder();
		String[] children = f.list();
		for (String s : children) {
			if (s.startsWith("part")) {
				System.out.println("find part");
				result.append(getContent(fileLoc + "/" + s) + "\n");
			}
		}
		return result.toString();
	}

	private String getContent(String s) {
		System.out.println("getting result of " + s);
		StringBuilder contents = new StringBuilder();

		try {
			// use buffering, reading one line at a time
			// FileReader always assumes default encoding is OK!
			BufferedReader input = new BufferedReader(new FileReader(s));
			try {
				String line = null; // not declared within while loop
				/*
				 * readLine is a bit quirky : it returns the content of a line
				 * MINUS the newline. it returns null only for the END of the
				 * stream. it returns an empty String if two newlines appear in
				 * a row.
				 */
				while ((line = input.readLine()) != null) {
					contents.append(line);
					contents.append(System.getProperty("line.separator"));
				}
			} finally {
				input.close();
			}
		} catch (IOException ex) {
			ex.printStackTrace();
		}

		return contents.toString();
	}

	public MRGetLogResponse mRGetLog(LocalRpcService.Status status,
			final MRGetLogRequest request) {
		String result = "";
		try {
			result = AccessController
					.doPrivileged(new PrivilegedExceptionAction<String>() {
						public String run() throws IOException {
							return getLogInternal(request.getData());
						}
					});
		} catch (PrivilegedActionException e) {
			e.printStackTrace();
		}

		MRGetLogResponse resp = new MRGetLogResponse();
		resp.setLog(result);
		return resp;
	}

	protected String getLogInternal(String data) {
		String outputPath = data;
		// outputLoc = urllib.unquote(outputLoc)
		String fileLoc = mrTmpLocation+"/" + outputPath;

		String rmr = "/bin/rm -rf " + fileLoc;

		System.out.println("executing... " + rmr);

		String[] rmrCmd = new String[3];
		rmrCmd[0] = "/bin/rm";
		rmrCmd[1] = "-rf";
		rmrCmd[2] = fileLoc;

		try {
			Runtime.getRuntime().exec(rmrCmd);
		} catch (IOException e) {
			System.out.println("can't remove old output for log");
			e.printStackTrace();

		}

		String get = hadoopHome+"/bin/hadoop fs -get "
				+ fileLoc + " " + fileLoc;

		System.out.println("executing... " + get + "for log");

		String getCmd[] = new String[5];
		getCmd[0] = hadoopHome+"/bin/hadoop";
		getCmd[1] = "fs";
		getCmd[2] = "-get";
		getCmd[3] = fileLoc;
		getCmd[4] = fileLoc;
		try {
			Runtime.getRuntime().exec(getCmd);
		} catch (IOException e) {
			System.out.println("can't remove old output");
			e.printStackTrace();

		}

		String contents = "no logs available";

		File f = new File(fileLoc + "/_logs/history");
		StringBuilder sb = new StringBuilder();
		while (true) {
			try {
				Thread.sleep(1000);
			} catch (InterruptedException e1) {
				e1.printStackTrace();
				continue;
			
			}
			if (f.exists()) {
				String[] catCmd = new String[2];
				catCmd[0] = "/bin/cat";
				String[] children = f.list();
				for (int i = 0; i < children.length; i++) {
					System.out.println(children[i]);
					if (!children[i].endsWith(".xml"))
						continue;
					catCmd[1] = fileLoc + "/_logs/history/" + children[i];

					System.out.println("cat " + fileLoc + "/_logs/history/"
							+ children[i]);
					try {
						System.out.println("cmd[1]: " + catCmd[1]);
						Process process = Runtime.getRuntime().exec(catCmd);
						String s = "";
						BufferedReader br = new BufferedReader(
								new InputStreamReader(process.getInputStream()));
						contents = "";
						while ((s = br.readLine()) != null) {
							// s += s + "\n";
							System.out.println(s);
							if (s != null && !s.equals("null")) {
								sb.append(s+"\n");
//								contents += s;
//								contents += '\n';
							}
						}
						System.out.println("result from result file! "
								+ contents);
					} catch (Exception e) {
						e.printStackTrace();
					}
				}
				break;
			}
			else
			{
				System.out.println(f.getAbsolutePath()+" does not exist!");
			}
		}
		if (contents.equals("")){
			System.out.println(sb.toString());
			return sb.toString();
		}else{
			System.out.println(contents);
			return contents;
		
		}
	}

}
