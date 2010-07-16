"""Logging Utilities.

@see: Cake Build System (http://sourceforge.net/projects/cake-build)
@copyright: Copyright (c) 2010 Lewis Baker, Stuart McMahon.
@license: Licensed under the MIT license.
"""

import sys
import threading

class Logger(object):
  """A class used to log tool output.
  
  Message output for each function is guaranteed to not intermingle
  with other messages output due to the use of a thread lock.
  """
  
  def __init__(self):
    """Default construction.
    """
    self.debugComponents = set()
    self.errorCount = 0
    self.warningCount = 0
    self._lock = threading.Lock()

  def enableDebug(self, component):
    """Enable debugging for a given component.  

    @param component: The component to enable debugging of.
    @type component: string
    """
    self.debugComponents.add(component)
    
  def dsableDebug(self, component):
    """Disable debugging for a given component.  

    @param component: The component to disable debugging of.
    @type component: string
    """
    self.debugComponents.discard(component)

  def debugEnabled(self, keyword):
    """Returns True if currently debugging the given component.
    
    @param keyword: The component to check.
    @type keyword: string
    
    @return: True if the logger is debugging the given component,
    otherwise False.
    @rtype: bool
    """
    return keyword in self.debugComponents
    
  def outputError(self, message):
    """Output an error message.
    
    @param message: The message to output.
    @type message: string
    """
    self._lock.acquire()
    try:
      self.errorCount += 1
      sys.stderr.write(message)
      sys.stderr.flush()
    finally:
      self._lock.release()
      
  def outputWarning(self, message):
    """Output a warning message.
    
    @param message: The message to output.
    @type message: string
    """
    self._lock.acquire()
    try:
      self.warningCount += 1
      sys.stderr.write(message)
      sys.stderr.flush()
    finally:
      self._lock.release()
      
  def outputInfo(self, message):
    """Output an informative message.
    
    @param message: The message to output.
    @type message: string
    """
    self._lock.acquire()
    try:
      sys.stdout.write(message)
      sys.stdout.flush()
    finally:
      self._lock.release()
      
  def outputDebug(self, keyword, message):
    """Output a debug message.
    
    The message will output only if the keyword matches a component
    we are currently debugging.
    
    @param keyword: The debug keyword associated with this message.
    @type keyword: string
    @param message: The message to output.
    @type message: string
    """
    if keyword in self.debugComponents:
      self._lock.acquire()
      try:
        sys.stdout.write(message)
        sys.stdout.flush()
      finally:
        self._lock.release()
