package com.google.appengine.tools.resources;

public class ResourceLoader {
	
	private static ResourceLoader res = null;
	
	public static ResourceLoader getResouceLoader(){
		if (res == null)
			res = new ResourceLoader();
		if (System.getenv("APPSCALE_HOME") != null){
			apphome  = System.getenv("APPSCALE_HOME");
		}
		System.out.println("appscale home is: "+ apphome);
		return res;
	}
	private static String apphome= "/opt/appscale";
	
	private String DEFAULT_KEY_STORE_PATH = "/AppServer_Java/keystore.ImportKey";
	private String DEFAULT_KEYSTORE_PASSWORD = "importkey";

	public String getKeyStorePath() {
		return apphome+DEFAULT_KEY_STORE_PATH;
	}
	
	public String getKetStorePwd(){
		return DEFAULT_KEYSTORE_PASSWORD;
	}

	public boolean getDatastoreSeurityMode() {
		//true means SSL(https), otherwise normal http
		return true;
	}

	public int getPbServerPort() {
		//8443 is the current port
		return 8443;
	}

	public String getPbServerIp() {
		String dbLocation = System.getProperty("DB_LOCATION");
		if (dbLocation != null)
			return dbLocation;
		return null;
	}
	
	public String getMemcachedServerIp(){
		return apphome+"/.appscale/all_ips";
	}
	
	public String getNumOfNode(){
		return apphome+"/.appscale/num_of_nodes";
	}

	public String getHadoopHome() {
		String hadoophome = "/AppDB/hadoop-0.20.0";
		hadoophome = apphome + "/AppDB/hadoop-0.20.0";
		return hadoophome;
	}

	public String getMrTmpLocation() {
		return "/tmp";
	}
	
}
