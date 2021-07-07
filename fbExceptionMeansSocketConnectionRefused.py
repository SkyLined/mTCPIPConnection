import socket;

def fbExceptionMeansSocketConnectionRefused(oException):
  return (
    isinstance(oException, ConnectionRefusedError) or
    (isinstance(oException, socket.error) and oException.errno == 0x274D) # WSAECONNREFUSED
  );