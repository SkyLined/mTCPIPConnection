import select, socket;

try: # mDebugOutput use is Optional
  from mDebugOutput import ShowDebugOutput, fShowDebugOutput;
except ModuleNotFoundError as oException:
  if oException.args[0] != "No module named 'mDebugOutput'":
    raise;
  ShowDebugOutput = fShowDebugOutput = lambda x: x; # NOP

from mNotProvided import *;

from .cTCPIPConnection import cTCPIPConnection;
from .fbExceptionMeansSocketAlreadyInUseAsAcceptor import fbExceptionMeansSocketAlreadyInUseAsAcceptor;
from .fbExceptionMeansSocketDisconnected import fbExceptionMeansSocketDisconnected;
from .fbExceptionMeansSocketHostnameCannotBeResolved import fbExceptionMeansSocketHostnameCannotBeResolved;
from .fbExceptionMeansSocketAddressIsInvalid import fbExceptionMeansSocketAddressIsInvalid;
from .fbExceptionMeansSocketShutdown import fbExceptionMeansSocketShutdown;
from .mExceptions import *;

from mMultiThreading import cLock, cThread, cWithCallbacks;
try: # SSL support is optional.
  import mSSL as m0SSL;
except ModuleNotFoundError as oException:
  if oException.args[0] != "No module named 'mSSL'":
    raise;
  m0SSL = None; # No SSL support

# If theire are no default port numbers, or they are in use, pick the first
# one that is free one from this range of numbers:
o0DefaultAdditionalPortNumberRange = range(28876, 65536);
sbDefaultHostname = bytes(socket.gethostname(), "ascii", "strict");

class cTCPIPConnectionAcceptor(cWithCallbacks):
  bSSLIsSupported = m0SSL is not None;
  # There are no default port numbers but subclasses that implement a specific
  # protocol can provide them (e.g. port 80 vs 443 for HTTP/HTTPS)
  u0DefaultNonSSLPortNumber = None;
  u0DefaultSSLPortNumber = None;
  sbDefaultHostname = sbDefaultHostname;
  o0DefaultAdditionalPortNumberRange = o0DefaultAdditionalPortNumberRange;
  
  @ShowDebugOutput
  def __init__(oSelf,
    fNewConnectionHandler,
    sbzHostname = zNotProvided, uzPortNumber = zNotProvided,
    o0SSLContext = None, n0zSecureTimeoutInSeconds = zNotProvided,
  ):
    fAssertType("sbzHostname", sbzHostname, bytes, zNotProvided);
    fAssertType("uzPortNumber", uzPortNumber, int, zNotProvided);
    if m0SSL:
      fAssertType("o0SSLContext", o0SSLContext, m0SSL.cSSLContext, None);
    else:
      assert o0SSLContext is None, \
          "Cannot load mSSL; o0SSLContext cannot be %s!" % repr(o0SSLContext);
    fAssertType("n0zSecureTimeoutInSeconds", n0zSecureTimeoutInSeconds, int, float, zNotProvided, None);
    oSelf.__fNewConnectionHandler = fNewConnectionHandler;
    oSelf.__sbHostname = sbzHostname if fbIsProvided(sbzHostname) else oSelf.sbDefaultHostname;
    oSelf.__o0SSLContext = o0SSLContext;
    oSelf.__n0zSecureTimeoutInSeconds = n0zSecureTimeoutInSeconds;
    
    oSelf.__bStopping = False;
    oSelf.__oTerminatedLock = cLock(
      "%s.__oTerminatedLock" % oSelf.__class__.__name__,
      bLocked = True
    );
    
    oSelf.__aoPythonSockets = None;
    
    # Resolve hostname
    sLowerHostname = str(oSelf.__sbHostname, "ascii", "strict").lower();
    def fbBindToPortNumberAndSetProperties(uPortNumber):
      dxDetails = {"sbHostname": oSelf.__sbHostname, "uPortNumber": uPortNumber};
      try:
        atxAddressInfo = socket.getaddrinfo(sLowerHostname, uPortNumber, type = socket.SOCK_STREAM, flags = socket.AI_CANONNAME)
      except Exception as oException:
        if fbExceptionMeansSocketHostnameCannotBeResolved(oException):
          raise cDNSUnknownHostnameException("Cannot resolve hostname", dxDetails);
        elif fbExceptionMeansSocketAddressIsInvalid(oException):
          raise cTCPIPInvalidAddressException("Invalid hostname", dxDetails);
        else:
          raise;
      uIndex = 0;
      aoPythonSockets = [];
      for (iFamily, iType, iProto, sCanonicalName, txAddress) in atxAddressInfo:
        uIndex += 1;
        oPythonSocket = socket.socket(iFamily, iType, iProto);
        oPythonSocket.settimeout(None);
        fShowDebugOutput("Trying to bind to %s:%d (%d/%d)" % (txAddress[0], txAddress[1], uIndex, len(atxAddressInfo)));
        try:
          oPythonSocket.bind(txAddress);
        except Exception as oException:
          if fbExceptionMeansSocketAlreadyInUseAsAcceptor(oException):
            break;
          raise;
        aoPythonSockets.append(oPythonSocket);
      else:
        # We succesfully bound to the port on each address: return sockets.
        oSelf.__aoPythonSockets = aoPythonSockets;
        oSelf.__uPortNumber = uPortNumber;
        return True;
      # We could not bind to at list one address: close sockets and return None.
      for oPythonSocket in aoPythonSockets:
        oPythonSocket.close();
      return False;
    # END fbBindToPortNumberAndSetProperties
    if fbIsProvided(uzPortNumber):
      if not fbBindToPortNumberAndSetProperties(uzPortNumber):
        raise mExceptions.cTCPIPPortAlreadyInUseAsAcceptorException(
          "Cannot bind server socket to port because it is already in use on this system",
          {"sbHostname": oSelf.__sbHostname, "uPortNumber": uzPortNumber},
        );
    else:
      # Try a bunch of ports until we find one that is not currently in use:
      u0DefaultPortNumber = oSelf.u0DefaultSSLPortNumber if o0SSLContext else oSelf.u0DefaultNonSSLPortNumber;
      bBound = False;
      if u0DefaultPortNumber is not None:
        fShowDebugOutput("Trying to bind to default port %d" % u0DefaultPortNumber);
        if fbBindToPortNumberAndSetProperties(u0DefaultPortNumber):
          bBound = True;
        else:
          if not oSelf.o0DefaultAdditionalPortNumberRange:
            raise mExceptions.cTCPIPPortAlreadyInUseAsAcceptorException(
              "Cannot bind server socket to default port because it is already in use on this system",
              {"sbHostname": oSelf.__sbHostname, "uPortNumber": u0DefaultPortNumber},
            );
      if not bBound:
        # Either no default port number was provided, or it was not available.
        # Try the range (which cannot be None because of checks in the code above).
        fShowDebugOutput("Trying to bind to default port in range %d-%d" % \
            (oSelf.o0DefaultAdditionalPortNumberRange[0], oSelf.o0DefaultAdditionalPortNumberRange[-1]));
        for uPortNumber in (oSelf.o0DefaultAdditionalPortNumberRange or []):
          if fbBindToPortNumberAndSetProperties(uPortNumber):
            break;
        else:
          raise mExceptions.cTCPIPPortAlreadyInUseAsAcceptorException(
            "Cannot bind server socket because all possible default ports are already in use on this system",
            {"sbHostname": oSelf.__sbHostname, "u0DefaultPortNumber": u0DefaultPortNumber, \
                "o0DefaultAdditionalPortNumberRange": oSelf.o0DefaultAdditionalPortNumberRange},
          );
    for oPythonSocket in oSelf.__aoPythonSockets:
      oPythonSocket.listen(1);
    oSelf.__oMainThread = cThread(oSelf.__fMain);
    oSelf.__oMainThread.fStart(bVital = False);
    oSelf.fAddEvents(
      "new connection", # Fired first for both secure and nonsecure connections
      "new nonsecure connection", # Fired for nonsecure connections only.
      "new secure connection", # Fired after SSL negotiation has completed successfully.
      "connection cannot be secured", # Fired if SSL negotiation failed to complete successfully and before timeout.
      "terminated" # Fired when the acceptor stops accepting connections.
    );
  
  @property
  def sbHostname(oSelf):
    return oSelf.__sbHostname;
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
    return cTCPIPConnection(oPythonSocket, bCreatedLocally = False);
  
  @ShowDebugOutput
  def __fMain(oSelf):
    fShowDebugOutput("Waiting to accept first connection...");
    while not oSelf.__bStopping:
      # This select call will wait for the socket to be closed or a new connection to be made.
      (aoPythonServerSocketsThatCanAccept, aoNotUsed, aoPythonServerSocketsWithErrors) = \
          select.select(oSelf.__aoPythonSockets, [], oSelf.__aoPythonSockets);
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
            raise;
        fShowDebugOutput("New connection accepted from %s:%d..." % (txRemoteAddress[0], txRemoteAddress[1]));
        oSelf.__fHandleNewConnectedPythonSocket(oConnectedPythonSocket);
        fShowDebugOutput("Waiting to accept next connection...");
      else:
        # everything successfull: loop
        continue;
      # one server socket is broken; stop.
      break;
    fShowDebugOutput("cTCPIPConnectionAcceptor terminated.");
    oSelf.__oTerminatedLock.fRelease();
    oSelf.fFireCallbacks("terminated");
  
  def __fHandleNewConnectedPythonSocket(oSelf, oConnectedPythonSocket):
    oNewConnection = oSelf.foCreateNewConnectionForPythonSocket(oConnectedPythonSocket);
    if oSelf.__o0SSLContext:
      try:
        oNewConnection.fSecure(oSelf.__o0SSLContext, n0zTimeoutInSeconds = oSelf.__n0zSecureTimeoutInSeconds);
      except Exception as oException:
        if m0SSL and isinstance(oException, m0SSL.mExceptions.cSSLException):
          fShowDebugOutput("SSL exception while securing connection.");
          sCause = "SSL error";
        elif isinstance(oException, cTCPIPConnectionShutdownException):
          fShowDebugOutput("Shut down while securing connection.");
          sCause = "shutdown";
        elif isinstance(oException, cTCPIPConnectionDisconnectedException):
          fShowDebugOutput("Disconnected while securing connection.");
          sCause = "disconnected";
        else:
          raise;
        oSelf.fFireCallbacks("connection cannot be secured", oNewConnection, sCause);
        return;
      else:
        oSelf.fFireCallbacks("new secure connection", oNewConnection);
    else:
        oSelf.fFireCallbacks("new nonsecure connection", oNewConnection);
    oSelf.fFireCallbacks("new connection", oNewConnection);
    oSelf.__fNewConnectionHandler(oSelf, oNewConnection);
  
  def fasGetDetails(oSelf):
    # This is done without a property lock, so race-conditions exist and it
    # approximates the real values.
    bTerminated = oSelf.bTerminated;
    bStopping = not bTerminated and oSelf.__bStopping;
    return [s for s in [
      "%s:%d" % (oSelf.__sbHostname, oSelf.__uPortNumber),
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

for cException in acExceptions:
  setattr(cTCPIPConnectionAcceptor, cException.__name__, cException);
