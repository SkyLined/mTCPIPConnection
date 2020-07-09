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

from .cTCPIPConnection import cTCPIPConnection;
from .mExceptions import *;

from mMultiThreading import cLock;
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
    oSelf.__sReadBuffer = "";
    super(cBufferedTCPIPConnection, oSelf).__init__(*txArguments, **dxArguments);

  def fSecure(oSelf, *txArguments, **dxArguments):
    assert len(oSelf.__sReadBuffer) == 0, \
        "This connection cannot be secured because it has data in its read buffer: %s!" % repr(oSelf.__sReadBuffer);
    return super(cBufferedTCPIPConnection, oSelf).fSecure(*txArguments, **dxArguments);

  @property
  def bShouldAllowReading(oSelf):
    return len(oSelf.__sReadBuffer) > 0 or super(cBufferedTCPIPConnection, oSelf).bShouldAllowReading;

  @ShowDebugOutput
  def fbBytesAreAvailableForReading(oSelf, *txArguments, **dxArguments):
    # If there are no buffered bytes but there should be data available for reading, buffer it:
    if (
      len(oSelf.__sReadBuffer) == 0
      and super(cBufferedTCPIPConnection, oSelf).fbBytesAreAvailableForReading(*txArguments, **dxArguments)
    ):
      oSelf.__sReadBuffer += super(cBufferedTCPIPConnection, oSelf).fsReadAvailableBytes();
    # if we have buffered bytes, they are available for reading.
    return len(oSelf.__sReadBuffer) > 0;
  
  @ShowDebugOutput
  def fWaitUntilBytesAreAvailableForReading(oSelf, *txArguments, **dxArguments):
    if len(oSelf.__sReadBuffer) == 0:
      super(cBufferedTCPIPConnection, oSelf).fWaitUntilBytesAreAvailableForReading(*txArguments, **dxArguments);
  
  def fsReadAvailableBytes(oSelf, uMaxNumberOfBytes = None):
    sBytes = oSelf.__sReadBuffer;
    oSelf.__sReadBuffer = "";
    try:
      sBytes += super(cBufferedTCPIPConnection, oSelf).fsReadAvailableBytes();
    except (cTCPIPConnectionShutdownException, cTCPIPConnectionDisconnectedException) as oException:
      # If we have no bytes in the buffer and we cannot read bytes because the
      # connection was shut down or disconnected, throw the relevant exception.
      # Otherwise, we will return the bytes in the buffer.
      if len(sBytes) == 0:
        raise;
      pass;
    return sBytes;
  
  @ShowDebugOutput
  def fsReadBytesUntilDisconnected(oSelf, *txArguments, **dxArguments):
    sBytes = oSelf.__sReadBuffer;
    oSelf.__sReadBuffer = "";
    return sBytes + super(cBufferedTCPIPConnection, oSelf).fsReadBytesUntilDisconnected(*txArguments, **dxArguments);
  
  def __fReadBytesIntoBuffer(oSelf, uMinNumberOfBytes, nzEndTime, sWhile):
    # Reads data until at least the requested number of bytes is in the buffer.
    # Can throw a timeout, shutdown or disconnected exception.
    # Returns when the requested number of bytes is in the buffer.
    while len(oSelf.__sReadBuffer) < uMinNumberOfBytes:
      nzTimeoutInSeconds = None if nzEndTime is None else nzEndTime - time.clock();
      if nzTimeoutInSeconds is not None and nzTimeoutInSeconds <= 0:
        raise cTCPIPDataTimeoutException("Timeout while %s" % sWhile, {"uMinNumberOfBytes": uMinNumberOfBytes});
      super(cBufferedTCPIPConnection, oSelf).fWaitUntilBytesAreAvailableForReading(nzTimeoutInSeconds);
      sBytesRead = super(cBufferedTCPIPConnection, oSelf).fsReadAvailableBytes();
      oSelf.__sReadBuffer += sBytesRead;
      oSelf.fFireCallbacks("bytes read", {"sBytes": sBytesRead});
    fShowDebugOutput("Read bytes to make sure there are at least %d bytes resulted in a %d byte buffer." % \
        (uMinNumberOfBytes, len(oSelf.__sReadBuffer)));
  
  @ShowDebugOutput
  def fsReadBytes(oSelf, uNumberOfBytes, nzTimeoutInSeconds = None):
    # Reads data until at least the requested number of bytes is in the buffer.
    # Returns the requested number of bytes, which are removed from the buffer.
    # Can throw a timeout, shutdown or disconnected exception.
    nzEndTime = time.clock() + nzTimeoutInSeconds if nzTimeoutInSeconds is not None else None;
    oSelf.__fReadBytesIntoBuffer(uNumberOfBytes, nzEndTime, "reading bytes into buffer");
    sBytes = oSelf.__sReadBuffer[:uNumberOfBytes];
    oSelf.__sReadBuffer = oSelf.__sReadBuffer[uNumberOfBytes:];
    return sBytes;
  
  @ShowDebugOutput
  def fszReadUntilMarker(oSelf, sMarker, uzMaxNumberOfBytes = None, nzTimeoutInSeconds = None):
    # Reads data into the buffer until the marker is found in the buffer or the
    # Returns the bytes up to and including the marker, which are removed from
    # the buffer.
    # If the marker cannot be found within the max number of bytes, return None
    # Can throw a timeout, shutdown or disconnected exception.
    nzEndTime = time.clock() + nzTimeoutInSeconds if nzTimeoutInSeconds is not None else None;
    uMarkerSize = len(sMarker);
    assert uzMaxNumberOfBytes is None or uzMaxNumberOfBytes >= uMarkerSize, \
        "It is impossible to find %d bytes without reading more than %d bytes" % (uMarkerSize, uzMaxNumberOfBytes);
    uNextFindStartIndex = 0;
    while 1:
      # We need to read enough bytes to be able to start another search (i.e. one).
      uMinNumberOfBytesNeededInBuffer = uNextFindStartIndex + uMarkerSize;
      oSelf.__fReadBytesIntoBuffer(uMinNumberOfBytesNeededInBuffer, nzEndTime, "reading bytes into buffer until a marker is found");
      # If the marker can be found stop looking.
      uStartIndex = oSelf.__sReadBuffer.find(sMarker, uNextFindStartIndex, uzMaxNumberOfBytes);
      if uStartIndex != -1:
        uEndIndex = uStartIndex + uMarkerSize;
        assert uzMaxNumberOfBytes is None or uEndIndex <= uzMaxNumberOfBytes, \
            "The code above should have only found the marker within the max number of bytes, but it was found outside it!";
        sBytes = oSelf.__sReadBuffer[:uEndIndex];
        oSelf.__sReadBuffer = oSelf.__sReadBuffer[uEndIndex:];
        return sBytes;
      # The next find operation will not need to scan the entire buffer again:
      uNextFindStartIndex = len(oSelf.__sReadBuffer) - uMarkerSize + 1;
      uNextFindEndIndex = uNextFindStartIndex + uMarkerSize;
      # If the marker cannot be found within the max number of bytes, return None;
      if uzMaxNumberOfBytes is not None and uNextFindEndIndex > uzMaxNumberOfBytes:
        return None;
  
  def fShutdownForReading(oSelf):
    oSelf.__sReadBuffer = None; # This should not be used again!
    super(cBufferedTCPIPConnection, oSelf).fShutdownForReading();

  def fShutdown(oSelf):
    oSelf.__sReadBuffer = None; # This should not be used again!
    super(cBufferedTCPIPConnection, oSelf).fShutdown();
  
  def fDisconnect(oSelf):
    oSelf.__sReadBuffer = None; # This should not be used again!
    super(cBufferedTCPIPConnection, oSelf).fDisconnect();
  
  def fasGetDetails(oSelf):
    asDetails = super(cBufferedTCPIPConnection, oSelf).fasGetDetails();
    uBufferedBytes = len(oSelf.__sReadBuffer) if oSelf.__sReadBuffer else 0;
    if uBufferedBytes > 0:
      asDetails.append("%d bytes buffered" % uBufferedBytes);
    return asDetails;

