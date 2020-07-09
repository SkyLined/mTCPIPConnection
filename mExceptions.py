try: # SSL support is optional
  from mSSL.mExceptions import *;
except:
  cSSLException = None; # can be used to detect support

class cTCPIPException(Exception):
  def __init__(oSelf, sMessage, xDetails):
    oSelf.sMessage = sMessage;
    oSelf.xDetails = xDetails;
    Exception.__init__(oSelf, (sMessage, xDetails));
  
  def __repr__(oSelf):
    return "<%s %s>" % (oSelf.__class__.__name__, oSelf);
  def __str__(oSelf):
    sDetails = str(oSelf.xDetails) if not hasattr(oSelf.xDetails, "fsToString") else oSelf.xDetails.fsToString();
    return "%s (%s)" % (oSelf.sMessage, sDetails);

class cTCPIPConnectionRefusedException(cTCPIPException):
  pass;
class cTCPIPConnectionDisconnectedException(cTCPIPException):
  pass;
class cTCPIPInvalidAddressException(cTCPIPException):
  pass;
class cTCPIPConnectTimeoutException(cTCPIPException):
  pass;
class cTCPIPDataTimeoutException(cTCPIPException):
  pass;
class cDNSUnknownHostnameException(cTCPIPException):
  pass;
class cTCPIPConnectionShutdownException(cTCPIPException):
  pass;

