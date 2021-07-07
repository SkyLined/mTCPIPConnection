try: # SSL support is optional
  from mSSL.mExceptions import *;
except:
  cSSLException = None; # can be used to detect support

class cTCPIPException(Exception):
  def __init__(oSelf, sMessage, dxDetails):
    oSelf.sMessage = sMessage;
    oSelf.dxDetails = dxDetails;
    Exception.__init__(oSelf, sMessage, dxDetails);
  
  def __repr__(oSelf):
    return "<%s %s>" % (oSelf.__class__.__name__, oSelf);
  def __str__(oSelf):
    sDetails = ", ".join("%s: %s" % (str(sName), repr(xValue)) for (sName, xValue) in oSelf.dxDetails.items());
    return "%s (%s)" % (oSelf.sMessage, sDetails);

class cTCPIPPortAlreadyInUseAsAcceptorException(cTCPIPException):
  pass;
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

