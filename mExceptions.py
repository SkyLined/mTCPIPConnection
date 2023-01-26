
class cTCPIPException(Exception):
  def __init__(oSelf, sMessage):
    assert isinstance(sMessage, str), \
        "sMessage must be a str, not %s" % repr(sMessage);
    oSelf.sMessage = sMessage;
    Exception.__init__(oSelf, sMessage);
  
  def __str__(oSelf):
    return "%s (%s)" % (oSelf.sMessage, ", ".join(oSelf.fasDetails()));
  def __repr__(oSelf):
    return "<%s.%s %s>" % (oSelf.__class__.__module__, oSelf.__class__.__name__, oSelf);

class cTCPIPExceptionWithHostname(cTCPIPException):
  def __init__(oSelf, sMessage, sHostname, **dxArguments):
    assert isinstance(sHostname, str), \
        "sHostname must be a str, not %s" % repr(sHostname);
    oSelf.sHostname = sHostname;
    cTCPIPException.__init__(oSelf, sMessage, **dxArguments);
  def fasDetails(oSelf):
    return ["Hostname or IP address: %s" % repr(oSelf.sHostname)];
class cTCPIPDNSUnknownHostnameException(cTCPIPExceptionWithHostname):
  pass;
class cTCPIPNoAvailablePortsException(cTCPIPExceptionWithHostname):
  pass;

class cTCPIPExceptionWithHostnameOrIPAddressAndPortNumber(cTCPIPException):
  def __init__(oSelf, sMessage, sHostnameOrIPAddress, uPortNumber, **dxArguments):
    assert isinstance(sHostnameOrIPAddress, str), \
        "sHostnameOrIPAddress must be a str, not %s" % repr(sHostnameOrIPAddress);
    assert isinstance(uPortNumber, int), \
        "uPortNumber must be an int, not %s" % repr(uPortNumber);
    oSelf.sHostnameOrIPAddress = sHostnameOrIPAddress;
    oSelf.uPortNumber = uPortNumber;
    cTCPIPException.__init__(oSelf, sMessage, **dxArguments);
  def fasDetails(oSelf):
    return ["Hostname or IP address and port: %s" % repr("%s:%d" % (oSelf.sHostnameOrIPAddress, oSelf.uPortNumber))];
class cTCPIPPortNotPermittedException(cTCPIPExceptionWithHostnameOrIPAddressAndPortNumber):
  pass;
class cTCPIPPortAlreadyInUseAsAcceptorException(cTCPIPExceptionWithHostnameOrIPAddressAndPortNumber):
  pass;
class cTCPIPConnectionRefusedException(cTCPIPExceptionWithHostnameOrIPAddressAndPortNumber):
  pass;
class cTCPIPInvalidAddressException(cTCPIPExceptionWithHostnameOrIPAddressAndPortNumber):
  pass;
class cTCPIPConnectTimeoutException(cTCPIPExceptionWithHostnameOrIPAddressAndPortNumber):
  def __init__(oSelf, sMessage, sHostnameOrIPAddress, uPortNumber, nTimeoutInSeconds, **dxArguments):
    assert isinstance(nTimeoutInSeconds, (int, float)), \
        "nTimeoutInSeconds must be an int or float, not %s" % repr(nTimeoutInSeconds);
    oSelf.nTimeoutInSeconds = nTimeoutInSeconds;
    cTCPIPExceptionWithHostnameOrIPAddressAndPortNumber.__init__(oSelf, sMessage, sHostnameOrIPAddress, uPortNumber, **dxArguments);
  def fasDetails(oSelf):
    return ["Hostname or IP address and port: %s" % repr("%s:%d" % (oSelf.sHostnameOrIPAddress, oSelf.uPortNumber))];

class cTCPIPExceptionWithConnection(cTCPIPException):
  def __init__(oSelf, sMessage, oConnection, **dxArguments):
    # JIT import to avoid a loop.
    from .cTCPIPConnection import cTCPIPConnection;
    assert isinstance(oConnection, cTCPIPConnection), \
        "oConnection must be a cTCPIPConnection, not %s" % repr(oConnection);
    oSelf.oConnection = oConnection;
    cTCPIPException.__init__(oSelf, sMessage, **dxArguments);
  def fasDetails(oSelf):
    return ["Connection: %s" % repr(oSelf.oConnection)];
class cTCPIPConnectionCannotBeUsedConcurrentlyException(cTCPIPExceptionWithConnection):
  pass;
class cTCPIPDataTimeoutException(cTCPIPExceptionWithConnection):
  pass;
class cTCPIPConnectionShutdownException(cTCPIPExceptionWithConnection):
  pass;
class cTCPIPConnectionDisconnectedException(cTCPIPExceptionWithConnection):
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