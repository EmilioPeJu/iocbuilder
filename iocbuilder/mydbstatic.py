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
    ('dbGetNMenuChoices',   c_int, (c_void_p,)),
    ('dbGetMenuChoices',    c_void_p, (c_void_p,)),
    ('dbNextField',         c_int, (c_void_p,)),
    ('dbGetString',         c_char_p, (c_void_p,)),
    ('dbVerify',            c_char_p, (c_void_p, c_char_p)),
)


_dctGetType = ('dbGetFieldType',      c_int, (c_void_p,))
_getType = ('dbGetFieldDbfType',   c_int, (c_void_p,))


def _populateRecordConstants(dct):
    # populate constants used for field types
    #
    # Because the DCT get type function was removed in R7, there are 2 sets of
    # constants for backward compatibility.
    # In order to make it generic, the following convenient lists of
    # types are exported:
    # FIELD_INT_TYPES, FIELD_CHOICE_TYPES, FIELD_REAL_TYPES and
    # FIELD_STRING_TYPES
    if dct:
        (DCT_STRING, DCT_INTEGER, DCT_REAL, DCT_MENU, DCT_MENUFORM, DCT_INLINK,
         DCT_OUTLINK, DCT_FWDLINK, DCT_NOACCESS) = range(9)
        FIELD_INT_TYPES = [DCT_INTEGER]
        FIELD_CHOICE_TYPES = [DCT_MENU, DCT_MENUFORM]
        FIELD_REAL_TYPES = [DCT_REAL]
        FIELD_STRING_TYPES = [DCT_STRING, DCT_INLINK, DCT_OUTLINK, DCT_FWDLINK]
    else:
        (DBF_STRING, DBF_CHAR, DBF_UCHAR, DBF_SHORT, DBF_USHORT, DBF_LONG,
         DBF_ULONG, DBF_INT64, DBF_UINT64, DBF_FLOAT, DBF_DOUBLE, DBF_ENUM,
         DBF_MENU, DBF_DEVICE, DBF_INLINK, DBF_OUTLINK, DBF_FWDLINK,
         DBF_NOACCESS) = range(18)
        FIELD_INT_TYPES = [DBF_CHAR, DBF_UCHAR, DBF_SHORT, DBF_USHORT,
                           DBF_LONG, DBF_ULONG, DBF_INT64, DBF_UINT64,
                           DBF_ENUM]
        FIELD_CHOICE_TYPES = [DBF_MENU, DBF_DEVICE]
        FIELD_REAL_TYPES = [DBF_FLOAT, DBF_DOUBLE]
        FIELD_STRING_TYPES = [DBF_STRING, DBF_INLINK, DBF_OUTLINK, DBF_FWDLINK]

    for key, val in locals().items():
        if key.startswith('FIELD_'):
            globals()[key] = val


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
    libpath_statichost = path.join(libdir, 'libdbStaticHost.so')
    libpath_dbcore = path.join(libdir, 'libdbCore.so')
    if access(libpath_statichost, R_OK):
        libdb = CDLL(libpath_statichost)
    elif access(libpath_dbcore, R_OK):
        libdb = CDLL(libpath_dbcore)
    else:
        raise OSError("EPICS db library not found")

    dct = hasattr(libdb, _dctGetType[0])
    _populateRecordConstants(dct)

    getFieldName, getFieldRestype, getFieldArgtypes = \
        _dctGetType if dct else _getType
    function = getattr(libdb, getFieldName)
    function.restype = getFieldRestype
    function.argtypes = getFieldArgtypes
    globals()["dbGetFieldType"] = function

    for name, restype, argtypes in _FunctionList:
        function = getattr(libdb, name)
        function.restype = restype
        function.argtypes = argtypes
        globals()[name] = function
