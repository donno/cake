import subprocess
import cake.filesys
import cake.path
from cake.library import Tool, FileTarget, deepCopyBuiltins, getPathsAndTasks
from cake.engine import Script, DependencyInfo, FileInfo

_undefined = object()

class ShellTool(Tool):

  def __init__(self):
    self.__env = {}

  def run(self, args, targets=None, sources=[], cwd=None):

    script = Script.getCurrent()
    engine = script.engine

    env = deepCopyBuiltins(self.__env)
    
    def spawnProcess():

      if targets:
        # Check dependencies to see if they've changed
        buildArgs = (args, sourcePaths)
        try:
          if all(cake.filesys.isFile(t) for t in targets):
            oldDependencyInfo = engine.getDependencyInfo(targets[0])
            if oldDependencyInfo.isUpToDate(engine, buildArgs):
              # Target is up to date, no work to do
              return
        except EnvironmentError:
          pass
        
      # Create target directories first
      if targets:
        for t in targets:
          cake.filesys.makeDirs(cake.path.dirName(t))

      engine.logger.outputInfo("run: %s\n" % " ".join(args))

      try:
        p = subprocess.Popen(
          args=args,
          env=env,
          stdin=subprocess.PIPE,
          cwd=cwd,
          )
      except EnvironmentError, e:
        msg = "cake: failed to launch %s: %s\n" % (args[0], str(e))
        engine.raiseError(msg)

      p.stdin.close()
      exitCode = p.wait()
      
      if exitCode != 0:
        msg = "%s exited with code %i\n" % (args[0], exitCode)
        engine.raiseError(msg)

      if targets:
        newDependencyInfo = DependencyInfo(
          targets=[FileInfo(path=t) for t in targets],
          args=buildArgs,
          dependencies=[
            FileInfo(path=s, timestamp=engine.getTimestamp(s))
            for s in sourcePaths
            ],
          )

        engine.storeDependencyInfo(newDependencyInfo)

    sourcePaths, tasks = getPathsAndTasks(sources)

    task = engine.createTask(spawnProcess)
    task.startAfter(tasks)

    if targets is None:
      return task
    else:
      return [FileTarget(path=t, task=task) for t in targets]

  def __iter__(self):
    return iter(self.__env)

  def keys(self):
    return self.__env.keys()

  def items(self):
    return self.__env.items()

  def update(self, value):
    return self.__env.update(value)

  def get(self, key, default=_undefined):
    if default is _undefined:
      return self.__env.get(key)
    else:
      return self.__env.get(key, default)

  def __getitem__(self, key):
    return self.__env

  def __setitem__(self, key, value):
    self.__env[key] = value

  def __delitem__(self, key):
    del self.__env[key]

  def appendPath(self, path):
    pathEnv = self.get('PATH', None)
    if pathEnv is None:
      pathEnv = path
    else:
      pathEnv = os.pathsep.join((pathEnv, path))
    self['PATH'] = pathEnv

  def prependPath(self, path):
    pathEnv = self.get('PATH', None)
    if pathEnv is None:
      pathEnv = path
    else:
      pathEnv = os.pathsep.join((path, pathEnv))
    self['PATH'] = pathEnv