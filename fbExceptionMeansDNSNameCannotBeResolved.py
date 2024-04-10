import socket;

def fbExceptionMeansDNSNameCannotBeResolved(oException):
  return isinstance(oException, socket.gaierror);