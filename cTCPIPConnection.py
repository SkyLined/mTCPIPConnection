import select, socket, time;

from .cTCPIPException import cTCPIPException;
from .fbExceptionMeansSocketDisconnected import fbExceptionMeansSocketDisconnected;
from .fbExceptionMeansSocketShutdown import fbExceptionMeansSocketShutdown;
from .fbExceptionMeansSocketConnectionRefused import fbExceptionMeansSocketConnectionRefused;
from .fbExceptionMeansSocketHostnameCannotBeResolved import fbExceptionMeansSocketHostnameCannotBeResolved;
from .fbExceptionMeansSocketInvalidAddress import fbExceptionMeansSocketInvalidAddress;
from .fbExceptionMeansSocketTimeout import fbExceptionMeansSocketTimeout;
from .fbExceptionMeansSocketHasNoDataAvailable import fbExceptionMeansSocketHasNoDataAvailable;

from mDebugOutput import ShowDebugOutput, fShowDebugOutput;
from mMultiThreading import cLock, cWithCallbacks;

# To turn access to data store in multiple variables into a single transaction, we will create locks.
# These locks should only ever be locked for a short time; if it is locked for too long, it is considered a "deadlock"
# bug, where "too long" is defined by the following value:
gnDeadlockTimeoutInSeconds = 1; # We're not doing anything time consuming, so this should suffice.

class cTCPIPConnection(cWithCallbacks):
  nzDefaultConnectTimeoutInSeconds = 5; # How long to try to connect before giving up?
  uDefaultReadChunkSize = 0x1000; # How many bytes to try to read if we do not know how many are comming.
  
  class cTimeoutException(cTCPIPException):
    pass;
  class cConnectionRefusedException(cTCPIPException):
    pass;
  class cUnknownHostnameException(cTCPIPException):
    pass;
  class cInvalidAddressException(cTCPIPException):
    pass;
  class cShutdownException(cTCPIPException):
    pass;
  class cDisconnectedException(cTCPIPException):
    pass;
  
  @classmethod
  @ShowDebugOutput
  def foConnectTo(cClass, \
    sHostname, uPort, nzConnectTimeoutInSeconds = None, \
    ozSSLContext = None, bCheckHostname = False, nzSecureTimeoutInSeconds = None
  ):
    nzConnectTimeoutInSeconds = cClass.nzDefaultConnectTimeoutInSeconds if nzConnectTimeoutInSeconds is None else nzConnectTimeoutInSeconds;
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
    dxDetails = {"sHostname": sHostname, "uPort": uPort, "nzConnectTimeoutInSeconds": nzConnectTimeoutInSeconds};
    try:
      oPythonSocket.settimeout(nzConnectTimeoutInSeconds);
      oPythonSocket.connect((sHostname, uPort));
    except Exception as oException:
      if fbExceptionMeansSocketHostnameCannotBeResolved(oException):
        raise cClass.cUnknownHostnameException("Cannot resolve hostname", dxDetails);
      elif fbExceptionMeansSocketInvalidAddress(oException):
        raise cClass.cInvalidAddressException("Invalid hostname", dxDetails);
      elif fbExceptionMeansSocketTimeout(oException):
        raise cClass.cTimeoutException("Cannot connect to server", dxDetails);
      elif fbExceptionMeansSocketConnectionRefused(oException):
        raise cClass.cConnectionRefusedException("Connection refused by server", dxDetails);
      else:
        raise;
    oSelf = cClass(oPythonSocket, bCreatedLocally = True);
    if ozSSLContext:
      oSelf.fSecure(ozSSLContext, bCheckHostname, nzSecureTimeoutInSeconds);
    return oSelf;
  
  @classmethod
  @ShowDebugOutput
  def faoWaitUntilBytesAreAvailableForReading(cClass, aoConnections, nzTimeoutInSeconds = None):
    # select.select does not work well on secure sockets, so we use the non-secure sockets
    # as proxies; there may be SSL traffic without data being send from the remote end, so
    # we may flag a connection as having data to be read when it has none.
    nzEndTime = time.time() + nzTimeoutInSeconds if nzTimeoutInSeconds else None;
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
      nzTimeoutInSeconds = nzEndTime - time.time() if nzEndTime else None;
      if not select.select(aoPythonSockets, [], [], nzTimeoutInSeconds)[0]:
        return []; # Waiting timed out.
  
  @ShowDebugOutput
  def __init__(oSelf, oPythonSocket, oSecurePythonSocket = None, ozSSLContext = None, bCreatedLocally = False):
    oSelf.__oPythonSocket = oSecurePythonSocket or oPythonSocket;
    oSelf.__oNonSecurePythonSocket = oPythonSocket;
    oSelf.__oSecurePythonSocket = oSecurePythonSocket;
    oSelf.__ozSSLContext = ozSSLContext;
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
      nzDeadlockTimeoutInSeconds = gnDeadlockTimeoutInSeconds
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
  
  @ShowDebugOutput
  def fSecure(oSelf, oSSLContext, bCheckHostname = True, nzTimeoutInSeconds = None, sWhile = "securing connection"):
    assert oSelf.__oSecurePythonSocket is None, \
        "Cannot secure a connection twice!";
    oSelf.fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, {}, bShouldAllowReading = True, bShouldAllowWriting = True);
    try:
      oSelf.__oPythonSocket = oSelf.__oSecurePythonSocket = oSSLContext.foWrapSocket(
        oPythonSocket = oSelf.__oNonSecurePythonSocket,
        bCheckHostname = bCheckHostname,
        nzTimeoutInSeconds = nzTimeoutInSeconds,
      );
    except Exception as oException:
      if fbExceptionMeansSocketTimeout(oException):
        raise oSelf.cTimeoutException("Timeout while %s." % sWhile, {"nzTimeoutInSeconds": nzTimeoutInSeconds});
      if fbExceptionMeansSocketShutdown(oException):
        oSelf.__fCheckIfSocketAllowsReading(sWhile);
        oSelf.__fCheckIfSocketAllowsWriting(sWhile);
      elif fbExceptionMeansSocketDisconnected(oException):
        fShowDebugOutput("Connection disconnected while %s." % sWhile);
        oSelf.__fHandleDisconnect();
      else:
        raise;
      oSelf.fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, {}, bShouldAllowReading = True, bMustThrowException = True);
    oSelf.__ozSSLContext = oSSLContext;
  
  @property
  def ozSSLContext(oSelf):
    return oSelf.__ozSSLContext;
  @property
  def bSecure(oSelf):
    return oSelf.__oSecurePythonSocket is not None;
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
  def fbWait(oSelf, nzTimeoutInSeconds):
    return oSelf.__oTerminatedLock.fbWait(nzTimeoutInSeconds);
  
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
    try:
      # .rec() on the secure socket may succeed even if the connection is
      # closed. .recv() on the non-secure socket will throw an exception and
      # will not interfere with ssl; hence we call that:
      oSelf.__oNonSecurePythonSocket.settimeout(0);
      oSelf.__oNonSecurePythonSocket.recv(0);
    except Exception as oException:
      if fbExceptionMeansSocketTimeout(oException):
        pass; # Still connected
      elif fbExceptionMeansSocketShutdown(oException):
        oSelf.__fHandleShutdownForReading(sWhile);
      elif fbExceptionMeansSocketDisconnected(oException):
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
    try:
      oSelf.__oNonSecurePythonSocket.settimeout(0);
      oSelf.__oNonSecurePythonSocket.send("");
    except Exception as oException:
      if fbExceptionMeansSocketShutdown(oException):
        oSelf.__fHandleShutdownForWriting(sWhile);
      elif fbExceptionMeansSocketDisconnected(oException):
        oSelf.__fHandleDisconnect();
      else:
        raise;
      return;
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
      raise oSelf.cDisconnectedException("Disconnected while %s" % sWhile, dxDetails);
    if bShouldAllowReading and not oSelf.__bShouldAllowReading:
      raise oSelf.cShutdownException("Shutdown for reading while %s" % sWhile, dxDetails);
    if bShouldAllowWriting and not oSelf.__bShouldAllowWriting:
      raise oSelf.cShutdownException("Shutdown for writing while %s" % sWhile, dxDetails);
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
  def fWaitUntilBytesAreAvailableForReading(oSelf, nzTimeoutInSeconds = None, sWhile = "waiting for bytes to become available for reading"):
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
      [oSelf.__oNonSecurePythonSocket], [], [oSelf.__oNonSecurePythonSocket], nzTimeoutInSeconds
    );
    if len(aoErrorSockets) == 0 and len(aoReadableSockets) == 0:
      # No errors and no readable sockets means no bytes available for reading
      # before the timeout.
      raise oSelf.cTimeoutException("Timeout while %s" % sWhile, {"nzTimeoutInSeconds": nzTimeoutInSeconds});
    fShowDebugOutput("Checking if signal means data is available or socket is closed...");
    oSelf.fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, {}, bShouldAllowReading = True);
    fShowDebugOutput("Data should be available for reading now.");
  
  @ShowDebugOutput
  def fsReadAvailableBytes(oSelf, uzMaxNumberOfBytes = None, sWhile = "reading available bytes"):
    # Can throw a shutdown or disconnected exception *if* this happens before any bytes can be read.
    # Returns any bytes that can currently be read, this could be "".
    dxDetails = {"uzMaxNumberOfBytes": uzMaxNumberOfBytes};
    oSelf.fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, dxDetails, bShouldAllowReading = True);
    sAvailableBytes = "";
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
        uzMaxNumberOfBytes - len(sAvailableBytes) if uzMaxNumberOfBytes is not None \
        else oSelf.uReadChunkSize
      );
      try:
        oSelf.__oPythonSocket.settimeout(0);
        sBytesRead = oSelf.__oPythonSocket.recv(uReadMaxNumberOfBytes);
      except Exception as oException:
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
  def fsReadBytesUntilDisconnected(oSelf, uzMaxNumberOfBytes = None, nzTimeoutInSeconds = None, sWhile = "reading bytes until disconnected"):
    nzEndTime = time.time() + nzTimeoutInSeconds if nzTimeoutInSeconds else None;
    sBytes = "";
    uzMaxNumberOfBytesRemaining = uzMaxNumberOfBytes;
    try:
      while uzMaxNumberOfBytesRemaining is None or uzMaxNumberOfBytesRemaining > 0:
        nzTimeoutInSeconds = nzEndTime - time.time() if nzEndTime is not None else None;
        oSelf.fWaitUntilBytesAreAvailableForReading(nzTimeoutInSeconds, sWhile);
        sBytes += oSelf.fsReadAvailableBytes(uzMaxNumberOfBytes = uzMaxNumberOfBytesRemaining, sWhile = sWhile);
    except (oSelf.cShutdownException, oSelf.cDisconnectedException) as oException:
      pass;
    return sBytes;
  
  @ShowDebugOutput
  def fWriteBytes(oSelf, sBytes, nzTimeoutInSeconds = None, sWhile = "writing bytes"):
    # Can throw a timeout, shutdown or disconnected exception.
    # Returns once all bytes have been written.
    uNumberOfBytesToWrite = len(sBytes);
    dxDetails = {"sBytes": sBytes, "uNumberOfBytesToWrite": uNumberOfBytesToWrite, \
        "uNumberOfBytesWritten": 0, "nzTimeoutInSeconds": nzTimeoutInSeconds};
    oSelf.fThrowDisconnectedOrShutdownExceptionIfApplicable(sWhile, dxDetails, bShouldAllowWriting = True);
    nzEndTime = time.time() + nzTimeoutInSeconds if nzTimeoutInSeconds is not None else None;
    uTotalNumberOfBytesWritten = 0;
    while uTotalNumberOfBytesWritten < uNumberOfBytesToWrite:
      if nzEndTime is not None and time.time() >= nzEndTime:
        raise oSelf.cTimeoutException("Timeout while %s" % sWhile, dxDetails);
      try:
        oSelf.__oPythonSocket.settimeout(0);
        uNumberOfBytesWrittenInSendCall = oSelf.__oPythonSocket.send(sBytes);
      except Exception as oException:
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
    try:
      oSelf.__oPythonSocket.settimeout(0);
      oSelf.__oPythonSocket.shutdown(xFlags);
    except Exception as oException:
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
        except oSelf.cDisconnectedException as oException:
          pass; # A debug message will have already explained what happened.
      if oSelf.bConnected:
        if oSelf.__oSecurePythonSocket:
          fShowDebugOutput("Disconnecting secure socket...");
          try:
            oSelf.__oSecurePythonSocket.close();
          except Exception as oException:
            if not fbExceptionMeansSocketDisconnected(oException):
              raise;
          fShowDebugOutput("Disconnecting non-secure socket...");
        else:
          fShowDebugOutput("Disconnecting socket...");
        try:
          oSelf.__oNonSecurePythonSocket.close();
        except Exception as oException:
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
        if not fbExceptionMeansSocketDisconnected(oException):
          raise;
      if oSelf.__oSecurePythonSocket: 
        try:
          oSelf.__oSecurePythonSocket.close();
        except Exception as oException:
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
