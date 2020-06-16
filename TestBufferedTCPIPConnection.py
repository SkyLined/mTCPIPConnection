import os, sys, threading, time;
sys.path.append(os.path.join(__file__, "..", ".."));

from mTCPIPConnections import cBufferedTCPIPConnection as cConnection, cBufferedTCPIPConnectionAcceptor as cConnectionAcceptor;
from mDebugOutput import fShowDebugOutputForModule;
from mMultiThreading import cThread;
import mTCPIPConnections, mMultiThreading;

fShowDebugOutputForModule(mTCPIPConnections);
fShowDebugOutputForModule(mMultiThreading);

sHostname = "127.0.0.1";
uPort = 28875;
bDisconnectionDetectedByClient = False;
bDisconnectionDetectedByServer = False;

def fHandleNewConnectionOnServerSide(oAcceptor, oServerConnection):
  global bDisconnectionDetectedByServer;
  print "Server: %s." % (oServerConnection);
  print "Server waiting for bytes...";
  try:
    oServerConnection.fWaitUntilBytesAreAvailableForReading(1, 60);
  except (oServerConnection.cShutdownException, oServerConnection.cDisconnectedException):
    bDisconnectionDetectedByServer = True;
    print "Disconnect detected by server!";
    return;
  sAvailableBytes = oServerConnection.fsReadAvailableBytes();
  print "Bytes read: %s" % repr(sAvailableBytes);
  print "Server done.";

oConnectionAcceptor = cConnectionAcceptor(fHandleNewConnectionOnServerSide, sHostname, uPort);

oClientConnection = cConnection.foConnectTo(sHostname, uPort);
print "Client: %s" % oClientConnection;

def fWait():
  global bDisconnectionDetectedByClient;
  print "Client waiting for bytes...";
  try:
    oClientConnection.fWaitUntilBytesAreAvailableForReading(1, 60);
  except (oClientConnection.cShutdownException, oClientConnection.cDisconnectedException):
    bDisconnectionDetectedByClient = True;
    print "Disconnect detected by client!";
  else:
    sAvailableBytes = oClientConnection.fsReadAvailableBytes();
    print "Bytes read: %s" % repr(sAvailableBytes);
  print "Client done";

oThread = cThread(fWait);
oThread.fStart();
time.sleep(1);
print "Disconnecting %s" % oClientConnection;
oClientConnection.fDisconnect();
print "Stopping %s" % oConnectionAcceptor;
oConnectionAcceptor.fStop();
print "Waiting for %s" % oConnectionAcceptor;
assert oConnectionAcceptor.fbWait(1), "Failed";

print "Waiting for %s" % oClientConnection;
assert oClientConnection.fbWait(1), "Failed";
print "Waiting for %s" % oThread;
assert oThread.fbWait(1), "Failed";

print "Test %s" % (" and ".join([s for s in [
  "failed in client" if not bDisconnectionDetectedByClient else None, 
  "failed in server" if not bDisconnectionDetectedByServer else None,
] if s]) or "successful");
