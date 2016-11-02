# Copyright (c) 2001 Zope Corporation and Contributors. All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
"""Namespace module, so you don't need PyXML
"""

ident = "$Id$"
try:
    from xml.ns import SOAP, SCHEMA, WSDL, XMLNS, DSIG, ENCRYPTION
    DSIG.C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"

except:
    class SOAP:
        ENV = "http://schemas.xmlsoap.org/soap/envelope/"
        ENC = "http://schemas.xmlsoap.org/soap/encoding/"
        ACTOR_NEXT = "http://schemas.xmlsoap.org/soap/actor/next"

    class SCHEMA:
        XSD1 = "http://www.w3.org/1999/XMLSchema"
        XSD2 = "http://www.w3.org/2000/10/XMLSchema"
        XSD3 = "http://www.w3.org/2001/XMLSchema"
        XSD_LIST = [XSD1, XSD2, XSD3]
        XSI1 = "http://www.w3.org/1999/XMLSchema-instance"
        XSI2 = "http://www.w3.org/2000/10/XMLSchema-instance"
        XSI3 = "http://www.w3.org/2001/XMLSchema-instance"
        XSI_LIST = [XSI1, XSI2, XSI3]
        BASE = XSD3

    class WSDL:
        BASE = "http://schemas.xmlsoap.org/wsdl/"
        BIND_HTTP = "http://schemas.xmlsoap.org/wsdl/http/"
        BIND_MIME = "http://schemas.xmlsoap.org/wsdl/mime/"
        BIND_SOAP = "http://schemas.xmlsoap.org/wsdl/soap/"
        BIND_SOAP12 = "http://schemas.xmlsoap.org/wsdl/soap12/"

    class XMLNS:
        BASE = "http://www.w3.org/2000/xmlns/"
        XML = "http://www.w3.org/XML/1998/namespace"
        HTML = "http://www.w3.org/TR/REC-html40"

    class DSIG:
        BASE = "http://www.w3.org/2000/09/xmldsig#"
        C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
        C14N_COMM = \
            "http://www.w3.org/TR/2000/CR-xml-c14n-20010315#WithComments"
        C14N_EXCL = "http://www.w3.org/2001/10/xml-exc-c14n#"
        DIGEST_MD2 = "http://www.w3.org/2000/09/xmldsig#md2"
        DIGEST_MD5 = "http://www.w3.org/2000/09/xmldsig#md5"
        DIGEST_SHA1 = "http://www.w3.org/2000/09/xmldsig#sha1"
        ENC_BASE64 = "http://www.w3.org/2000/09/xmldsig#base64"
        ENVELOPED = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
        HMAC_SHA1 = "http://www.w3.org/2000/09/xmldsig#hmac-sha1"
        SIG_DSA_SHA1 = "http://www.w3.org/2000/09/xmldsig#dsa-sha1"
        SIG_RSA_SHA1 = "http://www.w3.org/2000/09/xmldsig#rsa-sha1"
        XPATH = "http://www.w3.org/TR/1999/REC-xpath-19991116"
        XSLT = "http://www.w3.org/TR/1999/REC-xslt-19991116"

    class ENCRYPTION:
        BASE = "http://www.w3.org/2001/04/xmlenc#"
        BLOCK_3DES = "http://www.w3.org/2001/04/xmlenc#des-cbc"
        BLOCK_AES128 = "http://www.w3.org/2001/04/xmlenc#aes128-cbc"
        BLOCK_AES192 = "http://www.w3.org/2001/04/xmlenc#aes192-cbc"
        BLOCK_AES256 = "http://www.w3.org/2001/04/xmlenc#aes256-cbc"
        DIGEST_RIPEMD160 = "http://www.w3.org/2001/04/xmlenc#ripemd160"
        DIGEST_SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"
        DIGEST_SHA512 = "http://www.w3.org/2001/04/xmlenc#sha512"
        KA_DH = "http://www.w3.org/2001/04/xmlenc#dh"
        KT_RSA_1_5 = "http://www.w3.org/2001/04/xmlenc#rsa-1_5"
        KT_RSA_OAEP = "http://www.w3.org/2001/04/xmlenc#rsa-oaep-mgf1p"
        STREAM_ARCFOUR = "http://www.w3.org/2001/04/xmlenc#arcfour"
        WRAP_3DES = "http://www.w3.org/2001/04/xmlenc#kw-3des"
        WRAP_AES128 = "http://www.w3.org/2001/04/xmlenc#kw-aes128"
        WRAP_AES192 = "http://www.w3.org/2001/04/xmlenc#kw-aes192"
        WRAP_AES256 = "http://www.w3.org/2001/04/xmlenc#kw-aes256"


class WSRF_V1_2:

    '''
    OASIS WSRF Specifications Version 1.2
    '''

    class LIFETIME:
        XSD_DRAFT1 = "http://docs.oasis-open.org/wsrf/2004/06/"
        "wsrf-WS-ResourceLifetime-1.2-draft-01.xsd"
        XSD_DRAFT4 = "http://docs.oasis-open.org/wsrf/2004/11/"
        "wsrf-WS-ResourceLifetime-1.2-draft-04.xsd"

        WSDL_DRAFT1 = "http://docs.oasis-open.org/wsrf/2004/06/"
        "wsrf-WS-ResourceLifetime-1.2-draft-01.wsdl"
        WSDL_DRAFT4 = "http://docs.oasis-open.org/wsrf/2004/11/"
        "wsrf-WS-ResourceLifetime-1.2-draft-04.wsdl"
        LATEST = WSDL_DRAFT4
        WSDL_LIST = (WSDL_DRAFT1, WSDL_DRAFT4)
        XSD_LIST = (XSD_DRAFT1, XSD_DRAFT4)

    class PROPERTIES:
        XSD_DRAFT1 = "http://docs.oasis-open.org/wsrf/2004/06/"
        "wsrf-WS-ResourceProperties-1.2-draft-01.xsd"
        XSD_DRAFT5 = "http://docs.oasis-open.org/wsrf/2004/11/"
        "wsrf-WS-ResourceProperties-1.2-draft-05.xsd"

        WSDL_DRAFT1 = "http://docs.oasis-open.org/wsrf/2004/06/"
        "wsrf-WS-ResourceProperties-1.2-draft-01.wsdl"
        WSDL_DRAFT5 = "http://docs.oasis-open.org/wsrf/2004/11/"
        "wsrf-WS-ResourceProperties-1.2-draft-05.wsdl"
        LATEST = WSDL_DRAFT5
        WSDL_LIST = (WSDL_DRAFT1, WSDL_DRAFT5)
        XSD_LIST = (XSD_DRAFT1, XSD_DRAFT5)

    class BASENOTIFICATION:
        XSD_DRAFT1 = "http://docs.oasis-open.org/wsn/2004/06/"
        "wsn-WS-BaseNotification-1.2-draft-01.xsd"
        WSDL_DRAFT1 = "http://docs.oasis-open.org/wsn/2004/06/"
        "wsn-WS-BaseNotification-1.2-draft-01.wsdl"
        LATEST = WSDL_DRAFT1
        WSDL_LIST = (WSDL_DRAFT1,)
        XSD_LIST = (XSD_DRAFT1,)

    class BASEFAULTS:
        XSD_DRAFT1 = "http://docs.oasis-open.org/wsrf/2004/06/"
        "wsrf-WS-BaseFaults-1.2-draft-01.xsd"
        XSD_DRAFT3 = "http://docs.oasis-open.org/wsrf/2004/11/"
        "wsrf-WS-BaseFaults-1.2-draft-03.xsd"
        # LATEST = DRAFT3
        # WSDL_LIST = (WSDL_DRAFT1, WSDL_DRAFT3)
        XSD_LIST = (XSD_DRAFT1, XSD_DRAFT3)

WSRF = WSRF_V1_2
WSRFLIST = (WSRF_V1_2,)


class OASIS:

    '''URLs for Oasis specifications
    '''
    WSSE = "http://docs.oasis-open.org/wss/2004/01/"
    "oasis-200401-wss-wssecurity-secext-1.0.xsd"
    UTILITY = "http://docs.oasis-open.org/wss/2004/01/"
    "oasis-200401-wss-wssecurity-utility-1.0.xsd"

    class X509TOKEN:
        Base64Binary = "http://docs.oasis-open.org/wss/2004/01/"
        "oasis-200401-wss-soap-message-security-1.0#Base64Binary"
        STRTransform = "http://docs.oasis-open.org/wss/2004/01/"
        "oasis-200401-wss-soap-message-security-1.0"
        PKCS7 = "http://docs.oasis-open.org/wss/2004/01/"
        "oasis-200401-wss-x509-token-profile-1.0#PKCS7"
        X509 = "http://docs.oasis-open.org/wss/2004/01/"
        "oasis-200401-wss-x509-token-profile-1.0#X509"
        X509PKIPathv1 = "http://docs.oasis-open.org/wss/2004/01/"
        "oasis-200401-wss-x509-token-profile-1.0#X509PKIPathv1"
        X509v3SubjectKeyIdentifier = "http://docs.oasis-open.org/wss/2004/01/"
        "oasis-200401-wss-x509-token-profile-1.0#X509v3SubjectKeyIdentifier"

    LIFETIME = WSRF_V1_2.LIFETIME.XSD_DRAFT1
    PROPERTIES = WSRF_V1_2.PROPERTIES.XSD_DRAFT1
    BASENOTIFICATION = WSRF_V1_2.BASENOTIFICATION.XSD_DRAFT1
    BASEFAULTS = WSRF_V1_2.BASEFAULTS.XSD_DRAFT1


class APACHE:

    '''
    This name space is defined by AXIS and it is used for the TC in
    TCapache.py, Map and file attachment (DataHandler)
    '''
    AXIS_NS = "http://xml.apache.org/xml-soap"


class WSTRUST:
    BASE = "http://schemas.xmlsoap.org/ws/2004/04/trust"
    ISSUE = "http://schemas.xmlsoap.org/ws/2004/04/trust/Issue"


class WSSE:
    BASE = "http://schemas.xmlsoap.org/ws/2002/04/secext"
    TRUST = WSTRUST.BASE


class WSU:
    BASE = "http://schemas.xmlsoap.org/ws/2002/04/utility"
    UTILITY = "http://schemas.xmlsoap.org/ws/2002/07/utility"


class WSR:
    PROPERTIES = \
        "http://www.ibm.com/xmlns/stdwip/web-services/WS-ResourceProperties"
    LIFETIME = \
        "http://www.ibm.com/xmlns/stdwip/web-services/WS-ResourceLifetime"


class WSA200508:
    ADDRESS = "http://www.w3.org/2005/08/addressing"
    ANONYMOUS = "%s/anonymous" % ADDRESS
    FAULT = "%s/fault" % ADDRESS


class WSA200408:
    ADDRESS = "http://schemas.xmlsoap.org/ws/2004/08/addressing"
    ANONYMOUS = "%s/role/anonymous" % ADDRESS
    FAULT = "%s/fault" % ADDRESS


class WSA200403:
    ADDRESS = "http://schemas.xmlsoap.org/ws/2004/03/addressing"
    ANONYMOUS = "%s/role/anonymous" % ADDRESS
    FAULT = "%s/fault" % ADDRESS


class WSA200303:
    ADDRESS = "http://schemas.xmlsoap.org/ws/2003/03/addressing"
    ANONYMOUS = "%s/role/anonymous" % ADDRESS
    FAULT = None


WSA = WSA200408
WSA_LIST = (WSA200508, WSA200408, WSA200403, WSA200303)


class _WSAW(str):

    """
    Define ADDRESS attribute to be compatible with WSA* layout
    """
    ADDRESS = property(lambda s: s)

WSAW200605 = _WSAW("http://www.w3.org/2006/05/addressing/wsdl")

WSAW_LIST = (WSAW200605,)


class WSP:
    POLICY = "http://schemas.xmlsoap.org/ws/2002/12/policy"


class BEA:
    SECCONV = "http://schemas.xmlsoap.org/ws/2004/04/sc"
    SCTOKEN = "http://schemas.xmlsoap.org/ws/2004/04/security/sc/sct"


class GLOBUS:
    SECCONV = "http://wsrf.globus.org/core/2004/07/security/secconv"
    CORE = "http://www.globus.org/namespaces/2004/06/core"
    SIG = "http://www.globus.org/2002/04/xmlenc#gssapi-sign"
    TOKEN = "http://www.globus.org/ws/2004/09/security/sc#GSSAPI_GSI_TOKEN"

ZSI_SCHEMA_URI = 'http://www.zolera.com/schemas/ZSI/'
