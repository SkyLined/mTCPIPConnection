import socket;

def fbExceptionMeansSocketInvalidAddress(oException):
  return isinstance(oException, socket.error) and oException.errno == 0x2741; # WSAEADDRNOTAVAIL
