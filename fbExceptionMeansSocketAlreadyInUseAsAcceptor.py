import os, socket;

def fbExceptionMeansSocketAlreadyInUseAsAcceptor(oException):
  return (
    (isinstance(oException, OSError) and oException.errno == 0x2740) # WSAEADDRINUSE
  ) if os.name == "nt" else (
    (isinstance(oException, OSError) and oException.errno == 98) # 
  );