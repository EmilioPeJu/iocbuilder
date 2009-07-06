from iocbuilder import Substitution, Device
from iocbuilder.arginfo import *

class IOCinfo(Substitution, Device):
    '''Provides basic information about the IOC, supplementing the information
    provided by vxStats: provides temperature information.'''

    # __init__ arguments
    ArgInfo = makeArgInfo(
        device = Simple('Device Prefix', str))

    # Substitution attributes
    Arguments = ArgInfo.Names()
    TemplateFile = 'IOCinfo.template'
    
    # Device attributes    
    DbdFileList = ['IOCinfo']
    LibFileList = ['IOCinfo']
