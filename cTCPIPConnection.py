import select, socket, time;

try: # mDebugOutput use is Optional
  from mDebugOutput import ShowDebugOutput, fShowDebugOutput;
except ModuleNotFoundError as oException:
  if oException.args[0] != "No module named 'mDebugOutput'":
    raise;
  ShowDebugOutput = lambda fx: fx; # NOP
  fShowDebugOutput = lambda x, s0 = None: x; # NOP

try: # mSSL support is optional
  import mSSL as m0SSL;
except ModuleNotFoundError as oException:
  if oException.args[0] != "No module named 'mSSL'":
    raise;
  m0SSL = None;

from mMultiThreading import (
  cLock,
  cWithCallbacks,
);
from mNotProvided import (
  fAssertType,
  fbIsProvided,
  fxGetFirstProvidedValue,
  zNotProvided,
);

from .fbExceptionMeansSocketConnectionRefused import fbExceptionMeansSocketConnectionRefused;
from .fbExceptionMeansSocketDisconnected import fbExceptionMeansSocketDisconnected;
from .fbExceptionMeansSocketHasNoDataAvailable import fbExceptionMeansSocketHasNoDataAvailable;
from .fbExceptionMeansDNSNameCannotBeResolved import fbExceptionMeansDNSNameCannotBeResolved;
from .fbExceptionMeansSocketAddressIsInvalid import fbExceptionMeansSocketAddressIsInvalid;
from .fbExceptionMeansSocketAddressIsUnreachable import fbExceptionMeansSocketAddressIsUnreachable;
from .fbExceptionMeansSocketShutdown import fbExceptionMeansSocketShutdown;
from .fbExceptionMeansSocketTimeout import fbExceptionMeansSocketTimeout;
from .fbExceptionMeansNetworkError import fbExceptionMeansNetworkError;
from .mExceptions import (
  cTCPIPConnectionDisconnectedException,
  cTCPIPConnectionRefusedException,
  cTCPIPConnectionShutdownException,
  cTCPIPConnectTimeoutException,
  cTCPIPDataTimeoutException,
  cTCPIPDNSNameCannotBeResolvedException,
  cTCPIPException,
  cTCPIPInvalidAddressException,
  cTCPIPUnreachableAddressException,
  cTCPIPNetworkErrorException,
);

# To turn access to data store in multiple variables into a single transaction, we will create locks.
# These locks should only ever be locked for a short time; if it is locked for too long, it is considered a "deadlock"
# bug, where "too long" is defined by the following value:
gnDeadlockTimeoutInSeconds = 1; # We're not doing anything time consuming, so this should suffice.

def fsbAddressFromHostAndPort(sbHost, uPort):
  # IPv6 Addresses have colons in them; wrap them in [] to prevent confusion with the port number.
  return (b"[%s]:%d" if b":" in sbHost else b"%s:%d") % (sbHost, uPort);

class cTCPIPConnection(cWithCallbacks):
  bSSLIsSupported = m0SSL is not None;
  n0DefaultConnectTimeoutInSeconds = 5; # How long to try to connect before giving up?
  uDefaultReadChunkSize = 0x100 * 0x400; # How many bytes to try to read if we do not know how many are coming.
  if m0SSL is not None:
    tcExceptions = (cTCPIPException, m0SSL.mExceptions.cSSLException);
  else:
    tcExceptions = (cTCPIPException,);

  @classmethod
  @ShowDebugOutput
  def faoWaitUntilReadEventOnPythonSocket(cClass,
    aoConnections,
    *,
    n0WaitTimeoutInSeconds = None,
  ):
    # "readable" doesn't mean there's data to read.
    fAssertType("aoConnections", aoConnections, [cTCPIPConnection]);
    fAssertType("n0WaitTimeoutInSeconds", n0WaitTimeoutInSeconds, int, float, None);
    if len(aoConnections) == 0: return [];
    n0EndTime = time.time() + n0WaitTimeoutInSeconds if n0WaitTimeoutInSeconds is not None else None;
    aoShutdownOrClosedConnections = [];
    doOpenConnections_by_oPythonSocket = {};
    for oConnection in aoConnections:
      if not oConnection.__fbConnected() or oConnection.__bShutdownForReading:
        aoShutdownOrClosedConnections.append(oConnection);
      else:
        if n0WaitTimeoutInSeconds is not None:
          oConnection.__oPythonSocket.settimeout(n0WaitTimeoutInSeconds);
        else:
          oConnection.__oPythonSocket.setblocking(True);
        doOpenConnections_by_oPythonSocket[oConnection.__oPythonSocket] = oConnection;
    # Wait until the python sockets become readable, shutdown or closed:
    n0WaitTimeoutInSeconds = (
      # If we have closed connections, we will not wait.
      0 if len(aoShutdownOrClosedConnections) > 0 else
      # If there is a time out, we will indefinitely.
      n0EndTime - time.time() if n0EndTime is not None else
      # Wait indefinitely.
      None
    );
    aoPythonSockets = list(doOpenConnections_by_oPythonSocket.keys());
    aoPythonSocketsWithReadEvent = select.select(aoPythonSockets, [], [], n0WaitTimeoutInSeconds)[0];
    aoConnectionsWithReadEvent = [
      doOpenConnections_by_oPythonSocket[oPythonSocket]
      for oPythonSocket in aoPythonSocketsWithReadEvent
    ];
    return aoShutdownOrClosedConnections + aoConnectionsWithReadEvent;

  @classmethod
  @ShowDebugOutput
  def foConnectTo(cClass, \
    sbHost,
    uPortNumber,
    *,
    n0zConnectTimeoutInSeconds = zNotProvided,
    o0SSLContext = None,
    bzCheckHost = zNotProvided,
    n0zSecureTimeoutInSeconds = zNotProvided,
    nSendDelayPerByteInSeconds = 0,
    f0HostInvalidCallback = None,
    f0ResolvingHostnameCallback = None,
    f0ResolvingHostnameFailedCallback = None,
    f0HostnameResolvedToIPAddressCallback = None,
    f0ConnectingToIPAddressCallback = None,
    f0ConnectingToIPAddressFailedCallback = None,
    f0ConnectedToIPAddressCallback = None,
    f0SecuringConnectionCallback = None,
    f0SecuringConnectionFailedCallback = None,
    f0ConnectionSecuredCallback = None,
  ):
    fAssertType("sbHost", sbHost, bytes);
    fAssertType("uPortNumber", uPortNumber, int);
    fAssertType("n0zConnectTimeoutInSeconds", n0zConnectTimeoutInSeconds, int, float, zNotProvided, None);
    if m0SSL:
      fAssertType("o0SSLContext", o0SSLContext, m0SSL.cSSLContext, None);
    else:
      assert o0SSLContext is None, \
          "Cannot load module mSSL; o0SSLContext cannot be %s!" % repr(o0SSLContext);
    fAssertType("n0zSecureTimeoutInSeconds", n0zSecureTimeoutInSeconds, int, float, zNotProvided, None);
    n0ConnectTimeoutInSeconds = fxGetFirstProvidedValue(n0zConnectTimeoutInSeconds, cClass.n0DefaultConnectTimeoutInSeconds);
    # Resolve host
    sLowerHost = str(sbHost, "ascii", "strict").lower();
    # We may at some point special case IP addresses and skip resolving them, as this adds no value.
    if f0ResolvingHostnameCallback:
      f0ResolvingHostnameCallback(sbHostname = sbHost);
    try:
      atxAddressInfo = socket.getaddrinfo(
        sLowerHost,
        uPortNumber,
        type = socket.SOCK_STREAM,
        proto = socket.IPPROTO_TCP,
        flags = socket.AI_CANONNAME,
      );
    except Exception as oException:
      if fbExceptionMeansSocketAddressIsInvalid(oException):
        if f0HostInvalidCallback:
          f0HostInvalidCallback(sbHost = sbHost, oException = oException);
        raise cTCPIPInvalidAddressException(
          "Cannot connect to invalid address %s:%s." % (
            repr(sbHost),
            repr(uPortNumber)
          ),
          sbzHost = sbHost,
          uzPortNumber = uPortNumber,
        );
      elif fbExceptionMeansDNSNameCannotBeResolved(oException):
        if f0ResolvingHostnameFailedCallback:
          f0ResolvingHostnameFailedCallback(sbHostname = sbHost, oException = oException);
        raise cTCPIPDNSNameCannotBeResolvedException(
          "Cannot connect to host %s because it cannot be resolved." % (
            repr(sbHost),
          ),
          sbzHost = sbHost,
        );
      else:
        raise;
    uIndex = 0;
    for (iFamily, iType, iProto, sCanonicalName, txAddress) in atxAddressInfo:
      if iFamily not in [socket.AF_INET, socket.AF_INET6]:
        continue;
      uIndex += 1;
      bIsLastAddressInfo = uIndex == len(atxAddressInfo);
      if iFamily == socket.AF_INET:
        (sIPAddress, uPortNumber) = txAddress; # IPv4
      elif iFamily == socket.AF_INET6:
        (sIPAddress, uPortNumber, uFlowInfo, uScopeId) = txAddress; # IPv6
      else:
        continue; # Not a protocol we support.
      sbIPAddress = bytes(sIPAddress, "ascii", "strict").lower();
      if sIPAddress.lower() != sLowerHost:
        if f0HostnameResolvedToIPAddressCallback:
          f0HostnameResolvedToIPAddressCallback(
            sbHostname = sbHost,
            sbIPAddress = sbIPAddress,
            sCanonicalName = sCanonicalName
          );
      fShowDebugOutput("Connecting to %s:%d (%saddress %s)..." % (
        ("[%s]" if ":" in sLowerHost else "%s") % (sLowerHost,), # IPv6 Addresses must be wrapped in []
        uPortNumber,
        ("canonical name %s, " % sCanonicalName) if (sCanonicalName != sLowerHost) else "",
        txAddress[0]
      ));
      # n0zSecureTimeoutInSeconds is pass through
      oPythonSocket = socket.socket(iFamily, iType, iProto);
      for (xType, sName, xValue) in (
        (socket.SOL_SOCKET,  "SO_KEEPALIVE",  1), # Send keep alive frames
        (socket.IPPROTO_TCP, "TCP_KEEPIDLE",  1), # After 1 second of inactivity
        (socket.IPPROTO_TCP, "TCP_KEEPINTVL", 1), # Send keep alive frames every 1 second
        (socket.IPPROTO_TCP, "TCP_KEEPCNT",   5), # Assume disconnected after missing 5 keep alive frames.
      ):
        try:
          oPythonSocket.setsockopt(xType,  getattr(socket, sName), xValue);
        except OSError:
          pass;
      if f0ConnectingToIPAddressCallback:
        f0ConnectingToIPAddressCallback(
          sbHost = sbHost,
          uPortNumber = uPortNumber,
          sbIPAddress = sbIPAddress,
        );
      oPythonSocket.settimeout(n0ConnectTimeoutInSeconds);
      try:
        oPythonSocket.connect(txAddress);
      except Exception as oException:
        # This is unexpected but we need to close the socket even though
        # we never opened it. *shrug*
        oPythonSocket.close();
        fShowDebugOutput("Exception during `connect()`: %s(%s)" % (oException.__class__.__name__, oException));
        if fbExceptionMeansSocketAddressIsInvalid(oException):
          raise cTCPIPInvalidAddressException(
            "Cannot connect to invalid address %s." % (
              repr("%s:%d" % (sLowerHost, uPortNumber)),
            ),
            sbzHost = sbHost,
            sbzIPAddress = sbIPAddress,
            uzPortNumber = uPortNumber,
          );
        elif fbExceptionMeansSocketAddressIsUnreachable(oException):
          raise cTCPIPUnreachableAddressException(
            "Cannot connect to invalid address %s." % (
              repr("%s:%d" % (sLowerHost, uPortNumber)),
            ),
            sbzHost = sbHost,
            sbzIPAddress = sbIPAddress,
            uzPortNumber = uPortNumber,
          );
        else:
          if fbExceptionMeansSocketTimeout(oException):
            # Note that a Python server socket will refuse connections after a few seconds if the queue is full (the size
            # of the queue is determined by the `backlog` argument in the `socket.listen(backlog)` call). You might expect
            # a `cTCPIPConnectTimeoutException` when a client attempts to connect to a server that is unable to accept the
            # connection immediately, but you could get a `cTCPIPConnectionRefusedException` exception instead because of
            # this. This may be true for other server sockets as well. For Python at least, there seems to be a timeout
            # on the server side of about 2 seconds but I have been unable to determine where this value comes from, if you
            # can control this, or disable it entirely.
            # If `n0ConnectTimeoutInSeconds` is smaller than the server side timeout that triggers a refused connection,
            # you will see a `cTCPIPConnectTimeoutException` as expected.
            oException = cTCPIPConnectTimeoutException(
              "Attempt to connect to server address %s timed out." % repr("%s:%d" % (sIPAddress, uPortNumber)),
              sbzHost = sbIPAddress,
              sbzIPAddress = sbIPAddress,
              uzPortNumber = uPortNumber,
              nzTimeoutInSeconds = n0ConnectTimeoutInSeconds,
            );
          elif fbExceptionMeansSocketConnectionRefused(oException):
            oException = cTCPIPConnectionRefusedException(
              "Attempt to connect to server address %s refused." % repr("%s:%d" % (sIPAddress, uPortNumber)),
              sbzHost = sbIPAddress,
              sbzIPAddress = sbIPAddress,
              uzPortNumber = uPortNumber,
            );
          elif fbExceptionMeansNetworkError(oException):
            oException = cTCPIPNetworkErrorException(
              "Attempt to connect to server address %s failed because of a network error." % repr("%s:%d" % (sIPAddress, uPortNumber)),
              sbzHost = sbIPAddress,
              sbzIPAddress = sbIPAddress,
              uzPortNumber = uPortNumber,
            );
          else:
            raise;
        if f0ConnectingToIPAddressFailedCallback:
          f0ConnectingToIPAddressFailedCallback(
            oException = oException,
            sbHost = sbHost,
            uPortNumber = uPortNumber,
            sbIPAddress = sbIPAddress,
          );
        # We will ignore this exception and try the next address unless there are no more addresses.
        if bIsLastAddressInfo:
          raise oException;
        else:
          continue;
      oConnection = cClass(
        oPythonSocket,
        sbzRemoteHost = sbHost,
        sbzRemoteIPAddress = sbIPAddress,
        bCreatedLocally = True,
        nSendDelayPerByteInSeconds = nSendDelayPerByteInSeconds,
      );
      if f0ConnectedToIPAddressCallback:
        f0ConnectedToIPAddressCallback(
            sbHost = sbHost,
            uPortNumber = uPortNumber,
            sbIPAddress = sbIPAddress,
            oConnection = oConnection,
        );
      if o0SSLContext:
        assert m0SSL, \
            "mSSL is not available";
        if f0SecuringConnectionCallback:
          f0SecuringConnectionCallback(
            sbHost = sbHost,
            uPortNumber = uPortNumber,
            sbIPAddress = sbIPAddress,
            oConnection = oConnection,
            oSSLContext = o0SSLContext,
          );
        try:
          oConnection.fSecure(
            oSSLContext = o0SSLContext,
            n0zTimeoutInSeconds = n0zSecureTimeoutInSeconds,
            bzCheckHost = bzCheckHost,
          );
        except m0SSL.mExceptions.cSSLException as oException:
          if f0SecuringConnectionFailedCallback:
            f0SecuringConnectionFailedCallback(
              oException = oException,
              sbHost = sbHost,
              uPortNumber = uPortNumber,
              sbIPAddress = sbIPAddress,
              oConnection = oConnection,
              oSSLContext = o0SSLContext,
            );
          raise;
        if f0ConnectionSecuredCallback:
          f0ConnectionSecuredCallback(
            sbHost = sbHost,
            uPortNumber = uPortNumber,
            sbIPAddress = sbIPAddress,
            oConnection = oConnection,
            oSSLContext = o0SSLContext,
          );
      return oConnection;
    raise AssertionError("socket.getaddrinfo(...) return an empty list!?");
    
  @ShowDebugOutput
  def __init__(oSelf,
    oPythonSocket,
    *,
    o0SSLContext = None,
    sbzRemoteHost = zNotProvided,
    sbzRemoteIPAddress = zNotProvided,
    bCreatedLocally = False,
    nSendDelayPerByteInSeconds = 0,
  ):
    fAssertType("sbzRemoteHost", sbzRemoteHost, bytes, zNotProvided);
    # The initial python socket is not secure. We can "wrap" the socket with SSL
    # to secure it repeatedly to "tunnel" multiple SSL connections. Each time
    # a new SSL connection is tunneled through the existing connection, a new
    # "wrapped" socket is created that can be used to communicate through this
    # SSL tunnel. We will keep a list of the python sockets corresponding to
    # these tunnels, in order:
    oSelf.__oPythonSocket = oPythonSocket;
    # We also keep a list of the SSL contexts for the tunneled secured
    # connections. This list is in the same order but does not have an entry
    # for the first socket, as it is not secure.
    oSelf.__o0SSLContext = o0SSLContext;
    oSelf.__bCreatedLocally = bCreatedLocally;
    oSelf.uReadChunkSize = oSelf.uDefaultReadChunkSize;
    # We will create a lock that will be released as soon as we detect that the
    # socket is disconnected to implement fbWait()
    oSelf.__oTerminatedLock = cLock(
      "%s.__oTerminatedLock" % oSelf.__class__.__name__,
      bLocked = True
    );
    # When we detect a disconnect, we need a way to check if this is the first
    # time that we detect it, so we can be sure we release the oConnectedLock
    # only once. This requires exclusive access to the "connected" property
    # to prevent race conditions where the lock is freed twice in two threads:
    oSelf.__oConnectedPropertyAccessLock = cLock(
      "%s.__oConnectedPropertyAccessLock" % oSelf.__class__.__name__,
      n0DeadlockTimeoutInSeconds = gnDeadlockTimeoutInSeconds
    );
    # We will also keep track of the fact that "fStop" of "fTerminate" has been called.
    oSelf.__bStopping = False;
    oSelf.__bShutdownForReading = False;
    oSelf.__bShutdownForWriting = False;
    
    oSelf.txLocalAddress = oPythonSocket.getsockname();
    oSelf.uLocalPortNumber = oSelf.txLocalAddress[1];
    oSelf.sbLocalHost = bytes(oSelf.txLocalAddress[0], "ascii", "strict");
    oSelf.sbLocalAddress = fsbAddressFromHostAndPort(oSelf.sbLocalHost, oSelf.uLocalPortNumber);
    
    oSelf.txRemoteAddress = oPythonSocket.getpeername();
    oSelf.sbRemoteHost = sbzRemoteHost if fbIsProvided(sbzRemoteHost) else bytes(oSelf.txRemoteAddress[0], "ascii", "strict");
    oSelf.sbRemoteIPAddress = sbzRemoteIPAddress if fbIsProvided(sbzRemoteIPAddress) else bytes(oPythonSocket.getpeername()[0], "ascii", "strict");
    oSelf.uRemotePortNumber = oSelf.txRemoteAddress[1];
    oSelf.sbRemoteAddress = fsbAddressFromHostAndPort(oSelf.sbRemoteHost, oSelf.uRemotePortNumber);
    oSelf.nSendDelayPerByteInSeconds = nSendDelayPerByteInSeconds;
    
    oSelf.fAddEvents(
      "read bytes",
      "wrote bytes",
      
      "shutdown for reading",
      "shutdown for writing",
      "shutdown",
      
      "disconnected",
      
      "terminated"
    );
  
  @ShowDebugOutput
  def fSecure(oSelf,
    oSSLContext,
    *,
    n0zTimeoutInSeconds = zNotProvided,
    bzCheckHost = zNotProvided,
  ):
    fAssertType("n0zTimeoutInSeconds", n0zTimeoutInSeconds, int, float, zNotProvided, None);
    assert m0SSL, \
        "Cannot load module mSSL; fSecure() cannot be used!";
    if oSelf.bSecure:
      raise NotImplementedError("Securing a secure socket is not implemented");
    oSelf.__fThrowExceptionIfApplicable(
      bThrowExceptionIfShutdownForReading = True,
      bThrowExceptionIfShutdownForWriting = True,
    );
    try:
      oSelf.__oPythonSocket = oSSLContext.foWrapSocket(
        oPythonSocket = oSelf.__oPythonSocket, # Tunnel through existing SSL layer if needed.
        n0zTimeoutInSeconds = n0zTimeoutInSeconds,
        bzCheckHost = bzCheckHost,
      );
    except Exception as oException:
      fShowDebugOutput(oSelf, "Exception while wrapping socket: %s(%s)" % (oException.__class__.__name__, oException));
      if fbExceptionMeansSocketShutdown(oException):
        fShowDebugOutput(oSelf, "Connection shut down.");
        # The following will check what was shut doen and call __fHandleShutDownFor(Reading|Writing)
        oSelf.__fThrowExceptionIfApplicable(
          bMustThrowException = True,
        );
      elif fbExceptionMeansSocketDisconnected(oException):
        fShowDebugOutput(oSelf, "Connection disconnected.");
        oSelf.__fHandleDisconnect();
        oSelf.__fThrowExceptionIfApplicable(
          bMustThrowException = True,
        );
      elif isinstance(oException, m0SSL.mExceptions.cSSLException):
        raise;
      else:
        raise;
    oSelf.__o0SSLContext = oSSLContext;
  
  @property
  def o0SSLContext(oSelf):
    return oSelf.__o0SSLContext;
  @property
  def bSecure(oSelf):
    return oSelf.__o0SSLContext is not None;
  
  @property
  def bCreatedLocally(oSelf):
    return oSelf.__bCreatedLocally;
  
  @property
  def bStopping(oSelf):
    return oSelf.__bStopping or not oSelf.__fbConnected();
  
  @property
  def bTerminated(oSelf):
    return not oSelf.__fbConnected();
  
  # Check to make sure the connection is terminated before being discarded.
  def __del__(oSelf):
    assert oSelf.bTerminated, \
        "%s was not terminated before being deleted!" % oSelf;
  
  @ShowDebugOutput
  def fStop(oSelf):
    if oSelf.__bStopping:
      fShowDebugOutput(oSelf, "Already stopping");
    else:
      fShowDebugOutput(oSelf, "Stopping...");
      oSelf.__bStopping = True;
      if oSelf.__fbConnected():
        if not oSelf.__bShutdownForReading or not oSelf.__bShutdownForWriting:
          try:
            oSelf.__fShutdown(
              bForReading = not oSelf.__bShutdownForReading,
              bForWriting = not oSelf.__bShutdownForWriting
            );
          except cTCPIPConnectionDisconnectedException:
            return;
        oSelf.__fDisconnect();
  
  @ShowDebugOutput
  def fTerminate(oSelf):
    oSelf.__bStopping = True;
    if oSelf.__fbConnected():
      oSelf.__fDisconnect();
  
  @ShowDebugOutput
  def fbWait(oSelf,
    nTimeoutInSeconds,
  ):
    fAssertType("nTimeoutInSeconds", nTimeoutInSeconds, int, float, None);
    return oSelf.__oTerminatedLock.fbWait(nTimeoutInSeconds);
  
  @property
  def bShutdownForReading(oSelf):
    return oSelf.__bShutdownForReading;
  
  @property
  def bShutdownForWriting(oSelf):
    return oSelf.__bShutdownForWriting;
  
  def __fHandleShutdownForReading(oSelf):
    oSelf.__bShutdownForReading = True;
    if not oSelf.__fbConnected():
      fShowDebugOutput(oSelf, "Connection disconnected.");
    elif oSelf.__bShutdownForWriting:
      fShowDebugOutput(oSelf, "Connection shutdown.");
    else:
      fShowDebugOutput(oSelf, "Connection shutdown for reading.");
  
  def __fHandleShutdownForWriting(oSelf):
    oSelf.__bShutdownForWriting = True;
    if not oSelf.__fbConnected():
      fShowDebugOutput(oSelf, "Connection disconnected.");
    if not oSelf.__bShutdownForReading:
      fShowDebugOutput(oSelf, "Connection shutdown.");
    else:
      fShowDebugOutput(oSelf, "Connection shutdown for writing.");
  
  @property
  def bConnected(oSelf):
    return oSelf.__fbConnected();
  def __fbConnected(oSelf):
    if oSelf.__oTerminatedLock.bLocked and oSelf.__oPythonSocket.fileno() == -1:
      oSelf.__fHandleDisconnect();
    return oSelf.__oTerminatedLock.bLocked;
  
  @ShowDebugOutput
  def fbHasReadEventOnPythonSocket(oSelf):
    if not oSelf.__fbConnected():
      fShowDebugOutput(oSelf, "Disconnected.");
      return True;
    if oSelf.__bShutdownForReading:
      fShowDebugOutput(oSelf, "Shutdown.");
      return True;
    oSelf.__oPythonSocket.settimeout(0);
    bHasReadEvent = len(select.select([oSelf.__oPythonSocket], [], [], 0)[0]) > 0;
    if bHasReadEvent:
      fShowDebugOutput(oSelf, "Read event detected.");
      return True;
    fShowDebugOutput(oSelf, "No read event detected.");
    return False;
  
  @ShowDebugOutput
  def fWaitUntilReadEventOnPythonSocket(oSelf):
    oSelf.__oPythonSocket.setblocking(True);
    select.select([oSelf.__oPythonSocket], [], []);

  @ShowDebugOutput
  def fbWaitUntilReadEventOnPythonSocket(oSelf,
    *,
    nWaitTimeoutInSeconds,
  ):
    fAssertType("nWaitTimeoutInSeconds", nWaitTimeoutInSeconds, int, float);
    oSelf.__oPythonSocket.settimeout(nWaitTimeoutInSeconds);
    bHasReadEvent = len(select.select([oSelf.__oPythonSocket], [], [], nWaitTimeoutInSeconds)[0]) > 0;
    if bHasReadEvent:
      fShowDebugOutput(oSelf, "Read event detected.");
      return True;
    fShowDebugOutput(oSelf, "No read event detected.");
    return False;

  def fThrowExceptionIfShutdownOrDisconnected(oSelf):
    oSelf.__fThrowExceptionIfApplicable(
      bThrowExceptionIfShutdownForReading = True,
      bThrowExceptionIfShutdownForWriting = True,
    );
  
  def __fThrowExceptionIfApplicable(oSelf,
    *,
    bThrowExceptionIfShutdownForReading = False,
    bThrowExceptionIfShutdownForWriting = False,
    bMustThrowException = False,
  ):
    if oSelf.__oPythonSocket.fileno() == -1:
      oSelf.__fHandleDisconnect();
    if not oSelf.__oTerminatedLock.bLocked:
      raise cTCPIPConnectionDisconnectedException(
        "Connection %s was disconnected." % (
          oSelf.fsGetEndPointsAndDirection(),
        ),
        ozConnection = oSelf,
      );
    if bThrowExceptionIfShutdownForReading and oSelf.__bShutdownForReading:
      raise cTCPIPConnectionShutdownException(
        "Connection %s was shutdown for reading%s." % (
          oSelf.fsGetEndPointsAndDirection(),
          " and writing" if oSelf.__bShutdownForWriting else "",
        ),
        ozConnection = oSelf,
      );
    if bThrowExceptionIfShutdownForWriting and oSelf.__bShutdownForWriting:
      raise cTCPIPConnectionShutdownException(
        "Connection %s was shutdown for writing." % (
          oSelf.fsGetEndPointsAndDirection(),
        ),
        ozConnection = oSelf,
      );
    assert not bMustThrowException, \
        "The connection was expected to be shut down or disconnected but neither was true.";
  
  @ShowDebugOutput
  def __fsbReadBytes(oSelf, uMaxNumberOfBytes, n0TimeoutInSeconds):
    assert uMaxNumberOfBytes > 0, \
          "uMaxNumberOfBytes must be larger than 0, not %d" % uMaxNumberOfBytes;
    if oSelf.__oPythonSocket.fileno() == -1:
      oSelf.__fHandleDisconnect();
      return b"";
    fShowDebugOutput(oSelf, "Reading up to %d bytes..." % uMaxNumberOfBytes);
    try:
      if n0TimeoutInSeconds:
        oSelf.__oPythonSocket.settimeout(n0TimeoutInSeconds);
      else:
        oSelf.__oPythonSocket.settimeout(0);
      bReadEventDetectedBefore = len(select.select([oSelf.__oPythonSocket],[],[],0)[0]) > 0;
      sbBytesRead = oSelf.__oPythonSocket.recv(uMaxNumberOfBytes);
      bReadEventDetectedAfter = len(select.select([oSelf.__oPythonSocket],[],[],0)[0]) > 0;
    except Exception as oException:
      fShowDebugOutput(oSelf, "Exception during `recv()`: %s(%s)" % (oException.__class__.__name__, oException));
      if fbExceptionMeansSocketHasNoDataAvailable(oException):
        fShowDebugOutput(oSelf, "No bytes to read.");
      elif fbExceptionMeansSocketShutdown(oException):
        fShowDebugOutput(oSelf, "Connection was shut down.");
        oSelf.__fHandleShutdownForReading();
      elif fbExceptionMeansSocketDisconnected(oException):
        fShowDebugOutput(oSelf, "Connection disconnected.");
        oSelf.__fHandleDisconnect();
      else:
        raise;
      return b"";
    fShowDebugOutput(oSelf, "Read event detected before." if bReadEventDetectedBefore else "No read event detected before.");
    fShowDebugOutput(oSelf, "Read %d bytes." % len(sbBytesRead));
    fShowDebugOutput(oSelf, "Read event detected after." if bReadEventDetectedAfter else "No read event detected after.");
    if len(sbBytesRead) == 0:
      if bReadEventDetectedBefore and bReadEventDetectedAfter:
        fShowDebugOutput(oSelf, "Nothing read even though read events were detected: connection must have been shut down.");
        oSelf.__fHandleShutdownForReading();
    else:
      uShowDataBytesPerLine = 32;
      for uOffset in range(0, len(sbBytesRead), uShowDataBytesPerLine):
        sbData = sbBytesRead[uOffset:uOffset + uShowDataBytesPerLine];
        fShowDebugOutput(
          " ".join(["%02X" % uByte for uByte in sbData]).ljust(3 * uShowDataBytesPerLine) +
          "| " +
          "".join([chr(uByte) if uByte in range(0x20, 0x7F) else "." for uByte in sbData])
        );
      oSelf.fFireCallbacks("read bytes", sbBytes = sbBytesRead);
    return sbBytesRead;

  @ShowDebugOutput
  def fsbReadAvailableBytes(oSelf,
    *,
    u0MaxNumberOfBytes = None,
    n0TimeoutInSeconds = None,
  ):
    # Can throw a shutdown or disconnected exception *if* this happens before any bytes can be read.
    # Returns any bytes that can currently be read, this could be "".
    fAssertType("u0MaxNumberOfBytes", u0MaxNumberOfBytes, int, None);
    if u0MaxNumberOfBytes is not None:
      sbBytesRead = oSelf.__fsbReadBytes(u0MaxNumberOfBytes, n0TimeoutInSeconds);
    else:
      fShowDebugOutput(oSelf, "Reading in blocks of %d bytes..." % oSelf.uReadChunkSize);
      nStartTime = time.time()
      n0RemainingTimeoutInSeconds = n0TimeoutInSeconds;
      sbBytesRead = b"";
      while 1:
        sbChunkBytesRead = oSelf.__fsbReadBytes(oSelf.uReadChunkSize, n0RemainingTimeoutInSeconds);
        sbBytesRead += sbChunkBytesRead;
        if len(sbChunkBytesRead) == 0:
          break;
        if n0TimeoutInSeconds is not None:
          n0RemainingTimeoutInSeconds = nStartTime + n0TimeoutInSeconds - time.time();
          if n0RemainingTimeoutInSeconds <= 0:
            break;
      fShowDebugOutput(oSelf, "Read a total of %d bytes." % len(sbBytesRead));
    if len(sbBytesRead) == 0 and oSelf.__bShutdownForReading:
      fShowDebugOutput(oSelf, "Read nothing: throwing shutdown-for-reading exception...");
      oSelf.__fThrowExceptionIfApplicable(
        bThrowExceptionIfShutdownForReading = True,
        bMustThrowException = True,
      );
    return sbBytesRead;
  
  @ShowDebugOutput
  def fsbReadBytesUntilDisconnected(oSelf,
    u0MaxNumberOfBytes = None,
    n0TimeoutInSeconds = None,
  ):
    fAssertType("u0MaxNumberOfBytes", u0MaxNumberOfBytes, int, None);
    fAssertType("n0TimeoutInSeconds", n0TimeoutInSeconds, int, float, None);
    nStartTime = time.time();
    sbBytesRead = b"";
    u0MaxNumberOfBytesRemaining = u0MaxNumberOfBytes;
    try:
      while u0MaxNumberOfBytesRemaining is None or u0MaxNumberOfBytesRemaining > 0:
        n0RemainingTimeoutInSeconds = max(0, nStartTime + n0TimeoutInSeconds - time.time()) if n0TimeoutInSeconds is not None else None;
        sbAvailableBytes = oSelf.fsbReadAvailableBytes(
          u0MaxNumberOfBytes = u0MaxNumberOfBytesRemaining,
          n0TimeoutInSeconds = n0RemainingTimeoutInSeconds,
        );
        if n0RemainingTimeoutInSeconds == 0:
          break;
        if len(sbAvailableBytes) == 0:
          raise cTCPIPDataTimeoutException(
            "Timeout on connection %s after %s seconds." % (
              oSelf.fsGetEndPointsAndDirection(),
              n0TimeoutInSeconds,
            ),
            ozConnection = oSelf,
          );
        sbBytesRead += sbAvailableBytes;
    except (cTCPIPConnectionShutdownException, cTCPIPConnectionDisconnectedException):
      pass;
    return sbBytesRead;
  
  @ShowDebugOutput
  def fWriteBytes(oSelf,
    sbBytes,
    *,
    n0TimeoutInSeconds = None,
  ):
    fAssertType("sbBytes", sbBytes, bytes);
    fAssertType("n0TimeoutInSeconds", n0TimeoutInSeconds, int, float, None);
    # Can throw a timeout, shutdown or disconnected exception.
    # Returns once all bytes have been written.
    uNumberOfBytesToWrite = len(sbBytes);
    oSelf.__fThrowExceptionIfApplicable(
      bThrowExceptionIfShutdownForWriting = True,
    );
    nStartTime = time.time();
    n0EndTime = (nStartTime + n0TimeoutInSeconds) if n0TimeoutInSeconds is not None else None;
    uTotalNumberOfBytesWritten = 0;
    while uTotalNumberOfBytesWritten < uNumberOfBytesToWrite:
      if n0EndTime is not None and time.time() >= n0EndTime:
        raise cTCPIPDataTimeoutException(
          "Timeout on connection %s after %s seconds." % (
            oSelf.fsGetEndPointsAndDirection(),
            n0TimeoutInSeconds,
          ),
          ozConnection = oSelf,
        );
      oSelf.__oPythonSocket.settimeout(0);
      if oSelf.nSendDelayPerByteInSeconds > 0:
        # sleep first
        time.sleep(oSelf.nSendDelayPerByteInSeconds);
        # then send only a single byte
        sbBytesToWrite = sbBytes[:1];
      else:
        sbBytesToWrite = sbBytes;
      try:
        uNumberOfBytesWrittenInSendCall = oSelf.__oPythonSocket.send(sbBytesToWrite);
      except Exception as oException:
        fShowDebugOutput(oSelf, "Exception during `send()`: %s(%s)" % (oException.__class__.__name__, oException));
        if fbExceptionMeansSocketShutdown(oException):
          fShowDebugOutput(oSelf, "Connection shutdown.");
          oSelf.__fHandleShutdownForWriting();
        elif fbExceptionMeansSocketDisconnected(oException):
          fShowDebugOutput(oSelf, "Connection disconnected.");
          oSelf.__fHandleDisconnect();
        else:
          raise;
        oSelf.__fThrowExceptionIfApplicable(
          bThrowExceptionIfShutdownForWriting = True,
          bMustThrowException = True,
        );
      fShowDebugOutput(oSelf, "%d bytes written." % uNumberOfBytesWrittenInSendCall);
      oSelf.fFireCallbacks("wrote bytes", sbBytes = sbBytes[:uNumberOfBytesWrittenInSendCall]);
      sbBytes = sbBytes[uNumberOfBytesWrittenInSendCall:];
      uTotalNumberOfBytesWritten += uNumberOfBytesWrittenInSendCall;
  
  @ShowDebugOutput
  def fShutdownForReading(oSelf):
    oSelf.__fShutdown(
      bForReading = True,
    );
  
  @ShowDebugOutput
  def fShutdownForWriting(oSelf):
    oSelf.__fShutdown(
      bForWriting = True,
    );
  
  @ShowDebugOutput
  def fShutdown(oSelf):
    oSelf.__fShutdown(
      bForReading = True,
      bForWriting = True,
    );
  
  def __fShutdown(oSelf,
    bForReading = False,
    bForWriting = False,
  ):
    if oSelf.__oPythonSocket.fileno() == -1:
      oSelf.__fHandleDisconnect();
      return;
    # Shutting down a secure connection does not appear to have the expected
    # results; we'll do it anyway but be aware that it does not appear that
    # the remote is notified of the shutdown.
    # Can throw a disconnected exception.
    bForReading = bForReading and not oSelf.__bShutdownForReading;
    bForWriting = bForWriting and not oSelf.__bShutdownForWriting;
    # If there's nothing to do, do nothing:
    if not bForReading and not bForWriting: return;
    xFlags = (
      socket.SHUT_RDWR if bForWriting and bForReading else
      socket.SHUT_RD   if bForReading else
      socket.SHUT_WR   if bForWriting else
      None
    )
    sShutdownFor = " and ".join([s for s in [
      "reading" if bForReading else None,
      "writing" if bForWriting else None,
    ] if s]);
    if xFlags is None:
      fShowDebugOutput(oSelf, "Already shut down for %s..." %  sShutdownFor);
      return;
    fShowDebugOutput(oSelf, "Shutting down for %s..." %  sShutdownFor);
    if bForReading:
      oSelf.__bShutdownForReading = True;
    if bForWriting:
      oSelf.__bShutdownForWriting = True;
    oSelf.__oPythonSocket.settimeout(0);
    try:
      oSelf.__oPythonSocket.shutdown(xFlags);
    except Exception as oException:
      fShowDebugOutput(oSelf, "Exception during `shutdown()`: %s(%s)" % (oException.__class__.__name__, oException));
      if fbExceptionMeansSocketDisconnected(oException):
        fShowDebugOutput(oSelf, "Connection disconnected while shutting down for %s." % sShutdownFor);
        oSelf.__fHandleDisconnect();
      else:
        raise;
      oSelf.__fThrowExceptionIfApplicable(
        bMustThrowException = True,
      );
    if bForReading:
      oSelf.fFireCallbacks("shutdown for reading");
    if bForWriting:
      oSelf.fFireCallbacks("shutdown for writing");
    oSelf.fFireCallbacks("shutdown");
  
  @ShowDebugOutput
  def fDisconnect(oSelf,
    bShutdownFirst = True,
  ):
    if not oSelf.__fbConnected(): return;
    if bShutdownFirst:
      fShowDebugOutput(oSelf, "Shutting socket down...");
      try:
        oSelf.__fShutdown(
          bForReading = not oSelf.__bShutdownForReading,
          bForWriting = not oSelf.__bShutdownForWriting
        );
      except cTCPIPConnectionDisconnectedException:
        # A debug message from __fShutdown will have already explained what happened.
        pass;
    if oSelf.__fbConnected():
      oSelf.__fDisconnect();
  
  @ShowDebugOutput
  def __fDisconnect(oSelf):
    if not oSelf.__fbConnected():
      fShowDebugOutput(oSelf, "Already disconnected.");
      return;
    fShowDebugOutput(oSelf, "Disconnecting socket...");
    try:
      oSelf.__oPythonSocket.close();
    except Exception as oException:
      fShowDebugOutput(oSelf, "Exception during `close()`: %s(%s)" % \
          (oException.__class__.__name__, oException));
      if not fbExceptionMeansSocketDisconnected(oException):
        raise;
    oSelf.__fHandleDisconnect();
    fShowDebugOutput(oSelf, "Disconnected.");
  
  @ShowDebugOutput
  def __fHandleDisconnect(oSelf):
    fShowDebugOutput(oSelf, "Connection disconnected, cleaning up...");
    oSelf.__bStopping = True;
    oSelf.__oConnectedPropertyAccessLock.fAcquire();
    try:
      if not oSelf.__oTerminatedLock.bLocked:
        return;
      try:
        oSelf.__oPythonSocket.close();
      except Exception as oException:
        fShowDebugOutput(oSelf, "Exception during `close()`: %s(%s)" % \
            (oException.__class__.__name__, oException));
        if not fbExceptionMeansSocketDisconnected(oException):
          raise;
      oSelf.__bShutdownForReading = True;
      oSelf.__bShutdownForWriting = True;
      oSelf.__oTerminatedLock.fRelease();
    finally:
      oSelf.__oConnectedPropertyAccessLock.fRelease();
    oSelf.fFireCallbacks("disconnected");
    # Fire terminated event now if we are not holding it.
    fShowDebugOutput(oSelf, "Firing terminated callbacks...");
    oSelf.fFireCallbacks("terminated");
  
  def fsGetEndPointsAndDirection(oSelf):
    return "%s %s %s" % (
      str(oSelf.sbLocalAddress, "ascii", "strict"),
      oSelf.__bCreatedLocally and "=>" or "<=",
      str(oSelf.sbRemoteAddress, "ascii", "strict"),
    );
  def fasGetDetails(oSelf):
    # This is done without a property lock, so race-conditions exist and it
    # approximates the real values.
    bTerminated = not oSelf.__oTerminatedLock.bLocked;
    bShutdownForReading = oSelf.__bShutdownForReading;
    bShutdownForWriting = oSelf.__bShutdownForWriting;
    bStopping = oSelf.__bStopping and not bTerminated;
    return [s for s in [
      oSelf.fsGetEndPointsAndDirection(),
      (
        "disconnected" if bTerminated else 
        "shutdown" if bShutdownForWriting and bShutdownForReading else
        "read-only" if bShutdownForWriting else
        "write-only" if bShutdownForReading else
        "connected"
      ),
      "stopping" if bStopping else None,
    ] if s];
  
  def __repr__(oSelf):
    sModuleName = ".".join(oSelf.__class__.__module__.split(".")[:-1]);
    return "<%s.%s#%X|%s>" % (sModuleName, oSelf.__class__.__name__, id(oSelf), "|".join(oSelf.fasGetDetails()));
  
  def __str__(oSelf):
    return "%s#%X{%s}" % (oSelf.__class__.__name__, id(oSelf), ", ".join(oSelf.fasGetDetails()));#
