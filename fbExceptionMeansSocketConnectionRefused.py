import socket;

def fbExceptionMeansSocketConnectionRefused(oException):
  return (oException.__class__ == socket.error and oException.errno == 0x274D); # WSAECONNREFUSED