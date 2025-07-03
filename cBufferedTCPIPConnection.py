import time;

try: # mDebugOutput use is Optional
  from mDebugOutput import ShowDebugOutput, fShowDebugOutput;
except ModuleNotFoundError as oException:
  if oException.args[0] != "No module named 'mDebugOutput'":
    raise;
  ShowDebugOutput = lambda fx: fx; # NOP
  fShowDebugOutput = lambda x, s0 = None: x; # NOP

from mNotProvided import (
  fAssertType,
  zNotProvided,
);

from .cTCPIPConnection import cTCPIPConnection;
from .mExceptions import (
  cTCPIPConnectionDisconnectedException,
  cTCPIPConnectionShutdownException,
  cTCPIPDataTimeoutException,
);

# We cannot use select.select to wait for data to be available for reading
# for secure connections, 
gnAreBytesAvailableForReadingForSecureConnectionsPollIntervalInSeconds = 0.1; 

class cBufferedTCPIPConnection(cTCPIPConnection):
  # Note that only reads buffered: writes are not!
  # If the connection is passively shutdown or disconnected (i.e. without
  # calling a shutdown or disconnect method, e.g. by the remote or because of
  # network issues) bytes can still be read from the buffer until it is empty.
  # If the connection is actively shutdown or disconnected, the read buffer
  # is discarded and no further reads will be possible.
  
  @classmethod
  @ShowDebugOutput
  def faoWaitUntilBytesAreAvailableForReadingOrShutdown(cClass,
    aoConnections,
    *,
    n0WaitTimeoutInSeconds = None,
  ):
    fAssertType("aoConnections", aoConnections, [cBufferedTCPIPConnection]);
    fAssertType("n0WaitTimeoutInSeconds", n0WaitTimeoutInSeconds, int, float, None);
    # select.select does not work well on secure sockets, so we use the non-secure sockets
    # as proxies; there may be SSL traffic without data being send from the remote end, so
    # we may flag a connection as having data to be read when it has none.
    n0EndTime = time.time() + n0WaitTimeoutInSeconds if n0WaitTimeoutInSeconds is not None else None;
    n0WaitTimeoutInSeconds = n0EndTime - time.time() if n0EndTime is not None else None;
    aoConnectionsWithBytesAvailableForReadingOrShutdown = [
      oConnection
      for oConnection in aoConnections
      if oConnection.bIsShutdownForReading or oConnection.fbBytesAreAvailableForReading()
    ];
    if len(aoConnectionsWithBytesAvailableForReadingOrShutdown) == 0:
      cTCPIPConnection.faoWaitUntilReadEventOnPythonSocket(
        aoConnections,
        n0WaitTimeoutInSeconds = n0WaitTimeoutInSeconds,
      );
      aoConnectionsWithBytesAvailableForReadingOrShutdown = [
        oConnection
        for oConnection in aoConnections
        if oConnection.bIsShutdownForReading or oConnection.fbBytesAreAvailableForReading()
      ];
      assert aoConnectionsWithBytesAvailableForReadingOrShutdown or n0WaitTimeoutInSeconds is not None, \
          "This is not supposed to be possible";
    return aoConnectionsWithBytesAvailableForReadingOrShutdown;
  
  def __init__(oSelf, *txArguments, **dxArguments):
    oSelf.__sbReadBuffer = b"";
    super(cBufferedTCPIPConnection, oSelf).__init__(*txArguments, **dxArguments);
  
  def fSecure(oSelf,
    oSSLContext,
    *,
    n0zTimeoutInSeconds = zNotProvided,
    bzCheckHost = zNotProvided,
  ):
    fAssertType("n0zTimeoutInSeconds", n0zTimeoutInSeconds, int, float, zNotProvided, None);
    assert len(oSelf.__sbReadBuffer) == 0, \
        "This connection cannot be secured because it has data in its read buffer: %s!" % repr(oSelf.__sbReadBuffer);
    return super(cBufferedTCPIPConnection, oSelf).fSecure(
      oSSLContext,
      n0zTimeoutInSeconds = n0zTimeoutInSeconds,
      bzCheckHost = bzCheckHost,
    );
  
  @property
  def bIsShutdownForReading(oSelf):
    # We'll report that the socket allows reading until all bytes have been read from the
    # socket. After that, we'll let the base class decide.
    return not oSelf.fbBytesAreAvailableForReading() and super(cBufferedTCPIPConnection, oSelf).bIsShutdownForReading;
  
  @property
  def bConnected(oSelf):
    # We'll report that the socket is connected until all bytes have been read from the
    # socket. After that, we'll let the base class decide.
    return oSelf.fbBytesAreAvailableForReading() or super(cBufferedTCPIPConnection, oSelf).bConnected;

  @ShowDebugOutput
  def fbBytesAreAvailableForReading(oSelf):
    # if we have buffered bytes, they are available for reading.
    if len(oSelf.__sbReadBuffer) > 0:
      fShowDebugOutput(oSelf, "%d buffered bytes are available for reading" % len(oSelf.__sbReadBuffer));
      return True;
    try:
      oSelf.__sbReadBuffer += super(cBufferedTCPIPConnection, oSelf).fsbReadAvailableBytes(
        u0MaxNumberOfBytes = 1, # We only need one to make sure
      );
    except cTCPIPConnectionShutdownException:
      fShowDebugOutput(oSelf, "Connection shut down; nothing to read.");
      return False;
    except cTCPIPConnectionDisconnectedException:
      fShowDebugOutput(oSelf, "Connection disconnected; nothing to read.");
      return False;
    if len(oSelf.__sbReadBuffer) == 0:
      fShowDebugOutput(oSelf, "0 buffered bytes and nothing to read on the connection.");
      return False;
    if len(oSelf.__sbReadBuffer) > 0:
      fShowDebugOutput(oSelf, "Read %d bytes into buffer." % len(oSelf.__sbReadBuffer));
      return True;
    return False;
  
  @ShowDebugOutput
  def fWaitUntilBytesAreAvailableForReading(oSelf):
    while 1:
      if len(oSelf.__sbReadBuffer) > 0: return;
      try:
        oSelf.__sbReadBuffer += super(cBufferedTCPIPConnection, oSelf).fsbReadAvailableBytes(
          u0MaxNumberOfBytes = 1, # We only need one to make sure
        );
      except cTCPIPConnectionShutdownException:
        break;

  @ShowDebugOutput
  def fbWaitUntilBytesAreAvailableForReading(oSelf,
    *,
    nWaitTimeoutInSeconds = None,
  ):
    while 1:
      if len(oSelf.__sbReadBuffer) > 0:
        return True;
      oSelf.__sbReadBuffer += super(cBufferedTCPIPConnection, oSelf).fsbReadAvailableBytes(
        u0MaxNumberOfBytes = 1, # We only need one to make sure
        n0TimeoutInSeconds = nWaitTimeoutInSeconds,
      );
      return len(oSelf.__sbReadBuffer) > 0;

  @ShowDebugOutput
  def fsbReadAvailableBytes(oSelf,
    *,
    u0MaxNumberOfBytes = None,
    n0TimeoutInSeconds = None,
  ):
    fAssertType("u0MaxNumberOfBytes", u0MaxNumberOfBytes, int, None);
    fAssertType("n0TimeoutInSeconds", n0TimeoutInSeconds, int, float, None);
    if u0MaxNumberOfBytes is not None and len(oSelf.__sbReadBuffer) > 0:
      if u0MaxNumberOfBytes < len(oSelf.__sbReadBuffer):
        # If we have enough bytes buffered, we can return them:
        sbBytes = oSelf.__sbReadBuffer[:u0MaxNumberOfBytes];
        oSelf.__sbReadBuffer = oSelf.__sbReadBuffer[u0MaxNumberOfBytes:];
        return sbBytes;
      # We need to read less because we have some in the buffer
      u0MaxNumberOfBytes -= len(oSelf.__sbReadBuffer);
    try:
      oSelf.__sbReadBuffer += super(cBufferedTCPIPConnection, oSelf).fsbReadAvailableBytes(
        u0MaxNumberOfBytes = u0MaxNumberOfBytes,
        n0TimeoutInSeconds = n0TimeoutInSeconds,
      );
    except (cTCPIPConnectionDisconnectedException, cTCPIPConnectionShutdownException):
      # If we have no bytes in the buffer and we cannot read bytes because the
      # connection was shut down or disconnected, throw the relevant exception.
      # Otherwise, we will return the bytes in the buffer.
      if len(oSelf.__sbReadBuffer) == 0:
        raise;
    if u0MaxNumberOfBytes is None:
      sbBytes = oSelf.__sbReadBuffer;
      oSelf.__sbReadBuffer = b"";
    else:
      sbBytes = oSelf.__sbReadBuffer[:u0MaxNumberOfBytes];
      oSelf.__sbReadBuffer = oSelf.__sbReadBuffer[u0MaxNumberOfBytes:];
    return sbBytes;
  
  @ShowDebugOutput
  def fsbReadBytesUntilShutdown(oSelf,
    *,
    u0MaxNumberOfBytes = None,
    n0TimeoutInSeconds = None,
  ):
    sbBytes = oSelf.__sbReadBuffer;
    oSelf.__sbReadBuffer = b"";
    return sbBytes + super(cBufferedTCPIPConnection, oSelf).fsbReadBytesUntilShutdown(
      u0MaxNumberOfBytes = u0MaxNumberOfBytes,
      n0TimeoutInSeconds = n0TimeoutInSeconds,
    );
  
  def __fReadBytesIntoBuffer(oSelf,
    *,
    uMinNumberOfBytes,
    n0EndTime,
    n0TimeoutInSeconds,
  ):
    # Read data until at least the requested number of bytes is in the buffer.
    # Can throw a timeout, shutdown or disconnected exception.
    # Returns when the requested number of bytes is in the buffer.
    while len(oSelf.__sbReadBuffer) < uMinNumberOfBytes:
      if n0TimeoutInSeconds:
        nRemainingWaitTimeInSeconds = max(0, n0EndTime - time.time());
        if (
          not oSelf.fbWaitUntilBytesAreAvailableForReading(nWaitTimeoutInSeconds = nRemainingWaitTimeInSeconds)
          and not oSelf.bIsShutdownForReading
        ):
          raise cTCPIPDataTimeoutException(
            "Timeout on connection %s while reading after %s seconds." % (
              oSelf.fsGetEndPointsAndDirection(),
              n0TimeoutInSeconds,
            ),
            ozConnection = oSelf,
            nzTimeoutInSeconds = n0TimeoutInSeconds, # should never be None in this code path.
          );
      else:
        oSelf.fWaitUntilBytesAreAvailableForReading();
      sbBytesRead = super(cBufferedTCPIPConnection, oSelf).fsbReadAvailableBytes();
      oSelf.__sbReadBuffer += sbBytesRead;
    fShowDebugOutput(oSelf, "Read bytes to make sure there are at least %d bytes resulted in a %d byte buffer." % \
        (uMinNumberOfBytes, len(oSelf.__sbReadBuffer)));
  
  @ShowDebugOutput
  def fsbReadBytes(oSelf, uNumberOfBytes, n0TimeoutInSeconds = None):
    fAssertType("uNumberOfBytes", uNumberOfBytes, int);
    fAssertType("n0TimeoutInSeconds", n0TimeoutInSeconds, int, float, None);
    # Read data until at least the requested number of bytes is in the buffer.
    # Returns the requested number of bytes, which are removed from the buffer.
    # Can throw a timeout, shutdown or disconnected exception.
    n0EndTime = time.time() + n0TimeoutInSeconds if n0TimeoutInSeconds else None;
    oSelf.__fReadBytesIntoBuffer(
      uMinNumberOfBytes = uNumberOfBytes,
      n0EndTime = n0EndTime,
      n0TimeoutInSeconds = n0TimeoutInSeconds
    );
    sbBytes = oSelf.__sbReadBuffer[:uNumberOfBytes];
    oSelf.__sbReadBuffer = oSelf.__sbReadBuffer[uNumberOfBytes:];
    return sbBytes;
  
  @ShowDebugOutput
  def fsb0ReadUntilMarker(oSelf, sbMarker, u0MaxNumberOfBytes = None, n0TimeoutInSeconds = None):
    fAssertType("sbMarker", sbMarker, bytes);
    fAssertType("u0MaxNumberOfBytes", u0MaxNumberOfBytes, int, None);
    fAssertType("n0TimeoutInSeconds", n0TimeoutInSeconds, int, float, None);
    # Read data into the buffer until the marker is found in the buffer or the
    # Returns the bytes up to and including the marker, which are removed from
    # the buffer.
    # If the marker cannot be found within the max number of bytes, return None
    # Can throw a timeout, shutdown or disconnected exception.
    n0EndTime = time.time() + n0TimeoutInSeconds if n0TimeoutInSeconds else None;
    uMarkerSize = len(sbMarker);
    assert u0MaxNumberOfBytes is None or u0MaxNumberOfBytes >= uMarkerSize, \
        "It is impossible to find %d bytes without reading more than %d bytes" % (uMarkerSize, u0MaxNumberOfBytes);
    uNextFindStartIndex = 0;
    while 1:
      # We need to read enough bytes to be able to start another search (i.e. one).
      uMinNumberOfBytesNeededInBuffer = uNextFindStartIndex + uMarkerSize;
      oSelf.__fReadBytesIntoBuffer(
        uMinNumberOfBytes = uMinNumberOfBytesNeededInBuffer,
        n0EndTime = n0EndTime,
        n0TimeoutInSeconds = n0TimeoutInSeconds,
      );
      # If the marker can be found stop looking.
      uStartIndex = oSelf.__sbReadBuffer.find(sbMarker, uNextFindStartIndex, u0MaxNumberOfBytes);
      if uStartIndex != -1:
        uEndIndex = uStartIndex + uMarkerSize;
        assert u0MaxNumberOfBytes is None or uEndIndex <= u0MaxNumberOfBytes, \
            "The code above should have only found the marker within the max number of bytes, but it was found outside it!";
        sbBytes = oSelf.__sbReadBuffer[:uEndIndex];
        oSelf.__sbReadBuffer = oSelf.__sbReadBuffer[uEndIndex:];
        return sbBytes;
      # The next find operation will not need to scan the entire buffer again:
      uNextFindStartIndex = len(oSelf.__sbReadBuffer) - uMarkerSize + 1;
      uNextFindEndIndex = uNextFindStartIndex + uMarkerSize;
      # If the marker cannot be found within the max number of bytes, return None;
      if u0MaxNumberOfBytes is not None and uNextFindEndIndex > u0MaxNumberOfBytes:
        return None;
  
  def fShutdownForReading(oSelf):
    super(cBufferedTCPIPConnection, oSelf).fShutdownForReading();
    oSelf.__sbReadBuffer = b""; # Whatever is buffered is discarded
  
  def fShutdown(oSelf):
    super(cBufferedTCPIPConnection, oSelf).fShutdown();
    oSelf.__sbReadBuffer = b""; # Whatever is buffered is discarded
  
  def fDisconnect(oSelf):
    super(cBufferedTCPIPConnection, oSelf).fDisconnect();
    oSelf.__sbReadBuffer = b""; # Whatever is buffered is discarded
  
  def fasGetDetails(oSelf):
    asDetails = super(cBufferedTCPIPConnection, oSelf).fasGetDetails();
    uBufferedBytes = len(oSelf.__sbReadBuffer) if oSelf.__sbReadBuffer else 0;
    if uBufferedBytes > 0:
      asDetails.append("%d bytes buffered" % uBufferedBytes);
    return asDetails;

