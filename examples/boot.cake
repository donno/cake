from cake.library.script import ScriptTool
from cake.library.filesys import FileSystemTool
from cake.library.variant import VariantTool
from cake.library.zipping import ZipTool
from cake.library.logging import LoggingTool
from cake.library.project import ProjectTool
from cake.library.env import Environment
from cake.library.compilers import CompilerNotFoundError
from cake.engine import Script, Variant
import cake.system

script = Script.getCurrent()
engine = script.engine
configuration = script.configuration

# This is how you set default keywords passed on the command-line
configuration.defaultKeywords["compiler"] = "all"
configuration.defaultKeywords["release"] = ["debug", "release"]

# This is how you set an alternative base-directory
# All relative paths will be relative to this absolute path.
#configuration.baseDir = configuration.baseDir + '/..'

hostPlatform = cake.system.platform().lower()
hostArchitecture = cake.system.architecture().lower()

base = Variant()
base.tools["script"] = ScriptTool()
base.tools["filesys"] = FileSystemTool()
base.tools["variant"] = VariantTool()
base.tools["zipping"] = ZipTool()
base.tools["logging"] = LoggingTool()
env = base.tools["env"] = Environment()
env["EXAMPLES"] = "."
projectTool = base.tools["project"] = ProjectTool()
projectTool.product = projectTool.VS2008
projectTool.enabled = engine.createProjects
engine.addBuildSuccessCallback(lambda e=engine: projectTool.build(e))

def createVariants(parent):
  for release in ["debug", "release"]:
    variant = parent.clone(release=release)

    platform = variant.keywords["platform"]
    compiler = variant.keywords["compiler"]
    architecture = variant.keywords["architecture"]
    
    env = variant.tools["env"]
    env["BUILD"] = "build/" + "_".join([
      platform,
      compiler,
      architecture,
      release,
      ])
  
    compiler = variant.tools["compiler"]
    compiler.objectCachePath = "cache/obj"
    compiler.enableRtti = True
    compiler.enableExceptions = True
    compiler.outputMapFile = True
    
    if release == "debug":
      compiler.addDefine("_DEBUG")
      compiler.debugSymbols = True
      compiler.useIncrementalLinking = True
      compiler.optimisation = compiler.NO_OPTIMISATION
    elif release == "release":
      compiler.addDefine("NDEBUG")
      compiler.useIncrementalLinking = False
      compiler.useFunctionLevelLinking = True
      compiler.optimisation = compiler.FULL_OPTIMISATION
    
    # Disable the compiler during project generation
    if engine.createProjects:
      compiler.enabled = False

    configuration.addVariant(variant)

# Dummy
from cake.library.compilers.dummy import DummyCompiler
dummy = base.clone(platform=hostPlatform, compiler="dummy", architecture=hostArchitecture)
dummy.tools["compiler"] = DummyCompiler()
createVariants(dummy)

if cake.system.platform() == 'Windows':
  # MSVC
  from cake.library.compilers.msvc import findMsvcCompiler
  for a in ["x86", "x64", "ia64"]:
    try:
      msvc = base.clone(platform="windows", compiler="msvc", architecture=a)
      msvc.tools["compiler"] = findMsvcCompiler(architecture=a) 
      createVariants(msvc)
    except CompilerNotFoundError:
      pass

  try:
    # MinGW
    from cake.library.compilers.gcc import findMinGWCompiler
    mingw = base.clone(platform="windows", compiler="mingw", architecture=hostArchitecture)
    mingw.tools["compiler"] = findMinGWCompiler()
    createVariants(mingw)
  except CompilerNotFoundError:
    pass

try:
  # GCC
  from cake.library.compilers.gcc import findGccCompiler
  gcc = base.clone(platform=hostPlatform, compiler="gcc", architecture=hostArchitecture)
  compiler = gcc.tools["compiler"] = findGccCompiler()
  compiler.addLibrary("stdc++")
  createVariants(gcc)
except CompilerNotFoundError:
  pass
