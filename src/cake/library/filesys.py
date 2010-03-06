"""File System Tool.

@see: Cake Build System (http://sourceforge.net/projects/cake-build)
@copyright: Copyright (c) 2010 Lewis Baker, Stuart McMahon.
@license: Licensed under the MIT license.
"""

import cake.path
import cake.filesys
from cake.library import Tool, FileTarget, getPathAndTask
from cake.engine import Script

class FileSystemTool(Tool):
  """Tool that provides file system related utilities. 
  """

  def copyFile(self, source, target):
    """Copy a file from one location to another.
    
    @param source: The path of the source file or a FileTarget
    representing a file that will be created.
    @type source: string or L{FileTarget}
    
    @param target: The path of the target file to copy to
    @type target: string
    
    @return: A FileTarget representing the file that will be copied.
    @rtype: L{FileTarget}
    """
    if not isinstance(target, basestring):
      raise TypeError("target must be a string")
    
    sourcePath, sourceTask = getPathAndTask(source)
   
    engine = Script.getCurrent().engine
   
    def doCopy():
      
      if engine.forceBuild:
        reasonToBuild = "rebuild has been forced"
      elif not cake.filesys.isFile(target):
        reasonToBuild = "'%s' does not exist" % target
      elif engine.getTimestamp(sourcePath) > engine.getTimestamp(target):
        reasonToBuild = "'%s' is newer than '%s'" % (sourcePath, target)
      else:
        # up-to-date
        return

      engine.logger.outputDebug(
        "reason",
        "Rebuilding '%s' because %s.\n" % (target, reasonToBuild),
        )
      engine.logger.outputInfo("Copying %s to %s\n" % (sourcePath, target))
      
      try:
        cake.filesys.makeDirs(cake.path.dirName(target))
        cake.filesys.copyFile(sourcePath, target)
      except EnvironmentError, e:
        engine.raiseError("%s: %s\n" % (target, str(e)))

      engine.notifyFileChanged(target)
      
    copyTask = engine.createTask(doCopy)
    copyTask.startAfter(sourceTask)

    return FileTarget(path=target, task=copyTask)

  def copyFiles(self, sources, target):
    """Copy a collection of files to a target directory.
    
    Not yet Implemented!
    
    @param sources: A list of files to copy.
    @type sources: list of string's
    @param target: The target directory to copy to.
    @type target: string
    
    @return: A list of FileTarget's representing the files that will be
    copied.
    @rtype: list of L{FileTarget}
    """
    raise NotImplementedError()
  
  def copyDirectory(self, source, target, pattern=None):
    """Copy the directory's contents to the target directory,
    creating the target directory if needed.

    Not yet Implemented!
    """
    raise NotImplementedError()
  
  