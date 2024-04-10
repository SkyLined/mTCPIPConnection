import socket;

def fbExceptionMeansNetworkError(oException):
  return isinstance(oException, socket.ConnectionAbortedError);
