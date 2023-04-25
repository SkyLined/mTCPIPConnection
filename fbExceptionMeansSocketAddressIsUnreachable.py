import os, socket;

def fbExceptionMeansSocketAddressIsUnreachable(oException):
  return (
    # https://learn.microsoft.com/en-us/windows/win32/winsock/windows-sockets-error-codes-2
    (isinstance(oException, (socket.error, OSError)) and oException.errno in (
      10051, # WSAENETUNREACH
      10065, # WSAEHOSTUNREACH
    )) 
  ) if os.name == "nt" else (
    False and (isinstance(oException, OSError) and oException.errno == 1234567)
  );
