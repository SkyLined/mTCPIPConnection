import time;

try: # mDebugOutput use is Optional
  from mDebugOutput import ShowDebugOutput, fShowDebugOutput;
except ModuleNotFoundError as oException:
  if oException.args[0] != "No module named 'mDebugOutput'":
    raise;
  ShowDebugOutput = lambda fx: fx; # NOP
  fShowDebugOutput = lambda x, s0 = None: x; # NOP

from mNotProvided import \
    fAssertType, \
    zNotProvided;

from .cTCPIPConnection import cTCPIPConnection;
from .mExceptions import \
    cTCPIPConnectionDisconnectedException, \
    cTCPIPConnectionShutdownException, \
    cTCPIPDataTimeoutException;

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
  
  def __init__(oSelf, *txArguments, **dxArguments):
    oSelf.__sbReadBuffer = b"";
    # code can ask for access to the python socket instance used by this class
    # This break functionality, so once this is done, a lot of methods can no
    # longer be trusted to function correctly. This flag is set in such cases
    # and these methods will throw an AssertionError when it is.
    oSelf.__bPythonSocketAccessProvided = False;
    super(cBufferedTCPIPConnection, oSelf).__init__(*txArguments, **dxArguments);
  
  @property
  def oPythonSocket(oSelf):
    # For use with "regular" Python code that doesn't accept cBufferedTCPConnection instances.
    # Please try to avoid using this, as it defeats the purpose of having this class.
    # Also, it interferes with the functionality of this class, which is why it can only be
    # handed out if the buffer is empty and why the class methods stop working:
    raise AssertionError("You're not supposed to do this");
    assert len(oSelf.__sbReadBuffer) == 0, \
        "Cannot provide a Python socket instance because there are %d bytes in the buffer" % len(oSelf.__sbReadBuffer);
    oSelf.__bPythonSocketAccessProvided = True;
    return super(cBufferedTCPIPConnection, oSelf).oPythonSocket;
  
  def fSecure(oSelf, oSSLContext, n0zTimeoutInSeconds = zNotProvided):
    fAssertType("n0zTimeoutInSeconds", n0zTimeoutInSeconds, int, float, zNotProvided, None);
    assert len(oSelf.__sbReadBuffer) == 0, \
        "This connection cannot be secured because it has data in its read buffer: %s!" % repr(oSelf.__sbReadBuffer);
    assert not oSelf.__bPythonSocketAccessProvided, \
        "This method cannot be used after the `oPythonSocket` property has been accessed";
    return super(cBufferedTCPIPConnection, oSelf).fSecure(
      oSSLContext,
      n0zTimeoutInSeconds = n0zTimeoutInSeconds
    );
  
  @property
  def bShouldAllowReading(oSelf):
    assert not oSelf.__bPythonSocketAccessProvided, \
        "This property cannot be read after the `oPythonSocket` property has been accessed";
    return len(oSelf.__sbReadBuffer) > 0 or super(cBufferedTCPIPConnection, oSelf).bShouldAllowReading;
  
  @ShowDebugOutput
  def fbBytesAreAvailableForReading(oSelf, *txArguments, **dxArguments):
    assert not oSelf.__bPythonSocketAccessProvided, \
        "This method cannot be used after the `oPythonSocket` property has been accessed";
    # If there are no buffered bytes but there should be data available for reading, buffer it:
    if (
      len(oSelf.__sbReadBuffer) == 0
      and super(cBufferedTCPIPConnection, oSelf).fbBytesAreAvailableForReading(*txArguments, **dxArguments)
    ):
      oSelf.__sbReadBuffer += super(cBufferedTCPIPConnection, oSelf).fsbReadAvailableBytes();
    # if we have buffered bytes, they are available for reading.
    return len(oSelf.__sbReadBuffer) > 0;
  
  @ShowDebugOutput
  def fWaitUntilBytesAreAvailableForReading(oSelf, *txArguments, **dxArguments):
    assert not oSelf.__bPythonSocketAccessProvided, \
        "This method cannot be used after the `oPythonSocket` property has been accessed";
    if len(oSelf.__sbReadBuffer) == 0:
      super(cBufferedTCPIPConnection, oSelf).fWaitUntilBytesAreAvailableForReading(*txArguments, **dxArguments);
  
  @ShowDebugOutput
  def fsbReadAvailableBytes(oSelf, u0MaxNumberOfBytes = None, n0TimeoutInSeconds = None, *txArguments, **dxArguments):
    fAssertType("u0MaxNumberOfBytes", u0MaxNumberOfBytes, int, None);
    fAssertType("n0TimeoutInSeconds", n0TimeoutInSeconds, int, float, None);
    assert not oSelf.__bPythonSocketAccessProvided, \
        "This method cannot be used after the `oPythonSocket` property has been accessed";
    u0AdditionalBytesNeeded = len(oSelf.__sbReadBuffer) - u0MaxNumberOfBytes if u0MaxNumberOfBytes is not None else None
    if u0AdditionalBytesNeeded is None or u0AdditionalBytesNeeded > 0:
      try:
        oSelf.__sbReadBuffer += super(cBufferedTCPIPConnection, oSelf).fsbReadAvailableBytes(
          u0MaxNumberOfBytes = u0AdditionalBytesNeeded,
          n0TimeoutInSeconds = n0TimeoutInSeconds,
          *txArguments,
          **dxArguments,
        );
      except (cTCPIPConnectionDisconnectedException, cTCPIPConnectionShutdownException):
        # If we have no bytes in the buffer and we cannot read bytes because the
        # connection was shut down or disconnected, throw the relevant exception.
        # Otherwise, we will return the bytes in the buffer.
        if len(oSelf.__sbReadBuffer) == 0:
          raise;
        pass;
    if u0MaxNumberOfBytes is None:
      sbBytes = oSelf.__sbReadBuffer;
      oSelf.__sbReadBuffer = b"";
    else:
      sbBytes = oSelf.__sbReadBuffer[:u0MaxNumberOfBytes];
      oSelf.__sbReadBuffer = oSelf.__sbReadBuffer[u0MaxNumberOfBytes:];
    return sbBytes;
  
  @ShowDebugOutput
  def fsbReadBytesUntilDisconnected(oSelf, *txArguments, **dxArguments):
    assert not oSelf.__bPythonSocketAccessProvided, \
        "This method cannot be used after the `oPythonSocket` property has been accessed";
    sbBytes = oSelf.__sbReadBuffer;
    oSelf.__sbReadBuffer = b"";
    return sbBytes + super(cBufferedTCPIPConnection, oSelf).fsbReadBytesUntilDisconnected(*txArguments, **dxArguments);
  
  def __fReadBytesIntoBuffer(oSelf, uMinNumberOfBytes, n0EndTime, sWhile):
    # Reads data until at least the requested number of bytes is in the buffer.
    # Can throw a timeout, shutdown or disconnected exception.
    # Returns when the requested number of bytes is in the buffer.
    while len(oSelf.__sbReadBuffer) < uMinNumberOfBytes:
      if n0EndTime:
        n0TimeoutInSeconds = n0EndTime - time.time();
        if n0TimeoutInSeconds <= 0:
          raise cTCPIPDataTimeoutException(
            "Timeout on connection %s while %s after %s seconds." % (
              oSelf.fsGetEndPointsAndDirection(),
              sWhile,
              n0TimeoutInSeconds,
            ),
            oConnection = oSelf,
          );
      else:
        n0TimeoutInSeconds = None;
      super(cBufferedTCPIPConnection, oSelf).fWaitUntilBytesAreAvailableForReading(
        n0TimeoutInSeconds = n0TimeoutInSeconds,
      );
      sbBytesRead = super(cBufferedTCPIPConnection, oSelf).fsbReadAvailableBytes();
      oSelf.__sbReadBuffer += sbBytesRead;
    fShowDebugOutput(oSelf, "Read bytes to make sure there are at least %d bytes resulted in a %d byte buffer." % \
        (uMinNumberOfBytes, len(oSelf.__sbReadBuffer)));
  
  @ShowDebugOutput
  def fsbReadBytes(oSelf, uNumberOfBytes, n0TimeoutInSeconds = None):
    fAssertType("uNumberOfBytes", uNumberOfBytes, int);
    fAssertType("n0TimeoutInSeconds", n0TimeoutInSeconds, int, float, None);
    assert not oSelf.__bPythonSocketAccessProvided, \
        "This method cannot be used after the `oPythonSocket` property has been accessed";
    # Reads data until at least the requested number of bytes is in the buffer.
    # Returns the requested number of bytes, which are removed from the buffer.
    # Can throw a timeout, shutdown or disconnected exception.
    n0EndTime = time.time() + n0TimeoutInSeconds if n0TimeoutInSeconds else None;
    oSelf.__fReadBytesIntoBuffer(uNumberOfBytes, n0EndTime, "reading bytes into buffer");
    sbBytes = oSelf.__sbReadBuffer[:uNumberOfBytes];
    oSelf.__sbReadBuffer = oSelf.__sbReadBuffer[uNumberOfBytes:];
    return sbBytes;
  
  @ShowDebugOutput
  def fsb0ReadUntilMarker(oSelf, sbMarker, u0MaxNumberOfBytes = None, n0TimeoutInSeconds = None):
    fAssertType("sbMarker", sbMarker, bytes);
    fAssertType("u0MaxNumberOfBytes", u0MaxNumberOfBytes, int, None);
    fAssertType("n0TimeoutInSeconds", n0TimeoutInSeconds, int, float, None);
    assert not oSelf.__bPythonSocketAccessProvided, \
        "This method cannot be used after the `oPythonSocket` property has been accessed";
    # Reads data into the buffer until the marker is found in the buffer or the
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
      oSelf.__fReadBytesIntoBuffer(uMinNumberOfBytesNeededInBuffer, n0EndTime, "reading bytes into buffer until a marker is found");
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
    assert not oSelf.__bPythonSocketAccessProvided, \
        "This method cannot be used after the `oPythonSocket` property has been accessed";
    oSelf.__sbReadBuffer = ""; # Whatever is buffered is discarded
    super(cBufferedTCPIPConnection, oSelf).fShutdownForReading();
  
  def fShutdown(oSelf):
    oSelf.__sbReadBuffer = ""; # Whatever is buffered is discarded
    super(cBufferedTCPIPConnection, oSelf).fShutdown();
  
  def fDisconnect(oSelf):
    oSelf.__sbReadBuffer = ""; # Whatever is buffered is discarded
    super(cBufferedTCPIPConnection, oSelf).fDisconnect();
  
  def fasGetDetails(oSelf):
    asDetails = super(cBufferedTCPIPConnection, oSelf).fasGetDetails();
    if oSelf.__bPythonSocketAccessProvided:
      asDetails.append("oPythonSocket has been read");
    else:
      uBufferedBytes = len(oSelf.__sbReadBuffer) if oSelf.__sbReadBuffer else 0;
      if uBufferedBytes > 0:
        asDetails.append("%d bytes buffered" % uBufferedBytes);
    return asDetails;

