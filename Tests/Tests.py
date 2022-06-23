import os, sys;
sModulePath = os.path.dirname(__file__);
sys.path = [sModulePath] + [sPath for sPath in sys.path if sPath.lower() != sModulePath.lower()];

from fTestDependencies import fTestDependencies;
fTestDependencies();

try: # mDebugOutput use is Optional
  import mDebugOutput as m0DebugOutput;
except ModuleNotFoundError as oException:
  if oException.args[0] != "No module named 'mDebugOutput'":
    raise;
  m0DebugOutput = None;

guExitCodeInternalError = 1; # Use standard value;
try:
  try:
    from mConsole import oConsole;
  except ModuleNotFoundError as oException:
    if oException.args[0] != "No module named 'oConsole'":
      raise;
    import sys, threading;
    oConsoleLock = threading.Lock();
    class oConsole(object):
      @staticmethod
      def fOutput(*txArguments, **dxArguments):
        sOutput = "";
        for x in txArguments:
          if isinstance(x, str):
            sOutput += x;
        sPadding = dxArguments.get("sPadding");
        if sPadding:
          sOutput.ljust(120, sPadding);
        oConsoleLock.acquire();
        print(sOutput);
        sys.stdout.flush();
        oConsoleLock.release();
      @staticmethod
      def fStatus(*txArguments, **dxArguments):
        pass;
  
  import os, sys;
  
  import mTCPIPConnection;
  
  try:
    import mSSL as m0SSL;
  except ModuleNotFoundError as oException:
    if oException.args[0] != "No module named 'mSSL'":
      raise;
    m0SSL = None;
  
  sbTestHostname = b"localhost";
  HEADER = 0xFF0A;
  DELETE_FILE = 0xFF0C;
  DELETE_FOLDER = 0xFF04;
  OVERWRITE_FILE = 0xFF0E;
  
  def fShowDeleteOrOverwriteFileOrFolder(sFileOrFolderPath, bFile, s0NewContent):
    if not bFile:
      oConsole.fOutput(DELETE_FOLDER, " - ", sFileOrFolderPath);
    elif s0NewContent is None:
      oConsole.fOutput(DELETE_FILE, " - ", sFileOrFolderPath);
    else:
      oConsole.fOutput(OVERWRITE_FILE, " * ", sFileOrFolderPath, " => %d bytes." % len(s0NewContent));
  
  bQuick = False;
  bFull = False;
  for sArgument in sys.argv[1:]:
    if sArgument == "--quick": 
      bQuick = True;
    elif sArgument == "--full": 
      bFull = True;
    elif sArgument == "--debug": 
      assert m0DebugOutput, \
          "This feature requires mDebugOutput!";
      m0DebugOutput.fEnableDebugOutputForModule(mTCPIPConnection);
    else:
      raise AssertionError("Unknown argument %s" % sArgument);
  assert not bQuick or not bFull, \
      "Cannot test both quick and full!";
  
  if m0SSL is not None:
    import tempfile;
    sCertificateAuthorityFolderPath = os.path.join(tempfile.gettempdir(), "tmp");
    
    oCertificateAuthority = m0SSL.cCertificateAuthority(sCertificateAuthorityFolderPath, "mSSL Test");
    oConsole.fOutput("  oCertificateAuthority = ", str(oCertificateAuthority));
    if os.path.isdir(sCertificateAuthorityFolderPath):
      if bQuick:
        oConsole.fOutput(HEADER, "\u2500\u2500\u2500\u2500 Reset Certificate Authority folder... ", sPadding = "\u2500");
        oCertificateAuthority.fResetCacheFolder(fShowDeleteOrOverwriteFileOrFolder);
      else:
        oConsole.fOutput(HEADER, "\u2500\u2500\u2500\u2500 Delete Certificate Authority folder... ", sPadding = "\u2500");
        oCertificateAuthority.fDeleteCacheFolder(fShowDeleteOrOverwriteFileOrFolder);
    
    sTestHostname = str(sbTestHostname, "ascii", "strict");
    oCertificateAuthority.foGenerateServersideSSLContextForHostname(sbTestHostname);
    oCertificateStore = m0SSL.cCertificateStore();
    oCertificateStore.fAddCertificateAuthority(oCertificateAuthority);
    o0ServerSSLContext = oCertificateStore.foGetServersideSSLContextForHostname(sbTestHostname);
    o0ClientSSLContext = oCertificateStore.foGetClientsideSSLContextForHostname(sbTestHostname);
    oConsole.fOutput("=== SSL Contexts ", sPadding = "=");
    oConsole.fOutput("o0ServerSSLContext = ", repr(o0ServerSSLContext));
    oConsole.fOutput("o0ClientSSLContext = ", repr(o0ClientSSLContext));
    
  from fRunTestsOnTCPIPConnectionClasses import fRunTestsOnTCPIPConnectionClasses;
  fRunTestsOnTCPIPConnectionClasses(oConsole, None, None);
  if m0SSL:
    fRunTestsOnTCPIPConnectionClasses(oConsole, o0ClientSSLContext, o0ServerSSLContext);
  
  from fTestConnectionAndAcceptor import fTestConnectionAndAcceptor;
  
  oConsole.fOutput("=== Testing TCP/IP Connections ", sPadding = "=");
  fTestConnectionAndAcceptor(mTCPIPConnection.cTCPIPConnection, mTCPIPConnection.cTCPIPConnectionAcceptor, None, None);
  if m0SSL:
    fTestConnectionAndAcceptor(mTCPIPConnection.cTCPIPConnection, mTCPIPConnection.cTCPIPConnectionAcceptor, o0ClientSSLContext, o0ServerSSLContext);
  oConsole.fOutput("=== Testing Buffered TCP/IP Connections ", sPadding = "=");
  fTestConnectionAndAcceptor(mTCPIPConnection.cBufferedTCPIPConnection, mTCPIPConnection.cBufferedTCPIPConnectionAcceptor, None, None);
  if m0SSL:
    fTestConnectionAndAcceptor(mTCPIPConnection.cBufferedTCPIPConnection, mTCPIPConnection.cBufferedTCPIPConnectionAcceptor, o0ClientSSLContext, o0ServerSSLContext);
  oConsole.fOutput("=== Testing Transactional Buffered TCP/IP Connections ", sPadding = "=");
  fTestConnectionAndAcceptor(mTCPIPConnection.cTransactionalBufferedTCPIPConnection, mTCPIPConnection.cTransactionalBufferedTCPIPConnectionAcceptor, None, None);
  if m0SSL:
    fTestConnectionAndAcceptor(mTCPIPConnection.cTransactionalBufferedTCPIPConnection, mTCPIPConnection.cTransactionalBufferedTCPIPConnectionAcceptor, o0ClientSSLContext, o0ServerSSLContext);
  
  if m0SSL is not None:
    if not bQuick:
      oConsole.fOutput(HEADER, "\u2500\u2500\u2500\u2500 Delete Certificate Authority folder... ", sPadding = "\u2500");
      oCertificateAuthority.fDeleteCacheFolder(fShowDeleteOrOverwriteFileOrFolder);
  
except Exception as oException:
  if m0DebugOutput:
    m0DebugOutput.fTerminateWithException(oException, guExitCodeInternalError, bShowStacksForAllThread = True);
  raise;
