import ssl;

def fbExceptionMeansSocketHasNoDataAvailable(oException):
  return (
    (oException.__class__ == ssl.SSLWantReadError and oException.errno in [
      2, # The operation did not complete (read)
    ]) or
    (oException.__class__ == BlockingIOError and oException.errno in [
      10035, # A non-blocking socket operation could not be completed immediately
    ])
  );