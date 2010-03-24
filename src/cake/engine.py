"""Engine-Level Classes and Utilities.

@see: Cake Build System (http://sourceforge.net/projects/cake-build)
@copyright: Copyright (c) 2010 Lewis Baker, Stuart McMahon.
@license: Licensed under the MIT license.
"""

import codecs
import threading
import traceback
import sys
import os
import os.path
import time

import math
try:
  import cPickle as pickle
except ImportError:
  import pickle

import cake.bytecode
import cake.tools
import cake.task
import cake.path
import cake.hash

class BuildError(Exception):
  """Exception raised when a build fails.
  
  This exception is treated as expected by the Cake build system as it won't
  output the stack-trace if raised by a task.
  """
  pass

class Variant(object):
  """A container for build configuration information.

  @ivar tools: The available tools for this variant.
  @type tools: dict
  """
  
  def __init__(self, **keywords):
    """Construct an empty variant.
    """
    self.keywords = keywords
    self.tools = {}
  
  def __repr__(self):
    keywords = ", ".join('%s=%r' % (k, v) for k, v in self.keywords.iteritems())
    return "Variant(%s)" % keywords 
  
  def matches(*args, **keywords):
    """Query if this variant matches the specified keywords.
    """
    # Don't use self in signature in case the user wants a keyword of
    # self.
    self, = args
    variantKeywords = self.keywords
    for key, value in keywords.iteritems():
      variantValue = variantKeywords.get(key, None)
      if isinstance(value, (list, tuple)):
        for v in value:
          if variantValue == v:
            break
        else:
          return False
      elif value == "all" and variantValue is not None:
        continue
      elif variantValue != value:
        return False
    else:
      return True
  
  def clone(self, **keywords):
    """Create an independent copy of this variant.
    
    @param keywords: The name/value pairs that define the new variant.
    @type keywords: dict of string->string
    
    @return: The new Variant.
    """
    newKeywords = self.keywords.copy()
    newKeywords.update(keywords)
    v = Variant(**newKeywords)
    v.tools = dict((name, tool.clone()) for name, tool in self.tools.iteritems())
    return v

class Engine(object):
  """Main object that holds all of the singleton resources for a build.
  """
  
  forceBuild = False
  
  def __init__(self, logger):
    """Default Constructor.
    """
    self._variants = {}
    self.defaultVariants = []
    self._byteCodeCache = {}
    self._timestampCache = {}
    self._digestCache = {}
    self._dependencyInfoCache = {}
    self._executed = {}
    self._executedLock = threading.Lock()
    self.logger = logger
      
  def addVariant(self, variant, default=False):
    """Register a new variant with this engine.
    
    @param variant: The Variant object to register.
    @type variant: L{Variant}
    
    @param default: If True then make this newly added variant the default
    build variant.
    @type default: C{bool}
    """
    key = frozenset(variant.keywords.iteritems())
    if key in self._variants:
      raise KeyError("Already added variant with these keywords: %r" % variant)
    
    self._variants[key] = variant
    if default:
      self.defaultVariants.append(variant)
    
  def findAllVariants(self, keywords):
    """Find all variants that match the specified keywords.
    """
    for variant in self._variants.itervalues():
      if variant.matches(**keywords):
        yield variant
  
  def findVariant(self, keywords, baseVariant=None):
    """Find the variant that matches the specified keywords.
    
    @param keywords: A dictionary of key/value pairs the variant needs
    to match. The value can be either a string, "all", a list of
    strings or None.
    
    @param baseVariant: If specified then attempts to find the 
    
    @raise LookupError: If no variants matched or more than one variant
    matched the criteria.
    """
    if baseVariant is None:
      results = [v for v in self.findAllVariants(keywords)]
    else:
      results = []
      getBaseValue = baseVariant.keywords.get
      for variant in self.findAllVariants(keywords):
        for key, value in variant.keywords.iteritems():
          if key not in keywords:
            baseValue = getBaseValue(key, None)
            if value != baseValue:
              break
        else:
          results.append(variant) 
    
    if not results:
      raise LookupError("No variants matched criteria.")
    elif len(results) > 1:
      msg = "Found %i variants that matched criteria.\n"
      msg += "".join("- %r\n" % v for v in results)
      raise LookupError(msg)

    return results[0]
    
  def createTask(self, func):
    """Construct a new task that will call the specified function.
    
    This function wraps the function in an exception handler that prints out
    the stacktrace and exception details if an exception is raised by the
    function.
    
    @param func: The function that will be called with no args by the task once
    the task has been started.
    @type func: any callable
    
    @return: The newly created Task.
    @rtype: L{Task}
    """
    def _wrapper():
      try:
        return func()
      except BuildError:
        # Assume build errors have already been reported
        raise
      except Exception, e:
        tbs = [traceback.extract_tb(sys.exc_info()[2])]

        t = task
        while t is not None:
          tb = getattr(t, "traceback", None)
          if tb is not None:
            tbs.append(t.traceback)
          t = t.parent

        tracebackString = ''.join(
          ''.join(traceback.format_list(tb)) for tb in reversed(tbs)
          )
        exceptionString = ''.join(traceback.format_exception_only(e.__class__, e))
        message = 'Unhandled Task Exception:\n%s%s' % (tracebackString, exceptionString)
        if not self.logger.debugEnabled("stack"):
          message += "Pass '-d stack' if you require a more complete stack trace.\n"    
        self.logger.outputError(message)
        raise

    task = cake.task.Task(_wrapper)

    # Set a traceback for the parent script task
    if self.logger.debugEnabled("stack"):    
      if Script.getCurrent() is not None:
        task.traceback = traceback.extract_stack()[:-1]

    return task
    
  def raiseError(self, message):
    """Log an error and raise the BuildError exception.
    
    @param message: The error message to output.
    @type message: string
    
    @raise BuildError: Raises a build error that should cause the current
    task to fail.
    """
    self.logger.outputError(message)
    raise BuildError(message)
    
  def execute(self, path, variant):
    """Execute the script with the specified variant.
    
    @param path: Path of the Cake script file to execute.
    @type path: string

    @param variant: The build variant to execute this script with.
    @type variant: L{Variant} 

    @return: A Task object that completes when the script and any
    tasks it starts finish executing.
    @rtype: L{cake.task.Task}
    """

    path = os.path.normpath(path)

    key = (os.path.normcase(path), variant)

    currentScript = Script.getCurrent()
    if currentScript:
      currentVariant = currentScript.variant
    else:
      currentVariant = None
    
    self._executedLock.acquire()
    try:
      if key in self._executed:
        script = self._executed[key]
        task = script.task
      else:
        def execute():
          cake.tools.__dict__.clear()
          for name, tool in variant.tools.items():
            setattr(cake.tools, name, tool.clone())
          if variant is not currentVariant:
            self.logger.outputInfo("Building with %s\n" % str(variant))
          self.logger.outputInfo("Executing %s\n" % script.path)
          script.execute()
        task = self.createTask(execute)
        script = Script(
          path=path,
          variant=variant,
          task=task,
          engine=self,
          )
        self._executed[key] = script
        task.addCallback(
          lambda: self.logger.outputDebug(
            "script",
            "Finished %s\n" % script.path,
            )
          )
        task.start()
    finally:
      self._executedLock.release()

    return task

  def getByteCode(self, path):
    """Load a python file and return the compiled byte-code.
    
    @param path: The path of the python file to load.
    @type path: string
    
    @return: A code object that can be executed with the python 'exec'
    statement.
    @rtype: C{types.CodeType}
    """
    byteCode = self._byteCodeCache.get(path, None)
    if byteCode is None:
      byteCode = cake.bytecode.loadCode(path)
      self._byteCodeCache[path] = byteCode
    return byteCode
    
  def notifyFileChanged(self, path):
    """Let the engine know a file has changed.
    
    This allows the engine to invalidate any information about the file
    it may have previously cached.
    
    @param path: The path of the file that has changed.
    @type path: string
    """
    self._timestampCache.pop(path, None)
    
  def getTimestamp(self, path):
    """Get the timestamp of the file at the specified path.
    
    @param path: Path of the file whose timestamp you want.
    @type path: string
    
    @return: The timestamp in seconds since 1 Jan, 1970 UTC.
    @rtype: float 
    """
    timestamp = self._timestampCache.get(path, None)
    if timestamp is None:
      stat = os.stat(path)
      timestamp = time.mktime(time.gmtime(stat.st_mtime))
      # The above calculation truncates to the nearest second so we need to
      # re-add the fractional part back to the timestamp otherwise 
      timestamp += math.fmod(stat.st_mtime, 1)
      self._timestampCache[path] = timestamp
    return timestamp

  def updateFileDigestCache(self, path, timestamp, digest):
    """Update the internal cache of file digests with a new entry.
    
    @param path: The path of the file.
    @param timestamp: The timestamp of the file at the time the digest
    was calculated.
    @param digest: The digest of the contents of the file.
    """
    key = (path, timestamp)
    self._digestCache[key] = digest

  def getFileDigest(self, path):
    """Get the SHA1 digest of a file's contents.
    
    @param path: Path of the file to digest.
    @type path: string
    
    @return: The SHA1 digest of the file's contents.
    @rtype: string of 20 bytes
    """
    timestamp = self.getTimestamp(path)
    key = (path, timestamp)
    digest = self._digestCache.get(key, None)
    if digest is None:
      hasher = cake.hash.sha1()
      f = open(path, 'rb')
      try:
        blockSize = 512 * 1024
        data = f.read(blockSize)
        while data:
          hasher.update(data)
          data = f.read(blockSize)
      finally:
        f.close()
      digest = hasher.digest()
      self._digestCache[key] = digest
      
    return digest
    
  def getDependencyInfo(self, targetPath):
    """Load the dependency info for the specified target.
    
    The dependency info contains information about the parameters and
    dependencies of a target at the time it was last built.
    
    @param targetPath: The path of the target.
    @type targetPath: string 
    
    @return: A DependencyInfo object for the target.
    @rtype: L{DependencyInfo}
    
    @raise EnvironmentError: if the dependency info could not be retrieved.
    """
    dependencyInfo = self._dependencyInfoCache.get(targetPath, None)
    if dependencyInfo is None:
      depPath = targetPath + '.dep'
      
      # Read entire file at once otherwise thread-switching will kill
      # performance
      f = open(depPath, 'rb')
      try:
        dependencyString = f.read()
      finally:
        f.close()
        
      dependencyInfo = pickle.loads(dependencyString) 
      
      # Check that the dependency info is valid  
      if not isinstance(dependencyInfo, DependencyInfo):
        raise EnvironmentError("invalid dependency file")

      self._dependencyInfoCache[targetPath] = dependencyInfo
      
    return dependencyInfo

  def checkDependencyInfo(self, targetPath, args):
    """Check dependency info to see if the target is up to date.
    
    The dependency info contains information about the parameters and
    dependencies of a target at the time it was last built.
    
    @param targetPath: The path of the target.
    @type targetPath: string 
    @param args: The current arguments.
    @type args: list of string 

    @return: A tuple containing the previous DependencyInfo or None if not
    found, and the string reason to build or None if the target is up
    to date.
    @rtype: tuple of (L{DependencyInfo} or None, string or None)
    """
    try:
      dependencyInfo = self.getDependencyInfo(targetPath)
    except EnvironmentError:
      return None, "'" + targetPath + ".dep' doesn't exist"

    if dependencyInfo.version != DependencyInfo.VERSION:
      return None, "'" + targetPath + ".dep' version has changed"

    if self.forceBuild:
      return dependencyInfo, "rebuild has been forced"

    if args != dependencyInfo.args:
      return dependencyInfo, "'" + repr(args) + "' != '" + repr(dependencyInfo.args) + "'"
    
    isFile = cake.filesys.isFile
    for target in dependencyInfo.targets:
      if not isFile(target):
        return dependencyInfo, "'" + target + "' doesn't exist"
    
    getTimestamp = self.getTimestamp
    paths = dependencyInfo.depPaths
    timestamps = dependencyInfo.depTimestamps
    assert len(paths) == len(timestamps)
    for i in xrange(len(paths)):
      path = paths[i]
      try:
        if getTimestamp(path) != timestamps[i]:
          return dependencyInfo, "'" + path + "' has changed since last build"
      except EnvironmentError:
        return dependencyInfo, "'" + path + "' no longer exists" 
    
    return dependencyInfo, None

  def createDependencyInfo(self, targets, args, dependencies, calculateDigests=False):
    """Construct a new DependencyInfo object.
    
    @param targets: A list of file paths of targets.
    @type targets: list of string
    @param args: A value representing the parameters of the build.
    @type args: object
    @param dependencies: A list of file paths of dependencies.
    @type dependencies: list of string
    @param calculateDigests: Whether or not to store the digests of
    dependencies in the DependencyInfo.
    @type calculateDigests: bool
    
    @return: A DependencyInfo object.
    """
    dependencyInfo = DependencyInfo(targets=list(targets), args=args)
    paths = dependencyInfo.depPaths = list(dependencies)
    getTimestamp = self.getTimestamp
    dependencyInfo.depTimestamps = [getTimestamp(p) for p in paths]
    if calculateDigests:
      getFileDigest = self.getFileDigest
      dependencyInfo.depDigests = [getFileDigest(p) for p in paths]
    return dependencyInfo

  def storeDependencyInfo(self, dependencyInfo):
    """Call this method after a target was built to save the
    dependencies of the target.
    
    @param dependencyInfo: The dependency info object to be stored.
    @type dependencyInfo: L{DependencyInfo}  
    """
    depPath = dependencyInfo.targets[0] + '.dep'
    for target in dependencyInfo.targets:
      self._dependencyInfoCache[target] = dependencyInfo
    
    dependencyString = pickle.dumps(dependencyInfo, pickle.HIGHEST_PROTOCOL)
    
    cake.filesys.makeDirs(cake.path.dirName(depPath))
    f = open(depPath, 'wb')
    try:
      f.write(dependencyString)
    finally:
      f.close()
    
class DependencyInfo(object):
  """Object that holds the dependency info for a target.
  
  @ivar version: The version of this dependency info.
  @type version: int
  @ivar targets: A list of target file paths.
  @type targets: list of strings
  @ivar args: The arguments used for the build.
  @type args: usually a list of string's
  """
  
  VERSION = 3
  """The most recent DependencyInfo version."""
  
  def __init__(self, targets, args):
    self.version = self.VERSION
    self.targets = targets
    self.args = args
    self.depPaths = None
    self.depTimestamps = None
    self.depDigests = None

  def primeFileDigestCache(self, engine):
    """Prime the engine's file-digest cache using any cached
    information stored in this dependency info.
    """
    if self.depDigests and self.depTimestamps:
      assert len(self.depDigests) == len(self.depPaths)
      assert len(self.depTimestamps) == len(self.depPaths)
      paths = self.depPaths
      timestamps = self.depTimestamps
      digests = self.depDigests
      updateFileDigestCache = engine.updateFileDigestCache
      for i in xrange(len(paths)):
        updateFileDigestCache(paths[i], timestamps[i], digests[i])

  def isUpToDate(self, engine, args):
    """Query if the targets are up to date.
    
    @param engine: The engine instance.
    @type engine: L{Engine}
    @param args: The current args.
    @type args: usually a list of string's
    @return: True if the targets are up to date, otherwise False.
    @rtype: bool
    """
    if self.version != self.VERSION:
      return False
    
    if args != self.args:
      return False
    
    isFile = cake.filesys.isFile
    for target in self.targets:
      if not isFile(target):
        return False

    assert len(self.depTimestamps) == len(self.depPaths)
    
    getTimestamp = engine.getTimestamp
    paths = self.depPaths
    timestamps = self.depTimestamps
    for i in xrange(len(paths)):
      try:
        if getTimestamp(paths[i]) != timestamps[i]:
          return False
      except EnvironmentError:
        # File doesn't exist any more?
        return False
      
    return True

  def calculateDigest(self, engine):
    """Calculate the digest of the sources/dependencies.

    @param engine: The engine instance.
    @type engine: L{Engine}
    @return: The current digest of the dependency info.
    @rtype: string of 20 bytes
    """
    self.primeFileDigestCache(engine)
    
    hasher = cake.hash.sha1()
    addToDigest = hasher.update
    
    encodeToUtf8 = lambda value, encode=codecs.utf_8_encode: encode(value)[0]
    getFileDigest = engine.getFileDigest 
    
    # Include the paths of the targets in the digest
    for target in self.targets:
      addToDigest(encodeToUtf8(target))
      
    # Include parameters of the build    
    addToDigest(encodeToUtf8(repr(self.args)))
    
    for path in self.depPaths:
      # Include the dependency file's path and content digest in
      # this digest.
      addToDigest(encodeToUtf8(path))
      addToDigest(getFileDigest(path))
      
    return hasher.digest()

class Script(object):
  """A class that represents an instance of a Cake script. 
  """
  
  _current = threading.local()
  
  def __init__(self, path, variant, engine, task, parent=None):
    """Constructor.
    
    @param path: The path to the script file.
    @param variant: The variant to build.
    @param engine: The engine instance.
    @param task: A task that should complete when all tasks within
    the script have completed.
    @param parent: The parent script or None if this is the root script. 
    """
    self.path = path
    self.dir = os.path.dirname(path)
    self.variant = variant
    self.engine = engine
    self.task = task
    if parent is None:
      self.root = self
      self._included = {self.path : self}
    else:
      self.root = parent.root
      self._included = parent._included

  @staticmethod
  def getCurrent():
    """Get the current thread's currently executing script.
    
    @return: The currently executing script.
    @rtype: L{Script}
    """
    return getattr(Script._current, "value", None)
  
  @staticmethod
  def getCurrentRoot():
    """Get the current thread's root script.
    
    This is the top-level script currently being executed.
    A script may not be the top-level script if it is executed due
    to inclusion from another script.
    """
    current = Script.getCurrent()
    if current is not None:
      return current.root
    else:
      return None

  def cwd(self, *args):
    """Return the path prefixed with the current script's directory.
    """
    return cake.path.join(self.dir, *args)

  def include(self, path):
    """Include another script for execution within this script's context.
    
    A script will only be included once within a given context.
    
    @param path: The path of the file to include.
    @type path: string
    """
    if path in self._included:
      return
      
    includedScript = Script(
      path=path,
      variant=self.variant,
      engine=self.engine,
      task=self.task,
      parent=self,
      )
    self._included[path] = includedScript
    includedScript.execute()
    
  def execute(self):
    """Execute this script.
    """
    # Use an absolute path so an absolute path is embedded in the .pyc file.
    # This will make exceptions clickable in Eclipse, but it means copying
    # your .pyc files may cause their embedded paths to be incorrect.
    absPath = os.path.abspath(self.path)
    byteCode = self.engine.getByteCode(absPath)
    old = Script.getCurrent()
    Script._current.value = self
    try:
      exec byteCode in {}
    finally:
      Script._current.value = old
