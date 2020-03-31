from ctypes import *
from os import access, path, R_OK

from iocbuilder import paths

import platform


_FunctionList = (
    ('dbFreeBase',          None, (c_void_p,)),
    ('dbReadDatabase',      c_int, (c_void_p, c_char_p, c_char_p, c_char_p)),
    ('dbAllocEntry',        c_void_p, (c_void_p,)),
    ('dbFirstRecordType',   c_int, (c_void_p,)),
    ('dbGetRecordTypeName', c_char_p, (c_void_p,)),
    ('dbNextRecordType',    c_int, (c_void_p,)),
    ('dbFreeEntry',         None, (c_void_p,)),
    ('dbCopyEntry',         c_void_p, (c_void_p,)),
    ('dbFirstField',        c_int, (c_void_p,)),
    ('dbGetFieldName',      c_char_p, (c_void_p,)),
    ('dbGetPrompt',         c_char_p, (c_void_p,)),
    ('dbGetPromptGroup',    c_int, (c_void_p,)),
    ('dbGetFieldType',      c_int, (c_void_p,)),
    ('dbGetNMenuChoices',   c_int, (c_void_p,)),
    ('dbGetMenuChoices',    c_void_p, (c_void_p,)),
    ('dbNextField',         c_int, (c_void_p,)),
    ('dbGetString',         c_char_p, (c_void_p,)),
    ('dbVerify',            c_char_p, (c_void_p, c_char_p)),
)

# This function is called late to complete the process of importing all the
# exports from this module.  This is done late so that paths.EPICS_BASE can be
# configured late.
def ImportFunctions():
    # Mapping from host architecture to EPICS host architecture name can be done
    # with a little careful guesswork.  As EPICS architecture names are a little
    # arbitrary this isn't guaranteed to work.
    system_map = {
        ('Linux',   '32bit'):   'linux-x86',
        ('Linux',   '64bit'):   'linux-x86_64',
        ('Darwin',  '32bit'):   'darwin-x86',
        ('Darwin',  '64bit'):   'darwin-x86',
        ('Windows', '32bit'):   'win32-x86',
        ('Windows', '64bit'):   'windows-x64',  # Not quite yet!
    }
    bits = platform.architecture()[0]
    current_host_arch = system_map[(platform.system(), bits)]

    libdir = path.join(paths.EPICS_BASE, 'lib', current_host_arch)
    libpath_r3 = path.join(libdir, 'libdbStaticHost.so')
    libpath_r7 = path.join(libdir, 'libdbCore.so')
    if access(libpath_r3, R_OK):
        libdb = CDLL(libpath_r3)
    elif access(libpath_r7, R_OK):
        libdb = CDLL(libpath_r7)
    else:
        raise OSError("EPICS db library not found")

    for name, restype, argtypes in _FunctionList:
        function = getattr(libdb, name)
        function.restype = restype
        function.argtypes = argtypes
        globals()[name] = function
