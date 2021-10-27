import socket;

def fbExceptionMeansSocketAddressIsInvalid(oException):
  return isinstance(oException, (socket.error, OSError)) and oException.errno == 0x2741; # WSAEADDRNOTAVAIL     The requested address is not valid in its context
