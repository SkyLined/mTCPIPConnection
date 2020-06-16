import socket, ssl;

def fbExceptionMeansSocketTimeout(oException):
  return (
    isinstance(oException, socket.timeout)
    or (isinstance(oException, socket.error) and oException.errno == 0x2733) # WSAEWOULDBLOCK
    or (isinstance(oException, ssl.SSLError) and oException.message == "The read operation timed out")
    or (isinstance(oException, ssl.SSLWantReadError) and oException.errno == 2)
  );