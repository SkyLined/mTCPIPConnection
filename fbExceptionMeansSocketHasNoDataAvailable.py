import ssl;

def fbExceptionMeansSocketHasNoDataAvailable(oException):
  return (
    (oException.__class__ == ssl.SSLWantReadError and oException.errno in [
      2, # The operation did not complete (read)
    ])
  );