from mNotProvided import fbIsProvided, zNotProvided;

from .cTCPIPConnection import cTCPIPConnection;

class cTCPIPException(Exception):
  # this is a flexible base class that can store and report various
  # information related to TCP/IP exceptions. All specific exceptions
  # are based off it, so you can use it as a catch-all class.
  def __init__(oSelf,
    sMessage: str,
    *,
    sbzHost: bytes | type(zNotProvided) = zNotProvided,
    sbzIPAddress: bytes | type(zNotProvided) = zNotProvided,
    uzPortNumber: int | type(zNotProvided) = zNotProvided,
    nzTimeoutInSeconds: float | int | type(zNotProvided) = zNotProvided,
    ozConnection: cTCPIPConnection | type(zNotProvided) = zNotProvided,
  ):
    assert isinstance(sMessage, str), \
        "sMessage must be a str, not %s" % repr(sMessage);
    oSelf.sMessage = sMessage;
    if fbIsProvided(sbzHost):
      oSelf.sbHost = sbzHost;
    if fbIsProvided(sbzIPAddress):
      oSelf.sbIPAddress = sbzIPAddress;
    if fbIsProvided(uzPortNumber):
      oSelf.uPortNumber = uzPortNumber;
    if fbIsProvided(nzTimeoutInSeconds):
      oSelf.nTimeoutInSeconds = nzTimeoutInSeconds;
    if fbIsProvided(ozConnection):
      oSelf.oConnection = ozConnection;
    Exception.__init__(oSelf, sMessage);
  
  def fasDetails(oSelf):
    asDetails = [];
    if hasattr(oSelf, "sbHost"):
      asDetails += [f"Host: {oSelf.sbHost}"];
    if hasattr(oSelf, "sbIPAddress"):
      asDetails += [f"IP address: {oSelf.sbIPAddress}"];
    if hasattr(oSelf, "uPortNumber"):
      asDetails += [f"Port Number: {oSelf.uPortNumber}"];
    if hasattr(oSelf, "nTimeoutInSeconds"):
      asDetails += [f"Timeout: {oSelf.nTimeoutInSeconds} seconds"];
    if hasattr(oSelf, "oConnection"):
      asDetails += [f"Connection: {oSelf.oConnection}"];
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


__all__ = [
  "cTCPIPConnectionCannotBeUsedConcurrentlyException",
  "cTCPIPConnectionDisconnectedException",
  "cTCPIPConnectionRefusedException",
  "cTCPIPConnectionShutdownException",
  "cTCPIPConnectTimeoutException",
  "cTCPIPDataTimeoutException",
  "cTCPIPDNSNameCannotBeResolvedException",
  "cTCPIPException",
  "cTCPIPInvalidAddressException",
  "cTCPIPNetworkErrorException",
  "cTCPIPNoAvailablePortsException",
  "cTCPIPPortAlreadyInUseAsAcceptorException",
  "cTCPIPPortNotPermittedException",
  "cTCPIPUnreachableAddressException",
];
