package com.google.appengine.api.xmpp;

import com.google.appengine.api.utils.HttpRequestParser;
import java.io.IOException;
import javax.mail.BodyPart;
import javax.mail.MessagingException;
import javax.mail.internet.MimeMultipart;
import javax.servlet.http.HttpServletRequest;

class InboundMessageParser extends HttpRequestParser
{
    static Message parseMessage(HttpServletRequest request) throws IOException
    {
        MessageBuilder builder = new MessageBuilder();
        builder.withMessageType(MessageType.CHAT);

        if(request.getParameter("from") != null)
            builder.withFromJid(new JID(request.getParameter("from")));
        if(request.getParameter("to") != null)
            builder.withRecipientJids(new JID[] { new JID(request.getParameter("to")) });
        if(request.getParameter("body") != null)
            builder.withBody(request.getParameter("body"));
        if(request.getParameter("stanza") != null) 
            builder.withStanza(request.getParameter("stanza"));
    
        return builder.build();
    }
}
