import time;

try: # mDebugOutput use is Optional
  from mDebugOutput import ShowDebugOutput, fShowDebugOutput;
except ModuleNotFoundError as oException:
  if oException.args[0] != "No module named 'mDebugOutput'":
    raise;
  ShowDebugOutput = lambda fx: fx; # NOP
  fShowDebugOutput = lambda x, s0 = None: x; # NOP

from mMultiThreading import cLock;
from mNotProvided import \
  fAssertType;

from .cBufferedTCPIPConnection import cBufferedTCPIPConnection;
from .mExceptions import \
    cTCPIPConnectionCannotBeUsedConcurrentlyException, \
    cTCPIPConnectionDisconnectedException, \
    cTCPIPConnectionShutdownException;

gnDeadlockTimeoutInSeconds = 1; # We're not doing anything time consuming, so this should suffice.

class cTransactionalBufferedTCPIPConnection(cBufferedTCPIPConnection):
  @classmethod
  @ShowDebugOutput
  def __faoWaitUntilSomeStateAndStartTransactions(cClass,
    aoConnections,
    sWaitingUntilState,
    faoWaitUntilSomeState,
    n0WaitTimeoutInSeconds,
    n0TransactionTimeoutInSeconds
  ):
    # Keep track of which connections are in the waiting state and which
    # connects we have started transactions on, so we can undo this if an
    # exception is thrown.
    aoConnectionsWaitingForSomeState = [];
    aoConnectionsWithStartedTransactions = [];
    try:
      for oConnection in aoConnections:
        try:
          oConnection.__fStartWaitingUntilSomeState(sWaitingUntilState);
        except cTCPIPConnectionCannotBeUsedConcurrentlyException as oException:
          assert oConnection.bStopping, \
            "Cannot wait until %s on %s: %s" % (sWaitingUntilState, repr(oConnection), repr(oException));
        else:
          aoConnectionsWaitingForSomeState.append(oConnection);
      aoConnectionsInSomeState = faoWaitUntilSomeState(
        aoConnectionsWaitingForSomeState,
        n0WaitTimeoutInSeconds = n0WaitTimeoutInSeconds,
      );
      for oConnection in aoConnectionsWaitingForSomeState[:]:
        # We iterate over a copy because we modify the list, which could cause items to be skipped otherwise.
        bStartTransaction = oConnection in aoConnectionsInSomeState;
        aoConnectionsWaitingForSomeState.remove(oConnection);
        oConnection.__fEndWaitingUntilSomeState(
          sWaitingUntilState,
          bStartTransaction = bStartTransaction,
          n0TransactionTimeoutInSeconds = n0TransactionTimeoutInSeconds,
        );
        if not oConnection.__bStopping and bStartTransaction:
          aoConnectionsWithStartedTransactions.append(oConnection);
    except Exception as oException:
      fShowDebugOutput("Exception: %s(%s)" % (oException.__class__.__name__, oException));
      for oConnection in aoConnectionsWaitingForSomeState:
        oConnection.__fEndWaitingUntilSomeState(
          sWaitingUntilState,
          bStartTransaction = False,
        );
      for oConnection in aoConnectionsWithStartedTransactions:
        oConnection.fEndTransaction();
      raise;
    return aoConnectionsWithStartedTransactions;
  
  @classmethod
  @ShowDebugOutput
  def faoWaitUntilBytesAreAvailableForReadingAndStartTransactions(cClass,
    aoConnections,
    *,
    n0WaitTimeoutInSeconds = None,
    n0TransactionTimeoutInSeconds = None,
  ):
    fAssertType("aoConnections", aoConnections, [cTransactionalBufferedTCPIPConnection]);
    return cClass.__faoWaitUntilSomeStateAndStartTransactions(
      aoConnections,
      sWaitingUntilState = "bytes are available for reading",
      faoWaitUntilSomeState = super(cTransactionalBufferedTCPIPConnection, cClass).faoWaitUntilBytesAreAvailableForReading,
      n0WaitTimeoutInSeconds = n0WaitTimeoutInSeconds,
      n0TransactionTimeoutInSeconds = n0TransactionTimeoutInSeconds,
    );
  
  @classmethod
  @ShowDebugOutput
  def faoWaitUntilTransactionsCanBeStartedAndStartTransactions(cClass,
    aoConnections,
    *,
    n0WaitTimeoutInSeconds = None,
    n0TransactionTimeoutInSeconds = None,
  ):
    fAssertType("aoConnections", aoConnections, [cTransactionalBufferedTCPIPConnection]);
    return cClass.__faoWaitUntilSomeStateAndStartTransactions(
      aoConnections,
      sWaitingUntilState = "transaction can be started",
      faoWaitUntilSomeState = cTransactionalBufferedTCPIPConnection.__faoWaitUntilTransactionCanBeStarted,
      n0WaitTimeoutInSeconds = n0WaitTimeoutInSeconds,
      n0TransactionTimeoutInSeconds = n0TransactionTimeoutInSeconds,
    );
  @classmethod
  @ShowDebugOutput
  def __faoWaitUntilTransactionCanBeStarted(oSelf,
    aoConnections,
    n0TimeoutInSeconds,
  ):
    fAssertType("aoConnections", aoConnections, [cTransactionalBufferedTCPIPConnection]);
    aoUnlockedTransactionLocks = cLock.faoWaitUntilLocksAreUnlocked(
      aoLocks = [
        oConnection.__oTransactionLock
        for oConnection in aoConnections
      ],
      n0TimeoutInSeconds = n0TimeoutInSeconds,
    );
    return [
      oConnection
      for oConnection in aoConnections
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
    oSelf.__s0WaitingUntilState = None;
    oSelf.__oTransactionLock = cLock(
      "%s.__oTransactionLock" % oSelf.__class__.__name__
    );
    oSelf.__n0TransactionEndTime = None;
    super(cTransactionalBufferedTCPIPConnection, oSelf).__init__(*txArguments, **dxArguments);
    oSelf.fAddEvents("transaction started", "transaction ended");
  
  @ShowDebugOutput
  def fStartTransaction(oSelf,
    *,
    n0TimeoutInSeconds = None,
    sWhile = "starting transaction",
  ):
    # Start a transaction if no transaction is currently active and no one is
    # waiting for bytes to be available for reading to start a transaction.
    # Returns True if a transaction was started, False if one was active.
    # Can throw a disconnected exception.
    if not oSelf.bConnected or oSelf.__bStopping:
      raise cTCPIPConnectionDisconnectedException(
        "Connection %s was disconnected while %s." % (
          oSelf.fsGetEndPointsAndDirection(),
          sWhile,
        ),
        oConnection = oSelf,
      );
    oSelf.__oPropertiesLock.fAcquire();
    try:
      if oSelf.__oWaitingUntilSomeStateLock.bLocked:
        # Somebody is waiting for bytes to be available for reading or to be
        # able to start a transaction on this connection so we cannot start
        # a transaction at this time.
        fShowDebugOutput(oSelf, "Waiting until %s; cannot start transaction" % oSelf.__s0WaitingUntilState);
        raise cTCPIPConnectionCannotBeUsedConcurrentlyException(
          "Connection %s is already waiting until %s while %s." % (
            oSelf.fsGetEndPointsAndDirection(),
            oSelf.__s0WaitingUntilState,
            sWhile,
          ),
          oConnection = oSelf,
        );
      if not oSelf.__oTransactionLock.fbAcquire():
        # Somebody has already started a transaction on this connection.
        fShowDebugOutput(oSelf, "Transaction already started");
        raise cTCPIPConnectionCannotBeUsedConcurrentlyException(
          "Connection %s is already in a transaction while %s." % (
            oSelf.fsGetEndPointsAndDirection(),
            sWhile,
          ),
          oConnection = oSelf,
        );
      fShowDebugOutput(oSelf, "Transaction lock acquired.");
      # A transaction requires communication from both sides: if the connection
      # is shut down or dicsonnected, we cannot start a transaction.
      try:
        oSelf.fThrowExceptionIfShutdownOrDisconnected();
      except cTCPIPConnectionShutdownException:
        # If we are shut down, we should disconnect, end the transaction, and raise a
        # disconnected exception.
        fShowDebugOutput(oSelf, "Connection is shut down; disconnecting");
        try:
          oSelf.fDisconnect();
        finally:
          fShowDebugOutput(oSelf, "Releasing transaction lock because connection is disconnected.");
          oSelf.__oTransactionLock.fbRelease();
        oSelf.fThrowExceptionIfShutdownOrDisconnected();
      except cTCPIPConnectionDisconnectedException:
        # If we are disconnected we should end the transaction, and re-raise the exception.
        fShowDebugOutput(oSelf, "Releasing transaction lock because connection is disconnected.");
        oSelf.__oTransactionLock.fbRelease();
        raise;
      fShowDebugOutput(oSelf, "Transaction started.");
      oSelf.__n0TransactionEndTime = time.time() + n0TimeoutInSeconds if n0TimeoutInSeconds is not None else None;
    finally:
      oSelf.__oPropertiesLock.fRelease();
    oSelf.fPostponeTerminatedCallback();
    oSelf.fFireCallbacks("transaction started", {"n0TimeoutInSeconds": n0TimeoutInSeconds});
  
  @ShowDebugOutput
  def fRestartTransaction(oSelf,
    *,
    n0TimeoutInSeconds = None,
    sWhile = "restarting transaction",
  ):
    # End the current transaction and start a new one, with a new timeout,
    # but without unlocking the connection. As a result, no other transaction
    # is allowed in between: the new transaction immediately follow the old one.
    # Can throw a disconnected exception.
    if not oSelf.bConnected or oSelf.__bStopping:
      raise cTCPIPConnectionDisconnectedException(
        "Connection %s was disconnected while %s." % (
          oSelf.fsGetEndPointsAndDirection(),
          sWhile,
        ),
        oConnection = oSelf,
      );
    oSelf.fFireCallbacks("transaction ended");
    oSelf.__oPropertiesLock.fAcquire();
    try:
      assert not oSelf.__oWaitingUntilSomeStateLock.bLocked, \
        "The connection %s is waiting until %s; cannot restart transaction!" % (oSelf, oSelf.__s0WaitingUntilState);
      assert oSelf.__oTransactionLock.bLocked, \
        "The connection %s is not in a transaction; cannot restart!" % (oSelf,);
      oSelf.__n0TransactionEndTime = time.time() + n0TimeoutInSeconds if n0TimeoutInSeconds else None;
    finally:
      oSelf.__oPropertiesLock.fRelease();
    oSelf.fFireCallbacks("transaction started", {"n0TimeoutInSeconds": n0TimeoutInSeconds});
  
  @property
  def bInTransaction(oSelf):
    return oSelf.__oTransactionLock.bLocked;
  
  @property
  def n0TransactionTimeoutInSeconds(oSelf):
    oSelf.__oPropertiesLock.fAcquire();
    try:
      assert oSelf.bInTransaction, \
          "A transaction must be started before you can get its timeout!";
      return max(0, oSelf.__n0TransactionEndTime - time.time()) if oSelf.__n0TransactionEndTime is not None else None;
    finally:
      oSelf.__oPropertiesLock.fRelease();
  
  @ShowDebugOutput
  def fEndTransaction(oSelf):
    try:
      if oSelf.__bStopping:
        super(cTransactionalBufferedTCPIPConnection, oSelf).fStop();
      oSelf.__oPropertiesLock.fAcquire();
      try:
        oSelf.__oTransactionLock.fRelease();
        fShowDebugOutput(oSelf, "Ended transaction");
        oSelf.__n0TransactionEndTime = None;
      finally:
        oSelf.__oPropertiesLock.fRelease();
      oSelf.fFireCallbacks("transaction ended");
    finally:
      oSelf.fFireTerminatedCallbackIfPostponed();
  
  def __fStartWaitingUntilSomeState(oSelf,
    sWaitingUntilState,
  ):
    oSelf.__oPropertiesLock.fAcquire();
    try:
      if not oSelf.__oTransactionLock.fbAcquire():
        fShowDebugOutput(oSelf, "Transaction started; cannot wait until %s" % sWaitingUntilState);
        raise cTCPIPConnectionCannotBeUsedConcurrentlyException(
          "Connection %s is already in a transaction while attempting to wait until %s." % (
            oSelf.fsGetEndPointsAndDirection(),
            sWaitingUntilState,
          ),
          oConnection = oSelf,
        );
      fShowDebugOutput(oSelf, "Started transaction to start waiting until %s" % sWaitingUntilState);
      try:
        if not oSelf.__oWaitingUntilSomeStateLock.fbAcquire():
          fShowDebugOutput(oSelf, "Already waiting until %s; cannot wait until %s" % (oSelf.__s0WaitingUntilState, sWaitingUntilState));
          # Somebody else is waiting for bytes to be available for reading to start a transaction on this connection.
          raise cTCPIPConnectionCannotBeUsedConcurrentlyException(
            "Connection %s is already waiting until %s while attempting to wait until %s." % (
              oSelf.fsGetEndPointsAndDirection(),
              oSelf.__s0WaitingUntilState,
              sWaitingUntilState,
            ),
            oConnection = oSelf,
          );
      finally:
        # We are not starting a transaction yet, so do not keep this lock.
        oSelf.__oTransactionLock.fRelease();
        fShowDebugOutput(oSelf, "Ended transaction to start waiting until %s" % sWaitingUntilState);
      fShowDebugOutput(oSelf, "Waiting until %s..." % sWaitingUntilState);
      oSelf.__s0WaitingUntilState = sWaitingUntilState;
    finally:
      oSelf.__oPropertiesLock.fRelease();
  
  def __fEndWaitingUntilSomeState(oSelf,
    sWaitingUntilState,
    *,
    bStartTransaction = False,
    n0TransactionTimeoutInSeconds = None,
  ):
    oSelf.__oPropertiesLock.fAcquire();
    if bStartTransaction:
      oSelf.fPostponeTerminatedCallback();
      bTransactionStarted = False;
    try:
      assert sWaitingUntilState == oSelf.__s0WaitingUntilState, \
          "Code was %s but is now ending waiting until %s!?" % \
          ("waiting until " % oSelf.__s0WaitingUntilState if oSelf.__s0WaitingUntilState else "not waiting for anything", sWaitingUntilState);
      # Start a transaction before ending the wait, to avoid a race condition.
      fShowDebugOutput(oSelf, "Done waiting until %s%s..." % (sWaitingUntilState, "; starting transaction" if bStartTransaction else ""));
      if bStartTransaction:
        assert oSelf.__oTransactionLock.fbAcquire(), \
            "Cannot lock transaction lock (%s)!?" % oSelf.__oTransactionLock;
        bTransactionStarted = True;
        fShowDebugOutput(oSelf, "Started transaction after waiting until %s" % sWaitingUntilState);
        oSelf.__n0TransactionEndTime = time.time() + n0TransactionTimeoutInSeconds if n0TransactionTimeoutInSeconds else None;
      oSelf.__oWaitingUntilSomeStateLock.fRelease();
      oSelf.__s0WaitingUntilState = None;
    except:
      if bStartTransaction:
        if bTransactionStarted:
          oSelf.__oTransactionLock.fbRelease();
        oSelf.fFireTerminatedCallbackIfPostponed();
    finally:
      oSelf.__oPropertiesLock.fRelease();
    if bStartTransaction:
      oSelf.fFireCallbacks("transaction started", {"n0TransactionTimeoutInSeconds": n0TransactionTimeoutInSeconds});
  
  @property
  def bStopping(oSelf):
    return oSelf.__bStopping or super(cTransactionalBufferedTCPIPConnection, oSelf).bStopping;
  
  @ShowDebugOutput
  def fStop(oSelf):
    oSelf.__bStopping = True;
    if not oSelf.bConnected:
      fShowDebugOutput(oSelf, "Stopped a disconnected connection.");
      super(cTransactionalBufferedTCPIPConnection, oSelf).fStop();
      return;
    oSelf.__oPropertiesLock.fAcquire();
    try:
      bInTransaction = oSelf.__oTransactionLock.bLocked
      bWaitingBeforeStartingATransaction = not bInTransaction and oSelf.__oWaitingUntilSomeStateLock.bLocked;
      # If we are waiting to start a connection, we will disconnect to stop.
      if bWaitingBeforeStartingATransaction:
        fShowDebugOutput(oSelf, "Stopping a connection by disconnecting while waiting until some state before starting a transaction.");
        super(cTransactionalBufferedTCPIPConnection, oSelf).fDisconnect();
      elif not bInTransaction:
        fShowDebugOutput(oSelf, "Stopped an idle connection.");
        assert oSelf.__oTransactionLock.fbAcquire(), \
            "Cannot lock transaction lock (%s)!?" % oSelf.__oTransactionLock;
        try:
          super(cTransactionalBufferedTCPIPConnection, oSelf).fStop();
        finally:
          oSelf.__oTransactionLock.fRelease();
    finally:
      oSelf.__oPropertiesLock.fRelease();
  
  @ShowDebugOutput
  def fWaitUntilBytesAreAvailableForReadingAndStartTransaction(oSelf,
    *,
    n0WaitTimeoutInSeconds = None,
    n0TransactionTimeoutInSeconds = None,
  ):
    # Wait until bytes are available for reading and then start a transaction.
    # Raise cTCPIPConnectionCannotBeUsedConcurrentlyException if a transaction is
    # currently active or someone else is already waiting until some state.
    # (A transaction if not started in this case).
    # Return True if bytes are available for reading and a transaction was started.
    # Can throw a timeout, shutdown or disconnected exception.
    sWaitingUntilState = "bytes are available for reading";
    oSelf.__fStartWaitingUntilSomeState(sWaitingUntilState);
    try:
      oSelf.fWaitUntilBytesAreAvailableForReading(
        n0WaitTimeoutInSeconds = n0WaitTimeoutInSeconds,
      );
    except:
      oSelf.__fEndWaitingUntilSomeState(
        sWaitingUntilState,
        bStartTransaction = False,
      );
      raise;
    if not oSelf.bConnected or oSelf.__bStopping:
      raise cTCPIPConnectionDisconnectedException(
        "Connection %s was disconnected while waiting until %s." % (
          oSelf.fsGetEndPointsAndDirection(),
          sWaitingUntilState,
        ),
        oConnection = oSelf,
      );
    oSelf.__fEndWaitingUntilSomeState(
      sWaitingUntilState,
      bStartTransaction = True,
      n0TransactionTimeoutInSeconds = n0TransactionTimeoutInSeconds,
    );
  
  def fsbReadAvailableBytes(oSelf, *txArguments, **dxArguments):
    assert oSelf.bInTransaction, \
        "A transaction must be started before bytes can be read from this connection!";
    return super(cTransactionalBufferedTCPIPConnection, oSelf).fsbReadAvailableBytes(*txArguments, **dxArguments);
  
  def fsbReadBytesUntilDisconnected(oSelf,
    *,
    u0MaxNumberOfBytes = None,
  ):
    assert oSelf.bInTransaction, \
        "A transaction must be started before bytes can be read from this connection!";
    return super(cTransactionalBufferedTCPIPConnection, oSelf).fsbReadBytesUntilDisconnected( \
        u0MaxNumberOfBytes = u0MaxNumberOfBytes, n0TimeoutInSeconds = oSelf.n0TransactionTimeoutInSeconds);
  
  def fsbReadBytes(oSelf,
    uNumberOfBytes,
  ):
    assert oSelf.bInTransaction, \
        "A transaction must be started before bytes can be read from this connection!";
    return super(cTransactionalBufferedTCPIPConnection, oSelf).fsbReadBytes( \
        uNumberOfBytes = uNumberOfBytes, n0TimeoutInSeconds = oSelf.n0TransactionTimeoutInSeconds);
  
  def fsb0ReadUntilMarker(oSelf,
    sbMarker,
    u0MaxNumberOfBytes = None,
  ):
    assert oSelf.bInTransaction, \
        "A transaction must be started before bytes can be read from this connection!";
    return super(cTransactionalBufferedTCPIPConnection, oSelf).fsb0ReadUntilMarker( \
        sbMarker = sbMarker, u0MaxNumberOfBytes = u0MaxNumberOfBytes, n0TimeoutInSeconds = oSelf.n0TransactionTimeoutInSeconds);
  
  def fShutdownForReading(oSelf, *txArguments, **dxArguments):
    assert oSelf.bInTransaction, \
        "A transaction must be started before this connection can be shut down for reading!";
    return super(cTransactionalBufferedTCPIPConnection, oSelf).fShutdownForReading(*txArguments, **dxArguments);
  
  def fuWriteBytes(oSelf,
    sbBytes,
  ):
    assert oSelf.bInTransaction, \
        "A transaction must be started before bytes can be written to this connection!";
    return super(cTransactionalBufferedTCPIPConnection, oSelf).fuWriteBytes( \
        sbBytes = sbBytes, n0TimeoutInSeconds = oSelf.n0TransactionTimeoutInSeconds);
  
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
