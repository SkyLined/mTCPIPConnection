import os, socket, ssl;

def fbExceptionMeansSocketDisconnected(oException):
  return (
    isinstance(oException, ConnectionResetError)
    or isinstance(oException, ssl.SSLEOFError)
    or (
      (
        isinstance(oException, OSError) and oException.errno in [
          9, # "Bad file descriptor"
          0x2736, # WSAENOTSOCK     An operation was attempted on something that is not a socket
          0x2742, # WSAENETDOWN     A socket operation encountered a dead network.
          0x2743, # WSAENETUNREACH  A socket operation was attempted to an unreachable network.
          0x2744, # WSAENETRESET    The connection has been broken due to keep-alive activity detecting a failure while the operation was in progress.
          0x2745, # WSAECONNABORTED An established connection was aborted by the software in your host machine.
          0x2746, # WSAECONNRESET   An existing connection was forcibly closed by the remote host.
          0x2749, # WSAENOTCONN     A request to send or receive data was disallowed because the socket is not connected.
          0x2751, # WSAEHOSTUNREACH A socket operation was attempted to an unreachable host. 
        ]
      ) if os.name == "nt" else (
        isinstance(oException, OSError) and oException.errno == 107
      )
    )
  );