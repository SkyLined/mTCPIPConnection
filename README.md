This repository contains the a python module that can be used to create TCP/IP
connections. It offers a more standardized API than the built-in socket module
and offers buffered and transactional connections that make it easier to
implement protocol handlers (such as HTTP).

`cTCPIPConnection`
------------------
Represents a single TCP/IP connection. Allows secure connections if the *mSSL*
module is available.

`cBufferedTCPIPConnection`
--------------------------
Implements `cTCPIPConnection` but buffers incoming data to allow more complex
processing.

`cTransactionalBufferedTCPIPConnection`
--------------------------
Implements `cBufferedTCPIPConnection` but offers reading and writing data as a
single transactions to allow multiple threads to coordinate use of connections
and prevent them from interfering with each other.
