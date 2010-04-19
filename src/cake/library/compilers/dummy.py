"""A Dummy Compiler.

@see: Cake Build System (http://sourceforge.net/projects/cake-build)
@copyright: Copyright (c) 2010 Lewis Baker, Stuart McMahon.
@license: Licensed under the MIT license.
"""

__all__ = ["DummyCompiler"]

import cake.filesys
import cake.path
from cake.library import memoise, getPathsAndTasks
from cake.library.compilers import Compiler, makeCommand

class DummyCompiler(Compiler):
  
  objectSuffix = '.obj'
  libraryPrefixSuffixes = [('', '.lib')]
  moduleSuffix = '.dll'
  programSuffix = '.exe'
  pchSuffix = '.pch'
  
  def __init__(self):
    Compiler.__init__(self)

  @memoise
  def _getCompileArgs(self, language):
    args = ['cc', '/c']
    if self.debugSymbols:
      args.append('/debug')
    if self.optimisation != self.NO_OPTIMISATION:
      args.append('/O')
    if self.enableRtti:
      args.append('/rtti')
    if self.enableExceptions:
      args.append('/ex')
    if language:
      args.append('/lang:%s' % language)
    args.extend('/I%s' % p for p in self.getIncludePaths())
    args.extend('/D%s' % d for d in self.getDefines())
    args.extend('/FI%s' % p for p in getPathsAndTasks(self.getForcedIncludes())[0])
    return args

  def getPchCommands(self, target, source, header, object, configuration):

    language = self.language
    if not language:
      if source.lower().endswith('.c'):
        language = 'c'
      else:
        language = 'c++'

    compilerArgs = list(self._getCompileArgs(language))
    compilerArgs += ['/H' + header, source, '/o' + target]
    
    def compile():
      configuration.engine.logger.outputDebug("run", "%s\n" % " ".join(compilerArgs))
      absTarget = configuration.abspath(target)
      cake.filesys.makeDirs(cake.path.dirName(absTarget))
      f = open(absTarget, 'wb')
      f.close()
        
      dependencies = [source]
      return dependencies

    canBeCached = True
    return compile, compilerArgs, canBeCached

  def getObjectCommands(self, target, source, pch, configuration):

    language = self.language
    if not language:
      if source.lower().endswith('.c'):
        language = 'c'
      else:
        language = 'c++'

    compilerArgs = list(self._getCompileArgs(language))
    compilerArgs += [source, '/o' + target]
    
    def compile():
      configuration.engine.logger.outputDebug("run", "%s\n" % " ".join(compilerArgs))
      absTarget = configuration.abspath(target)
      cake.filesys.makeDirs(cake.path.dirName(absTarget))
      f = open(absTarget, 'wb')
      f.close()
        
      dependencies = [source]
      if pch is not None:
        dependencies.append(pch.path)
      return dependencies

    canBeCached = True
    return compile, compilerArgs, canBeCached

  def getLibraryCommand(self, target, sources, configuration):
    
    args = ['ar'] + sources + ['/o' + target]

    @makeCommand(args)
    def archive():
      configuration.engine.logger.outputDebug("run", "%s\n" % " ".join(args))
      absTarget = configuration.abspath(target)
      cake.filesys.makeDirs(cake.path.dirName(absTarget))
      f = open(absTarget, 'wb')
      f.close()
      
    @makeCommand("dummy-scanner")
    def scan():
      return sources
      
    return archive, scan
  
  def getProgramCommands(self, target, sources, configuration):
    args = ['ld'] + sources + ['/o' + target]
    
    @makeCommand(args)
    def link():
      configuration.engine.logger.outputDebug("run", "%s\n" % " ".join(args))
      absTarget = configuration.abspath(target)
      cake.filesys.makeDirs(cake.path.dirName(absTarget))
      f = open(absTarget, 'wb')
      f.close()
    
    @makeCommand("dummy-scanner")
    def scan():
      return sources
    
    return link, scan
    
  def getModuleCommands(self, target, sources, configuration):
    # Lazy
    return self.getProgramCommands(target, sources, configuration)
