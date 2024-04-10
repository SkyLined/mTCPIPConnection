import os;

def fbExceptionMeansPortNotPermitted(oException):
  return (
    False
  ) if os.name == "nt" else (
    (isinstance(oException, PermissionError) and oException.errno == 13) # Permission denied
  );