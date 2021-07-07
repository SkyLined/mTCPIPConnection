import os, select, socket, ssl, sys, threading, time;
# Add main folder to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."));

from fbExceptionMeansSocketDisconnected import fbExceptionMeansSocketDisconnected;
from fbExceptionMeansSocketShutdown import fbExceptionMeansSocketShutdown;
from fbExceptionMeansSocketTimeout import fbExceptionMeansSocketTimeout;

nConnectTimeoutInSeconds = 1.0;
sbHostname = b"localhost";
uPortNumber = 31337;
uReceiveBytes = 10;
sbSendBytes = b"X" * 10;

oListeningSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
oListeningSocket.settimeout(0);
oListeningSocket.bind((sbHostname, uPortNumber));
oListeningSocket.listen(1);

oServerSocket = None;
oSecureServerSocket = None;
oClientSocket = None;
oSecureClientSocket = None;
def foCreateSockets(bSecure, bClient):
  global oClientSocket, oSecureClientSocket, \
         oServerSocket, oSecureServerSocket
  try:
   oSecureClientSocket.close();
  except:
   pass;
  try:
   oClientSocket.close();
  except:
   pass;
  try:
   oSecureServerSocket.close();
  except:
   pass;
  try:
   oServerSocket.close();
  except:
   pass;
    
  # Create client socket
  oClientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
  oClientSocket.settimeout(nConnectTimeoutInSeconds);
  oClientSocket.connect((sbHostname, uPortNumber));
  # Create server socket
  aoR, aoW, aoX = select.select([oListeningSocket], [oListeningSocket], [oListeningSocket]);
  assert len(aoW) == 0, \
      "Listening socket is ready for writing!?";
  assert len(aoX) == 0, \
      "Listening socket has exception!?";
  assert len(aoR) == 1, \
      "Listening socket is not ready for reading!?";
  (oServerSocket, (sClientIP, uClientPortNumber)) = oListeningSocket.accept();
  if bSecure:
    def fSecureServerSide():
      global oSecureServerSocket;
      oSecureServerSocket = ssl.wrap_socket(oServerSocket, server_side=True, keyfile="localhost.key.pem", certfile="localhost.cert.pem");
    oThread = threading.Thread(target = fSecureServerSide);
    oThread.start();
    oSecureClientSocket = ssl.wrap_socket(oClientSocket, server_side=False);
    oThread.join();
    oSecureClientSocket.settimeout(0);
    oSecureServerSocket.settimeout(0);
    return oSecureClientSocket if bClient else oSecureServerSocket;
  else:
    oSecureClientSocket = None;
    oSecureServerSocket = None;
    return oClientSocket if bClient else oServerSocket;



def fTestSockets(bSecure, sState, bTestClient = True, bTestServer = True, bCanWaitForReading = True):
  global oClientSocket, oSecureClientSocket, \
         oServerSocket, oSecureServerSocket
  if bTestClient: sClientLog = "client:";
  if bTestServer: sServerLog = "server:";
  try:
    if bTestClient: sClientLog += " [" + fsTestSocketStatus(oSecureClientSocket, oClientSocket, bCanWaitForReading) + "]";
    if bTestServer: sServerLog += " [" + fsTestSocketStatus(oSecureServerSocket, oServerSocket, bCanWaitForReading) + "]";
    try:
      assert (oSecureClientSocket or oClientSocket).send(sbSendBytes) == len(sbSendBytes), "";
    except Exception as oException:
      if bTestClient: sClientLog += " wXXX";
    else:
      if bTestClient: sClientLog += " W";
    try:
      assert (oSecureServerSocket or oServerSocket).send(sbSendBytes) == len(sbSendBytes), "";
    except Exception as oException:
      if bTestServer: sServerLog += " wXXX";
    else:
      if bTestServer: sServerLog += " W";
    try:
      sData = (oSecureClientSocket or oClientSocket).recv(10);
    except Exception as oException:
      if bTestClient: sClientLog += " Read(10) => Exception";
    else:
      if bTestClient: sClientLog += " Read(10) => %d bytes" % (len(sData),);
    try:
      sData = (oSecureServerSocket or oServerSocket).recv(10);
    except Exception as oException:
      if bTestServer: sServerLog += " Read(10) => Exception";
    else:
      if bTestServer: sServerLog += " Read(10) => %d bytes" % (len(sData),);
  finally:
    print((",--- %s %s " % ("secure" if bSecure else "non-secure", sState)).ljust(80, "-"));
    if bTestClient: print("| " + sClientLog);
    if bTestServer: print("| " + sServerLog);
    print("'".ljust(80, "-"));

def fsTestSocketStatus(oSecureSocket, oNonSecureSocket, bCanWaitForReading):
  sLog = "";
  oSocket = oSecureSocket or oNonSecureSocket;
  oSocket.settimeout(0);
  try:
    sData = oNonSecureSocket.recv(0);
  except Exception as oException:
    if fbExceptionMeansSocketTimeout(oException):
      sLog += "Read(0):Timeout  ";
      bIsOpenForReading = True;
    elif fbExceptionMeansSocketShutdown(oException):
      sLog += "Read(0):Shutdown ";
      bIsOpenForReading = False;
    elif fbExceptionMeansSocketDisconnected(oException):
      return "xx:%sR0:X" % sLog;
    else:
      raise;
  else:
    sLog += "Read(0):Ok       ";
    bIsOpenForReading = True;
  
  nStartTime = time.time();
  nWaitTimeout = 1;
  bDataAvailable, bUnused, bException = [
    len(aoSocket) == 1
    for aoSocket in select.select([oSocket], [], [oSocket], nWaitTimeout)
  ];
  assert not bException, \
      "Unexpected exception";
  assert bCanWaitForReading or time.time() < nStartTime + nWaitTimeout, \
      "Waiting despite this is not expected."
  sLog += "Select(RX):[R] " if bDataAvailable else "Select(RX):[]  ";
  if bDataAvailable:
    try:
      oSocket.settimeout(0);
      sData = oSocket.recv(1);
    except (socket.error, ssl.SSLWantReadError) as oException:
      if fbExceptionMeansSocketTimeout(oException):
        sLog += "Read(1):Timeout  ";
      elif fbExceptionMeansSocketShutdown(oException):
        sLog += "Read(1):Shutdown ";
        bIsOpenForReading = False;
      elif fbExceptionMeansSocketDisconnected(oException):
        return "xx:%sR1:X" % sLog;
      else:
        raise;
    else:
      if len(sData) == 1:
        sLog += "Read(1):Ok       ";
      else:
        sLog += "Read(1):''       ";
        bIsOpenForReading = False;
  bUnused, bIsOpenForWriting, bException = [
    len(aoSocket) == 1
    for aoSocket in select.select([], [oSocket], [oSocket], 0)
  ];
  assert not bException, \
      "Unexpected exception";
  sLog += "Select(WX):[W] " if bIsOpenForWriting else "Select(WX):[]  ";
  if bIsOpenForWriting:
    try:
      oNonSecureSocket.send(b"");
    except socket.error as oException:
      if fbExceptionMeansSocketShutdown(oException):
        sLog += "Write(''):Shutdown ";
        bIsOpenForWriting = False;
      elif fbExceptionMeansSocketDisconnected(oException):
        return "xx:%sW0:X" % sLog;
      else:
        raise;
    else:
      sLog += "Write(''):Ok       ";
  return "%s => %s" % (
    sLog, (
      "Open" if bIsOpenForReading else
      "Write-only"
    ) if bIsOpenForWriting else (
      "Read-only" if bIsOpenForReading else
      "Closed"
    )
  );

try:
  for bSecure in (False, True):
    foCreateSockets(bSecure, False);
    fTestSockets(bSecure, "RW: connected");

  for bClient in (True, False):
    for bSecure in (False, True):
      foCreateSockets(bSecure, bClient).shutdown(socket.SHUT_RD);
      fTestSockets(bSecure, "Rx: read shutdown by %s" % ("client" if bClient else "server"), bTestClient = not bClient, bTestServer = bClient);
      
      foCreateSockets(bSecure, bClient).shutdown(socket.SHUT_WR);
      fTestSockets(bSecure, "xW: write shutdown by %s" % ("client" if bClient else "server"), bTestClient = not bClient, bTestServer = bClient, bCanWaitForReading = False);
      
      foCreateSockets(bSecure, bClient).shutdown(socket.SHUT_RDWR);
      fTestSockets(bSecure, "xx: shutdown by %s" % ("client" if bClient else "server"), bTestClient = not bClient, bTestServer = bClient, bCanWaitForReading = False);
      
      foCreateSockets(bSecure, bClient).close();
      if bSecure:
        (oClientSocket if bClient else oServerSocket).close();
      fTestSockets(bSecure, "xx: closed by %s" % ("client" if bClient else "server"), bTestClient = not bClient, bTestServer = bClient, bCanWaitForReading = False);

      oSocket = foCreateSockets(bSecure, bClient);
      oSocket.shutdown(socket.SHUT_RDWR);
      oSocket.close();
      if bSecure:
        try:
          (oClientSocket if bClient else oServerSocket).shutdown(socket.SHUT_RDWR);
        except Exception as oException:
          if not fbExceptionMeansSocketDisconnected(oException):
            raise;
        (oClientSocket if bClient else oServerSocket).close();
      fTestSockets(bSecure, "xx: shutdown and closed by %s" % ("client" if bClient else "server"), bTestClient = not bClient, bTestServer = bClient, bCanWaitForReading = False);

except Exception as oException:
  print("*** %s(%s) ***" % (oException.__class__.__name__, ", ".join([repr(s) for s in oException.args])));
  raise;