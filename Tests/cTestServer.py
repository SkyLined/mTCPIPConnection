import os, select, socket;
from mMultiThreading import cThread, cLock;

DIM =            0x0F08; # Dark gray
class cTestServer(object):
  def __init__(oSelf, oConsole, sHostname, uPort, sName, bListen = True, bAccept = True, u0MinRequestBytes = None, u0MaxRequestBytes = None, s0Response = None, bShutdownForReading = False, bShutdownForWriting = False, bDisconnect = False):
    oSelf.oConsole = oConsole; # not imported but passed as an argument because it may not be available, in which case a stub is used.
    oSelf.sHostname = sHostname;
    oSelf.uPort = uPort;
    oSelf.sName = sName;
    oSelf.oServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
#    oSelf.oServerSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); # Do not go to TIME_WAIT after close.
    oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: binding to %s:%d..." % (sHostname, uPort));
    oSelf.oServerSocket.bind((sHostname, uPort));
    oSelf.bListening = bListen;
    oSelf.bAccepting = bListen and bAccept;
    oSelf.oTerminatedLock = cLock("Terminated lock", bLocked = True);
    if not bListen:
      oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: closing server socket...");
      oSelf.oServerSocket.close();
    else:
      oSelf.bStopping = False;
      # If we are accepting connections, allow the next connection to be queued while we're handling the current
      # connection (see below)
      oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: listening...");
      oSelf.oServerSocket.listen(1 if bAccept else 0);
      oSelf.u0MinRequestBytes = u0MinRequestBytes;
      if u0MinRequestBytes is not None:
        assert bAccept, "Cannot have `bAccept is False` and `u0MinRequestBytes is not None`!";
        assert u0MaxRequestBytes is not None, "Cannot have `u0MinRequestBytes is not None` if `u0MaxRequestBytes is None`!";
        oSelf.uMaxRequestBytes = u0MaxRequestBytes;
      assert bAccept or s0Response is None, "Cannot have `bAccept is False` and `s0Response is not None`!";
      oSelf.s0Response = s0Response;
      assert bAccept or not bShutdownForReading, "Cannot have `bAccept is False` and `bShutdownForReading is True`!";
      oSelf.bShutdownForReading = bShutdownForReading;
      assert bAccept or not bShutdownForWriting, "Cannot have `bAccept is False` and `bShutdownForWriting is True`!";
      oSelf.bShutdownForWriting = bShutdownForWriting;
      assert bAccept or not bShutdownForWriting, "Cannot have `bAccept is False` and `bDisconnect is True`!";
      oSelf.bDisconnect = bDisconnect;
      if not bAccept:
        # If we are NOT accepting connections, make a connection to the server but we do not
        # accept it. Further connections cannot be made until it is accepted but will be queued
        # This is because we've told the socket not to queue additional connections (see above).
        oSelf.oHelperClientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
        oSelf.oHelperClientSocket.connect((sHostname, uPort));
        oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: NOT accepting connections...");
      else:
        oSelf.oServerThreadStartedLock = cLock("Server thread started lock", bLocked = True);
        oSelf.oServerThread = cThread(oSelf.fServerThread);
        oSelf.oServerThread.fStart(bVital = False);
        oSelf.oServerThreadStartedLock.fWait();
  
  def fStop(oSelf):
    oSelf.bStopping = True;
    if not oSelf.bListening:
      oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: stopped.");
      oSelf.oTerminatedLock.fRelease();
    elif not oSelf.bAccepting:
      oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: closing server socket...");
      oSelf.oServerSocket.close();
      oSelf.oHelperClientSocket.close();
      oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: stopped.");
      oSelf.oTerminatedLock.fRelease();
    else:
      oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: closing server socket...");
      oSelf.oServerSocket.close();
      # socket.accept will wait indefinitely, even after the socket is closed. This means
      # `fServerThread` will never return unless we force socket.accept to stop waiting.
      # This is done by connecting to the server, which causes socket.accept to return.
      # The code in `fServerThread` will then notice that `oSelf.bStopping` is `True` and
      # return.
      try:
        oClientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
        oClientSocket.connect((oSelf.sHostname, oSelf.uPort));
        oClientSocket.close();
      except:
        pass;
  
  def fWait(oSelf):
    oSelf.oTerminatedLock.fWait();
  
  def fServerThread(oSelf):
    oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: accepting connections...");
    oSelf.oServerThreadStartedLock.fRelease();
    while not oSelf.bStopping:
      (oClientSocket, (sClientIP, uClientPort)) = oSelf.oServerSocket.accept();
      if oSelf.bStopping:
        oClientSocket.close();
        break;
      oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: accepted connection.");
      bReadable = True;
      bWritable = True;
      if oSelf.u0MinRequestBytes is not None:
        oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: receiving %d-%d bytes request..." % (oSelf.u0MinRequestBytes, oSelf.uMaxRequestBytes));
        uBytesRead = 0;
        while not oSelf.bStopping and uBytesRead < oSelf.u0MinRequestBytes:
          try:
            uBytesRead += len(oClientSocket.recv(oSelf.uMaxRequestBytes - uBytesRead));
          except:
            bReadable = False;
      if not oSelf.bStopping and oSelf.s0Response is not None:
        oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: sending %s bytes response..." % (len(oSelf.s0Response)));
        try:
          oClientSocket.send(oSelf.s0Response);
        except:
          bWritable = False;
      bShutdownForReading = bReadable and oSelf.bShutdownForReading;
      bShutdownForWriting = bWritable and oSelf.bShutdownForWriting;
      if bShutdownForReading or bShutdownForWriting:
        oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: shutdown connection for ", " and ".join([s0 for s0 in [
          "reading" if bShutdownForReading else None,
          "writing" if bShutdownForWriting else None,
        ] if s0]), "...");
        oClientSocket.shutdown((
          socket.SHUT_RDWR if bShutdownForReading else socket.SHUT_WR
        ) if bShutdownForWriting else (
          socket.SHUT_RD
        ));
        if bShutdownForReading:
          bReadable = False;
        if bShutdownForWriting:
          bWritable = False;
      if oSelf.bDisconnect:
        oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: closing connection...");
        try:
          oClientSocket.close();
        except:
          pass;
        bReadable = False;
        bWritable = False;
      if bReadable:
        oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: reading data...");
      while not oSelf.bStopping and (bReadable or bWritable):
        if bReadable:
          try:
            sData = oClientSocket.recv(0x1000);
          except Exception as oException:
            bReadable = False;
            oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: connection closed for reading (%s)." % oException);
          else:
            if sData:
              oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: read %d bytes, reading more data..." % len(sData));
        if bWritable:
          if not select.select([], [oClientSocket], [])[1]:
            bWritable = False;
            oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: connection closed for writing.");
      try:
        oClientSocket.close();
      except:
        pass;
      oClientSocket = None;
      oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: disconnected, ", \
          "accepting new connection" if not oSelf.bStopping else "closing server socket", "...");
    oSelf.oServerSocket.close();
    oSelf.oConsole.fOutput(DIM, "* ", oSelf.sName, " test server: stopped.");
    oSelf.oTerminatedLock.fRelease();
