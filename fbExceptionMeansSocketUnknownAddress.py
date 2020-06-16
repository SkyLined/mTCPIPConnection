import socket;

def fbExceptionMeansSocketHostnameCannotBeResolved(oException):
  return isinstance(oException, socket.gaierror);