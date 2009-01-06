#!/usr/bin/env python2.4

import sys
import os
import pydoc
import shutil
import types

sys.path.append(os.path.abspath('../build/lib'))
import dls.builder

if os.access('pydoc', os.F_OK):
    shutil.rmtree('pydoc')
os.mkdir('pydoc')
os.chdir('pydoc')

def WriteModules(package):
    for name in dir(package):
        value = getattr(package, name)
        if type(value) is types.ModuleType:
            pydoc.writedoc(value)

pydoc.writedoc(dls.builder)
WriteModules(dls.builder)
WriteModules(dls.builder.hardware)