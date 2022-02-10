import os, socket;

def fbExceptionMeansSocketAddressIsInvalid(oException):
  return (
    (isinstance(oException, (socket.error, OSError)) and oException.errno == 0x2741)  # WSAEADDRNOTAVAIL
  ) if os.name == "nt" else (
    (isinstance(oException, OSError) and oException.errno == 113)
  );
