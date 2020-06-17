from fTestDependencies import fTestDependencies;
fTestDependencies();

try:
  import mDebugOutput;
except:
  mDebugOutput = None;
try:
  try:
    from oConsole import oConsole;
  except:
    import sys, threading;
    oConsoleLock = threading.Lock();
    class oConsole(object):
      @staticmethod
      def fOutput(*txArguments, **dxArguments):
        sOutput = "";
        for x in txArguments:
          if isinstance(x, (str, unicode)):
            sOutput += x;
        sPadding = dxArguments.get("sPadding");
        if sPadding:
          sOutput.ljust(120, sPadding);
        oConsoleLock.acquire();
        print sOutput;
        sys.stdout.flush();
        oConsoleLock.release();
      fPrint = fOutput;
      @staticmethod
      def fStatus(*txArguments, **dxArguments):
        pass;
  
  import sys;
  
  import mTCPIPConnections;
  
  for sArgument in sys.argv[1:]:
    if sArgument == "--quick": 
      pass; # Always quick :)
    elif sArgument == "--debug": 
      fEnableDebugOutputForModule(mTCPIPConnections);
    else:
      raise AssertionError("Unknown argument %s" % sArgument);
  
  from fTestConnectionAndAcceptor import fTestConnectionAndAcceptor;
  
  oConsole.fOutput("=== Testing TCP/IP Connections ".ljust(80, "="));
  fTestConnectionAndAcceptor(mTCPIPConnections.cTCPIPConnection, mTCPIPConnections.cTCPIPConnectionAcceptor);
  oConsole.fOutput("=== Testing Buffered TCP/IP Connections ".ljust(80, "="));
  fTestConnectionAndAcceptor(mTCPIPConnections.cBufferedTCPIPConnection, mTCPIPConnections.cBufferedTCPIPConnectionAcceptor);
  oConsole.fOutput("=== Testing Transactional Buffered TCP/IP Connections ".ljust(80, "="));
  fTestConnectionAndAcceptor(mTCPIPConnections.cTransactionalBufferedTCPIPConnection, mTCPIPConnections.cTransactionalBufferedTCPIPConnectionAcceptor);
  
  for sArgument in sys.argv[1:]:
    if sArgument == "--debug":
      fEnableDebugOutputForModule(mTCPIPConnections);
  
except Exception as oException:
  if mDebugOutput:
    mDebugOutput.fTerminateWithException(oException, bShowStacksForAllThread = True);
  raise;
