import select, socket, ssl, sys, threading, time;

txAddress = (
  sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1",
  int(sys.argv[2]) if len(sys.argv) > 2 else 28876
)

doSocket_by_sDescription = {};
def fOutputSocketInfo(header):
  print(header);
  for sDescription, oSocket in doSocket_by_sDescription.items():
    if oSocket.fileno() == -1:
      sState = "closed";
    else:
      asTestResults = [];
      bEndIfNotReadable = False;
      while 1:
        try:
          bReadable = len(select.select([oSocket],[],[],0,)[0]) > 0;
        except Exception as oException:
          asTestResults += ["SELECT ERROR: %s" % (oException.__class__.__name__)];
          break;
        if bReadable:
          asTestResults += ["E"];
        else:
          if bEndIfNotReadable:
            break;
        try:
          sbByte = oSocket.recv(1);
        except ConnectionAbortedError:
          asTestResults += ["shutdown (ABORTED)"];
          break;
        except ConnectionResetError:
          asTestResults += ["closed (RESET)"];
          break;
        except BrokenPipeError:
          asTestResults += ["shutdown (BROKEN)"];
          break;
        except (BlockingIOError, ssl.SSLWantReadError):
          asTestResults += ["open"];
          break;
        except Exception as oException:
          asTestResults += ["RECV ERROR: %s" % oException.__class__.__name__];
          break;
        asTestResults += ["R:%s" % repr(sbByte)[1:]];
        if bReadable and len(sbByte) == 0:
          asTestResults += ["shutdown (READ 0)"];
          break;
        bEndIfNotReadable = len(sbByte) == 0;
      sState = " | ".join(asTestResults);
    print("%-20s: %s" % (sDescription, sState));

global oClientSideSocket, oServerSideSocket;
def fCreateConnection(bSecure):
  global oClientSideSocket, oServerSideSocket;
  oClientSideSocket = socket.socket();
  oClientSideSocket.connect(txAddress);

  (oServerSideSocket, txRemoteAddress) = oListeningSocket.accept();
  if bSecure:
    oServerSideSocket = oServerContext.wrap_socket(oServerSideSocket, do_handshake_on_connect = False, server_side = True);
    oServerSideSocket.setblocking(True)

    client_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client_context.load_verify_locations('localhost.pem')
    client_context.check_hostname = False;
    oClientSideSocket = client_context.wrap_socket(oClientSideSocket, do_handshake_on_connect = False);
    oClientSideSocket.setblocking(True)

    oThread = threading.Thread(target = oClientSideSocket.do_handshake)
    oThread.start()

    oServerSideSocket.do_handshake()
    oThread.join()

  doSocket_by_sDescription["client side"] = oClientSideSocket;
  doSocket_by_sDescription["server side"] = oServerSideSocket;
  oClientSideSocket.settimeout(0);
  oServerSideSocket.settimeout(0);

def fTestSend(sSender, oSendingSocket):
  oSendingSocket.send(b"ABC");
  fOutputSocketInfo("--- AFTER %s SEND 'ABC'" % (sSender,));

def fTestReceive(sReceiver, oReceivingSocket):
  try:
    sbReceived = oReceivingSocket.recv(100);
  except Exception as oException:
    fOutputSocketInfo("--- AFTER %s RECV FAILED: %s" % (sReceiver, oException));
  else:
    fOutputSocketInfo("--- AFTER %s RECV %s" % (sReceiver, repr(sbReceived)[1:]));

def fTestSendAndReceive(sSender, oSendingSocket, sReceiver, oReceivingSocket): 
  fTestSend(sSender, oSendingSocket);
  #fTestReceive(sReceiver, oReceivingSocket);

def fTestShutdownAndReceive(sShutter, oShutDownSocket, sReceiver, oReceivingSocket): 
  oShutDownSocket.shutdown(socket.SHUT_RDWR);
  fOutputSocketInfo("--- AFTER %s SHUT_RDWR" % (sShutter,));
  #fTestReceive(sReceiver, oReceivingSocket);

def fTestCloseAndReceive(sShutter, oShutDownSocket, sReceiver, oReceivingSocket): 
  oShutDownSocket.close();
  fOutputSocketInfo("--- AFTER %s CLOSE" % (sShutter,));
  #fTestReceive(sReceiver, oReceivingSocket);

# do tests
oServerContext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
oServerContext.load_cert_chain('localhost.pem', 'localhost.key')

oListeningSocket = socket.socket();
oListeningSocket.bind(txAddress);
oListeningSocket.listen(1);

def fDoTests(bSecure):
  print("\n=========== %s" % ("SECURE" if bSecure else "NORMAL"));
  fCreateConnection(bSecure);
  fOutputSocketInfo("--- AFTER CONNECTED");
  #fTestReceive("SERVER", oServerSideSocket);
  #fTestReceive("CLIENT", oClientSideSocket);
  fTestSendAndReceive("CLIENT", oClientSideSocket, "SERVER", oServerSideSocket);
  fTestSendAndReceive("SERVER", oServerSideSocket, "CLIENT", oClientSideSocket);
  #fTestReceive("SERVER", oServerSideSocket);
  #fTestReceive("CLIENT", oClientSideSocket);
  print("");
  fCreateConnection(bSecure);
  fTestShutdownAndReceive("SERVER", oServerSideSocket, "CLIENT", oClientSideSocket);
  print("");
  fCreateConnection(bSecure);
  fTestShutdownAndReceive("CLIENT", oClientSideSocket, "SERVER", oServerSideSocket);
  print("");
  fCreateConnection(bSecure);
  fTestCloseAndReceive("SERVER", oServerSideSocket, "CLIENT", oClientSideSocket);
  print("");
  fCreateConnection(bSecure);
  fTestCloseAndReceive("CLIENT", oClientSideSocket, "SERVER", oServerSideSocket);

fDoTests(False);
fDoTests(True);