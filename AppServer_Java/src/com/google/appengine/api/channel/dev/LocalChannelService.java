package com.google.appengine.api.channel.dev;

import org.jivesoftware.smack.XMPPException;
import com.google.appengine.api.xmpp.dev.AppScaleXMPPClient;
import com.google.apphosting.api.ApiBasePb;
import com.google.apphosting.api.ApiProxy;
import com.google.appengine.api.channel.ChannelServicePb;
import com.google.appengine.api.channel.ChannelServicePb.ChannelServiceError.ErrorCode;
import com.google.appengine.api.channel.ChannelServicePb.CreateChannelRequest;
import com.google.appengine.api.channel.ChannelServicePb.CreateChannelResponse;
import com.google.appengine.api.channel.ChannelServicePb.SendMessageRequest;
import com.google.appengine.api.urlfetch.dev.LocalURLFetchService;
import com.google.appengine.tools.development.AbstractLocalRpcService;
import com.google.appengine.tools.development.LatencyPercentiles;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalRpcService.Status;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.appengine.tools.development.ServiceProvider;
import com.google.apphosting.api.ApiBasePb.VoidProto;
import com.google.apphosting.api.ApiProxy.ApplicationException;
import java.util.HashMap;
import java.util.Map;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Formatter;
import java.io.BufferedReader;
import java.io.FileReader;
import java.util.logging.Logger;
import java.io.BufferedInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;



@ServiceProvider(LocalRpcService.class)
public final class LocalChannelService extends AbstractLocalRpcService
{
  private static final Logger logger = Logger.getLogger(LocalChannelService.class.getName());
  public static final int CHANNEL_TOKEN_DEFAULT_DURATION = 120;
  public static final String PACKAGE = "channel";
  private ChannelManager channelManager;
  private LocalURLFetchService fetchService;
  private final String UASECRET_FILE = "/etc/appscale/secret.key";
  private final String USER_EXISTS = "Error: user already exists";
  private final String COMMIT_USER_SUCCESS = "true";
  private final String SOAP_ERROR = "internal error";
  private final int XMPP_PORT = 5222;
  public void start()
  {
  }

  public void stop()
  {
    this.channelManager = null;
    if (this.fetchService != null) {
      this.fetchService.stop();
      this.fetchService = null;
    }
  }

  public ChannelManager getChannelManager() {
    return this.channelManager;
  }

  public void init(LocalServiceContext context, Map<String, String> properties)
  {
    this.fetchService = createFetchService(properties);
    this.channelManager = new ChannelManager(context.getLocalServerEnvironment(), this.fetchService);
  }

  public LocalURLFetchService createFetchService(Map<String, String> properties)
  {
    if ((properties.get("appengine.dev.inbound-services") == null) || (!((String)properties.get("appengine.dev.inbound-services")).contains("channel_presence")))
    {
      return null;
    }

    LocalURLFetchService fetchService = new LocalURLFetchService();
    fetchService.init(null, new HashMap());

    fetchService.setTimeoutInMs(30000);

    return fetchService;
  }

  public String getPackage()
  {
    return "channel";
  }

  public ChannelServicePb.CreateChannelResponse createChannel(LocalRpcService.Status status, ChannelServicePb.CreateChannelRequest request)
  {
    if ((!request.hasApplicationKey()) || (request.getApplicationKey().equals(""))) {
      throw new ApiProxy.ApplicationException(ChannelServicePb.ChannelServiceError.ErrorCode.INVALID_CHANNEL_KEY.getValue());
    }

    ChannelServicePb.CreateChannelResponse response = new ChannelServicePb.CreateChannelResponse();
    int duration;
    if (request.hasDurationMinutes())
      duration = request.getDurationMinutes();
    else {
      duration = 120;
    }

    //AppScale - bypassing channelManager and making a call to the uaserver
    String appId = getAppId();
    String applicationKey = request.getApplicationKey();
    String uniqueAppId = getSha1AsString(appId + applicationKey); 
    String domain = getDomain();
    String clientId = "channel~" + uniqueAppId + "~" + applicationKey + "@" + domain;
    String encryptedPassword = getSha1AsString(clientId + applicationKey);
    String secret = getSecret();
    String UAServerUrl = getUAServerUrl();
    String soapResult = execSoapCall(clientId, encryptedPassword, secret, UAServerUrl); 

    if(soapResult.equals(SOAP_ERROR))
    {
        throw new LocalChannelFailureException("Failed to create channel for application key: " + request.getApplicationKey());
    }
    else if(soapResult.equals(USER_EXISTS) == false && soapResult.equals(COMMIT_USER_SUCCESS) == false)
    {
        throw new LocalChannelFailureException("Unexpected response from soap call: " + soapResult);
    }

    response.setToken(clientId);    
    return response;
  }

  @LatencyPercentiles(latency50th=40)
  public ApiBasePb.VoidProto sendChannelMessage(LocalRpcService.Status status, ChannelServicePb.SendMessageRequest request)
  {
    if ((!request.hasMessage()) || (request.getMessage().equals(""))) {
      throw new ApiProxy.ApplicationException(ChannelServicePb.ChannelServiceError.ErrorCode.BAD_MESSAGE.getValue());
    }
    
    //Bypassing channelManager and sending an XMPP message
    String appId = getAppId();
    String secret = getSecret();
    String domain = getDomain();
    String applicationKey = request.getApplicationKey();
    String from = appId + "@" + domain;
    
    AppScaleXMPPClient xmppClient = new AppScaleXMPPClient();
    xmppClient.setUserName(appId);
    xmppClient.setPassword(secret);
    xmppClient.setUrl(domain);
    xmppClient.setPort(XMPP_PORT);
    
    String uniqueAppId = getSha1AsString(appId + applicationKey);
    String toJid = "channel~" + uniqueAppId + "~" + applicationKey + "@"  + domain;
    try
    {
        xmppClient.sendMessage(toJid, from, request.getMessage(), "chat");
    }
    catch(XMPPException e)
    {
        logger.severe("Caught exception sending xmpp message to application key: " + applicationKey + ", error: " + e.getMessage());
    }
    ApiBasePb.VoidProto response = new ApiBasePb.VoidProto();
    return response;
  }

  private String getSha1AsString(String input)
  {
      MessageDigest md = null;
      try
      {
          md = MessageDigest.getInstance("SHA-1"); 
      }
      catch(NoSuchAlgorithmException e)
      {
          logger.severe("Caught NoSuchAlgorithmException getting sha-1");
          return null;
      }
      byte[] hash = md.digest(input.getBytes());
      Formatter formatter = new Formatter();
      for (byte b : hash) 
      {
          formatter.format("%02x", b);
      }
      return formatter.toString();
  }

  private String getAppId()
  {
      String appId = System.getProperty("APPLICATION_ID");
      return appId;
  }

  private String getDomain()
  {
      String domain = System.getProperty("LOGIN_SERVER");
      return domain;
  }

  private String getSecret()
  {
      String secret = "";
      try
      {
          BufferedReader br = new BufferedReader(new FileReader(UASECRET_FILE));
          secret = br.readLine();
          br.close();
      }
      catch(Exception e)
      {
          logger.severe("Error getting secret from ua_secret file: " + e.getMessage());
      }
      return secret;
  }

  private String getUAServerUrl()
  {
      String url = "https://" + System.getProperty("DB_LOCATION") + ":4343";
      return url;
  }

  private String execSoapCall(String clientId, String password, String secret, String url)
  {
      InputStream inStream = null;
      BufferedInputStream buf = null;
      InputStreamReader inStreamReader = null;
      BufferedReader bufferedReader = null;
      Runtime r = Runtime.getRuntime();
      String result = null;
      try
      {
          Process p = r.exec("python /root/appscale/AppServer_Java/src/com/google/appengine/api/channel/dev/soap_helper.py " + clientId + " " + password + " " + secret + " " + url); 
          inStream = p.getInputStream();
          buf = new BufferedInputStream(inStream);
          inStreamReader = new InputStreamReader(buf);
          bufferedReader = new BufferedReader(inStreamReader);

          String line;
          while ((line = bufferedReader.readLine()) != null) 
          {
              result = line;
          }

          if (p.waitFor() != 0) 
          {
              logger.warning("LocalChannelService - Executing python script returned unexpected value: " + p.waitFor());
          }
      }
      catch(Exception e)
      {
          logger.severe("LocalChannelService - Failed to execute SOAP call to create channel: " + e.getMessage());
          return "internal error";
      }
      return result;
  }
}
