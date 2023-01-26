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

from mMultiThreading import cLock, cWithCallbacks;
from mNotProvided import \
    fAssertType, \
    fbIsProvided, \
    fxGetFirstProvidedValue, \
    zNotProvided;

from .fbExceptionMeansSocketConnectionRefused import fbExceptionMeansSocketConnectionRefused;
from .fbExceptionMeansSocketDisconnected import fbExceptionMeansSocketDisconnected;
from .fbExceptionMeansSocketHasNoDataAvailable import fbExceptionMeansSocketHasNoDataAvailable;
from .fbExceptionMeansSocketHostnameCannotBeResolved import fbExceptionMeansSocketHostnameCannotBeResolved;
from .fbExceptionMeansSocketAddressIsInvalid import fbExceptionMeansSocketAddressIsInvalid;
from .fbExceptionMeansSocketShutdown import fbExceptionMeansSocketShutdown;
from .fbExceptionMeansSocketTimeout import fbExceptionMeansSocketTimeout;
from .mExceptions import *;

# To turn access to data store in multiple variables into a single transaction, we will create locks.
# These locks should only ever be locked for a short time; if it is locked for too long, it is considered a "deadlock"
# bug, where "too long" is defined by the following value:
gnDeadlockTimeoutInSeconds = 1; # We're not doing anything time consuming, so this should suffice.

def fsbAddressFromHostnameAndPort(sbHostname, uPort):
  # IPv6 Addresses have colons in them; wrap them in [] to prevent confusion with the port number.
  return (b"[%s]:%d" if b":" in sbHostname else b"%s:%d") % (sbHostname, uPort);

class cTCPIPConnection(cWithCallbacks):
  bSSLIsSupported = m0SSL is not None;
  n0DefaultConnectTimeoutInSeconds = 5; # How long to try to connect before giving up?
  uDefaultReadChunkSize = 0x100 * 0x400; # How many bytes to try to read if we do not know how many are comming.
  if m0SSL is not None:
    tcExceptions = (cTCPIPException, m0SSL.mExceptions.cSSLException);
  else:
    tcExceptions = (cTCPIPException,);
  
  @classmethod
  @ShowDebugOutput
  def foConnectTo(cClass, \
    sbHostnameOrIPAddress, uPortNumber, n0zConnectTimeoutInSeconds = zNotProvided,
    o0SSLContext = None, n0zSecureTimeoutInSeconds = zNotProvided,
    f0HostnameOrIPAddressInvalidCallback = None,
    f0ResolvingHostnameCallback = None,
    f0ResolvingHostnameFailedCallback = None,
    f0HostnameResolvedToIPAddressCallback = None,
    f0ConnectingToIPAddressCallback = None,
    f0ConnectingToIPAddressFailedCallback = None,
  ):
    fAssertType("sbHostnameOrIPAddress", sbHostnameOrIPAddress, bytes);
    fAssertType("uPortNumber", uPortNumber, int);
    fAssertType("n0zConnectTimeoutInSeconds", n0zConnectTimeoutInSeconds, int, float, zNotProvided, None);
    if m0SSL:
      fAssertType("o0SSLContext", o0SSLContext, m0SSL.cSSLContext, None);
    else:
      assert o0SSLContext is None, \
          "Cannot load module mSSL; o0SSLContext cannot be %s!" % repr(o0SSLContext);
    fAssertType("n0zSecureTimeoutInSeconds", n0zSecureTimeoutInSeconds, int, float, zNotProvided, None);
    n0ConnectTimeoutInSeconds = fxGetFirstProvidedValue(n0zConnectTimeoutInSeconds, cClass.n0DefaultConnectTimeoutInSeconds);
    # Resolve hostname
    sLowerHostnameOrIPAddress = str(sbHostnameOrIPAddress, "ascii", "strict").lower();
    # We may at some poing special case IP addresses and skip resolving them, as this adds no value.
    if f0ResolvingHostnameCallback:
      f0ResolvingHostnameCallback(sbHostname = sbHostnameOrIPAddress);
    try:
      atxAddressInfo = socket.getaddrinfo(
        sLowerHostnameOrIPAddress,
        uPortNumber,
        type = socket.SOCK_STREAM,
        proto = socket.IPPROTO_TCP,
        flags = socket.AI_CANONNAME,
      );
    except Exception as oException:
      if fbExceptionMeansSocketAddressIsInvalid(oException):
        if f0HostnameOrIPAddressInvalidCallback:
          f0HostnameOrIPAddressInvalidCallback(sbHostnameOrIPAddress = sbHostnameOrIPAddress);
        raise cTCPIPInvalidAddressException(
          "Cannot connect to invalid address %s." % (
            repr("%s:%d" % (sLowerHostnameOrIPAddress, uPortNumber)),
          ),
          sHostnameOrIPAddress = sLowerHostnameOrIPAddress,
          uPortNumber = uPortNumber,
        );
      elif fbExceptionMeansSocketHostnameCannotBeResolved(oException):
        if f0ResolvingHostnameFailedCallback:
          f0ResolvingHostnameFailedCallback(sbHostname = sbHostnameOrIPAddress);
        raise cTCPIPDNSUnknownHostnameException(
          "Cannot connect to hostname %s because it cannot be resolved." % (
            repr(sLowerHostnameOrIPAddress),
          ),
          sHostname = sLowerHostnameOrIPAddress,
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
        continue; # Not a protocol we suport.
      if sIPAddress.lower() != sLowerHostnameOrIPAddress:
        if f0HostnameResolvedToIPAddressCallback:
          f0HostnameResolvedToIPAddressCallback(
            sbHostname = sbHostnameOrIPAddress,
            sIPAddress = sIPAddress,
            sCanonicalName = sCanonicalName
          );
        sbzHostname = sbHostnameOrIPAddress;
      else:
        sbzHostname = zNotProvided;
      fShowDebugOutput("Connecting to %s:%d (%saddress %s)..." % (
        ("[%s]" if ":" in sLowerHostnameOrIPAddress else "%s") % (sLowerHostnameOrIPAddress,), # IPv6 Addresses must be wrapped in []
        uPortNumber,
        ("canonical name %s, " % sCanonicalName) if (sCanonicalName != sLowerHostnameOrIPAddress) else "",
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
          sbHostnameOrIPAddress = sbHostnameOrIPAddress,
          uPortNumber = uPortNumber,
          sIPAddress = sIPAddress,
          sbzHostname = sbzHostname,
        );
      oPythonSocket.settimeout(n0ConnectTimeoutInSeconds);
      nStartTime = time.time();
      try:
        oPythonSocket.connect(txAddress);
      except Exception as oException:
        fShowDebugOutput("Exception during `connect()`: %s(%s)" % (oException.__class__.__name__, oException));
        if fbExceptionMeansSocketAddressIsInvalid(oException):
          raise cTCPIPInvalidAddressException(
            "Cannot connect to invalid address %s." % (
              repr("%s:%d" % (sLowerHostnameOrIPAddress, uPortNumber)),
            ),
            sHostnameOrIPAddress = sIPAddress,
            uPortNumber = uPortNumber,
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
              sHostnameOrIPAddress = sIPAddress,
              uPortNumber = uPortNumber,
              nTimeoutInSeconds = n0ConnectTimeoutInSeconds,
            );
          elif fbExceptionMeansSocketConnectionRefused(oException):
            oException = cTCPIPConnectionRefusedException(
              "Attempt to connect to server address %s refused." % repr("%s:%d" % (sIPAddress, uPortNumber)),
              sHostnameOrIPAddress = sIPAddress,
              uPortNumber = uPortNumber,
            );
          else:
            raise;
        if f0ConnectingToIPAddressFailedCallback:
          f0ConnectingToIPAddressFailedCallback(
            oException = oException,
            sbHostnameOrIPAddress = sbHostnameOrIPAddress,
            uPortNumber = uPortNumber,
            sIPAddress = sIPAddress,
            sbzHostname = sbzHostname,
          );
        # We will ignore this exception and try the next address unless there are no more addresses.
        if bIsLastAddressInfo:
          raise oException;
        else:
          continue;
      oConnection = cClass(oPythonSocket, sbzRemoteHostname = sbzHostname, bCreatedLocally = True);
      if o0SSLContext:
        oConnection.fSecure(
          oSSLContext = o0SSLContext,
          n0zTimeoutInSeconds = n0zSecureTimeoutInSeconds,
       );
      return oConnection;
    raise AssertionError("socket.getaddrinfo(...) return an empty list!?");
    
  @classmethod
  @ShowDebugOutput
  def faoWaitUntilBytesAreAvailableForReading(cClass, aoConnections, n0TimeoutInSeconds = None):
    fAssertType("aoConnections", aoConnections, [cTCPIPConnection]);
    fAssertType("n0TimeoutInSeconds", n0TimeoutInSeconds, int, float, None);
    # select.select does not work well on secure sockets, so we use the non-secure sockets
    # as proxies; there may be SSL traffic without data being send from the remote end, so
    # we may flag a connection as having data to be read when it has none.
    n0EndTime = time.time() + n0TimeoutInSeconds if n0TimeoutInSeconds is not None else None;
    while 1:
      aoConnectionsWithBytesAvailableForReading = [];
      aiPythonSocketFileNos = [];
      for oConnection in aoConnections:
        if oConnection.fbBytesAreAvailableForReading():
          aoConnectionsWithBytesAvailableForReading.append(oConnection);
        else:
          iFileNo = oConnection.__oPythonSocket.fileno();
          if oConnection.bConnected:
            aiPythonSocketFileNos.append(iFileNo);
      if aoConnectionsWithBytesAvailableForReading:
        # There currently are connections with bytes available for reading.
        return aoConnectionsWithBytesAvailableForReading;
      if not aiPythonSocketFileNos:
        return []; # All connections have been closed; no connection left to wait for.
      # Wait until the python sockets become readable, shutdown or closed:
      n0TimeoutInSeconds = n0EndTime - time.time() if n0EndTime is not None else None;
      if n0TimeoutInSeconds < 0 or len(select.select(aiPythonSocketFileNos, [], [], n0TimeoutInSeconds)[0]) == 0:
        return []; # Waiting timed out.
  
  @ShowDebugOutput
  def __init__(oSelf, oPythonSocket, o0SecurePythonSocket = None, o0SSLContext = None, sbzRemoteHostname = zNotProvided, bCreatedLocally = False):
    fAssertType("sbzRemoteHostname", sbzRemoteHostname, bytes, zNotProvided);
    # The initial python socket is not secure. We can "wrap" the socket with SSL
    # to secure it repeatedly to "tunnel" multiple SSL connections. Each time
    # a new SSL connection is tunneled through the existing connection, a new
    # "wrapped" socket is created that can be used to communicate through this
    # SSL tunnel. We will keep a list of the python sockets corresponding to
    # these tunnels, in order:
    oSelf.__aoPythonSockets = [o0 for o0 in [
      oPythonSocket,
      o0SecurePythonSocket
    ] if o0];
    # We also keep a list of the SSL contexts for the tunneled secured
    # connections. This list is in the same order but does not have an entry
    # for the first socket, as it is not secure.
    oSelf.__aoSSLContexts = [o0 for o0 in [
      o0SSLContext
    ] if o0];
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
    # only once. This requires exclusive acccess to the "connected" property
    # to prevent race conditions where the lock is freed twice in two threads:
    oSelf.__oConnectedPropertyAccessLock = cLock(
      "%s.__oConnectedPropertyAccessLock" % oSelf.__class__.__name__,
      n0DeadlockTimeoutInSeconds = gnDeadlockTimeoutInSeconds
    );
    # We will also keep track of the fact that "fStop" of "fTerminate" has been called.
    oSelf.__bStopping = False;
    oSelf.__bShouldAllowReading = True;
    oSelf.__bShouldAllowWriting = True;
    
    oSelf.txLocalAddress = oSelf.__oPythonSocket.getsockname();
    oSelf.uLocalPortNumber = oSelf.txLocalAddress[1];
    oSelf.sbLocalHostname = bytes(oSelf.txLocalAddress[0], "ascii", "strict");
    oSelf.sbLocalAddress = fsbAddressFromHostnameAndPort(oSelf.sbLocalHostname, oSelf.uLocalPortNumber);
    
    oSelf.txRemoteAddress = oSelf.__oPythonSocket.getpeername();
    oSelf.uRemotePortNumber = oSelf.txRemoteAddress[1];
    oSelf.sbRemoteHostname = sbzRemoteHostname if fbIsProvided(sbzRemoteHostname) else bytes(oSelf.txRemoteAddress[0], "ascii", "strict");
    oSelf.sbRemoteAddress = fsbAddressFromHostnameAndPort(oSelf.sbRemoteHostname, oSelf.uRemotePortNumber);
    
    oSelf.__uTerminatedCallbackPostponeCounter = 0;
    oSelf.__bTerminatedCallbackPostponed = False;
    
    oSelf.fAddEvents(
      "bytes read",
      "bytes written",
      "shutdown for reading", "shutdown for writing", "shutdown",
      "terminated"
    );
  
  def fPostponeTerminatedCallback(oSelf):
    oSelf.__uTerminatedCallbackPostponeCounter += 1;
    if oSelf.__uTerminatedCallbackPostponeCounter == 1:
      fShowDebugOutput(oSelf, "Started postponing terminated callbacks.");
    else:
      fShowDebugOutput(oSelf, "Increased postpone terminated callbacks counter to %d (%sevent postponed)." % \
          (oSelf.__uTerminatedCallbackPostponeCounter, "" if oSelf.__bTerminatedCallbackPostponed else "no "));
  
  def fFireTerminatedCallbackIfPostponed(oSelf):
    assert oSelf.__uTerminatedCallbackPostponeCounter > 0, \
        "This function has been called more often than fPostponeTerminatedCallback, which is an error!";
    oSelf.__uTerminatedCallbackPostponeCounter -= 1;
    if oSelf.__uTerminatedCallbackPostponeCounter == 0:
      if oSelf.__bTerminatedCallbackPostponed:
        fShowDebugOutput(oSelf, "Firing postponing terminated callbacks...");
        oSelf.__bTerminatedCallbackPostponed = False;
        oSelf.fFireCallbacks("terminated");
      fShowDebugOutput(oSelf, "Ended postponing terminated callbacks (not postponed).");
    else:
      fShowDebugOutput(oSelf, "Decreased postponing terminated callbacks to %d (%sevent postponed)." % \
        (oSelf.__uTerminatedCallbackPostponeCounter, "" if oSelf.__bTerminatedCallbackPostponed else "no "));
  
  @property
  def __oNonSecurePythonSocket(oSelf):
    return oSelf.__aoPythonSockets[0];
  @property
  def __oSecurePythonSocket(oSelf):
    return oSelf.__aoPythonSockets[-1] if len(oSelf.__aoPythonSockets) > 1 else None;
  @property
  def __oPythonSocket(oSelf):
    # For internal use only.
    return oSelf.__aoPythonSockets[-1];
  @property
  def __o0SSLContext(oSelf):
    return oSelf.__aoSSLContexts[-1] if len(oSelf.__aoSSLContexts) > 0 else None;
  
  @ShowDebugOutput
  def fSecure(oSelf, oSSLContext, n0zTimeoutInSeconds = zNotProvided, sWhile = "securing connection"):
    fAssertType("n0zTimeoutInSeconds", n0zTimeoutInSeconds, int, float, zNotProvided, None);
    assert m0SSL, \
        "Cannot load module mSSL; fSecure() cannot be used!";
    oSelf.__fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, bShouldAllowReading = True, bShouldAllowWriting = True);
    try:
      oSecurePythonSocket = oSSLContext.foWrapSocket(
        oPythonSocket = oSelf.__oPythonSocket, # Tunnel through existing SSL layer if needed.
        n0zTimeoutInSeconds = n0zTimeoutInSeconds,
      );
    except Exception as oException:
      fShowDebugOutput(oSelf, "Exception while wrapping socket: %s(%s)" % (oException.__class__.__name__, oException));
      if fbExceptionMeansSocketShutdown(oException):
        fShowDebugOutput(oSelf, "Connection shut down while %s." % sWhile);
        # The following will check what was shut doen and call __fHandleShutDownFor(Reading|Writing)
        oSelf.__fCheckIfSocketAllowsReading(sWhile);
        oSelf.__fCheckIfSocketAllowsWriting(sWhile);
        oSelf.__fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, bMustThrowException = True);
      elif fbExceptionMeansSocketDisconnected(oException):
        fShowDebugOutput(oSelf, "Connection disconnected while %s." % sWhile);
        oSelf.__fHandleDisconnect();
        oSelf.__fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, bMustThrowException = True);
      elif isinstance(oException, m0SSL.mExceptions.cSSLException):
        raise;
# This has been disabled - I presume I did so because SSL disconnects the connect when there is an acception.
#        # The connection could have been shutdown or disconnected while doing the SSL handshake.
#        # In that case, we'll throw the appropriate exception instead of the mSSL exception.
#        oSelf.__fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, bShouldAllowReading = True, bShouldAllowWriting = True);
      else:
        raise;
    oSelf.__aoPythonSockets.append(oSecurePythonSocket);
    oSelf.__aoSSLContexts.append(oSSLContext);
  
  @property
  def o0SSLContext(oSelf):
    return oSelf.__o0SSLContext;
  @property
  def bSecure(oSelf):
    return len(oSelf.__aoSSLContexts) > 0;
  
  @property
  def bCreatedLocally(oSelf):
    return oSelf.__bCreatedLocally;
  
  @property
  def bStopping(oSelf):
    return oSelf.__bStopping;
  
  @ShowDebugOutput
  def fStop(oSelf):
    if oSelf.__bStopping:
      fShowDebugOutput(oSelf, "Already stopping");
    else:
      fShowDebugOutput(oSelf, "Stopping...");
      oSelf.__bStopping = True;
      if oSelf.bConnected:
        if oSelf.__bShouldAllowReading or oSelf.__bShouldAllowWriting:
          try:
            oSelf.__fShutdown(
              bForReading = oSelf.__bShouldAllowReading,
              bForWriting = oSelf.__bShouldAllowWriting
            );
          except cTCPIPConnectionDisconnectedException:
            return;
        oSelf.__fDisconnect();
  
  @ShowDebugOutput
  def fTerminate(oSelf):
    oSelf.__bStopping = True;
    if oSelf.bConnected:
      oSelf.__fDisconnect();
  
  @ShowDebugOutput
  def fbWait(oSelf, nTimeoutInSeconds):
    fAssertType("nTimeoutInSeconds", nTimeoutInSeconds, int, float, None);
    return oSelf.__oTerminatedLock.fbWait(nTimeoutInSeconds);
  
  @property
  def bShouldAllowReading(oSelf):
    return oSelf.__bShouldAllowReading;
  
  @property
  def bShouldAllowWriting(oSelf):
    return oSelf.__bShouldAllowWriting;
  
  def __fCheckIfSocketAllowsReading(oSelf, sWhile):
    assert oSelf.__bShouldAllowReading, \
        "Check if __bShouldAllowReading is True before calling!";
    if oSelf.__oPythonSocket.fileno() == -1:
      oSelf.__fHandleDisconnect();
      return False;
    # Check if it is not shutdown or disconnected at this time.
    try:
      # This can also throw an exception if the socket has been closed, so it's
      # inside the try...except loop:
      oSelf.__oPythonSocket.settimeout(0);
      # .rec() on the secure socket may succeed even if the connection is
      # closed. .recv() on the non-secure socket will throw an exception and
      # will not interfere with ssl; hence we call that:
      oSelf.__oPythonSocket.recv(0);
    except Exception as oException:
      fShowDebugOutput(oSelf, "Exception during `recv()`: %s(%s)" % (oException.__class__.__name__, oException));
      if fbExceptionMeansSocketTimeout(oException):
        fShowDebugOutput(oSelf, "The socket still allows reading.");
      elif fbExceptionMeansSocketShutdown(oException):
        fShowDebugOutput(oSelf, "The socket has been shut down for reading.");
        oSelf.__fHandleShutdownForReading(sWhile);
      elif fbExceptionMeansSocketDisconnected(oException):
        fShowDebugOutput(oSelf, "The socket has been disconnected.");
        oSelf.__fHandleDisconnect();
      else:
        raise;
    else:
      fShowDebugOutput(oSelf, "The socket should still allows reading.");
  
  def __fHandleShutdownForReading(oSelf, sWhile):
    oSelf.__bShouldAllowReading = False;
    if oSelf.__bShouldAllowWriting: oSelf.__fCheckIfSocketAllowsWriting(sWhile);
    if not oSelf.bConnected:
      fShowDebugOutput(oSelf, "Connection disconnected while %s." % sWhile);
    elif not oSelf.__bShouldAllowWriting:
      fShowDebugOutput(oSelf, "Connection shutdown while %s." % sWhile);
    else:
      fShowDebugOutput(oSelf, "Connection shutdown for reading while %s." % sWhile);
  
  def __fCheckIfSocketAllowsWriting(oSelf, sWhile):
    assert oSelf.__bShouldAllowWriting, \
        "Check if __bShouldAllowWriting is True before calling!";
    iFileNo = oSelf.__oPythonSocket.fileno();
    if iFileNo == -1:
      oSelf.__fHandleDisconnect();
      return False;
    # Check if it is not shutdown for writing or disconnected at this time.
    bIsWritable = len(select.select([], [iFileNo], [], 0)[1]) == 1;
    if not bIsWritable:
      oSelf.__fHandleShutdownForWriting(sWhile);
    try:
      # This can also throw an exception if the socket has been closed, so it's
      # inside the try...except loop:
      oSelf.__oPythonSocket.settimeout(0);
    except Exception as oException:
      fShowDebugOutput(oSelf, "Exception during `settimeout()`: %s(%s)" % (oException.__class__.__name__, oException));
      if fbExceptionMeansSocketDisconnected(oException):
        fShowDebugOutput(oSelf, "The socket has been disconnected.");
        oSelf.__fHandleDisconnect();
      else:
        raise;
    else:
      fShowDebugOutput(oSelf, "The socket should still allows writing.");
  
  def __fHandleShutdownForWriting(oSelf, sWhile):
    oSelf.__bShouldAllowWriting = False;
    if oSelf.__bShouldAllowReading: oSelf.__fCheckIfSocketAllowsReading(sWhile);
    if not oSelf.bConnected:
      fShowDebugOutput(oSelf, "Connection disconnected while %s." % sWhile);
    if not oSelf.__bShouldAllowReading:
      fShowDebugOutput(oSelf, "Connection shutdown while %s." % sWhile);
    else:
      fShowDebugOutput(oSelf, "Connection shutdown for writing while %s." % sWhile);
  
  @property
  def bConnected(oSelf):
    if oSelf.__oPythonSocket.fileno() == -1:
      oSelf.__fHandleDisconnect();
    return oSelf.__oTerminatedLock.bLocked;
  
  @property
  def bTerminated(oSelf):
    return not oSelf.bConnected;
  
  def fThrowExceptionIfShutdownOrDisconnected(oSelf):
    oSelf.__fThrowDisconnectedOrShutdownExceptionIfApplicable(
      sWhile = "checking if connection is not shut down or disconnected",
      bShouldAllowReading = True,
      bShouldAllowWriting = True
    );
  
  def __fThrowDisconnectedOrShutdownExceptionIfApplicable(oSelf, sWhile, bShouldAllowReading = False, bShouldAllowWriting = False, bMustThrowException = False):
    if oSelf.__oPythonSocket.fileno() == -1:
      oSelf.__fHandleDisconnect();
    else:
      if oSelf.__bShouldAllowReading: oSelf.__fCheckIfSocketAllowsReading(sWhile);
      if oSelf.__bShouldAllowWriting: oSelf.__fCheckIfSocketAllowsWriting(sWhile);
    if not oSelf.bConnected:
      raise cTCPIPConnectionDisconnectedException(
        "Connection %s was disconnected while %s." % (
          oSelf.fsGetEndPointsAndDirection(),
          sWhile,
        ),
        oConnection = oSelf,
      );
    if bShouldAllowReading and not oSelf.__bShouldAllowReading:
      raise cTCPIPConnectionShutdownException(
        "Connection %s was shutdown for reading while %s." % (
          oSelf.fsGetEndPointsAndDirection(),
          sWhile,
        ),
        oConnection = oSelf,
      );
    if bShouldAllowWriting and not oSelf.__bShouldAllowWriting:
      raise cTCPIPConnectionShutdownException(
        "Connection %s was shutdown for writing while %s." % (
          oSelf.fsGetEndPointsAndDirection(),
          sWhile,
        ),
        oConnection = oSelf,
      );
    assert not bMustThrowException, \
        "The connection was expected to be shut down or disconnected but neither was true.";
  
  def __fbSelectForBytesAvailable(oSelf, n0TimeoutInSeconds, sWhile):
    oSelf.__fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, bShouldAllowReading = True);
    iFileNo = oSelf.__oPythonSocket.fileno();
    if iFileNo == -1:
      oSelf.__fHandleDisconnect();
      bReadable = False;
    else:
      fShowDebugOutput(oSelf, "Checking if there is a signal on the socket...");
      (aiReadableFileNos, xIgnore, aiErrorFileNos) = select.select([iFileNo], [], [iFileNo], n0TimeoutInSeconds);
      bReadable = len(aiErrorFileNos) == 0;
    if not bReadable:
      oSelf.__fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, bShouldAllowReading = True, bMustThrowException = True);
    return len(aiReadableFileNos) == 1;
  
  @ShowDebugOutput
  def fbBytesAreAvailableForReading(oSelf, sWhile = "checking if bytes are available for reading"):
    # Can throw a shutdown or disconnected exception.
    # Returns true if there are any bytes that can currently to be read.
    if oSelf.__fbSelectForBytesAvailable(0, sWhile):
      fShowDebugOutput(oSelf, "Data should be available for reading now.");
      return True;
    return False;
  
  @ShowDebugOutput
  def fWaitUntilBytesAreAvailableForReading(oSelf, n0TimeoutInSeconds = None, sWhile = "waiting for bytes to become available for reading"):
    fAssertType("n0TimeoutInSeconds", n0TimeoutInSeconds, int, float, None);
    # Can throw a timeout, shutdown or disconnected exception.
    # Returns once there are any bytes that can currently to be read or the
    # socket was disconnected; the later may not result in an exception being
    # raised! It is currently not possible to determine if the connecton was
    # closed without attempting to read at least one byte from the socket.
    # After calling this function, the caller should try to read bytes to
    # determine if there really are bytes available or if the connection was
    # closed.
    # Reading from the socket did not cause an exception, so the socket isn't
    # shutdown or closed yet.
    if oSelf.__fbSelectForBytesAvailable(n0TimeoutInSeconds, sWhile):
      fShowDebugOutput(oSelf, "Data should be available for reading now.");
      return True;
    raise cTCPIPDataTimeoutException(
      "Timeout on connection %s while %s after %s seconds." % (
        oSelf.fsGetEndPointsAndDirection(),
        sWhile,
        n0TimeoutInSeconds,
      ),
      oConnection = oSelf,
    );
  
  @ShowDebugOutput
  def fsbReadAvailableBytes(oSelf, u0MaxNumberOfBytes = None, n0TimeoutInSeconds = None, sWhile = "reading available bytes"):
    # Can throw a shutdown or disconnected exception *if* this happens before any bytes can be read.
    # Returns any bytes that can currently be read, this could be "".
    fAssertType("u0MaxNumberOfBytes", u0MaxNumberOfBytes, int, None);
    fAssertType("n0TimeoutInSeconds", n0TimeoutInSeconds, int, float, None);
    oSelf.__fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, bShouldAllowReading = True);
    sbAvailableBytes = b"";
    nStartTime = time.time();
    n0EndTime = (nStartTime + n0TimeoutInSeconds) if n0TimeoutInSeconds is not None else None;
    while n0EndTime is None or time.time() < n0EndTime:
      if not oSelf.__fbSelectForBytesAvailable(0, sWhile):
        fShowDebugOutput(oSelf, "No more data available for reading now.");
        break;
      # Readable socket and no errors while reading 0 bytes means bytes are
      # available for reading.
      fShowDebugOutput(oSelf, "Data should be available for reading now.");
      uReadMaxNumberOfBytes = ( # Try to read the maximum number of bytes or a "chunk" if there is no max.
        u0MaxNumberOfBytes - len(sbAvailableBytes) if u0MaxNumberOfBytes is not None \
        else oSelf.uReadChunkSize
      );
      oSelf.__oPythonSocket.settimeout(0);
      try:
        sbBytesRead = oSelf.__oPythonSocket.recv(uReadMaxNumberOfBytes);
      except Exception as oException:
        fShowDebugOutput(oSelf, "Exception during `recv()`: %s(%s)" % (oException.__class__.__name__, oException));
        if fbExceptionMeansSocketHasNoDataAvailable(oException):
          pass;
        elif fbExceptionMeansSocketShutdown(oException):
          oSelf.__fHandleShutdownForReading(sWhile);
        elif fbExceptionMeansSocketDisconnected(oException):
          fShowDebugOutput(oSelf, "Connection disconnected while %s." % sWhile);
          oSelf.__fHandleDisconnect();
        else:
          raise;
        break;
      fShowDebugOutput(oSelf, "%d bytes read." % len(sbBytesRead));
      uShowDataBytesPerLine = 32;
      for uOffset in range(0, len(sbBytesRead), uShowDataBytesPerLine):
        sbData = sbBytesRead[uOffset:uOffset + uShowDataBytesPerLine];
        fShowDebugOutput(
          " ".join(["%02X" % uByte for uByte in sbData]).ljust(3 * uShowDataBytesPerLine) +
          "| " +
          "".join([chr(uByte) if uByte in range(0x20, 0x7F) else "." for uByte in sbData])
        );
      if len(sbBytesRead) == 0:
        # select.select reported a signal on the socket. If it did not signal
        # there was data available it means the connection was shutdown or
        # disconnected. We do not know which, so we assume a shutdown.
        fShowDebugOutput(oSelf, "No bytes read indicates the socket was shutdown and/or disconnected.");
        oSelf.__fHandleShutdownForReading(sWhile);
        break;
      oSelf.fFireCallbacks("bytes read", sbBytesRead);
      sbAvailableBytes += sbBytesRead;
    return sbAvailableBytes;
  
  @ShowDebugOutput
  def fsbReadBytesUntilDisconnected(oSelf, u0MaxNumberOfBytes = None, n0TimeoutInSeconds = None, sWhile = "reading bytes until disconnected"):
    fAssertType("u0MaxNumberOfBytes", u0MaxNumberOfBytes, int, None);
    fAssertType("n0TimeoutInSeconds", n0TimeoutInSeconds, int, float, None);
    nStartTime = time.time();
    n0EndTime = (nStartTime + n0TimeoutInSeconds) if n0TimeoutInSeconds is not None else None;
    sbBytesRead = b"";
    u0MaxNumberOfBytesRemaining = u0MaxNumberOfBytes;
    try:
      while u0MaxNumberOfBytesRemaining is None or u0MaxNumberOfBytesRemaining > 0:
        n0TimeoutInSeconds = (n0EndTime - time.time()) if n0EndTime is not None else None;
        if n0TimeoutInSeconds is not None and n0TimeoutInSeconds < 0:
          raise cTCPIPDataTimeoutException(
            "Timeout on connection %s while %s after %s seconds." % (
              oSelf.fsGetEndPointsAndDirection(),
              sWhile,
              n0TimeoutInSeconds,
            ),
            oConnection = oSelf,
          );
        oSelf.fWaitUntilBytesAreAvailableForReading(n0TimeoutInSeconds, sWhile);
        sbAvailableBytes = oSelf.fsbReadAvailableBytes(u0MaxNumberOfBytes = u0MaxNumberOfBytesRemaining, sWhile = sWhile);
        if len(sbAvailableBytes) == 0:
          # select.select reported a signal on the socket. If it did not signal
          # there was data available it means the connection was shutdown or
          # disconnected. We do not know which, so we assume a shutdown.
          fShowDebugOutput(oSelf, "No bytes read indicates the socket was shutdown and/or disconnected.");
          oSelf.__fHandleShutdownForReading(sWhile);
          break;
        sbBytesRead += sbAvailableBytes;
    except (cTCPIPConnectionShutdownException, cTCPIPConnectionDisconnectedException):
      pass;
    return sbBytesRead;
  
  @ShowDebugOutput
  def fWriteBytes(oSelf, sbBytes, n0TimeoutInSeconds = None, sWhile = "writing bytes"):
    fAssertType("sbBytes", sbBytes, bytes);
    fAssertType("n0TimeoutInSeconds", n0TimeoutInSeconds, int, float, None);
    # Can throw a timeout, shutdown or disconnected exception.
    # Returns once all bytes have been written.
    uNumberOfBytesToWrite = len(sbBytes);
    oSelf.__fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, bShouldAllowWriting = True);
    nStartTime = time.time();
    n0EndTime = (nStartTime + n0TimeoutInSeconds) if n0TimeoutInSeconds is not None else None;
    uTotalNumberOfBytesWritten = 0;
    while uTotalNumberOfBytesWritten < uNumberOfBytesToWrite:
      if n0EndTime is not None and time.time() >= n0EndTime:
        raise cTCPIPDataTimeoutException(
          "Timeout on connection %s while %s after %s seconds." % (
            oSelf.fsGetEndPointsAndDirection(),
            sWhile,
            n0TimeoutInSeconds,
          ),
          oConnection = oSelf,
        );
      oSelf.__oPythonSocket.settimeout(0);
      try:
        uNumberOfBytesWrittenInSendCall = oSelf.__oPythonSocket.send(sbBytes);
      except Exception as oException:
        fShowDebugOutput(oSelf, "Exception during `send()`: %s(%s)" % (oException.__class__.__name__, oException));
        if fbExceptionMeansSocketShutdown(oException):
          fShowDebugOutput(oSelf, "Connection shutdown while %s." % sWhile);
          oSelf.__fHandleShutdownForWriting(sWhile);
        elif fbExceptionMeansSocketDisconnected(oException):
          fShowDebugOutput(oSelf, "Connection disconnected while %s." % sWhile);
          oSelf.__fHandleDisconnect();
        else:
          raise;
        oSelf.__fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, bShouldAllowWriting = True, bMustThrowException = True);
      fShowDebugOutput(oSelf, "%d bytes written." % uNumberOfBytesWrittenInSendCall);
      oSelf.fFireCallbacks("bytes written", sbBytes[:uNumberOfBytesWrittenInSendCall]);
      sbBytes = sbBytes[uNumberOfBytesWrittenInSendCall:];
      uTotalNumberOfBytesWritten += uNumberOfBytesWrittenInSendCall;
  
  @ShowDebugOutput
  def fShutdownForReading(oSelf):
    oSelf.__fShutdown(bForReading = True);
  
  @ShowDebugOutput
  def fShutdownForWriting(oSelf):
    oSelf.__fShutdown(bForWriting = True);
  
  @ShowDebugOutput
  def fShutdown(oSelf):
    oSelf.__fShutdown(bForReading = True, bForWriting = True);
  
  def __fShutdown(oSelf, bForReading = False, bForWriting = False):
    if oSelf.__oPythonSocket.fileno() == -1:
      oSelf.__fHandleDisconnect();
      return;
    # Shutting down a secure connection does not appear to have the expected
    # results; we'll do it anyway but be aware that it does not appear that
    # the remote is notified of the shutdown.
    # Can throw a disconnected exception.
    bForReading = bForReading and oSelf.__bShouldAllowReading;
    bForWriting = bForWriting and oSelf.__bShouldAllowWriting;
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
      oSelf.__bShouldAllowReading = False;
    if bForWriting:
      oSelf.__bShouldAllowWriting = False;
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
      oSelf.__fThrowDisconnectedOrShutdownExceptionIfApplicable("shutting down for %s" % sShutdownFor, bMustThrowException = True);
    if bForReading:
      oSelf.fFireCallbacks("shutdown for reading");
    if bForWriting:
      oSelf.fFireCallbacks("shutdown for writing");
    oSelf.fFireCallbacks("shutdown");
  
  @ShowDebugOutput
  def fDisconnect(oSelf, bShutdownFirst = True):
    if not oSelf.bConnected: return;
    if bShutdownFirst:
      fShowDebugOutput(oSelf, "Shutting socket down...");
      try:
        oSelf.__fShutdown(
          bForReading = oSelf.__bShouldAllowReading,
          bForWriting = oSelf.__bShouldAllowWriting
        );
      except cTCPIPConnectionDisconnectedException:
        # A debug message from __fShutdown will have already explained what happened.
        pass;
    if oSelf.bConnected:
      oSelf.__fDisconnect();
  
  @ShowDebugOutput
  def __fDisconnect(oSelf):
    if not oSelf.bConnected:
      fShowDebugOutput(oSelf, "Already disconnected.");
      return;
    if oSelf.__oSecurePythonSocket:
      fShowDebugOutput(oSelf, "Disconnecting secure socket...");
      try:
        oSelf.__oSecurePythonSocket.close();
      except Exception as oException:
        fShowDebugOutput(oSelf, "Exception during `close()` on secure socket: %s(%s)" % \
            (oException.__class__.__name__, oException));
        if not fbExceptionMeansSocketDisconnected(oException):
          raise;
      fShowDebugOutput(oSelf, "Disconnecting non-secure socket...");
    else:
      fShowDebugOutput(oSelf, "Disconnecting socket...");
    try:
      oSelf.__oNonSecurePythonSocket.close();
    except Exception as oException:
      fShowDebugOutput(oSelf, "Exception during `close()`%s: %s(%s)" % \
          (" on non-secure socket" if oSelf.__oSecurePythonSocket else "", oException.__class__.__name__, oException));
      if not fbExceptionMeansSocketDisconnected(oException):
        raise;
    oSelf.__fHandleDisconnect();
    fShowDebugOutput(oSelf, "Disconnected.");
  
  def __fHandleDisconnect(oSelf):
    oSelf.__oConnectedPropertyAccessLock.fAcquire();
    try:
      if not oSelf.__oTerminatedLock.bLocked:
        return;
      try:
        oSelf.__oNonSecurePythonSocket.close();
      except Exception as oException:
        fShowDebugOutput(oSelf, "Exception during `close()`%s: %s(%s)" % \
            (" on non-secure socket" if oSelf.__oSecurePythonSocket else "", oException.__class__.__name__, oException));
        if not fbExceptionMeansSocketDisconnected(oException):
          raise;
      if oSelf.__oSecurePythonSocket: 
        try:
          oSelf.__oSecurePythonSocket.close();
        except Exception as oException:
          fShowDebugOutput(oSelf, "Exception during `close()` on secure socket: %s(%s)" % (oException.__class__.__name__, oException));
          if not fbExceptionMeansSocketDisconnected(oException):
            raise;
      oSelf.__bShouldAllowReading = False;
      oSelf.__bShouldAllowWriting = False;
      oSelf.__oTerminatedLock.fRelease();
    finally:
      oSelf.__oConnectedPropertyAccessLock.fRelease();
    # Fire terminated event now if we are not holding it.
    if oSelf.__uTerminatedCallbackPostponeCounter == 0:
      fShowDebugOutput(oSelf, "Firing terminated callbacks...");
      oSelf.fFireCallbacks("terminated");
    else:
      fShowDebugOutput(oSelf, "Postponed terminated callbacks.");
      oSelf.__bTerminatedCallbackPostponed = True;
  
  def fsGetEndPointsAndDirection(oSelf):
    return "%s %s %s" % (
      str(oSelf.sbLocalAddress, "ascii", "strict"),
      oSelf.__bCreatedLocally and "=>" or "<=",
      str(oSelf.sbRemoteAddress, "ascii", "strict"),
    );
  def fasGetDetails(oSelf):
    # This is done without a property lock, so race-conditions exist and it
    # approximates the real values.
    bConnected = oSelf.bConnected;
    bShouldAllowReading = bConnected and oSelf.__bShouldAllowReading;
    bShouldAllowWriting = bConnected and oSelf.__bShouldAllowWriting;
    bStopping = bConnected and oSelf.__bStopping;
    return [s for s in [
      oSelf.fsGetEndPointsAndDirection(),
      (
        "disconnected" if not bConnected else 
        "connected" if bShouldAllowWriting and bShouldAllowReading else
        "read-only" if bShouldAllowReading else
        "write-only" if bShouldAllowWriting else
        "shutdown"
      ),
      "stopping" if bStopping else None,
    ] if s];
  
  def __repr__(oSelf):
    sModuleName = ".".join(oSelf.__class__.__module__.split(".")[:-1]);
    return "<%s.%s#%X|%s>" % (sModuleName, oSelf.__class__.__name__, id(oSelf), "|".join(oSelf.fasGetDetails()));
  
  def __str__(oSelf):
    return "%s#%X{%s}" % (oSelf.__class__.__name__, id(oSelf), ", ".join(oSelf.fasGetDetails()));

for cException in acExceptions:
  setattr(cTCPIPConnection, cException.__name__, cException);
