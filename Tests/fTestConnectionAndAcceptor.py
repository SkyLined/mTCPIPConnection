from mConsoleLoader import oConsole;

gsbHostname = b"127.0.0.1";
guPortNumber = 28876;

def fWriteData(oConnection, sbData):
  oConsole.fOutput("%s: writing %d bytes data: %s." % (oConnection, len(sbData), repr(sbData)));
  oConnection.fWriteBytes(sbData);

def fWaitForAndReadData(oConnection):
  if hasattr(oConnection, "fWaitUntilBytesAreAvailableForReading"):
    oConsole.fOutput("%s: Waiting until bytes are available for reading..." % oConnection);
    oConnection.fWaitUntilBytesAreAvailableForReading();
  oConsole.fOutput("%s: Reading data..." % oConnection);
  sbReceivedData = oConnection.fsbReadAvailableBytes();
  oConsole.fOutput("%s:   Read %d bytes data: %s." % (oConnection, len(sbReceivedData), repr(sbReceivedData)));

def fDisconnectAndWait(oConnection):
  fStartTransactionIfPossible(oConnection);
  oConsole.fOutput("%s: Disconnecting..." % oConnection);
  oConnection.fDisconnect();
  fEndTransactionIfPossible(oConnection);
  oConsole.fOutput("%s: Waiting for connection to terminate..." % oConnection);
  assert oConnection.fbWait(nTimeoutInSeconds = 1), \
      "%s did not disconnect in a reasonable time!?";

def fStartTransactionIfPossible(oConnection):
  if hasattr(oConnection, "fStartTransaction"):
    oConsole.fOutput("%s: Starting transaction..." % oConnection);
    oConnection.fStartTransaction();

def fEndTransactionIfPossible(oConnection):
  if hasattr(oConnection, "fEndTransaction"):
    oConsole.fOutput("%s: Ending transaction..." % oConnection);
    oConnection.fEndTransaction();

def fTestConnectionAndAcceptor(cConnection, cConnectionAcceptor, o0ClientSSLContext, o0ServerSSLContext):
  def __fHandleServerSideConnection(oAcceptor, oConnection):
    oConsole.fOutput("Server side: New connection %s." % oConnection);
    
    fStartTransactionIfPossible(oConnection);
    fWaitForAndReadData(oConnection);
    fWriteData(oConnection, b"Hello, client!");
    fEndTransactionIfPossible(oConnection);
    
    fDisconnectAndWait(oConnection)
    
    oConsole.fOutput("Server side: Ended connection %s." % oConnection);
    
    oConsole.fOutput("Stopping acceptor %s..." % oAcceptor);
    oAcceptor.fStop();
  
  # Function code starts here
  oConsole.fOutput("Creating Acceptor...");
  oAcceptor = cConnectionAcceptor(__fHandleServerSideConnection, gsbHostname, guPortNumber, o0SSLContext = o0ServerSSLContext);
  oConsole.fOutput("  Acceptor(%s): Listening on %s:%d." % (oAcceptor, gsbHostname, guPortNumber));
  
  oConsole.fOutput("Creating Connection...");
  oConnection = cConnection.foConnectTo(gsbHostname, guPortNumber, o0SSLContext = o0ClientSSLContext);
  oConsole.fOutput("Client side: New connection %s." % oConnection);
  
  fStartTransactionIfPossible(oConnection);
  fWriteData(oConnection, b"Hello, server!");
  fWaitForAndReadData(oConnection);  
  fEndTransactionIfPossible(oConnection);
  
  fDisconnectAndWait(oConnection)
  oConsole.fOutput("Client side: Ended connection %s." % oConnection);

  oConsole.fOutput("Waiting for acceptor %s to stop..." % oAcceptor);
  assert oAcceptor.fbWait(nTimeoutInSeconds = 1), \
      "Acceptor did not terminate in a reasonable time!?";

  oConsole.fOutput("Done.");