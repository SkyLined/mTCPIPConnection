import os;

def fbExceptionMeansPortNotPermitted(oException):
  return (
    (isinstance(oException, PermissionError) and oException.errno == 13) # Permission denied
  );