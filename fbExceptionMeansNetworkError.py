import socket;

def fbExceptionMeansNetworkError(oException):
  return isinstance(oException, ConnectionAbortedError);
