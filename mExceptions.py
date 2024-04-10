from mNotProvided import fbIsProvided, zNotProvided;

class cTCPIPException(Exception):
  # this is a flexible base class that can store and report various
  # information related to TCP/IP exceptions. All specific exceptions
  # are based off it, so you can use it as a catch-all class.
  def __init__(
    oSelf,
    sMessage,
    *,
    sbzHost = zNotProvided,
    sbzIPAddress = zNotProvided,
    uzPortNumber = zNotProvided,
    nzTimeoutInSeconds = zNotProvided,
    ozConnection = zNotProvided,
  ):
    assert isinstance(sMessage, str), \
        "sMessage must be a str, not %s" % repr(sMessage);
    oSelf.sMessage = sMessage;
    oSelf.sbzHost = sbzHost;
    oSelf.sbzIPAddress = sbzIPAddress;
    oSelf.uzPortNumber = uzPortNumber;
    oSelf.nzTimeoutInSeconds = nzTimeoutInSeconds;
    oSelf.ozConnection = ozConnection;
    Exception.__init__(oSelf, sMessage);
  
  @property
  def sbHost(oSelf):
    assert fbIsProvided(oSelf.sbzHost), \
        "sbzHost is not provided for this exception";
    return oSelf.sbzHost;
  
  @property
  def sbIPAddress(oSelf):
    assert fbIsProvided(oSelf.sbzIPAddress), \
        "sbzIPAddress is not provided for this exception";
    return oSelf.sbzIPAddress;
  
  @property
  def uPortNumber(oSelf):
    assert fbIsProvided(oSelf.uzPortNumber), \
        "uzPortNumber is not provided for this exception";
    return oSelf.uzPortNumber;
  
  @property
  def nTimeoutInSeconds(oSelf):
    assert fbIsProvided(oSelf.nzTimeoutInSeconds), \
        "nzTimeoutInSeconds is not provided for this exception";
    return oSelf.nzTimeoutInSeconds;
  
  @property
  def oConnection(oSelf):
    assert fbIsProvided(oSelf.ozConnection), \
        "ozConnection is not provided for this exception";
    return oSelf.ozConnection;
  
  def fasDetails(oSelf):
    asDetails = [];
    if fbIsProvided(oSelf.sbzHost):
      asDetails += [f"Host: {oSelf.sbzHost}"];
    if fbIsProvided(oSelf.sbzIPAddress):
      asDetails += [f"IP address: {oSelf.sbzIPAddress}"];
    if fbIsProvided(oSelf.uzPortNumber):
      asDetails += [f"Port Number: {oSelf.uzPortNumber}"];
    if fbIsProvided(oSelf.nzTimeoutInSeconds):
      asDetails += [f"Timeout: {oSelf.nzTimeoutInSeconds} seconds"];
    if fbIsProvided(oSelf.ozConnection):
      asDetails += [f"Connection: {oSelf.ozConnection}"];
    return asDetails;

  def __str__(oSelf):
    return "%s (%s)" % (oSelf.sMessage, ", ".join(oSelf.fasDetails()));
  def __repr__(oSelf):
    return "<%s.%s %s>" % (oSelf.__class__.__module__, oSelf.__class__.__name__, oSelf);

class cTCPIPConnectionCannotBeUsedConcurrentlyException(cTCPIPException):
  pass;
class cTCPIPConnectionDisconnectedException(cTCPIPException):
  pass;
class cTCPIPConnectionRefusedException(cTCPIPException):
  pass;
class cTCPIPConnectionShutdownException(cTCPIPException):
  pass;
class cTCPIPConnectTimeoutException(cTCPIPException):
  pass;
class cTCPIPDataTimeoutException(cTCPIPException):
  pass;
class cTCPIPDNSNameCannotBeResolvedException(cTCPIPException):
  pass;
class cTCPIPInvalidAddressException(cTCPIPException):
  pass;
class cTCPIPNetworkErrorException(cTCPIPException):
  pass;
class cTCPIPNoAvailablePortsException(cTCPIPException):
  pass;
class cTCPIPPortAlreadyInUseAsAcceptorException(cTCPIPException):
  pass;
class cTCPIPPortNotPermittedException(cTCPIPException):
  pass;
class cTCPIPUnreachableAddressException(cTCPIPException):
  pass;


acExceptions = [
  cTCPIPConnectionCannotBeUsedConcurrentlyException,
  cTCPIPConnectionDisconnectedException,
  cTCPIPConnectionRefusedException,
  cTCPIPConnectionShutdownException,
  cTCPIPConnectTimeoutException,
  cTCPIPDataTimeoutException,
  cTCPIPDNSNameCannotBeResolvedException,
  cTCPIPException,
  cTCPIPInvalidAddressException,
  cTCPIPNetworkErrorException,
  cTCPIPNoAvailablePortsException,
  cTCPIPPortAlreadyInUseAsAcceptorException,
  cTCPIPPortNotPermittedException,
  cTCPIPUnreachableAddressException,
];