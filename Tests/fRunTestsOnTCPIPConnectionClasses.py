import gc;

from mTCPIPConnection import (
  cBufferedTCPIPConnection,
  cTCPIPConnection,
  cTCPIPConnectionDisconnectedException,
  cTCPIPConnectionRefusedException,
  cTCPIPConnectionShutdownException,
  cTCPIPConnectTimeoutException,
  cTCPIPDataTimeoutException,
  cTCPIPDNSNameCannotBeResolvedException,
  cTCPIPInvalidAddressException,
  cTransactionalBufferedTCPIPConnection,
);

from cTestServer import *;

gsbRequestData = b"Request";
gsbResponseData = b"Response";
gsbTestServerHost = b"127.0.0.1";
guTestServerPortNumber = 28876;
gnConnectTimeoutInSeconds = 5;
gnTransactionTimeoutInSeconds = 5;
gnWaitForDataTimeoutInSeconds = 5;
gnDisconnectTimeoutInSeconds = 1;
gnWaitForConnectionToStopTimeoutInSeconds = 5;

NORMAL =            0x0F07; # Light gray
INFO =              0x0F0F; # Bright white
OK =                0x0F0A; # Bright green
ERROR =             0x0F0C; # Bright red
WARNING =           0x0F0E; # Yellow

dddxTest_by_sName = {
  "unknown host": {
    "sbHost": b"does.not.exist.example.com",
    "cExpectedExceptionClass": cTCPIPDNSNameCannotBeResolvedException,
  },
  "invalid address": {
    "sbHost": b"0.0.0.0",
    "cExpectedExceptionClass": cTCPIPInvalidAddressException,
  },
  "connection refused": {
    "cTestServer arguments": {
      "bListen": False, # Not listening on a server socket should cause connections to be refused.
    },
    "cExpectedExceptionClass": cTCPIPConnectionRefusedException,
  },
  "connect timeout": {
    "cTestServer arguments": {
      "bAccept": False, # Not accepting a connection on the server socket should cause connections to timeout.
    },
    "cExpectedExceptionClass": cTCPIPConnectTimeoutException,
    "ac0AcceptableExceptionClasses": [cTCPIPConnectionRefusedException], # It's hard to create a reliable server that triggers a timeout
  },
  "disconnected immediately": {
    "cTestServer arguments": {
      "bDisconnect": True, # Will accepting a connection on a server socket and disconnect immediately.
    },
    "sbExpectedResponseData": gsbResponseData, # Waiting for this response should trigger an exception
    "cExpectedExceptionClass": cTCPIPConnectionDisconnectedException,
    "ac0AcceptableExceptionClasses": [cTCPIPConnectionShutdownException], # It's hard to create a reliable server that does not shutdown the connection
  },
  "shutdown immediately": {
    "cTestServer arguments": {
      "bShutdownForWriting": True, # Will accepting a connection on a server socket and shutdown for writing immediately.
    },
    "sbRequestData": gsbRequestData,
    "sbExpectedResponseData": gsbResponseData, # Waiting for this response should trigger an exception
    "cExpectedExceptionClass": cTCPIPConnectionShutdownException,
    "ac0AcceptableExceptionClasses": [cTCPIPConnectionDisconnectedException], # Reported when connection is shutdown during SSL handshake
  },
  "response timeout": {
    "acAppliesToConnectionClasses": [cTransactionalBufferedTCPIPConnection], # Class must support timeouts.
    "cTestServer arguments": {}, # Accept connections but do nothing
    "sbRequestData": gsbRequestData,
    "sbExpectedResponseData": gsbResponseData,
    "cExpectedExceptionClass": cTCPIPDataTimeoutException,
  },
};

def fRunTestsOnTCPIPConnectionClasses(oConsole, o0ClientSSLContext, o0ServerSSLContext):
  for cConnectionClass in (cTCPIPConnection, cBufferedTCPIPConnection, cTransactionalBufferedTCPIPConnection):
    fRunTestsOnTCPIPConnectionClass(oConsole, cConnectionClass, o0ClientSSLContext, o0ServerSSLContext);

def fRunTestsOnTCPIPConnectionClass(oConsole, cConnectionClass, o0ClientSSLContext, o0ServerSSLContext):
  for (sName, ddxTest) in dddxTest_by_sName.items():
    a0cAppliesToConnectionClasses = ddxTest.get("acAppliesToConnectionClasses");
    if not a0cAppliesToConnectionClasses or cConnectionClass in a0cAppliesToConnectionClasses:
      fRunATestOnTCPIPConnectionClass(oConsole, cConnectionClass, o0ClientSSLContext, o0ServerSSLContext, sName, ddxTest);

def fRunATestOnTCPIPConnectionClass(oConsole, cConnectionClass, o0ClientSSLContext, o0ServerSSLContext, sName, ddxTest):
  oConsole.fOutput(
    "┌──[ ",
    INFO, sName,
    NORMAL, " test using ", INFO, cConnectionClass.__name__,
    NORMAL, " over a", "" if o0ClientSSLContext else "n", " ",
    INFO, "" if o0ClientSSLContext else "in", "secure",
    NORMAL, " connection ]",
    sPadding = "─"
  );
  sb0TestHost = ddxTest.get("sbHost");
  if sb0TestHost:
    sbTestHost = sb0TestHost;
    o0TestServer = None;
    uTestPortNumber = ddxTest.get("uPortNumber", 1); # If not specified, connect to port 1.
  else:
    o0TestServer = cTestServer(
      oConsole,
      gsbTestServerHost,
      guTestServerPortNumber,
      o0ServerSSLContext,
      sName,
      **ddxTest.get("cTestServer arguments", {})
    );
    sbTestHost = gsbTestServerHost;
    uTestPortNumber = guTestServerPortNumber;
  
  c0ExpectedExceptionClass = ddxTest.get("cExpectedExceptionClass");
  ac0AcceptableExceptionClasses = ddxTest.get("ac0AcceptableExceptionClasses", []);
  o0Connection = None;
  try:
    # Connect
    oConsole.fOutput("│ ", sName, " test client: connecting for %f seconds to server at %s:%d..." % (gnConnectTimeoutInSeconds, sbTestHost, uTestPortNumber));
    oConnection = cConnectionClass.foConnectTo(
      sbTestHost,
      uTestPortNumber,
      n0zConnectTimeoutInSeconds = gnConnectTimeoutInSeconds,
      o0SSLContext = o0ClientSSLContext,
      n0zSecureTimeoutInSeconds = None,
    );
    o0Connection = oConnection;
    bBuffered = isinstance(oConnection, cBufferedTCPIPConnection);
    bTransactional = isinstance(oConnection, cTransactionalBufferedTCPIPConnection);
    # Start transaction if applicable
    if bTransactional:
      oConsole.fOutput("│ ", sName, " test client: starting %f second transaction..." % (gnTransactionTimeoutInSeconds,));
      oConnection.fStartTransaction(n0TimeoutInSeconds = gnTransactionTimeoutInSeconds);
    # Send request if applicable
    sb0RequestData = ddxTest.get("sbRequestData");
    if sb0RequestData is not None:
      oConsole.fOutput("│ ", sName, " test client: writing ", str(len(sb0RequestData)), " bytes data...", );
      oConnection.fWriteBytes(sb0RequestData);
    # Read response if applicable
    sb0ExpectedResponseData = ddxTest.get("sbExpectedResponseData");
    if sb0ExpectedResponseData is not None:
      if bTransactional:
        sbReceivedData = oConnection.fsbReadBytes(
          uNumberOfBytes = len(sb0ExpectedResponseData),
        );
      elif bBuffered:
        sbReceivedData = oConnection.fsbReadBytes(
          uNumberOfBytes = len(sb0ExpectedResponseData),
          n0TimeoutInSeconds = gnWaitForDataTimeoutInSeconds,
        );
      else:
        sbReceivedData = b"";
        while len(sbReceivedData) < len(sb0ExpectedResponseData):
          if bBuffered:
            oConsole.fOutput("│ ", sName, " test client: waiting %f seconds until bytes are available for reading..." % (gnWaitForDataTimeoutInSeconds,));
            bBytesAreAvailableForReading = oConnection.fbWaitUntilBytesAreAvailableForReading(
              nWaitTimeoutInSeconds = gnWaitForDataTimeoutInSeconds,
            );
            assert bBytesAreAvailableForReading, \
                "No bytes available for reading after %f seconds" % gnWaitForDataTimeoutInSeconds;
            oConsole.fOutput("│ ", sName, " test client: reading bytes...");
            sbReceivedData += oConnection.fsbReadAvailableBytes();
          else:
            oConsole.fOutput("│ ", sName, " test client: reading bytes...");
            sbReceivedData += oConnection.fsbReadAvailableBytes(
              n0TimeoutInSeconds = gnWaitForDataTimeoutInSeconds,
            );
      assert sbReceivedData == sb0ExpectedResponseData, \
          "Expected %s, got %s" % (repr(sb0ExpectedResponseData), repr(sbReceivedData));
  except Exception as oException:
    if oException.__class__ is c0ExpectedExceptionClass:
      oConsole.fOutput("│ ", OK, "+", NORMAL, " Got expected exception: ", oException.__class__.__name__, ": ", str(oException));
    elif oException.__class__ in ac0AcceptableExceptionClasses:
      oConsole.fOutput("│ ", WARNING, "~", NORMAL, " Got acceptable exception: ", oException.__class__.__name__, ": ", str(oException));
      oConsole.fOutput("│    Expected exception: ", c0ExpectedExceptionClass.__name__);
    else:
      oConsole.fOutput("│ ", ERROR, "-", NORMAL, " Unexpected exception: %s(%s)" % (oException.__class__.__name__, oException));
      if c0ExpectedExceptionClass:
        oConsole.fOutput("│    Expected exceptions: %s" % (c0ExpectedExceptionClass.__name__,));
      if len(ac0AcceptableExceptionClasses) > 0:
        oConsole.fOutput("│    Acceptable exceptions:");
        for c0AcceptableExceptionClass in ac0AcceptableExceptionClasses:
          oConsole.fOutput("│    * ", "No exception" if c0AcceptableExceptionClass is None else c0AcceptableExceptionClass.__name__);
      raise;
  else:
    if c0ExpectedExceptionClass:
      oConsole.fOutput("│ ", ERROR, "-", NORMAL, " Expected exceptions: %s" % (c0ExpectedExceptionClass.__name__,));
      if len(ac0AcceptableExceptionClasses) > 0:
        oConsole.fOutput("│    Acceptable exceptions:");
        for c0AcceptableExceptionClass in ac0AcceptableExceptionClasses:
          oConsole.fOutput("│    * ", "No exception" if c0AcceptableExceptionClass is None else c0AcceptableExceptionClass.__name__);
      raise AssertionError("Expected an exception but got none.");
    oConsole.fOutput("│ ", OK, "+", NORMAL, " Got no exception.");
  # Cleanup the connection if needed:
  if o0Connection and oConnection.bConnected:
    # A transaction may need to be started before we can disconnect:
    if bTransactional and not oConnection.bInTransaction:
      oConsole.fOutput("│ ", sName, " test client: starting transaction to close connection...");
      oConnection.fStartTransaction();
      
    oConsole.fOutput("│ ", sName, " test client: disconnecting...");
    oConnection.fDisconnect();
    
    if bTransactional and oConnection.bInTransaction:
      oConsole.fOutput("│ ", sName, " test client: ending transaction...");
      oConnection.fEndTransaction();
    
    oConsole.fOutput("│ ", sName, " test client: waiting for connection to terminate...");
    assert oConnection.fbWait(nTimeoutInSeconds = gnWaitForConnectionToStopTimeoutInSeconds), \
        "%s did not disconnect within %d seconds!?" % gnWaitForConnectionToStopTimeoutInSeconds;
  
  if o0TestServer:
    o0TestServer.fStop();
    o0TestServer.fWait();
  oConsole.fOutput("└", sPadding = "─");
  gc.collect();