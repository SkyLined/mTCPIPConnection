import socket;

def fbExceptionMeansSocketAlreadyInUseAsAcceptor(oException):
  return (
    (isinstance(oException, WindowsError) and oException.errno == 0x2740) # WSAEADDRINUSE
  );