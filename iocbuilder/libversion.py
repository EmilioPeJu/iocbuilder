#   Generic hardware module support

import os.path
import string

from support import autosuper, SameDirFile
from configure import Configure

import modules


__all__ = ['ModuleVersion', 'ModuleBase', 'SetModulePath']



def SetModulePath(prod):
    '''Define the directory path for locating modules.  This works with the
    Diamond directory conventions.'''
    
    global prodSupport
    prodSupport = prod



# Module version information specifying:
#   name     Directory name of module
#   version  Version of module
#   home     Home directory to locate module
class ModuleVersion:
    '''Create instances of this class to declare the version of each module
    to be used.'''

    # Restrict module names to names which can be used as identifiers.  This
    # helps a lot when generating EPICS14 IOCs.
    __ValidNameChars = set(
        string.ascii_uppercase + string.ascii_lowercase +
        string.digits + '_')
    
    def __init__(self, libname,
            version=None, home=None, override=False, use_name=True):
        # By default pick up each module from the prod support directory.  It
        # might be quite nice to extend this with a path search.
        if home is None:
            home = prodSupport

        assert set(libname) <= set(self.__ValidNameChars), \
            'Module name %s must be a valid identifier' % libname
        self.__name = libname
        self.version = version
        self.home = home
        self.use_name = use_name

        # A couple of sanity checks: libname must not be already defined iff
        # version override has not been requested.
        libDefined = libname in _ModuleVersionTable
        assert (not override) <= (not libDefined), \
               'Module %s multiply defined' % libname
        assert override <= libDefined, 'Module %s not defined' % libname
        
        # Add this to the list of module versions
        _ModuleVersionTable[libname] = self

        # Finally attempt to load any definitions associated with this
        # module.
        self.__LoadModuleDefinitions()
        

    def LibPath(self, noVersion=False):
        '''Returns the path to the module directory defined by this entry.'''
        path = self.home
        if self.use_name:
            path = os.path.join(path, self.__name)
        if self.version and not noVersion:
            path = os.path.join(path, self.version)
        return path

    def Name(self):
        '''Returns the module name.'''
        return self.__name

    # The following definitions ensure that when hashed and when compared
    # this class behaves exactly like its name: this ensures that sets and
    # sorted lists of modules behave predicably.
    def __hash__(self):         return hash(self.__name)
    def __cmp__(self, other):   return cmp(self.__name, other.__name)


    def __LoadModuleDefinitions(self):
        # Module definitions will be loaded from one of the following places:
        #   1. <module-path>/python/builder.py
        #   2. defaults/<name>.py
        DefsFile = os.path.join(self.LibPath(), 'python', 'builder.py')
        if not os.access(DefsFile, os.R_OK):
            # Ok, not that.  Try the defaults file.
            DefsFile = SameDirFile(__file__, 'defaults', '%s.py' % self.__name)
            if not os.access(DefsFile, os.R_OK):
                # Not that either.  Never mind then!
                DefsFile = None

        if DefsFile:
            print 'Trying to load', DefsFile

            global_context = Configure._Configure__globals()
            local_context = {}
            print 'globals:', global_context.keys()
            execfile(DefsFile, global_context, local_context)
            print 'globals:', global_context.keys()
            print 'locals:',  local_context.keys()
            if '__all__' in local_context:
                for name in local_context['__all__']:
                    setattr(modules, name, local_context[name])
                print 'modules:', dir(modules)
            
        else:
            print 'No file found for', self.__name

    

class ModuleBase(object):
    '''All entities which need to depend on module versions should subclass
    this class to obtain access to their configuration information.

    By default the name of the class will be used both as an index into the
    ModuleVersion entry and as the subdirectory name in the support directory.
    When the external name of the module doesn't match the class name then
    the symbol ModuleName should be set equal to the external module name
    thus:
        ModuleName = 'true-module-name'

    This class will always define a ModuleName symbol.  If the same module
    is to be used by all subclasses then this can be enabled by defining the
    symbol
        InheritModuleName = True
    '''

    # Meta class used for module instances: ensures that the ModuleName
    # symbol exists, defaulting to the class name.
    # 
    # Optionally the ModuleName can be inherited from the base class if the
    # symbol InheritModuleName is set to True.
    class __ModuleBaseMeta(autosuper):
        def __init__(cls, name, bases, dict):
            # This could more simply be written as autosuper.__...,
            # but then subclassing might go astray.  Module instances are
            # already broadly subclassed, so we ought to play by the rules.
            super(cls._ModuleBase__ModuleBaseMeta, cls).__init__(
                name, bases, dict)

            # If the class hasn't defined its own ModuleName then unless
            # InheritModuleName has been set to true then default ModuleName
            # to the class name.
            if 'ModuleName' not in cls.__dict__ and \
                    not cls.InheritModuleName:
                cls.ModuleName = name

    __metaclass__ = __ModuleBaseMeta


    # By default the module name is not inherited
    InheritModuleName = False

    @classmethod
    def LibPath(cls):
        '''Returns the path to the module.'''
        return cls.ModuleVersion().LibPath()

    @classmethod
    def ModuleFile(cls, filename):
        '''Returns an absolute path to a file within this module.'''
        filename = os.path.join(cls.LibPath(), filename)
        assert os.access(filename, os.R_OK), 'File "%s" not found' % filename
        return filename

    # Set of instantiated modules as ModuleVersion instances
    _ReferencedModules = set()

    # Ensures that this module is added to the list of instantiations.
    def __init__(self):
        self.UseModule()

    @classmethod
    def UseModule(cls):
        cls._ReferencedModules.add(cls.ModuleVersion())

    @classmethod
    def ListModules(cls):
        '''Returns the set of all modules that have been instantiated.  The
        objects returned are ModuleVersion instances.'''
        return cls._ReferencedModules

    @classmethod
    def ModuleVersion(cls):
        '''Returns the ModuleVersion instance associated with this module.'''
        return _ModuleVersionTable[cls.ModuleName]
        


# Dictionary of all modules with announced versions.  This will be
# interrogated when modules are initialised.
_ModuleVersionTable = {}