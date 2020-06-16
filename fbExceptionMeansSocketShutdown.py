import socket;

def fbExceptionMeansSocketShutdown(oException):
  return (
    (oException.__class__ == socket.error and oException.errno in [
      0x274A # WSAESHUTDOWN
    ])
  );