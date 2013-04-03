package com.google.appengine.api.xmpp.dev;

import java.util.logging.Logger;
import java.io.BufferedInputStream;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
 
import org.jivesoftware.smack.packet.Presence;
import org.jivesoftware.smack.Chat;
import org.jivesoftware.smack.ConnectionConfiguration;
import org.jivesoftware.smack.MessageListener;
import org.jivesoftware.smack.Roster;
import org.jivesoftware.smack.RosterEntry;
import org.jivesoftware.smack.XMPPConnection;
import org.jivesoftware.smack.XMPPException;
import org.jivesoftware.smack.packet.Message;

public class AppScaleXMPPClient implements MessageListener
{
    private static final Logger logger = Logger.getLogger(AppScaleXMPPClient.class.getName());
    private XMPPConnection connection;
    private String defaultUserName = null;
    private String userName;
    private String password;
    private String url;
    private int port;

    /*
     * AppScale - This method logs in and creates a connection to the AppScale ejabberd server. 
     */
    private void connectAndLogin() throws XMPPException
    {
        logger.info("Logging into xmpp server: username: " + userName + ", url: " + url + "port: " + port);
        ConnectionConfiguration config = new ConnectionConfiguration(url, port);
        connection = new XMPPConnection(config);
        connection.connect();
        defaultUserName = userName + "@" + url;
        connection.login(userName, password);
    }

    private void logoutAndDisconnect() throws XMPPException
    {
        Presence presence = new Presence(Presence.Type.unavailable);
        presence.setFrom(userName);
        connection.disconnect(presence);
    }

    /*
     * AppScale - This method sends a message to ejabberd taking in the recipient, who the message is from
     * (which defaults to the app name if not specified), and the type of message. GAE only supports normal
     * and chat messages. 
     */
    public void sendMessage(String to, String from, String body, String type) throws XMPPException
    {
        logger.fine("Xmpp sendMessage called: to: " + to + ", from: " + from + ", body: " + body + ", type: " + type);
        try
        {
            connectAndLogin();
        }
        catch(XMPPException e)
        {
            logger.severe("Caught XMPPException while trying to login, message: " + e.getMessage());
            e.printStackTrace();
            return;
        }
        Chat chat = connection.getChatManager().createChat(to, null);
        Message msg;
        if(type.equals("chat"))
        {
            msg = new Message(to, Message.Type.chat);   
        }
        else
        {
            msg = new Message(to, Message.Type.normal);
        }
        
        if(from != null && !from.equals("")) 
        {
            msg.setFrom(from);
        }
        else
        {
            msg.setFrom(defaultUserName);
        }
        msg.setBody(body);
        chat.sendMessage(msg);
        try
        {
            logoutAndDisconnect();
        }
        catch(XMPPException e)
        {
            logger.severe("Failed to disconnect and logout of ejabberd, message: " + e.getMessage());
            e.printStackTrace();
        }
    }

    /*
     * AppScale - This method sends data to ejabberd to update a user's presence. It is currently
     * not working, but leaving this code here for the future. 
     */
    public void sendPresence(String to, String from, String status, String type, String show) throws XMPPException
    {
        //TODO - This method gives an stream:error (invalid-from) error, fix it
        Presence presence;
        if(type == null || type.equals("") || type.equals("AVAILABLE"))
        {
            logger.info("Defaulting to Presence.Type (available)");
            presence = new Presence(Presence.Type.available);
        }
        else if("UNAVAILABLE".equals(type))
        {
            presence = new Presence(Presence.Type.unavailable);
        }
        else
        {
            logger.warning("Defaulting to default Presence.Type (available) for unhandled type: " + type);
            presence = new Presence(Presence.Type.available);
        }        
        presence.setStatus(status);
        if(from != null && !from.equals(""))
        {
            presence.setFrom(from);
        }
        else
        {
            presence.setFrom(defaultUserName);
        }
        if(to != null && !to.equals(""))
        {
            presence.setTo(to); 
        }

        if(show == null || show.equals("") || show.equals("NONE"))
        {
            logger.info("Defaulting to Presence.Mode.available");
            presence.setMode(Presence.Mode.available);
        }
        else if(show.equals("CHAT"))
        {
            presence.setMode(Presence.Mode.chat);
        }
        else if(show.equals("DND"))
        {
            presence.setMode(Presence.Mode.dnd);
        }
        else if(show.equals("XA"))
        {
            presence.setMode(Presence.Mode.xa);
        }
        else if(show.equals("AWAY"))
        {
            presence.setMode(Presence.Mode.away);
        }
        else
        {
            logger.info("Defaulting to Presence.Mode.available for mode [" + show + "]");
            presence.setMode(Presence.Mode.available);
        }
        if(connection.isConnected() == false)
        {
            connection.connect();
        }
        connection.sendPacket(presence);
    }
   
    /*
     * AppScale - This method takes in a user name and the login server which
     * has the list of active user names. It executes a system call to ssh into 
     * the login server and execute an ejabberd command to get the list of users. 
     * If the requested user is in that list, we return true.  
     */ 
    public boolean getPresence(String user, String loginServer)
    {
        InputStream inStream = null;
        BufferedInputStream buf = null;
        InputStreamReader inStreamReader = null;
        BufferedReader bufferedReader = null;
        boolean userFound = false;
        Runtime r = Runtime.getRuntime();

        try
        {
            Process p = r.exec("ssh root@" + loginServer + " ejabberdctl connected-users");
            inStream = p.getInputStream();
            buf = new BufferedInputStream(inStream);
            inStreamReader = new InputStreamReader(buf);
            bufferedReader = new BufferedReader(inStreamReader);

            String line;
            while ((line = bufferedReader.readLine()) != null) 
            {
                if(line.startsWith(user))
                {
                    userFound = true;
                    break;
                }
            }

            if (p.waitFor() != 0) 
            {
                logger.warning("AppScaleXMPPClient - Executing ssh command returned unexpected value: " + p.waitFor());
            }
        }
        catch(Exception e)
        {
            logger.warning("Caught exception executing ssh command " + e.getMessage());
        }
        finally
        {
            try{
                if(bufferedReader != null) bufferedReader.close();
                if(inStreamReader != null) inStreamReader.close();
                if(buf != null) buf.close();
                if(inStream != null) inStream.close();
            }
            catch(IOException e)
            {
                logger.warning("Caught IOException closing streams: " + e.getMessage());
            }
        }
        return userFound; 
    } 

    public void processMessage(Chat chat, Message msg)
    { 
        logger.info("MSG RECEIVED - body: " + msg.getBody() + ", subj: " + msg.getSubject());
    }

    public void setUserName(String _userName)
    {
        userName = _userName;
    }

    public void setPassword(String _password)
    {
        password = _password;
    }

    public void setUrl(String _url)
    {
        url = _url;
    }

    public void setPort(int _port)
    {
         port = _port;
    }
}
