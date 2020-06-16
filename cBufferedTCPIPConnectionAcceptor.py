
from .cBufferedTCPIPConnection import cBufferedTCPIPConnection;
from .cTCPIPConnectionAcceptor import cTCPIPConnectionAcceptor;

class cBufferedTCPIPConnectionAcceptor(cTCPIPConnectionAcceptor):
  def foCreateNewConnectionForPythonSocket(oSelf, oPythonSocket):
    return cBufferedTCPIPConnection(oPythonSocket, bCreatedLocally = False);
