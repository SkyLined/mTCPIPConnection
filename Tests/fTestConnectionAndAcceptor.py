from oConsole import oConsole;

gsData = "Hello, world!";
gsHostname = "127.0.0.1";
guPort = 28876;

def fWriteData(oConnection):
  oConsole.fOutput("%s: writing %d bytes data: %s." % (oConnection, len(gsData), repr(gsData)));
  oConnection.fWriteBytes(gsData);

def fWaitForAndReadData(oConnection):
  oConsole.fOutput("%s: Waiting until bytes are available for reading..." % oConnection);
  oConnection.fWaitUntilBytesAreAvailableForReading();
  oConsole.fOutput("%s: Reading data..." % oConnection);
  sReceivedData = oConnection.fsReadAvailableBytes();
  oConsole.fOutput("%s:   Read %d bytes data: %s." % (oConnection, len(sReceivedData), repr(sReceivedData)));

def fDisconnectAndWait(oConnection):
  fStartTransactionIfPossible(oConnection);
  oConsole.fOutput("%s: Disconnecting..." % oConnection);
  oConnection.fDisconnect();
  fEndTransactionIfPossible(oConnection);
  oConsole.fOutput("%s: Waiting for connection to terminate..." % oConnection);
  assert oConnection.fbWait(nzTimeoutInSeconds = 1), \
      "%s did not disconnect in a reasonable time!?";

def fStartTransactionIfPossible(oConnection):
  if hasattr(oConnection, "fbStartTransaction"):
    oConsole.fOutput("%s: Starting transaction..." % oConnection);
    assert oConnection.fbStartTransaction(), \
        "Could not start a transaction on %s!?" % oConnection;

def fEndTransactionIfPossible(oConnection):
  if hasattr(oConnection, "fEndTransaction"):
    oConsole.fOutput("%s: Ending transaction..." % oConnection);
    oConnection.fEndTransaction();

def fTestConnectionAndAcceptor(cConnection, cConnectionAcceptor):
  def __fHandleServerSideConnection(oAcceptor, oConnection):
    oConsole.fOutput("Server side: New connection %s." % oConnection);
    
    fStartTransactionIfPossible(oConnection);
    fWaitForAndReadData(oConnection);
    fWriteData(oConnection);
    fEndTransactionIfPossible(oConnection);
    
    fDisconnectAndWait(oConnection)
    
    oConsole.fOutput("Server side: Ended connection %s." % oConnection);
    
    oConsole.fOutput("Stopping acceptor %s..." % oAcceptor);
    oAcceptor.fStop();
  
  # Function code starts here
  oConsole.fOutput("Creating Acceptor...");
  oAcceptor = cConnectionAcceptor(__fHandleServerSideConnection, gsHostname, guPort);
  oConsole.fOutput("  Acceptor(%s): Listening on %s:%d." % (oAcceptor, gsHostname, guPort));
  
  oConsole.fOutput("Creating Connection...");
  oConnection = cConnection.foConnectTo(gsHostname, guPort);
  oConsole.fOutput("Client side: New connection %s." % oConnection);
  
  fStartTransactionIfPossible(oConnection);
  fWriteData(oConnection);
  fWaitForAndReadData(oConnection);  
  fEndTransactionIfPossible(oConnection);
  
  fDisconnectAndWait(oConnection)
  oConsole.fOutput("Client side: Ended connection %s." % oConnection);

  oConsole.fOutput("Waiting for acceptor %s to stop..." % oAcceptor);
  assert oAcceptor.fbWait(nzTimeoutInSeconds = 1), \
      "Acceptor did not terminate in a reasonable time!?";

  oConsole.fOutput("Done.");