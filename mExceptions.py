
class cTCPIPException(Exception):
  def __init__(oSelf, sMessage, *, o0Connection = None, dxDetails = None):
    assert isinstance(dxDetails, dict), \
        "dxDetails must be a dict, not %s" % repr(dxDetails);
    oSelf.sMessage = sMessage;
    oSelf.o0Connection = o0Connection;
    oSelf.dxDetails = dxDetails;
    Exception.__init__(oSelf, sMessage, o0Connection, dxDetails);
  
  def fasDetails(oSelf):
    return (
      (["Remote: %s" % str(oSelf.o0Connection.sbRemoteAddress, "ascii", "strict")] if oSelf.o0Connection else [])
      + ["%s: %s" % (str(sName), repr(xValue)) for (sName, xValue) in oSelf.dxDetails.items()]
    );
  def __str__(oSelf):
    return "%s (%s)" % (oSelf.sMessage, ", ".join(oSelf.fasDetails()));
  def __repr__(oSelf):
    return "<%s.%s %s>" % (oSelf.__class__.__module__, oSelf.__class__.__name__, oSelf);

class cTCPIPPortNotPermittedException(cTCPIPException):
  pass;
class cTCPIPPortAlreadyInUseAsAcceptorException(cTCPIPException):
  pass;
class cTCPIPNoAvailablePortsException(cTCPIPException):
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
class cTCPIPDNSUnknownHostnameException(cTCPIPException):
  pass;
class cTCPIPConnectionShutdownException(cTCPIPException):
  pass;
class cTCPIPConnectionCannotBeUsedConcurrentlyException(cTCPIPException):
  pass;

acExceptions = [
  cTCPIPException,
  cTCPIPPortNotPermittedException,
  cTCPIPPortAlreadyInUseAsAcceptorException,
  cTCPIPNoAvailablePortsException,
  cTCPIPConnectionRefusedException,
  cTCPIPConnectionDisconnectedException,
  cTCPIPInvalidAddressException,
  cTCPIPConnectTimeoutException,
  cTCPIPDataTimeoutException,
  cTCPIPDNSUnknownHostnameException,
  cTCPIPConnectionShutdownException,
  cTCPIPConnectionCannotBeUsedConcurrentlyException,
];