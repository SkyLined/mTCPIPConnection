
from .cTransactionalBufferedTCPIPConnection import cTransactionalBufferedTCPIPConnection;
from .cBufferedTCPIPConnectionAcceptor import cBufferedTCPIPConnectionAcceptor;

class cTransactionalBufferedTCPIPConnectionAcceptor(cBufferedTCPIPConnectionAcceptor):
  def foCreateNewConnectionForPythonSocket(oSelf, oPythonSocket):
    return cTransactionalBufferedTCPIPConnection(oPythonSocket, bCreatedLocally = False);

