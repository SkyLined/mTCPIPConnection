import time;

try: # mDebugOutput use is Optional
  from mDebugOutput import *;
except: # Do nothing if not available.
  ShowDebugOutput = lambda fxFunction: fxFunction;
  fShowDebugOutput = lambda sMessage: None;
  fEnableDebugOutputForModule = lambda mModule: None;
  fEnableDebugOutputForClass = lambda cClass: None;
  fEnableAllDebugOutput = lambda: None;
  cCallStack = fTerminateWithException = fTerminateWithConsoleOutput = None;

from mMultiThreading import cLock;

from .cBufferedTCPIPConnection import cBufferedTCPIPConnection;
from .mExceptions import *;
from .mNotProvided import *;

gnDeadlockTimeoutInSeconds = 1; # We're not doing anything time consuming, so this should suffice.

class cTransactionalBufferedTCPIPConnection(cBufferedTCPIPConnection):
  @classmethod
  @ShowDebugOutput
  def __faoWaitUntilSomeStateAndStartTransactions(cClass,
    aoConnections, sState,
    faoWaitUntilSomeState,
    n0WaitTimeoutInSeconds, n0TransactionTimeoutInSeconds
  ):
    # Keep track of which connections are in the waiting state and which
    # connects we have started transactions on, so we can undo this if an
    # exception is thrown.
    aoConnectionsWaitingForSomeState = [];
    aoConnectionsWithStartedTransactions = [];
    try:
      for oConnection in aoConnections:
        if not oConnection.__fbStartWaitingUntilSomeState():
          assert oConnection.bStopping, \
            "Cannot wait until %s on %s" % (sState, repr(oConnection));
        else:
          aoConnectionsWaitingForSomeState.append(oConnection);
      aoConnectionsInSomeState = faoWaitUntilSomeState(aoConnectionsWaitingForSomeState, n0WaitTimeoutInSeconds);
      for oConnection in aoConnectionsWaitingForSomeState[:]:
        # We iterate over a copy because we modify the list, which could cause items to be skipped otherwise.
        bStartTransaction = oConnection in aoConnectionsInSomeState;
        aoConnectionsWaitingForSomeState.remove(oConnection);
        oConnection.__fEndWaitingUntilSomeState(
          bStartTransaction = bStartTransaction,
          n0TransactionTimeoutInSeconds = n0TransactionTimeoutInSeconds
        );
        if bStartTransaction:
          aoConnectionsWithStartedTransactions.append(oConnection);
    except Exception as oException:
      for oConnection in aoConnectionsWaitingForSomeState:
        oConnection.__fEndWaitingUntilSomeState(bStartTransaction = False);
      for oConnection in aoConnectionsWithStartedTransactions:
        oConnection.fEndTransaction();
      raise;
    return aoConnectionsWithStartedTransactions;
  
  @classmethod
  @ShowDebugOutput
  def faoWaitUntilBytesAreAvailableForReadingAndStartTransactions(cClass, aoConnections, n0WaitTimeoutInSeconds = None, n0TransactionTimeoutInSeconds = None):
    return cClass.__faoWaitUntilSomeStateAndStartTransactions(
      aoConnections, sState = "bytes are available for reading",
      faoWait = super(cTransactionalBufferedTCPIPConnection, cClass).faoWaitUntilBytesAreAvailableForReading,
      n0WaitTimeoutInSeconds = n0WaitTimeoutInSeconds,
      n0TransactionTimeoutInSeconds = n0TransactionTimeoutInSeconds,
    );
  
  @classmethod
  @ShowDebugOutput
  def faoWaitUntilTransactionsCanBeStartedAndStartTransactions(cClass, aoConnections, n0WaitTimeoutInSeconds = None, n0TransactionTimeoutInSeconds = None):
    return cClass.__faoWaitUntilSomeStateAndStartTransactions(
      aoConnections, sState = "transaction can be started",
      faoWait = cTransactionalBufferedTCPIPConnection.__faoWaitUntilTransactionCanBeStarted,
      n0WaitTimeoutInSeconds = n0WaitTimeoutInSeconds,
      n0TransactionTimeoutInSeconds = n0TransactionTimeoutInSeconds,
    );
  @classmethod
  @ShowDebugOutput
  def __faoWaitUntilTransactionCanBeStarted(oSelf, aoConnections, n0TimeoutInSeconds):
    aoUnlockedTransactionLocks = cLock.faoWaitUntilLocksAreUnlocked(
      aoLocks = [
        oConnection.__oTransactionLock
        for oConnection in aoConnections
      ],
      n0TimeoutInSeconds = n0TimeoutInSeconds,
    );
    return [
      oConnection
      for oConnection in aoConnectons
      if oConnection.__oTransactionLock in aoUnlockedTransactionLocks
    ];
  
  def __init__(oSelf, *txArguments, **dxArguments):
    oSelf.__bStopping = False;
    # A properties lock is used to make sure different threads can perform
    # multiple read/writes on properties of this instance as a single operation.
    oSelf.__oPropertiesLock = cLock(
      "%s.__oPropertiesLock" % oSelf.__class__.__name__,
      n0DeadlockTimeoutInSeconds = gnDeadlockTimeoutInSeconds
    );
    oSelf.__oWaitingUntilSomeStateLock = cLock(
      "%s.__oWaitingUntilSomeStateLock" % oSelf.__class__.__name__
    );
    oSelf.__oTransactionLock = cLock(
      "%s.__oTransactionLock" % oSelf.__class__.__name__
    );
    oSelf.__n0TransactionEndTime = None;
    super(cTransactionalBufferedTCPIPConnection, oSelf).__init__(*txArguments, **dxArguments);
    oSelf.fAddEvents("transaction started", "transaction ended");
  
  @ShowDebugOutput
  def fbStartTransaction(oSelf, n0TimeoutInSeconds = None, sWhile = "starting transaction"):
    # Start a transaction if no transaction is currently active and no one is
    # waiting for bytes to be available for reading to start a transaction.
    # Returns True if a transaction was started, False if one was active.
    # Can throw a disconnected exception.
    if not oSelf.bConnected or oSelf.__bStopping:
      raise cTCPIPConnectionDisconnectedException("Disconnected while %s" % sWhile, {"n0TimeoutInSeconds": n0TimeoutInSeconds});
    oSelf.__oPropertiesLock.fAcquire();
    try:
      if oSelf.__oWaitingUntilSomeStateLock.bLocked:
        # Somebody is waiting for bytes to be available for reading or to be
        # able to start a transaction on this connection so we cannot start
        # a transaction at this time.
        fShowDebugOutput("Waiting until some state; cannot start transaction");
        return False;
      if not oSelf.__oTransactionLock.fbAcquire():
        # Somebody has already started a transaction on this connection.
        return False;
      oSelf.__n0TransactionEndTime = time.clock() + n0TimeoutInSeconds if n0TimeoutInSeconds is not None else None;
    finally:
      oSelf.__oPropertiesLock.fRelease();
    oSelf.fFireCallbacks("transaction started", {"n0TimeoutInSeconds": n0TimeoutInSeconds});
    return True;

  @ShowDebugOutput
  def fRestartTransaction(oSelf, n0TimeoutInSeconds = None, sWhile = "restarting transaction"):
    # End the current transaction and start a new one, with a new timeout,
    # but without unlocking the connection. As a result, no other transaction
    # is allowed in between: the new transaction immediately follow the old one.
    # Can throw a disconnected exception.
    if not oSelf.bConnected or oSelf.__bStopping:
      raise cTCPIPConnectionDisconnectedException("Disconnected while %s" % sWhile, {"n0TimeoutInSeconds": n0TimeoutInSeconds});
    oSelf.fFireCallbacks("transaction ended");
    oSelf.__oPropertiesLock.fAcquire();
    try:
      oSelf.__n0TransactionEndTime = time.clock() + n0TimeoutInSeconds if n0TimeoutInSeconds else None;
    finally:
      oSelf.__oPropertiesLock.fRelease();
    oSelf.fFireCallbacks("transaction started", {"n0TimeoutInSeconds": n0TimeoutInSeconds});
    return True;
  
  def __fbStartWaitingUntilSomeState(oSelf):
    oSelf.__oPropertiesLock.fAcquire();
    try:
      if not oSelf.__oTransactionLock.fbAcquire():
        # A transaction is currently active.
        return False;
      try:
        if not oSelf.__oWaitingUntilSomeStateLock.fbAcquire():
          # Somebody else is waiting for bytes to be available for reading to start a transaction on this connection.
          return False;
      finally:
        # We are not starting a transaction yet, so do not keep this lock.
        oSelf.__oTransactionLock.fbRelease();
    finally:
      oSelf.__oPropertiesLock.fRelease();
    return True;
  def __fEndWaitingUntilSomeState(oSelf, bStartTransaction, n0TransactionTimeoutInSeconds = None):
    oSelf.__oPropertiesLock.fbAcquire();
    try:
      oSelf.__oWaitingUntilSomeStateLock.fRelease();
      if bStartTransaction:
        assert oSelf.__oTransactionLock.fbAcquire(), \
            "Nobody is waiting for bytes to be available"
        oSelf.__n0TransactionEndTime = time.clock() + n0TransactionTimeoutInSeconds if n0TransactionTimeoutInSeconds else None;
    finally:
      oSelf.__oPropertiesLock.fRelease();
    if bStartTransaction:
      oSelf.fFireCallbacks("transaction started", {"n0TransactionTimeoutInSeconds": n0TransactionTimeoutInSeconds});
  
  @property
  def bInTransaction(oSelf):
    return oSelf.__oTransactionLock.bLocked;
  
  @property
  def n0TransactionTimeoutInSeconds(oSelf):
    oSelf.__oPropertiesLock.fbAcquire();
    try:
      assert oSelf.bInTransaction, \
          "A transaction must be started before you can get its timeout!";
      return max(0, oSelf.__n0TransactionEndTime - time.clock()) if oSelf.__n0TransactionEndTime is not None else None;
    finally:
      oSelf.__oPropertiesLock.fRelease();
  
  @ShowDebugOutput
  def fEndTransaction(oSelf):
    if oSelf.__bStopping:
      super(cTransactionalBufferedTCPIPConnection, oSelf).fStop();
    oSelf.__oPropertiesLock.fbAcquire();
    try:
      oSelf.__oTransactionLock.fRelease();
      oSelf.__n0TransactionEndTime = None;
    finally:
      oSelf.__oPropertiesLock.fRelease();
    oSelf.fFireCallbacks("transaction ended");
  
  def fSecure(oSelf,
    oSSLContext,
    n0TimeoutInSeconds = None,
  ):
    assert oSelf.fbStartTransaction(nzTimeoutInSeconds), \
        "Cannot start a transaction to secure the connection!?";
    try:
      return super(cTransactionalBufferedTCPIPConnection, oSelf).fSecure(
        oSSLContext,
        n0zTimeoutInSeconds = n0TimeoutInSeconds,
      );
    finally:
      oSelf.fEndTransaction();

  @property
  def bStopping(oSelf):
    return oSelf.__bStopping or super(cTransactionalBufferedTCPIPConnection, oSelf).bStopping;
  
  @ShowDebugOutput
  def fStop(oSelf):
    oSelf.__bStopping = True;
    # If we are no longer connected or if we can start a transaction, we can stop immediately:
    if not oSelf.bConnected or oSelf.__oTransactionLock.fbAcquire(nTimeoutInSeconds = 0):
      try:
        super(cTransactionalBufferedTCPIPConnection, oSelf).fStop();
      finally:
        oSelf.__nzTransactionEndTime = None;
        oSelf.__oTransactionLock.fRelease();

  @ShowDebugOutput
  def fTerminate(oSelf):
    # fTerminate normally calls fDisconnect but fDisconnect requires a
    # transaction in this class, so we call the super class' fDisconnect to
    # avoid this requirement:
    super(cTransactionalBufferedTCPIPConnection, oSelf).fDisconnect();
  
  @ShowDebugOutput
  def fbWaitUntilBytesAreAvailableForReadingAndStartTransaction(oSelf, nzWaitTimeoutInSeconds = None, nzTransactionTimeoutInSeconds = None):
    # Wait until bytes are available for reading and then start a transaction.
    # Return False if a transaction is currently active or someone else is
    # already waiting until bytes are available fore reading. The transaction
    # if not started in this case.
    # Return True if bytes are available for reading and a transaction was started.
    # Can throw a timeout, shutdown or disconnected exception.
    if not oSelf.__fbStartWaitingUntilSomeState():
      return False;
    try:
      fShowDebugOutput("Start waiting for bytes to be available for reading...");
      oSelf.fWaitUntilBytesAreAvailableForReading(nzWaitTimeoutInSeconds);
    except:
      fShowDebugOutput("Stop waiting for bytes to be available for reading.");
      oSelf.__fEndWaitingUntilSomeState(bStartTransaction = False);
      raise;
    fShowDebugOutput("Bytes should now be available for reading; starting transaction...");
    oSelf.__fEndWaitingUntilSomeState(bStartTransaction = True, nzTransactionTimeoutInSeconds = nzTransactionTimeoutInSeconds);
    return True;
  
  def fsReadAvailableBytes(oSelf, *txArguments, **dxArguments):
    assert oSelf.bInTransaction, \
        "A transaction must be started before bytes can be read from this connection!";
    return super(cTransactionalBufferedTCPIPConnection, oSelf).fsReadAvailableBytes(*txArguments, **dxArguments);
  
  def fsReadBytesUntilDisconnected(oSelf, uzMaxNumberOfBytes = None):
    assert oSelf.bInTransaction, \
        "A transaction must be started before bytes can be read from this connection!";
    return super(cTransactionalBufferedTCPIPConnection, oSelf).fsReadBytesUntilDisconnected( \
        uzMaxNumberOfBytes = uzMaxNumberOfBytes, nzTimeoutInSeconds = oSelf.nzTransactionTimeoutInSeconds);
  
  def fsReadBytes(oSelf, uNumberOfBytes):
    assert oSelf.bInTransaction, \
        "A transaction must be started before bytes can be read from this connection!";
    return super(cTransactionalBufferedTCPIPConnection, oSelf).fsReadBytes( \
        uNumberOfBytes = uNumberOfBytes, nzTimeoutInSeconds = oSelf.nzTransactionTimeoutInSeconds);
  
  def fszReadUntilMarker(oSelf, sMarker, uzMaxNumberOfBytes = None):
    assert oSelf.bInTransaction, \
        "A transaction must be started before bytes can be read from this connection!";
    return super(cTransactionalBufferedTCPIPConnection, oSelf).fszReadUntilMarker( \
        sMarker = sMarker, uzMaxNumberOfBytes = uzMaxNumberOfBytes, nzTimeoutInSeconds = oSelf.nzTransactionTimeoutInSeconds);
  
  def fShutdownForReading(oSelf, *txArguments, **dxArguments):
    assert oSelf.bInTransaction, \
        "A transaction must be started before this connection can be shut down for reading!";
    return super(cTransactionalBufferedTCPIPConnection, oSelf).fShutdownForReading(*txArguments, **dxArguments);
  
  def fuWriteBytes(oSelf, sBytes):
    assert oSelf.bInTransaction, \
        "A transaction must be started before bytes can be written to this connection!";
    return super(cTransactionalBufferedTCPIPConnection, oSelf).fuWriteBytes( \
        sBytes = sBytes, nzTimeoutInSeconds = oSelf.nzTransactionTimeoutInSeconds);
  
  def fShutdownForWriting(oSelf, *txArguments, **dxArguments):
    assert oSelf.bInTransaction, \
        "A transaction must be started before this connection can be shut down for writing!";
    return super(cTransactionalBufferedTCPIPConnection, oSelf).fShutdownForWriting(*txArguments, **dxArguments);
  
  def fShutdown(oSelf, *txArguments, **dxArguments):
    assert oSelf.bInTransaction, \
        "A transaction must be started before this connection can be shut down!";
    return super(cTransactionalBufferedTCPIPConnection, oSelf).fShutdown(*txArguments, **dxArguments);
  
  def fDisconnect(oSelf, *txArguments, **dxArguments):
    assert oSelf.bInTransaction, \
        "A transaction must be started before this connection can be disconnected!";
    return super(cTransactionalBufferedTCPIPConnection, oSelf).fDisconnect(*txArguments, **dxArguments);
  
  def fasGetDetails(oSelf):
    asDetails = super(cTransactionalBufferedTCPIPConnection, oSelf).fasGetDetails();
    if oSelf.bInTransaction:
      asDetails.append("in transaction");
      if oSelf.__bStopping and not super(cTransactionalBufferedTCPIPConnection, oSelf).bStopping:
        asDetails.append("stopping after transaction ends");
    return asDetails;
