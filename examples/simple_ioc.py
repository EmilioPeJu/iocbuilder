#!/usr/bin/env python2.4

import sys
import os
sys.path.append(
    os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

import iocbuilder

iocbuilder.ConfigureIOC()

from iocbuilder import hardware
from iocbuilder import modules
from iocbuilder import ModuleVersion, Substitution, WriteIoc

ModuleVersion('ipac',           '2-8dls4-3')
ModuleVersion('Hy8515',         '3-7')
ModuleVersion('asyn',           '4-9')
ModuleVersion('streamDevice',   '2-4dls2')
ModuleVersion('newstep',        '1-3',  load_path = 'defaults')
ModuleVersion('cmsIon',         '2-10')

from iocbuilder.hardware import streamProtocol


card4 = hardware.Hy8002(4)
serial1 = card4.Hy8515(0)
serial2 = card4.Hy8515(1)


for ch in range(2):
    asyn = hardware.AsynSerial(serial1.channel(ch))
    hardware.NSC200(
        M = 'blah', P = 'blah', PORT = asyn.DeviceName(), CH = ch)

hardware.cmsIon('TEST-BLAH-BLAH', 
    hardware.AsynSerial(serial2.channel(0)), high = 2, hihi = 4)



WriteIoc('iocs', 'BLAH', 'BLAH', 1)
