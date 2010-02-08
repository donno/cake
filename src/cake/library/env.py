"""Environment Tool.
"""

import cake.path

from cake.library import Tool

class Environment(Tool):
  """A dictionary of key/value pairs used for path substitution.
  """
  
  def __init__(self):
    """Default constructor.
    """
    self.__vars = {}
    
  def __getitem__(self, key):
    """Return an environment variables value given its key.
    
    @param key:  The key of the environment variable to get.
    @return: The value of the environment variable.
    """
    return self.__vars[key]
  
  def __setitem__(self, key, value):
    """Set a new value for an environment variable.
    
    @param key: The key of the environment variable to set.
    @param value: The value to set the environment variable to.
    """
    self.__vars[key] = value
    
  def __delitem__(self, key):
    """Delete an environment variable given its key.
    
    @param key: The key of the environment variable to delete. 
    """
    del self.__vars[key]

  def get(self, key, default=None):
    """Return an environment variable or default value if not found.
    
    @param key: The key of the environment variable to get.
    @param default: The value to return if the key is not found.
    """
    return self.__vars.get(key, default)

  def set(self, **kwargs):    
    """Set a series of keys/values.
    
    Similar to update() except key/value pairs are taken directly
    from the keyword arguments.
    
    Note that this means keys must conform to Python keyword argument
    naming conventions (eg. no spaces).
    
    Example::
      env.set(
        CODE_PATH="C:/code",
        ART_PATH="C:/art",
        )
    """
    self.__environment.update(kwargs)
    
  def delete(self, *arguments):    
    """Delete values given their keys.
    
    Note that this means keys must conform to Python argument naming
    conventions (eg. no spaces).

    Example::
      env.delete(
        CODE_PATH,
        ART_PATH
        )
    """
    for a in arguments:
      del self.__vars[a]
      
  def update(self, values):
    """Update the environment with key/value pairs from 'values'.
    
    Example::
      env.update({
        "CODE_PATH":"c:/code",
        "ART_PATH":"c:/art",
        })
    @param values: An iterable sequence of key/value pairs to update
    from.
    """
    self.__vars.update(values)
    
  def expand(self, value):
    """Expand variables in the specified string.
    
    Variables that are expanded are of the form ${VAR}
    or $VAR.

    Example::
      env["CODE_PATH"] = "c:/code"
      
      env.expand("${CODE_PATH}/a") -> "C:/code/a"
      
    @param value: The string to expand.
    @type value: string
    @return: The expanded string.
    @rtype: string
    """
    return cake.path.expandVars(value, self.__vars)

  def choose(self, key, default=None, **kwargs):
    """Choose and return an argument depending on the key given.
    
    Example::
    sources += env.choose("platform",
      windows=["Win32.cpp"],
      ps2=["PS2.cpp"],
      )
    
    @param key: The environment variable to choose.
    @type key: string
    @return: The argument whose key matches the environment variables value
    or default if there was no match.
    """
    return kwargs.get(self.__vars[key], default)
