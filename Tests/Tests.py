from fTestDependencies import fTestDependencies;
fTestDependencies();

from mDebugOutput import fEnableDebugOutputForClass, fEnableDebugOutputForModule, fTerminateWithException;
try:
  import sys;
  
  from oConsole import oConsole;
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
  fTerminateWithException(oException);