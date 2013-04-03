package com.google.appengine.api.xmpp.dev;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.logging.Logger;
import java.io.PrintStream;
import java.util.Map;

import com.google.appengine.api.xmpp.XMPPServicePb;
import com.google.appengine.api.xmpp.XMPPServicePb.PresenceRequest;
import com.google.appengine.api.xmpp.XMPPServicePb.PresenceResponse;
import com.google.appengine.api.xmpp.XMPPServicePb.XmppInviteRequest;
import com.google.appengine.api.xmpp.XMPPServicePb.XmppInviteResponse;
import com.google.appengine.api.xmpp.XMPPServicePb.XmppMessageRequest;
import com.google.appengine.api.xmpp.XMPPServicePb.XmppMessageResponse;
import com.google.appengine.api.xmpp.XMPPServicePb.XmppMessageResponse.XmppMessageStatus;
import com.google.appengine.api.xmpp.XMPPServicePb.XmppSendPresenceRequest;
import com.google.appengine.api.xmpp.XMPPServicePb.XmppSendPresenceResponse;
import com.google.appengine.tools.development.AbstractLocalRpcService;
import com.google.appengine.tools.development.LatencyPercentiles;
import com.google.appengine.tools.development.LocalRpcService;
import com.google.appengine.tools.development.LocalRpcService.Status;
import com.google.appengine.tools.development.LocalServiceContext;
import com.google.appengine.tools.development.ServiceProvider;

import org.jivesoftware.smack.XMPPException;

@ServiceProvider(LocalRpcService.class)
public final class LocalXMPPService extends AbstractLocalRpcService
{
  private static final Logger logger = Logger.getLogger(LocalXMPPService.class.getName());
  public static final String PACKAGE = "xmpp";
  public static final String APPCONTROLLER = "https://localhost:17443";
  public static final String UASECRET_FILE = "/etc/appscale/secret.key";
  public static final int XMPP_PORT = 5222;
  public static String APPID;
  public static String DOMAIN;
  public static String UASERVER;
  public static String UASECRET;
  public static String USERNAME;
  

  public void start()
  {
  }

  public void stop()
  {
  }

  public void init(LocalServiceContext context, Map<String, String> properties)
  {
      UASECRET = getUASecret();
      APPID = getAppId();
      DOMAIN = properties.get("LOGIN_SERVER");
      UASERVER = "https://" + properties.get("DB_LOCATION");
      USERNAME = APPID;
  }

  public String getPackage()
  {
    return "xmpp";
  }

  @LatencyPercentiles(latency50th=50)
  public XMPPServicePb.PresenceResponse getPresence(LocalRpcService.Status status, XMPPServicePb.PresenceRequest request) {
    AppScaleXMPPClient xmppClient = new AppScaleXMPPClient();
    xmppClient.setUserName(USERNAME);
    xmppClient.setPassword(UASECRET);
    xmppClient.setUrl(DOMAIN);
    xmppClient.setPort(XMPP_PORT); 
    XMPPServicePb.PresenceResponse response = new XMPPServicePb.PresenceResponse();
    String requestedUser = request.getJid();
    boolean available =  xmppClient.getPresence(requestedUser, DOMAIN);
    response.setIsAvailable(available);

    return response;
  }

  @LatencyPercentiles(latency50th=40)
  public XMPPServicePb.XmppMessageResponse sendMessage(LocalRpcService.Status status, XMPPServicePb.XmppMessageRequest request) {
    AppScaleXMPPClient xmppClient = new AppScaleXMPPClient();
    xmppClient.setUserName(USERNAME);
    xmppClient.setPassword(UASECRET);
    xmppClient.setUrl(DOMAIN);
    xmppClient.setPort(XMPP_PORT);
    XMPPServicePb.XmppMessageResponse response = new XMPPServicePb.XmppMessageResponse();
    for (String jid : request.jids()) 
    {
      try
      {
        xmppClient.sendMessage(jid, request.getFromJid(), request.getBody(), request.getType());
        response.addStatus(XMPPServicePb.XmppMessageResponse.XmppMessageStatus.NO_ERROR.getValue());
      }
      catch(XMPPException e)
      {
        //TODO: Parse exception and give appropriate error response
        response.addStatus(XMPPServicePb.XmppMessageResponse.XmppMessageStatus.OTHER_ERROR.getValue());
        logger.warning("Caught XMPPException sending message, error: " + e.getMessage());
        e.printStackTrace();
      }
    }
    return response; 
  }

  public XMPPServicePb.XmppInviteResponse sendInvite(LocalRpcService.Status status, XMPPServicePb.XmppInviteRequest request) {
    logger.severe("sendInvite is not implemented");

    XMPPServicePb.XmppInviteResponse response = new XMPPServicePb.XmppInviteResponse();
    return response;
  }

  @LatencyPercentiles(latency50th=4)
  public XMPPServicePb.XmppSendPresenceResponse sendPresence(LocalRpcService.Status status, XMPPServicePb.XmppSendPresenceRequest request) {
    AppScaleXMPPClient xmppClient = new AppScaleXMPPClient();
    xmppClient.setUserName(USERNAME);
    xmppClient.setPassword(UASECRET);
    xmppClient.setUrl(DOMAIN);
    xmppClient.setPort(XMPP_PORT);
    try
    {
        xmppClient.sendPresence(request.getJid(), request.getFromJid(), request.getStatus(), request.getType(), request.getShow());
    }
    catch(XMPPException e)
    {
        logger.severe("Caught exception sending presence, message: " + e.getMessage());
    }

    XMPPServicePb.XmppSendPresenceResponse response = new XMPPServicePb.XmppSendPresenceResponse();
    return response;
  }

  private String getUASecret()
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

  private String getAppId()
  {
      String appId = System.getProperty("APPLICATION_ID");
      return appId;
  }

}
