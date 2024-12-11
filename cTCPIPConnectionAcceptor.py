import select, socket;

try: # mDebugOutput use is Optional
  from mDebugOutput import ShowDebugOutput, fShowDebugOutput;
except ModuleNotFoundError as oException:
  if oException.args[0] != "No module named 'mDebugOutput'":
    raise;
  ShowDebugOutput = lambda fx: fx; # NOP
  fShowDebugOutput = lambda x, s0 = None: x; # NOP

from mMultiThreading import (
  cLock,
  cThread,
  cWithCallbacks,
);
from mNotProvided import (
  fAssertType,
  fbIsProvided,
  zNotProvided,
);
try: # SSL support is optional.
  import mSSL as m0SSL;
except ModuleNotFoundError as oException:
  if oException.args[0] != "No module named 'mSSL'":
    raise;
  m0SSL = None; # No SSL support


from .cTCPIPConnection import cTCPIPConnection;
from .fbExceptionMeansPortNotPermitted import fbExceptionMeansPortNotPermitted;
from .fbExceptionMeansSocketAddressIsInvalid import fbExceptionMeansSocketAddressIsInvalid;
from .fbExceptionMeansSocketAlreadyInUseAsAcceptor import fbExceptionMeansSocketAlreadyInUseAsAcceptor;
from .fbExceptionMeansSocketDisconnected import fbExceptionMeansSocketDisconnected;
from .fbExceptionMeansDNSNameCannotBeResolved import fbExceptionMeansDNSNameCannotBeResolved;
from .fbExceptionMeansSocketShutdown import fbExceptionMeansSocketShutdown;
from .mExceptions import (
  cTCPIPConnectionDisconnectedException,
  cTCPIPConnectionShutdownException,
  cTCPIPDNSNameCannotBeResolvedException,
  cTCPIPInvalidAddressException,
  cTCPIPNoAvailablePortsException,
  cTCPIPPortAlreadyInUseAsAcceptorException,
  cTCPIPPortNotPermittedException,
);

# If theire are no default port numbers, or they are in use, pick the first
# one that is free one from this range of numbers:
o0DefaultAdditionalPortNumberRange = range(28876, 65536);
sbDefaultHost = bytes(socket.gethostname(), "ascii", "strict");

class cTCPIPConnectionAcceptor(cWithCallbacks):
  bSSLIsSupported = m0SSL is not None;
  # There are no default port numbers but subclasses that implement a specific
  # protocol can provide them (e.g. port 80 vs 443 for HTTP/HTTPS)
  u0DefaultNonSSLPortNumber = None;
  u0DefaultSSLPortNumber = None;
  sbDefaultHost = sbDefaultHost;
  o0DefaultAdditionalPortNumberRange = o0DefaultAdditionalPortNumberRange;
  
  @ShowDebugOutput
  def __init__(oSelf,
    fNewConnectionHandler,
    sbzHost = zNotProvided,
    uzPortNumber = zNotProvided,
    o0SSLContext = None,
    n0zSecureTimeoutInSeconds = zNotProvided,
    nSendDelayPerByteInSeconds = 0,
  ):
    fAssertType("sbzHost", sbzHost, bytes, zNotProvided);
    fAssertType("uzPortNumber", uzPortNumber, int, zNotProvided);
    if m0SSL:
      fAssertType("o0SSLContext", o0SSLContext, m0SSL.cSSLContext, None);
    else:
      assert o0SSLContext is None, \
          "Cannot load mSSL; o0SSLContext cannot be %s!" % repr(o0SSLContext);
    fAssertType("n0zSecureTimeoutInSeconds", n0zSecureTimeoutInSeconds, int, float, zNotProvided, None);
    oSelf.__fNewConnectionHandler = fNewConnectionHandler;
    oSelf.__sbHost = sbzHost if fbIsProvided(sbzHost) else oSelf.sbDefaultHost;
    oSelf.__o0SSLContext = o0SSLContext;
    oSelf.__n0zSecureTimeoutInSeconds = n0zSecureTimeoutInSeconds;
    oSelf.nSendDelayPerByteInSeconds = nSendDelayPerByteInSeconds;
    
    oSelf.__bStopping = False;
    oSelf.__oTerminatedLock = cLock(
      "%s.__oTerminatedLock" % oSelf.__class__.__name__,
      bLocked = True
    );
    
    oSelf.__aoPythonSockets = None;
    
    # Resolve host
    sLowerHost = str(oSelf.__sbHost, "ascii", "strict").lower();
    def fBindToPortNumberOnAllAddressesAndSetProperties(uPortNumber):
      try:
        atxAddressInfo = socket.getaddrinfo(sLowerHost, uPortNumber, type = socket.SOCK_STREAM, flags = socket.AI_CANONNAME);
      except Exception as oException:
        if fbExceptionMeansSocketAddressIsInvalid(oException):
          raise cTCPIPInvalidAddressException(
            "Cannot bind to invalid address %s." % (
              repr("%s:%d" % (sLowerHost, uPortNumber)),
            ),
            sbzHost = oSelf.__sbHost,
            uzPortNumber = uPortNumber,
          );
        elif fbExceptionMeansDNSNameCannotBeResolved(oException):
          raise cTCPIPDNSNameCannotBeResolvedException(
            "Cannot bind to DNS name %s because it cannot be resolved." % (
              repr(sLowerHost),
            ),
            szbHost = oSelf.__sbHost,
          );
        else:
          raise;
      uIndex = 0;
      aoPythonSockets = [];
      try:
        for (iFamily, iType, iProto, sCanonicalName, txAddress) in atxAddressInfo:
          uIndex += 1;
          oPythonSocket = socket.socket(iFamily, iType, iProto);
          aoPythonSockets.append(oPythonSocket);
          oPythonSocket.settimeout(None);
          if iFamily == socket.AF_INET:
            (sIPAddress, uPortNumber) = txAddress; # IPv4
          elif iFamily == socket.AF_INET6:
            (sIPAddress, uPortNumber, uFlowInfo, uScopeId) = txAddress; # IPv6
          else:
            continue; # Not a protocol we support.
          sbIPAddress = bytes(sIPAddress, "ascii", "strict");
          fShowDebugOutput("Trying to bind to %s:%d (%d/%d)" % (sIPAddress, uPortNumber, uIndex, len(atxAddressInfo)));
          try:
            oPythonSocket.bind(txAddress);
          except Exception as oException:
            # Raise specific errors if possible:
            if fbExceptionMeansPortNotPermitted(oException):
              raise cTCPIPPortNotPermittedException(
                "Cannot bind to address %s because the port is not permitted." % (
                  repr("%s:%d" % (sIPAddress, uPortNumber)),
                ),
                sbzHost = oSelf.__sbHost,
                sbzIPAddress = sbIPAddress,
                uzPortNumber = uPortNumber,
              );
            if fbExceptionMeansSocketAlreadyInUseAsAcceptor(oException):
              raise cTCPIPPortAlreadyInUseAsAcceptorException(
                "Cannot bind to address %s because the port is already in use." % (
                  repr("%s:%d" % (sIPAddress, uPortNumber)),
                ),
                sbzHost = oSelf.__sbHost,
                sbzIPAddress = sbIPAddress,
                uzPortNumber = uPortNumber,
              );
            raise;
      except:
        # In case of an exception, make sure we close all sockets we opened.
        for oPythonSocket in aoPythonSockets:
          oPythonSocket.close();
        raise;
      # We successfully bound to the port on each address: return sockets.
      oSelf.__aoPythonSockets = aoPythonSockets;
      oSelf.__uPortNumber = uPortNumber;
    # END fbBindToPortNumberAndSetProperties
    if fbIsProvided(uzPortNumber):
      fBindToPortNumberOnAllAddressesAndSetProperties(uzPortNumber);
    else:
      # Try a bunch of ports until we find one that is not currently in use:
      u0DefaultPortNumber = oSelf.u0DefaultSSLPortNumber if o0SSLContext else oSelf.u0DefaultNonSSLPortNumber;
      bBound = False;
      if u0DefaultPortNumber is not None:
        fShowDebugOutput("Trying to bind to default port %d" % u0DefaultPortNumber);
        try:
          fBindToPortNumberOnAllAddressesAndSetProperties(u0DefaultPortNumber);
        except (cTCPIPPortNotPermittedException, cTCPIPPortAlreadyInUseAsAcceptorException):
          if not oSelf.o0DefaultAdditionalPortNumberRange:
            raise;
        else:
          bBound = True;
      if not bBound:
        # Either no default port number was provided, or it was not available.
        # Try the range (which cannot be None because of checks in the code above).
        fShowDebugOutput("Trying to bind to default port in range %d-%d" % \
            (oSelf.o0DefaultAdditionalPortNumberRange[0], oSelf.o0DefaultAdditionalPortNumberRange[-1]));
        for uPortNumber in (oSelf.o0DefaultAdditionalPortNumberRange or []):
          try:
            fBindToPortNumberOnAllAddressesAndSetProperties(uPortNumber);
          except (cTCPIPPortNotPermittedException, cTCPIPPortAlreadyInUseAsAcceptorException):
            pass;
          else:
            break;
        else:
          raise cTCPIPNoAvailablePortsException(
            "Cannot bind to host %s because no port was available." % (
              repr(sLowerHost),
            ),
            sbzHost = sLowerHost,
          );
    for oPythonSocket in oSelf.__aoPythonSockets:
      oPythonSocket.listen(1);
    oSelf.__oMainThread = cThread(oSelf.__fMain);
    oSelf.__oMainThread.fStart(bVital = False);
    oSelf.fAddEvents(
      "received connection from client",
      "terminated connection from client",
      
      "securing connection from client",
      "securing connection from client failed",
      "secured connection from client",
      
      "terminated",
    );
  
  @property
  def sbHost(oSelf):
    return oSelf.__sbHost;
  @property
  def uPortNumber(oSelf):
    return oSelf.__uPortNumber;
  @property
  def o0SSLContext(oSelf):
    return oSelf.__o0SSLContext;
  @property
  def bSecure(oSelf):
    return oSelf.__o0SSLContext is not None;
  @property
  def asbIPAddresses(oSelf):
    try:
      return [
        bytes(oPythonSocket.getsockname()[0], 'latin1')
        for oPythonSocket in oSelf.__aoPythonSockets
      ]
    except OSError as oException:
      if oException.args[0] == 10038 and oSelf.__bStopping: # WSAENOTSOCK
        return []; # Sockets have just been closed
      raise;
  @property
  def bTerminated(oSelf):
    return not oSelf.__oTerminatedLock.bLocked;
  
  @ShowDebugOutput
  def fStop(oSelf):
    if oSelf.__bStopping:
      return fShowDebugOutput("Already stopping");
    if not oSelf.__oTerminatedLock.bLocked:
      return fShowDebugOutput("Already terminated");
    oSelf.__bStopping = True;
    fShowDebugOutput("Closing server sockets...");
    while oSelf.__aoPythonSockets:
      oSelf.__aoPythonSockets.pop().close();
  
  @ShowDebugOutput
  def fTerminate(oSelf):
    if not oSelf.__oTerminatedLock.bLocked:
      return fShowDebugOutput("Already terminated");
    oSelf.__bStopping = True;
    fShowDebugOutput("Closing server sockets...");
    while oSelf.__aoPythonSockets:
      oSelf.__aoPythonSockets.pop().close();
  
  @ShowDebugOutput
  def fbWait(oSelf, nTimeoutInSeconds):
    return oSelf.__oTerminatedLock.fbWait(nTimeoutInSeconds);
  
  def foCreateNewConnectionForPythonSocket(oSelf, oPythonSocket):
    return cTCPIPConnection(
      oPythonSocket,
      bCreatedLocally = False,
      nSendDelayPerByteInSeconds = oSelf.nSendDelayPerByteInSeconds,
    );
  
  @ShowDebugOutput
  def __fMain(oSelf):
    fShowDebugOutput("Waiting to accept first connection...");
    while not oSelf.__bStopping:
      # This select call will wait for the socket to be closed or a new connection to be made.
      (aoPythonServerSocketsThatCanAccept, aoNotUsed, aoPythonServerSocketsWithErrors) = \
          select.select(oSelf.__aoPythonSockets, [], oSelf.__aoPythonSockets);
      fShowDebugOutput("%d sockets can accept connections, %d sockets have errors." % (
        len(aoPythonServerSocketsThatCanAccept),
        len(aoPythonServerSocketsWithErrors),
      ));
      assert len(aoPythonServerSocketsWithErrors) == 0, \
          "I do not know what caused this, so I can not handle it!";
      for oPythonServerSocketThatCanAccept in aoPythonServerSocketsThatCanAccept:
        try:
          # This accept call will accept a new connection or raise an exception if the socket is closed.
          (oConnectedPythonSocket, txRemoteAddress) = oPythonServerSocketThatCanAccept.accept();
          oConnectedPythonSocket.fileno(); # will throw "bad file descriptor" if the server socket was closed
        except Exception as oException:
          if (
            fbExceptionMeansSocketShutdown(oException)
            or fbExceptionMeansSocketDisconnected(oException)
          ):
            fShowDebugOutput("Server socket disconnected; stopped accepting connections...");
            break;
          else:
            fShowDebugOutput("Server socket accept() failed for unknown reasons: %s." % oException);
            raise;
        fShowDebugOutput("New connection accepted from %s:%d..." % (txRemoteAddress[0], txRemoteAddress[1]));
        oSelf.__fHandleNewConnectedPythonSocket(oConnectedPythonSocket);
        fShowDebugOutput("Waiting to accept next connection...");
      else:
        # everything successful: loop
        continue;
      # one server socket is broken; stop.
      break;
    fShowDebugOutput("cTCPIPConnectionAcceptor terminated.");
    oSelf.__oTerminatedLock.fRelease();
    oSelf.fFireCallbacks("terminated");
  
  def __fHandleNewConnectedPythonSocket(oSelf, oConnectedPythonSocket):
    oNewConnection = oSelf.foCreateNewConnectionForPythonSocket(oConnectedPythonSocket);
    oSelf.fFireCallbacks("received connection from client", oConnection = oNewConnection);
    oNewConnection.fAddCallback("terminated", lambda oConnection: oSelf.fFireCallbacks(
      "terminated connection from client",
      oConnection = oConnection,
    ));
    if oSelf.__o0SSLContext:
      oSelf.fFireCallbacks("securing connection from client", oConnection = oNewConnection, oSSLContext = oSelf.__o0SSLContext);
      try:
        oNewConnection.fSecure(oSelf.__o0SSLContext, n0zTimeoutInSeconds = oSelf.__n0zSecureTimeoutInSeconds);
      except Exception as oException:
        oSelf.fFireCallbacks("securing connection from client failed", oConnection = oNewConnection, oSSLContext = oSelf.__o0SSLContext, oException = oException);
        if m0SSL and isinstance(oException, m0SSL.cSSLException):
          fShowDebugOutput("SSL exception while securing connection.");
        elif isinstance(oException, cTCPIPConnectionShutdownException):
          fShowDebugOutput("Shut down while securing connection.");
        elif isinstance(oException, cTCPIPConnectionDisconnectedException):
          fShowDebugOutput("Disconnected while securing connection.");
        else:
          raise;
        return;
      oSelf.fFireCallbacks("secured connection from client", oConnection = oNewConnection, oSSLContext  = oSelf.__o0SSLContext);
    oSelf.__fNewConnectionHandler(oSelf, oNewConnection);
  
  def fasGetDetails(oSelf):
    # This is done without a property lock, so race-conditions exist and it
    # approximates the real values.
    bTerminated = oSelf.bTerminated;
    bStopping = not bTerminated and oSelf.__bStopping;
    return [s for s in [
      "%s:%d" % (oSelf.__sbHost, oSelf.__uPortNumber),
      "IPs: %s" % ", ".join(str(sbIPAddress) for sbIPAddress in oSelf.asbIPAddresses),
      "secure" if oSelf.__o0SSLContext is not None else None,
      "terminated" if bTerminated else
          "stopping" if bStopping else None,
    ] if s];
  
  def __repr__(oSelf):
    sModuleName = ".".join(oSelf.__class__.__module__.split(".")[:-1]);
    return "<%s.%s#%X|%s>" % (sModuleName, oSelf.__class__.__name__, id(oSelf), "|".join(oSelf.fasGetDetails()));
  
  def __str__(oSelf):
    return "%s#%X{%s}" % (oSelf.__class__.__name__, id(oSelf), ", ".join(oSelf.fasGetDetails()));
