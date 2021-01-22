import select, socket, time;

try: # mDebugOutput use is Optional
  from mDebugOutput import *;
except: # Do nothing if not available.
  ShowDebugOutput = lambda fxFunction: fxFunction;
  fShowDebugOutput = lambda sMessage: None;
  fEnableDebugOutputForModule = lambda mModule: None;
  fEnableDebugOutputForClass = lambda cClass: None;
  fEnableAllDebugOutput = lambda: None;
  cCallStack = fTerminateWithException = fTerminateWithConsoleOutput = None;

from mMultiThreading import cLock, cWithCallbacks;

from .fbExceptionMeansSocketConnectionRefused import fbExceptionMeansSocketConnectionRefused;
from .fbExceptionMeansSocketDisconnected import fbExceptionMeansSocketDisconnected;
from .fbExceptionMeansSocketHasNoDataAvailable import fbExceptionMeansSocketHasNoDataAvailable;
from .fbExceptionMeansSocketHostnameCannotBeResolved import fbExceptionMeansSocketHostnameCannotBeResolved;
from .fbExceptionMeansSocketInvalidAddress import fbExceptionMeansSocketInvalidAddress;
from .fbExceptionMeansSocketShutdown import fbExceptionMeansSocketShutdown;
from .fbExceptionMeansSocketTimeout import fbExceptionMeansSocketTimeout;
from .mExceptions import *;
from .mNotProvided import *;

# To turn access to data store in multiple variables into a single transaction, we will create locks.
# These locks should only ever be locked for a short time; if it is locked for too long, it is considered a "deadlock"
# bug, where "too long" is defined by the following value:
gnDeadlockTimeoutInSeconds = 1; # We're not doing anything time consuming, so this should suffice.

class cTCPIPConnection(cWithCallbacks):
  n0DefaultConnectTimeoutInSeconds = 5; # How long to try to connect before giving up?
  uDefaultReadChunkSize = 0x1000; # How many bytes to try to read if we do not know how many are comming.
  
  @classmethod
  @ShowDebugOutput
  def foConnectTo(cClass, \
    sHostname, uPort, n0zConnectTimeoutInSeconds = zNotProvided,
    o0SSLContext = None, n0zSecureTimeoutInSeconds = zNotProvided
  ):
    n0ConnectTimeoutInSeconds = fxGetFirstProvidedValue(n0zConnectTimeoutInSeconds, cClass.n0DefaultConnectTimeoutInSeconds);
    # n0zSecureTimeoutInSeconds is pass through
    oPythonSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
    # Send keep alive frames
    oPythonSocket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1);
    # Send keep alive frames after 1 second
    if hasattr(socket, "TCP_KEEPIDLE"):
      oPythonSocket.setsockopt(socket.SOL_SOCKET, socket.TCP_KEEPIDLE, 1);
    # Send keep alive frames every 1 second
    if hasattr(socket, "TCP_KEEPINTVL"):
      oPythonSocket.setsockopt(socket.SOL_SOCKET, socket.TCP_KEEPINTVL, 1);
    # Assume disconnected after missing one alive frame.
    if hasattr(socket, "TCP_KEEPCNT"):
      oPythonSocket.setsockopt(socket.SOL_SOCKET, socket.TCP_KEEPCNT, 1);
    dxDetails = {"sHostname": sHostname, "uPort": uPort, "n0ConnectTimeoutInSeconds": n0ConnectTimeoutInSeconds};
    oPythonSocket.settimeout(n0ConnectTimeoutInSeconds);
    nStartTime = time.clock();
    try:
      oPythonSocket.connect((sHostname, uPort));
    except Exception as oException:
      fShowDebugOutput("Exception during `connect()`: %s(%s)" % (oException.__class__.__name__, oException));
      dxDetails["nDuration"] = time.clock() - nStartTime;
      if fbExceptionMeansSocketHostnameCannotBeResolved(oException):
        raise cDNSUnknownHostnameException("Cannot resolve hostname", dxDetails);
      elif fbExceptionMeansSocketInvalidAddress(oException):
        raise cTCPIPInvalidAddressException("Invalid hostname", dxDetails);
      elif fbExceptionMeansSocketTimeout(oException):
        # Note that a Python server socket will refuse connections after a few seconds if the queue is full (the size
        # of the queue is determined by the `backlog` argument in the `socket.listen(backlog)` call). You might expect
        # a `cTCPIPConnectTimeoutException` when a client attempts to connect to a server that is unable to accept the
        # connection immediately, but you could get a `cTCPIPConnectionRefusedException` exception instead because of
        # this. This may be true for other server sockets as well. For Python at least, there seems to be a timeout
        # on the server side of about 2 seconds but I have been unable to determine where this value comes from, if you
        # can control this, or disable it entirely.
        # If `n0ConnectTimeoutInSeconds` is smaller than the server side timeout that triggers a refused connection,
        # you will see a `cTCPIPConnectTimeoutException` as expected.
        raise cTCPIPConnectTimeoutException("Cannot connect to server", dxDetails);
      elif fbExceptionMeansSocketConnectionRefused(oException):
        raise cTCPIPConnectionRefusedException("Connection refused by server", dxDetails);
      else:
        raise;
    oSelf = cClass(oPythonSocket, bCreatedLocally = True);
    if o0SSLContext:
      oSelf.fSecure(
        oSSLContext = o0SSLContext,
        n0zTimeoutInSeconds = n0zSecureTimeoutInSeconds,
     );
    return oSelf;
  
  @classmethod
  @ShowDebugOutput
  def faoWaitUntilBytesAreAvailableForReading(cClass, aoConnections, n0TimeoutInSeconds = None):
    # select.select does not work well on secure sockets, so we use the non-secure sockets
    # as proxies; there may be SSL traffic without data being send from the remote end, so
    # we may flag a connection as having data to be read when it has none.
    n0EndTime = time.clock() + n0TimeoutInSeconds if n0TimeoutInSeconds else None;
    while 1:
      aoConnectionsWithBytesAvailableForReading = [];
      aoPythonSockets = [];
      for oConnection in aoConnections:
        if oConnection.bConnected:
          if oConnection.fbBytesAreAvailableForReading():
            aoConnectionsWithBytesAvailableForReading.append(oConnection);
          else:
            aoPythonSockets.append(oConnection.__oPythonSocket);
      if aoConnectionsWithBytesAvailableForReading:
        # There currently are connections with bytes available for reading.
        return aoConnectionsWithBytesAvailableForReading;
      if not aoPythonSockets:
        return []; # All connections have been closed.
      # Wait until the python sockets become readable, shutdown or closed:
      n0TimeoutInSeconds = n0EndTime - time.clock() if n0EndTime else None;
      if not select.select(aoPythonSockets, [], [], n0TimeoutInSeconds)[0]:
        return []; # Waiting timed out.
  
  @ShowDebugOutput
  def __init__(oSelf, oPythonSocket, o0SecurePythonSocket = None, o0SSLContext = None, bCreatedLocally = False):
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
    oSelf.sLocalAddress = "%s:%d" % oSelf.txLocalAddress;
    oSelf.txRemoteAddress = oSelf.__oPythonSocket.getpeername();
    oSelf.sRemoteAddress = "%s:%d" % oSelf.txRemoteAddress;
    oSelf.fAddEvents(
      "bytes read",
      "bytes written",
      "shutdown for reading", "shutdown for writing", "shutdown",
      "terminated"
    );
  
  @property
  def __oNonSecurePythonSocket(oSelf):
    return oSelf.__aoPythonSockets[0];
  @property
  def __oSecurePythonSocket(oSelf):
    return oSelf.__aoPythonSockets[-1] if len(oSelf.__aoPythonSockets) > 1 else None;
  @property
  def __oPythonSocket(oSelf):
    return oSelf.__aoPythonSockets[-1];
  @property
  def __o0SSLContext(oSelf):
    return oSelf.__aoSSLContexts[-1] if len(oSelf.__aoSSLContexts) > 0 else None;

  @ShowDebugOutput
  def fSecure(oSelf, oSSLContext, n0zTimeoutInSeconds = zNotProvided, sWhile = "securing connection"):
    oSelf.fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, {}, bShouldAllowReading = True, bShouldAllowWriting = True);
    try:
      oSecurePythonSocket = oSSLContext.foWrapSocket(
        oPythonSocket = oSelf.__oPythonSocket, # Tunnel through existing SSL layer if needed.
        n0zTimeoutInSeconds = n0zTimeoutInSeconds,
      );
    except Exception as oException:
      fShowDebugOutput("Exception while wrapping socket: %s(%s)" % (oException.__class__.__name__, oException));
      if fbExceptionMeansSocketShutdown(oException):
        oSelf.__fCheckIfSocketAllowsReading(sWhile);
        oSelf.__fCheckIfSocketAllowsWriting(sWhile);
      elif fbExceptionMeansSocketDisconnected(oException):
        fShowDebugOutput("Connection disconnected while %s." % sWhile);
        oSelf.__fHandleDisconnect();
      else:
        raise;
      oSelf.fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, {}, bShouldAllowReading = True, bMustThrowException = True);
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
    oSelf.__bStopping = True;
    oSelf.fDisconnect();
  
  @ShowDebugOutput
  def fTerminate(oSelf):
    oSelf.__bStopping = True;
    oSelf.fDisconnect();
  
  @ShowDebugOutput
  def fbWait(oSelf, nTimeoutInSeconds):
    return oSelf.__oTerminatedLock.fbWait(nTimeoutInSeconds);
  
  @property
  def bShouldAllowReading(oSelf):
    return oSelf.__bShouldAllowReading;
  
  @property
  def bShouldAllowWriting(oSelf):
    return oSelf.__bShouldAllowWriting;
  
  @ShowDebugOutput
  def __fCheckIfSocketAllowsReading(oSelf, sWhile):
    assert oSelf.__bShouldAllowReading, \
        "Check if __bShouldAllowReading is True before calling!";
    # Check if it is not shutdown or disconnected at this time.
    oSelf.__oNonSecurePythonSocket.settimeout(0);
    try:
      # .rec() on the secure socket may succeed even if the connection is
      # closed. .recv() on the non-secure socket will throw an exception and
      # will not interfere with ssl; hence we call that:
      oSelf.__oNonSecurePythonSocket.recv(0);
    except Exception as oException:
      fShowDebugOutput("Exception during `recv()`: %s(%s)" % (oException.__class__.__name__, oException));
      if fbExceptionMeansSocketTimeout(oException):
        fShowDebugOutput("The socket still allows reading.");
      elif fbExceptionMeansSocketShutdown(oException):
        fShowDebugOutput("The socket has been shut down for reading.");
        oSelf.__fHandleShutdownForReading(sWhile);
      elif fbExceptionMeansSocketDisconnected(oException):
        fShowDebugOutput("The socket has been disconnected.");
        oSelf.__fHandleDisconnect();
      else:
        raise;
    else:
      fShowDebugOutput("The socket still allows reading.");
  
  def __fHandleShutdownForReading(oSelf, sWhile):
    oSelf.__bShouldAllowReading = False;
    if oSelf.__bShouldAllowWriting: oSelf.__fCheckIfSocketAllowsWriting(sWhile);
    if not oSelf.bConnected:
      fShowDebugOutput("Connection disconnected while %s." % sWhile);
    elif not oSelf.__bShouldAllowWriting:
      fShowDebugOutput("Connection shutdown while %s." % sWhile);
    else:
      fShowDebugOutput("Connection shutdown for reading while %s." % sWhile);
  
  @ShowDebugOutput
  def __fCheckIfSocketAllowsWriting(oSelf, sWhile):
    assert oSelf.__bShouldAllowWriting, \
        "Check if __bShouldAllowWriting is True before calling!";
    # Check if it is not shutdown for writing or disconnected at this time.
    aoUnused, aoWritableSockets, aoUnused2 = select.select(
      [], [oSelf.__oNonSecurePythonSocket], [], 0
    );
    if len(aoWritableSockets) == 0:
      oSelf.__fHandleShutdownForWriting(sWhile);
    oSelf.__oNonSecurePythonSocket.settimeout(0);
    try:
      oSelf.__oNonSecurePythonSocket.send("");
    except Exception as oException:
      fShowDebugOutput("Exception during `send()`: %s(%s)" % (oException.__class__.__name__, oException));
      if fbExceptionMeansSocketShutdown(oException):
        fShowDebugOutput("The socket has been shut down for writing.");
        oSelf.__fHandleShutdownForWriting(sWhile);
      elif fbExceptionMeansSocketDisconnected(oException):
        fShowDebugOutput("The socket has been disconnected.");
        oSelf.__fHandleDisconnect();
      else:
        raise;
    else:
      fShowDebugOutput("The socket still allows writing.");
  
  def __fHandleShutdownForWriting(oSelf, sWhile):
    oSelf.__bShouldAllowWriting = False;
    if oSelf.__bShouldAllowReading: oSelf.__fCheckIfSocketAllowsReading(sWhile);
    if not oSelf.bConnected:
      fShowDebugOutput("Connection disconnected while %s." % sWhile);
    if not oSelf.__bShouldAllowReading:
      fShowDebugOutput("Connection shutdown while %s." % sWhile);
    else:
      fShowDebugOutput("Connection shutdown for writing while %s." % sWhile);
  
  @property
  def bConnected(oSelf):
    return oSelf.__oTerminatedLock.bLocked;
  
  @property
  def bTerminated(oSelf):
    return not oSelf.bConnected;
  
  def fThrowDisconnectedOrShutdownExceptionIfApplicable(oSelf, sWhile, dxDetails, bShouldAllowReading = False, bShouldAllowWriting = False, bMustThrowException = False):
    if oSelf.__bShouldAllowReading: oSelf.__fCheckIfSocketAllowsReading(sWhile);
    if oSelf.__bShouldAllowWriting: oSelf.__fCheckIfSocketAllowsWriting(sWhile);
    if not oSelf.bConnected:
      raise cTCPIPConnectionDisconnectedException("Disconnected while %s" % sWhile, dxDetails);
    if bShouldAllowReading and not oSelf.__bShouldAllowReading:
      raise cTCPIPConnectionShutdownException("Shutdown for reading while %s" % sWhile, dxDetails);
    if bShouldAllowWriting and not oSelf.__bShouldAllowWriting:
      raise cTCPIPConnectionShutdownException("Shutdown for writing while %s" % sWhile, dxDetails);
    assert not bMustThrowException, \
        "The connection was expected to be shut down or disconnected but neither was true.";
  
  @ShowDebugOutput
  def fbBytesAreAvailableForReading(oSelf, sWhile = "checking if bytes are available for reading"):
    # Can throw a shutdown or disconnected exception.
    # Returns true if there are any bytes that can currently to be read.
    oSelf.fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, {}, bShouldAllowReading = True);
    fShowDebugOutput("Checking if there is a signal on the socket...");
    aoReadableSockets, aoUnused, aoErrorSockets = select.select(
      [oSelf.__oPythonSocket], [], [oSelf.__oPythonSocket], 0
    );
    if len(aoErrorSockets) == 0 and len(aoReadableSockets) == 0:
      # No errors and no readable sockets means no bytes available for reading.
      return False;
    fShowDebugOutput("Checking if signal means data is available or socket is closed...");
    oSelf.fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, {}, bShouldAllowReading = True);
    fShowDebugOutput("Data should be available for reading now.");
    return True;
  
  @ShowDebugOutput
  def fWaitUntilBytesAreAvailableForReading(oSelf, n0TimeoutInSeconds = None, sWhile = "waiting for bytes to become available for reading"):
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
    oSelf.fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, {}, bShouldAllowReading = True);
    fShowDebugOutput("Waiting for a sigal on the socket...");
    aoReadableSockets, aoUnused, aoErrorSockets = select.select(
      [oSelf.__oNonSecurePythonSocket], [], [oSelf.__oNonSecurePythonSocket], n0TimeoutInSeconds
    );
    if len(aoErrorSockets) == 0 and len(aoReadableSockets) == 0:
      # No errors and no readable sockets means no bytes available for reading
      # before the timeout.
      raise cTCPIPDataTimeoutException("Timeout while %s" % sWhile, {"n0TimeoutInSeconds": n0TimeoutInSeconds});
    fShowDebugOutput("Checking if signal means data is available or socket is closed...");
    oSelf.fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, {}, bShouldAllowReading = True);
    fShowDebugOutput("Data should be available for reading now.");
  
  @ShowDebugOutput
  def fsReadAvailableBytes(oSelf, u0MaxNumberOfBytes = None, sWhile = "reading available bytes"):
    # Can throw a shutdown or disconnected exception *if* this happens before any bytes can be read.
    # Returns any bytes that can currently be read, this could be "".
    dxDetails = {"u0MaxNumberOfBytes": u0MaxNumberOfBytes};
    oSelf.fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, dxDetails, bShouldAllowReading = True);
    sAvailableBytes = "";
    nStartTime = time.clock();
    while 1:
      fShowDebugOutput("Checking if there is a signal on the socket...");
      aoReadableSockets, aoUnused, aoErrorSockets = select.select(
        [oSelf.__oPythonSocket], [], [oSelf.__oPythonSocket], 0
      );
      if len(aoReadableSockets) == 0 and len(aoErrorSockets) == 0:
        fShowDebugOutput("No more data available for reading now.");
        break;
      # Readable socket and no errors while reading 0 bytes means bytes are
      # available for reading.
      fShowDebugOutput("Data should be available for reading now.");
      uReadMaxNumberOfBytes = ( # Try to read the maximum number of bytes or a "chunk" if there is no max.
        u0MaxNumberOfBytes - len(sAvailableBytes) if u0MaxNumberOfBytes is not None \
        else oSelf.uReadChunkSize
      );
      oSelf.__oPythonSocket.settimeout(0);
      try:
        sBytesRead = oSelf.__oPythonSocket.recv(uReadMaxNumberOfBytes);
      except Exception as oException:
        dxDetails["nDuration"] = time.clock() - nStartTime;
        fShowDebugOutput("Exception during `recv()`: %s(%s)" % (oException.__class__.__name__, oException));
        if fbExceptionMeansSocketHasNoDataAvailable(oException):
          pass;
        elif fbExceptionMeansSocketShutdown(oException):
          oSelf.__fHandleShutdownForReading(sWhile);
        elif fbExceptionMeansSocketDisconnected(oException):
          fShowDebugOutput("Connection disconnected while %s." % sWhile);
          oSelf.__fHandleDisconnect();
        else:
          raise;
        break;
      fShowDebugOutput("%d bytes read." % len(sBytesRead));
      if len(sBytesRead) == 0:
        # select.select reported a signal on the socket. If it did not signal
        # there was data available it means the connection was shutdown or
        # disconnected. We do not know which, so we assume a shutdown.
        fShowDebugOutput("No bytes read indicates the socket was shutdown and/or disconnected.");
        oSelf.__fHandleShutdownForReading(sWhile);
        break;
      oSelf.fFireCallbacks("bytes read", {"sBytes": sBytesRead});
      sAvailableBytes += sBytesRead;
    return sAvailableBytes;
  
  @ShowDebugOutput
  def fsReadBytesUntilDisconnected(oSelf, u0MaxNumberOfBytes = None, n0TimeoutInSeconds = None, sWhile = "reading bytes until disconnected"):
    n0EndTime = time.clock() + n0TimeoutInSeconds if n0TimeoutInSeconds else None;
    sBytes = "";
    u0MaxNumberOfBytesRemaining = u0MaxNumberOfBytes;
    try:
      while u0MaxNumberOfBytesRemaining is None or u0MaxNumberOfBytesRemaining > 0:
        n0TimeoutInSeconds = n0EndTime - time.clock() if n0EndTime is not None else None;
        oSelf.fWaitUntilBytesAreAvailableForReading(n0TimeoutInSeconds, sWhile);
        sBytes += oSelf.fsReadAvailableBytes(u0MaxNumberOfBytes = u0MaxNumberOfBytesRemaining, sWhile = sWhile);
    except (cTCPIPConnectionShutdownException, cTCPIPConnectionDisconnectedException) as oException:
      pass;
    return sBytes;
  
  @ShowDebugOutput
  def fWriteBytes(oSelf, sBytes, n0TimeoutInSeconds = None, sWhile = "writing bytes"):
    # Can throw a timeout, shutdown or disconnected exception.
    # Returns once all bytes have been written.
    uNumberOfBytesToWrite = len(sBytes);
    dxDetails = {"sBytes": sBytes, "uNumberOfBytesToWrite": uNumberOfBytesToWrite, \
        "uNumberOfBytesWritten": 0, "n0TimeoutInSeconds": n0TimeoutInSeconds};
    oSelf.fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, dxDetails, bShouldAllowWriting = True);
    nStartTime = time.clock();
    n0EndTime = nStartTime + n0TimeoutInSeconds if n0TimeoutInSeconds is not None else None;
    uTotalNumberOfBytesWritten = 0;
    while uTotalNumberOfBytesWritten < uNumberOfBytesToWrite:
      if n0EndTime is not None and time.clock() >= n0EndTime:
        raise cTCPIPDataTimeoutException("Timeout while %s" % sWhile, dxDetails);
      oSelf.__oPythonSocket.settimeout(0);
      try:
        uNumberOfBytesWrittenInSendCall = oSelf.__oPythonSocket.send(sBytes);
      except Exception as oException:
        dxDetails["nDuration"] = time.clock() - nStartTime;
        fShowDebugOutput("Exception during `send()`: %s(%s)" % (oException.__class__.__name__, oException));
        if fbExceptionMeansSocketShutdown(oException):
          fShowDebugOutput("Connection shutdown while %s." % sWhile);
          oSelf.__fHandleShutdownForWriting(sWhile);
        elif fbExceptionMeansSocketDisconnected(oException):
          fShowDebugOutput("Connection disconnected while %s." % sWhile);
          oSelf.__fHandleDisconnect();
        else:
          raise;
        oSelf.fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, dxDetails, bShouldAllowWriting = True, bMustThrowException = True);
      fShowDebugOutput("%d bytes written." % uNumberOfBytesWrittenInSendCall);
      oSelf.fFireCallbacks("bytes written", {"sBytes": sBytes[:uNumberOfBytesWrittenInSendCall]});
      sBytes = sBytes[uNumberOfBytesWrittenInSendCall:];
      uTotalNumberOfBytesWritten += uNumberOfBytesWrittenInSendCall;
      dxDetails["uNumberOfBytesWritten"] = uTotalNumberOfBytesWritten;
  
  @ShowDebugOutput
  def fShutdownForReading(oSelf, sWhile = "shutting down for reading"):
    oSelf.__fShutdown(sWhile, bForReading = True);
  
  @ShowDebugOutput
  def fShutdownForWriting(oSelf, sWhile = "shutting down for writing"):
    oSelf.__fShutdown(sWhile, bForWriting = True);
  
  @ShowDebugOutput
  def fShutdown(oSelf, sWhile = "shutting down"):
    oSelf.__fShutdown(sWhile, bForReading = True, bForWriting = True);
  
  def __fShutdown(oSelf, sWhile, bForReading = False, bForWriting = False):
    # Shutting down a secure connection does not appear to have the expected
    # results; we'll do it anyway but be aware that it does not appear that
    # the remote is notified of the shutdown.
    # Can throw a disconnected exception.
    bForReading = bForReading and oSelf.__bShouldAllowReading;
    bForWriting = bForWriting and oSelf.__bShouldAllowWriting;
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
      fShowDebugOutput("Already shut down for %s..." %  sShutdownFor);
      return;
    fShowDebugOutput("Shutting down for %s..." %  sShutdownFor);
    if bForReading:
      oSelf.__bShouldAllowReading = False;
    if bForWriting:
      oSelf.__bShouldAllowWriting = False;
    oSelf.__oPythonSocket.settimeout(0);
    try:
      oSelf.__oPythonSocket.shutdown(xFlags);
    except Exception as oException:
      fShowDebugOutput("Exception during `shutdown()`: %s(%s)" % (oException.__class__.__name__, oException));
      if fbExceptionMeansSocketDisconnected(oException):
        fShowDebugOutput("Connection disconnected while %s." % sWhile);
        oSelf.__fHandleDisconnect();
      else:
        raise;
      oSelf.fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, {}, bMustThrowException = True);
    if bForReading:
      oSelf.fFireCallbacks("shutdown for reading");
    if bForWriting:
      oSelf.fFireCallbacks("shutdown for writing");
    oSelf.fFireCallbacks("shutdown");
  
  @ShowDebugOutput
  def fDisconnect(oSelf, bShutdownFirst = True):
    if oSelf.bConnected:
      if bShutdownFirst:
        fShowDebugOutput("Shutting socket down...");
        try:
          oSelf.fShutdown(); # For reading and writing
        except cTCPIPConnectionDisconnectedException as oException:
          pass; # A debug message will have already explained what happened.
      if oSelf.bConnected:
        if oSelf.__oSecurePythonSocket:
          fShowDebugOutput("Disconnecting secure socket...");
          try:
            oSelf.__oSecurePythonSocket.close();
          except Exception as oException:
            fShowDebugOutput("Exception during `close()` on secure socket: %s(%s)" % \
                (oException.__class__.__name__, oException));
            if not fbExceptionMeansSocketDisconnected(oException):
              raise;
          fShowDebugOutput("Disconnecting non-secure socket...");
        else:
          fShowDebugOutput("Disconnecting socket...");
        try:
          oSelf.__oNonSecurePythonSocket.close();
        except Exception as oException:
          fShowDebugOutput("Exception during `close()`%s: %s(%s)" % \
              (" on non-secure socket" if oSelf.__oSecurePythonSocket else "", oException.__class__.__name__, oException));
          if not fbExceptionMeansSocketDisconnected(oException):
            raise;
        oSelf.__fHandleDisconnect();
        fShowDebugOutput("Disconnected.");
  
  def __fHandleDisconnect(oSelf):
    oSelf.__oConnectedPropertyAccessLock.fAcquire();
    try:
      if not oSelf.bConnected:
        return;
      try:
        oSelf.__oNonSecurePythonSocket.close();
      except Exception as oException:
        fShowDebugOutput("Exception during `close()`%s: %s(%s)" % \
            (" on non-secure socket" if oSelf.__oSecurePythonSocket else "", oException.__class__.__name__, oException));
        if not fbExceptionMeansSocketDisconnected(oException):
          raise;
      if oSelf.__oSecurePythonSocket: 
        try:
          oSelf.__oSecurePythonSocket.close();
        except Exception as oException:
          fShowDebugOutput("Exception during `close()` on secure socket: %s(%s)" % (oException.__class__.__name__, oException));
          if not fbExceptionMeansSocketDisconnected(oException):
            raise;
      oSelf.__bShouldAllowReading = False;
      oSelf.__bShouldAllowWriting = False;
      oSelf.__oTerminatedLock.fRelease();
    finally:
      oSelf.__oConnectedPropertyAccessLock.fRelease();
    fShowDebugOutput("%s terminating." % oSelf);
    oSelf.fFireCallbacks("terminated");
  
  def fasGetDetails(oSelf):
    # This is done without a property lock, so race-conditions exist and it
    # approximates the real values.
    bConnected = oSelf.bConnected;
    bShouldAllowReading = bConnected and oSelf.__bShouldAllowReading;
    bShouldAllowWriting = bConnected and oSelf.__bShouldAllowWriting;
    bStopping = bConnected and oSelf.__bStopping;
    return [s for s in [
      "%s %s %s" % (oSelf.sLocalAddress or "??", oSelf.__bCreatedLocally and "=>" or "<=", oSelf.sRemoteAddress or "??"),
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
