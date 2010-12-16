'''The IOC writers defined here are designed to be passed to the library
Configure call as an 'iocwriter' argument.'''

import sys, time
import os, os.path
import shutil
import types
import fnmatch
import subprocess

import iocinit
import recordset
import configure
import libversion
import hardware
import paths

from liblist import Hardware


__all__ = ['IocWriter', 'SimpleIocWriter', 'DiamondIocWriter', 'SetSource',
    'DocumentationIocWriter', 'DbOnlyWriter']

_Source = os.path.realpath(sys.argv[0])

# Set Source that appears in headers to be something other than the calling
# program.
def SetSource(s):
    global _Source
    _Source = s

def PrintDisclaimer(s, m=None, e=''):
    if m is None:  m = s
    now = time.strftime('%a %d %b %Y %H:%M:%S %Z')
    source = _Source
    message = '''\
This file was automatically generated on %(now)s from
source: %(source)s

*** Please do not edit this file: edit the source file instead. ***
''' % locals()
    print s + ('\n' + m).join(message.split('\n')) + e

def PrintDisclaimerScript():
    PrintDisclaimer('# ')

def PrintDisclaimerC():
    PrintDisclaimer('/* ', ' * ', ' */')

def PrintDisclaimerCommand(cmd):
    def f():
        print '#!' + cmd
        PrintDisclaimerScript()
    return f


# A support routine for writing files using the print mechanism.  This is
# simply a wrapper around sys.stdout redirection.  Use this thus:
#     output = WriteFileWrapper(filename)
#     ... write to stdout using print etcetera ...
#     output.Close()
# By default the standard disclaimer header is printed at the start of the
# generated file.
class WriteFileWrapper:

    # Set header=None to suppress header output.
    def __init__(self, filename,
            header=PrintDisclaimerScript, maxLineLength=0, mode='w'):
        self.__stdout = sys.stdout
        self.__output = open(filename, mode)
        self.__line = ''

        self.__maxLineLength = maxLineLength
        if self.__maxLineLength:
            sys.stdout = self
        else:
            sys.stdout = self.__output

        if header:
            header()

    def write(self, string):
        # Check that no line exceeds the maximum line length
        lines = string.split('\n')
        for line in lines[:-1]:
            full_line = self.__line + line
            self.__line = ''
            assert len(full_line) <= self.__maxLineLength, \
                'Line %s too long' % repr(full_line)
        self.__line = self.__line + lines[-1]

        self.__output.write(string)

    # Call this to close the file being written and to restore normal output
    # to stdout.
    def Close(self):
        assert self.__output != None, 'Close called out of sequence.'
        assert len(self.__line) <= self.__maxLineLength, \
            'Unterminated line %s too long' % repr(self.__line)
        self.__output.close()
        self.__output = None
        sys.stdout = self.__stdout


def WriteFile(filename, writer, *argv, **argk):
    output = WriteFileWrapper(filename, **argk)
    if callable(writer):
        writer(*argv)
    else:
        print writer
    output.Close()


# Class to support the creation of data files, either dynamically generated
# inline, or copied from elsewhere.  Designed to be passed down to makefile
# building tasks.
class DataDirectory:
    def __init__(self, ioc_root, directory):
        self.files = set()
        self.ioc_root = ioc_root
        self.directory = directory

    def Path(self, filename = None, absolute = False):
        if absolute:
            join = [self.ioc_root, self.directory]
        else:
            join = [self.directory]
        if filename is not None:
            join.append(filename)
        return os.path.join(*join)

    def __AddFilename(self, filename):
        assert '/' not in filename, 'Invalid target filename %s' % filename
        assert filename not in self.files, \
            'Filename %s already added' % filename

    # Opens a new file in the target directory.
    def OpenFile(self, filename):
        self.__AddFilename(filename)
        return file(self.Path(filename, True), 'w')

    # Copies the given file into the target directory, possibly giving a new
    # name.
    def CopyFile(self, filename, target_name=None):
        if target_name is None:
            target_name = os.path.basename(filename)
        self.__AddFilename(target_name)
        shutil.copyfile(filename, self.Path(target_name, True))


# Class to support the generation of makefiles.
class Makefile:
    def __init__(self, path, header, footer, name = 'Makefile'):
        self.path = path
        self.header = header
        self.lines = []
        self.footer = footer
        self.rules = []
        self.name = name

    def AddLine(self, *lines):
        self.lines.extend(lines)

    def AddRule(self, rule):
        self.rules.append(rule)

    def __print(self, lines):
        for line in lines:
            print line

    def Generate(self, root):
        output = WriteFileWrapper(os.path.join(root, self.path, self.name))
        self.__print(self.header)
        print
        self.__print(self.lines)
        print
        self.__print(self.footer)
        print
        self.__print(self.rules)
        output.Close()



# Base class for IOC writer.  A subclass of this class should be passed
# as an iocwriter option to the epics.Configure method.
#     Methods are provided for access to all of the resources which define
# an IOC.
class IocWriter:
    # Some target specific maximum line lengths for the IOC shell
    IOCmaxLineLength_vxWorks = 126      # Oops
    IOCmaxLineLength_linux = 0          # EPICS shell is better behaved

    def __init__(self, iocRoot=''):
        self.iocRoot = iocRoot

        # Set up the appropriate methods for the actions required during IOC
        # writing.

        # Printout of records and subsititution files
        self.PrintRecords = recordset.RecordSet.Print
        self.PrintSubstitutions = recordset.RecordsSubstitutionSet.Print
        # Alternative to mass expand substitution files at build time
        self.ExpandSubstitutions = \
            recordset.RecordsSubstitutionSet.ExpandSubstitutions

        self.CountRecords = recordset.RecordSet.CountRecords
        self.CountSubstitutions = \
            recordset.RecordsSubstitutionSet.CountSubstitutions

        # Print st.cmd for IOC
        self.PrintIoc = iocinit.iocInit.PrintIoc

        # Add filename to list of databases known to this IOC
        self.AddDatabase = iocinit.iocInit.AddDatabaseName

        # Copies all files bound to IOC into given location
        self.SetDataPath = iocinit.IocDataSet.SetDataPath
        self.CopyDataFiles = iocinit.IocDataSet.CopyDataFiles
        self.DataFileCount = iocinit.IocDataSet.DataFileCount

        self.IOCmaxLineLength = getattr(self,
            'IOCmaxLineLength_%s' % configure.TargetOS(), 0)

        self.SetIocName = iocinit.iocInit.SetIocName



    def WriteFile(self, filename, writer, *argv, **argk):
        if not isinstance(filename, types.StringTypes):
            filename = os.path.join(*filename)
        WriteFile(os.path.join(self.iocRoot, filename), writer, *argv, **argk)


    # This method resets only the record data but not the remaining IOC state.
    # This should only be used if incremental record creation without building
    # a new IOC is required.
    #
    # It is harmless to call this method repeatedly.
    def ResetRecords(self):
        recordset.Reset()



## This is the simplest possible IOC writer.  Two methods are supported,
# WriteRecords and WriteHardware, which write out respectively the set of
# generated records and the IOC startup script.
class SimpleIocWriter(IocWriter):

    __all__ = ['WriteRecords', 'WriteHardware']

    ## Writes all the currently generated records to the given file.
    # The set of records will be reset after this has been done, and so
    # further records can be generated and written.
    def WriteRecords(self, filename):
        # Let the IOC know about this database.
        self.AddDatabase(filename)
        # Write out the database: record set and template expansions.  In
        # this version we fully expand template instances.
        self.WriteFile(filename, self.PrintAndExpandRecords)
        # Finally reset the record set.
        self.ResetRecords()

    def PrintAndExpandRecords(self):
        self.PrintRecords()
        self.ExpandSubstitutions()

    ## Writes out the IOC startup command file.  The entire internal state
    # (apart from configuration) is reset: this allows a new IOC application
    # to be generated from scratch if required.
    #
    # Note that this function is strongly deprecated and probably no longer
    # works: use DiamondIocWriter instead!
    def WriteHardware(self, filename):
        self.WriteFile(filename, self.PrintIoc,
            maxLineLength=self.IOCmaxLineLength)

## This IOC Writer creates a documentation file for doxygen detailing how
# to build this IOC
class DocumentationIocWriter(IocWriter):
    __all__ = ['WriteNamedIoc']

    ## Creates build instructions page in path.
    # Simply wraps \ref DocumentationIocWriter.__init__
    @classmethod
    def WriteNamedIoc(cls, *args, **kargs):
        cls(*args, **kargs)

    ## Creates build instructions page in path. The file is written to \c path
    # using doxygen syntax so that it can appear in the documentation.
    # \param path
    #   Full path of the filename to write to
    # \param ioc_name
    #   Name of IOC used in instructions
    # \param *args
    #   Discarded
    # \param **kwargs
    #   Discarded
    def __init__(self, path, ioc_name, *args, **kwargs):
        # Remember parameters
        fname = os.path.basename(path)
        path = os.path.dirname(path)
        IocWriter.__init__(self, path)  # Sets up iocRoot
        self.ioc_name = ioc_name
        self.page_name = fname
        self.SetIocName(self.ioc_name, False)
        for func in _DbMakefileHooks:
            func(Makefile("", "", ""), self.ioc_name, "", "")
        self.WriteFile(fname, self.CreateBuildInstructions)

    def CreateBuildInstructions(self):
        print "/**"
        print "\page %s Build Instructions for %s" % \
            (self.page_name, self.ioc_name)
        print "Build Instructions for %s" %self.ioc_name
        print "<ol>"
        print "<li> Add the dependencies to configure/RELEASE."
        print "\\verbatim"
        gen_paths = [(m.LibPath(), m.MacroName())
            for m in libversion.ModuleBase.ListModules()]
        for path,name in gen_paths:
            if name != "EPICS_BASE":
                print name+"="+path
        print "\\endverbatim"
        print
        print "<li> Add the DBD dependencies to src/Makefile"
        print "\\verbatim"
        for dbd in Hardware.GetDbdList():
            print "%s_DBD += %s.dbd" % (self.ioc_name, dbd)
        print "\\endverbatim"
        print
        print "<li> Add the LIBS dependencies to src/Makefile"
        print "\\verbatim"
        for lib in reversed(Hardware.GetLibList()):
            print "%s_LIBS += %s" % (self.ioc_name, lib)
        for lib in reversed(Hardware.GetSysLibList()):
            print '%s_SYS_LIBS += %s' % (self.ioc_name, lib)
        print "\\endverbatim"
        print
        print "<li> Use the template files to add records to the database."
        print "\\verbatim"
        recordset.RecordsSubstitutionSet.Print()
        print "\\endverbatim"
        print
        print "<li> Add the startup commands to st.cmd"
        print "\\verbatim"
        Hardware.PrintBody()
        Hardware.PrintPostIocInit()
        print "\\endverbatim"
        print "</ol>"
        print "**/"


## This IOC Writer creates a db file and a substitution file for this IOC
class DbOnlyWriter(IocWriter):
    __all__ = ['WriteNamedIoc']

    ## Creates build instructions page in path.
    # Simply wraps \ref DbOnlyWriter.__init__
    @classmethod
    def WriteNamedIoc(cls, *args, **kargs):
        cls(*args, **kargs)

    ## Creates build instructions page in path. The file is written to \c path
    # using doxygen syntax so that it can appear in the documentation.
    # \param path
    #   Full path of the substitution file
    # \param ioc_name
    #   Name of IOC used in instructions
    # \param *args
    #   Discarded
    # \param **kwargs
    #   Discarded
    def __init__(self, path, ioc_name, *args, **kwargs):
        # Remember parameters
        IocWriter.__init__(self, path)  # Sets up iocRoot
        self.ioc_name = ioc_name
        self.SetIocName(self.ioc_name, False)
        for func in _DbMakefileHooks:
            func(Makefile('', '', ''), self.ioc_name, '', '')

        db = self.ioc_name + '.db'
        substitutions = self.ioc_name + '_expanded.substitutions'
        if self.CountRecords():
            self.WriteFile(db, self.PrintRecords)
        if self.CountSubstitutions():
            self.WriteFile(substitutions, self.PrintSubstitutions)
        else:
            self.WriteFile(substitutions, '')



## This IOC writer generates a complete IOC application tree in the Diamond
# style.
class DiamondIocWriter(IocWriter):
    __all__ = ['WriteIoc', 'WriteNamedIoc']


    MAIN_CPP = '''\
#include "epicsExit.h"
#include "epicsThread.h"
#include "iocsh.h"

int main(int argc,char *argv[])
{
    if(argc>=2) {
        iocsh(argv[1]);
        epicsThreadSleep(.2);
    }
    iocsh(NULL);
    epicsExit(0);
    return 0;
}
'''

    # Startup shell script for linux IOC
    LINUX_CMD = '''\
cd "$(dirname "$0")"
#    export HOME_DIR="$(cd "$(dirname "$0")"/../..; pwd)"
# cd "$HOME_DIR"
./%(ioc)s st%(ioc)s.boot'''

    # Configuration.  Unfortunately we need different configurations for old
    # and newer versions of EPICS: we can't write CHECK_RELEASE to CONFIG, so
    # at least for now we don't write it at all!
    CONFIG_TEXT = '''\
CROSS_COMPILER_TARGET_ARCHS = %(ARCH)s
'''
    CONFIG_SITE_TEXT = '''\
CROSS_COMPILER_TARGET_ARCHS = %(ARCH)s
CHECK_RELEASE = %(CHECK_RELEASE)s
'''


    # Makefile templates
    TOP_MAKEFILE_HEADER = [
        'TOP = .',
        'include $(TOP)/configure/CONFIG']
    TOP_MAKEFILE_FOOTER = [
        'include $(TOP)/configure/RULES_TOP']

    MAKEFILE_HEADER = [
        'TOP = ../..',
        'include $(TOP)/configure/CONFIG']
    EDL_MAKEFILE_HEADER = [
        'TOP = ../../..',
        'include $(TOP)/configure/CONFIG']
    MAKEFILE_FOOTER = [
        'include $(TOP)/configure/RULES']


    # Directory helper routines

    def MakeDirectory(self, *dir_names):
        os.makedirs(os.path.join(self.iocRoot, *dir_names))

    def DeleteIocDirectory(self, makefile_name):
        # Checks that the newly computed iocBoot directory is a plausible IOC
        # directory.  This prevents any unfortunate accidents caused by
        # accidentially pointing at some other directory by mistake...
        #    The only files we can absolutely expect to be present are the
        # configure and iocBoot directories (as these are created by
        # __init__), and we allow for all the built directories and our App
        # directories.  Anything else is suspicious!
        dirlist = os.listdir(self.iocRoot)
        require_list = ['configure', 'iocBoot']
        ignore_list = ['bin', 'db', 'dbd', 'Makefile', 'data'] + \
            fnmatch.filter(dirlist, '%sApp' % (self.ioc_name)) + \
            self.keep_files + [makefile_name]
        checklist = set(dirlist) - set(ignore_list)
        assert checklist <= set(require_list), \
            'Directory %s doesn\'t appear to be an IOC directory' % \
                self.iocRoot
        if self.keep_files:
            for file in dirlist:
                if file not in self.keep_files:
                    file = os.path.join(self.iocRoot, file)
                    try:
                        os.remove(file)
                    except OSError:
                        shutil.rmtree(file)
        else:
            shutil.rmtree(self.iocRoot)


    # Published methods: alternative IOC constructors

    ## A wrapper around WriteNamedIoc() to write an IOC with standard name.
    #
    # The IOC written by this call is placed below \<path> in the directory
    # \code
    #   <path>/<domain>/<iocDir>
    # \endcode
    #
    # where \<ioc>=\<domain>-\<techArea>-IOC-\<id> and \<iocDir> is either
    # \<techArea> or \<ioc> depending on whether \c long_name is set.
    #
    # \param path
    # \param domain
    # \param techArea
    # \param id
    #   The IOC name is computed from these four parameters as described
    #   above.
    # \param long_name
    #   Determines whether the full IOC name is used as part of the path to
    #   the IOC.
    # \param **kargs
    #   See WriteNamedIoc() for the remaining possible arguments.
    @classmethod
    def WriteIoc(cls,
            path, domain, techArea, id = 1, long_name = False, **kargs):
        ioc_name = '%s-%s-IOC-%02d' % (domain, techArea, id)
        if long_name:
            iocDir = ioc_name
        else:
            iocDir = techArea
        cls.WriteNamedIoc(
            os.path.join(path, domain, iocDir), ioc_name, **kargs)

    ## Creates an IOC in path with the specified name.
    # Simply wraps \ref DiamondIocWriter.__init__
    @classmethod
    def WriteNamedIoc(cls, *args, **kargs):
        cls(*args, **kargs)


    # Top level IOC writer control

    ## Creates an IOC in path with the specified name.  A complete standard
    # IOC directory is created and population based at \c path with internal
    # name \c ioc_name.  The directory structure is:
    #
    # \verbatim
    #  <path>/
    #    Makefile         Top level makefile to call <ioc>App Makefiles
    #    iocBoot/
    #      ioc<ioc_name>/       Directory for st.cmd and other ioc resources
    #        st<ioc_name>.cmd   IOC startup script
    #        <ioc files>        Other ioc specific files may be placed here
    #    <ioc_name>App/
    #      Makefile       Makefile to build IOC db directory and file
    #      Db/            Directory containing substitutions and other files
    #        <ioc>.db     Generated database file
    #        <ioc>.substitutions   Substitutions file
    # \endverbatim
    #
    # The target directory is erased unless the \c keep_files parameter is
    # set.
    #
    # \param path
    #   Directory where IOC will be written
    # \param ioc_name
    #   Name of IOC used for internal files
    # \param check_release
    #   Whether to set the CHECK_RELEASE flag in the build.  Defaults to True.
    # \param substitute_boot
    #   Whether \c msi is run over the generated boot scripts.  Defaults to
    #   False, not really recommended as can generate broken boot scripts
    #   without warning.
    # \param keep_files
    #   List of files in \c path to keep, defaults to empty list.  If empty
    #   the IOC directory is completely erased.
    # \param makefile_name
    #   Name of the makefile for the generated IOC, defaults to \c Makefile.
    def __init__(self, path, ioc_name,
            check_release = True, substitute_boot = False, edm_screen = False,
            keep_files = [], makefile_name = 'Makefile'):
        # Remember parameters
        IocWriter.__init__(self, path)  # Sets up iocRoot
        self.check_release = check_release
        self.substitute_boot = substitute_boot
        self.keep_files = keep_files
        self.edm_screen = edm_screen

        self.cross_build = configure.Architecture() != paths.EPICS_HOST_ARCH

        # Create the working skeleton
        self.CreateIocNames(ioc_name)
        self.StartMakefiles(makefile_name)
        self.CreateSkeleton(makefile_name)

        # Actually generate the IOC
        self.GenerateIoc()

    def CreateIocNames(self, ioc_name):
        # Create the names of the important components: configure, boot, app.
        self.ioc_name = ioc_name
        iocAppDir = ioc_name + 'App'
        self.iocDbDir   = os.path.join(iocAppDir, 'Db')
        self.iocSrcDir  = os.path.join(iocAppDir, 'src')
        if self.edm_screen:
            self.iocEdlDir  = os.path.join(iocAppDir, 'opi', 'edl')
        self.iocBootDir = os.path.join('iocBoot', 'ioc' + ioc_name)
        self.iocDataDir = os.path.join(iocAppDir, 'data')

    def StartMakefiles(self, makefile_name):
        header = self.MAKEFILE_HEADER
        footer = self.MAKEFILE_FOOTER

        self.makefile_db   = Makefile(self.iocDbDir,   header, footer)
        self.makefile_src  = Makefile(self.iocSrcDir,  header, footer)
        self.makefile_boot = Makefile(self.iocBootDir, header, footer)
        if self.edm_screen:
            self.makefile_edl  = Makefile(self.iocEdlDir,
                self.EDL_MAKEFILE_HEADER, footer)
        self.makefile_top  = Makefile('',
            self.TOP_MAKEFILE_HEADER, self.TOP_MAKEFILE_FOOTER,
            name = makefile_name)

    def CreateSkeleton(self, makefile_name):
        # Create the complete skeleton after first erasing any previous IOC
        if os.access(self.iocRoot, os.F_OK):
            self.DeleteIocDirectory(makefile_name)

        # The order here corresponds to the order of generation in the TOP
        # makefile.
        dirs = [
            'configure',
            self.iocDbDir,
            self.iocSrcDir,
            self.iocBootDir]
        if self.edm_screen:
            dirs.append(self.iocEdlDir)
        for d in dirs:
            self.MakeDirectory(d)
            self.makefile_top.AddLine('DIRS += %s' % d)

    # Coordinates the writing of the individual IOC components.
    def GenerateIoc(self):
        # Push IOC name and data directory out to components that need to know
        self.SetIocName(self.ioc_name, self.substitute_boot)
        self.SetDataPath(self.iocDataDir)
        # Now tell all module base classes that IOC generation has begun.
        libversion.ModuleBase.CallModuleMethod('Finalise')

        # Generate each of the output stages.  The order matters!
        self.CreateDatabaseFiles()
        self.CreateSourceFiles()
        self.CreateBootFiles()
        self.CreateConfigureFiles()
        self.CreateDataFiles()
        if self.edm_screen:
            self.CreateEdlFiles()

        # Finally generate the make files
        self.WriteMakefiles()

    # Outputs all the individual make files.
    def WriteMakefiles(self):
        self.makefile_top.Generate(self.iocRoot)
        self.makefile_boot.Generate(self.iocRoot)
        self.makefile_src.Generate(self.iocRoot)
        self.makefile_db.Generate(self.iocRoot)
        if self.edm_screen:
            self.makefile_edl.Generate(self.iocRoot)


    # Individual stages of IOC generation


    def CreateDatabaseFiles(self):
        # Names of the db files we're about to build
        db = self.ioc_name + '.db'
        substitutions = self.ioc_name + '_expanded.substitutions'
        expanded = self.ioc_name + '_expanded.db'
        makefile = self.makefile_db

        if paths.msiPath:
            makefile.AddLine('PATH := $(PATH):%s' % paths.msiPath)

        # Generate the .db and substitutions files and compute the
        # appropriate makefile targets.
        if self.CountRecords():
            self.WriteFile((self.iocDbDir, db), self.PrintRecords)
            self.AddDatabase(os.path.join('db', db))
            makefile.AddLine('DB += %s' % db)
        if self.CountSubstitutions():
            self.WriteFile(
                (self.iocDbDir, substitutions), self.PrintSubstitutions)
            self.AddDatabase(os.path.join('db', expanded))
            makefile.AddLine('DB += %s' % expanded)
        for func in _DbMakefileHooks:
            db_filename = ''
            if self.CountRecords():
                db_filename = db
            expanded_filename = ''
            if self.CountSubstitutions():
                expanded_filename = expanded
            func(makefile, self.ioc_name, db_filename, expanded_filename)

    def CreateSourceFiles(self):
        makefile = self.makefile_src
        ioc = self.ioc_name

        if self.cross_build:
            prod_ioc = 'PROD_IOC_%s' % configure.TargetOS()
        else:
            prod_ioc = 'PROD_IOC'
        makefile.AddLine('%s = %s' % (prod_ioc, ioc))
        makefile.AddLine('DBD += %s.dbd' % ioc)

        for dbd_part in Hardware.GetDbdList():
            makefile.AddLine('%s_DBD += %s.dbd' % (ioc, dbd_part))
        makefile.AddLine(
            '%s_SRCS += %s_registerRecordDeviceDriver.cpp' % (ioc, ioc))

        # Library dependencies need to be expressed in reverse dependency
        # order so that each library pulls in the required symbols from the
        # next library loaded.
        for lib in reversed(Hardware.GetLibList()):
            makefile.AddLine('%s_LIBS += %s' % (ioc, lib))
        # Add the system libraries
        for lib in reversed(Hardware.GetSysLibList()):
            makefile.AddLine('%s_SYS_LIBS += %s' % (ioc, lib))
        makefile.AddLine('%s_LIBS += $(EPICS_BASE_IOC_LIBS)' % ioc)

        # Finally add the target specific files.
        configure.Call_TargetOS(self, 'CreateSourceFiles')

    def CreateSourceFiles_linux(self):
        ioc = self.ioc_name
        self.WriteFile(
            (self.iocSrcDir, '%sMain.cpp' % ioc), self.MAIN_CPP,
            header = PrintDisclaimerC)
        self.makefile_src.AddLine('%s_SRCS += %sMain.cpp' % (ioc, ioc))

    def CreateSourceFiles_vxWorks(self):
        self.makefile_src.AddLine(
            '%s_OBJS += $(EPICS_BASE_BIN)/vxComLibrary' % self.ioc_name)


    def CreateBootFiles(self):
        extension = self.substitute_boot and 'src' or 'cmd'
        self.WriteFile(
            (self.iocBootDir, 'st%s.%s' % (self.ioc_name, extension)),
            self.PrintIoc, '../..', maxLineLength = self.IOCmaxLineLength)

        if self.cross_build:
            scripts = 'SCRIPTS_%s' % configure.TargetOS()
        else:
            scripts = 'SCRIPTS'
        configure.Call_TargetOS(self, 'CreateBootFiles', scripts)
        self.makefile_boot.AddLine(
            '%s += st%s.boot' % (scripts, self.ioc_name))
        if self.substitute_boot:
            if paths.msiPath:
                self.makefile_boot.AddLine('PATH := $(PATH):%s' % paths.msiPath)
        else:
            self.makefile_boot.AddRule(
                'envPaths cdCommands:\n'
                '\t$(PERL) $(TOOLS)/convertRelease.pl -a $(T_A) $@')
            self.makefile_boot.AddRule('%.boot: ../%.cmd\n\tcp $< $@')

    def CreateBootFiles_linux(self, scripts):
        ioc = self.ioc_name
        self.WriteFile((self.iocBootDir, 'st%s.sh' % ioc),
            self.LINUX_CMD % dict(ioc = ioc),
            header = PrintDisclaimerCommand('/bin/sh'))
        if not self.substitute_boot:
            self.makefile_boot.AddLine('%s += envPaths' % scripts)
        self.makefile_boot.AddLine(
            '%s += ../st%s.sh' % (scripts, self.ioc_name))

    def CreateBootFiles_vxWorks(self, scripts):
        if not self.substitute_boot:
            self.makefile_boot.AddLine('%s += cdCommands' % scripts)


    def CreateConfigureFiles(self):
        # Create the configure directory by copying files over from EPICS
        # base.  We don't copy RELEASE because we need to rewrite it
        # completely anyway.
        template_dir = os.path.join(
            paths.EPICS_BASE, 'templates/makeBaseApp/top/configure')
        template_files = os.listdir(template_dir)
        for file in template_files:
            if file != 'RELEASE':
                shutil.copy(
                    os.path.join(template_dir, file),
                    os.path.join(self.iocRoot, 'configure'))

        self.WriteConfigFile('CONFIG_SITE' in template_files)

        # Write out configure/RELEASE
        releases = []
        for module in sorted(libversion.ModuleBase.ListModules()):
            ## \todo Do something sensible on check_release
            # Something like this might be a good idea --
            #             if self.check_release:
            #                 module.CheckDependencies()
            releases.append(
                '%s = %s' % (module.MacroName(), module.LibPath()))
        self.WriteFile('configure/RELEASE', '\n'.join(releases))

    def WriteConfigFile(self, config_site):
        # If CONFIG_SITE exists add our configuration to that, otherwise add
        # it to CONFIG: this system changed in 3.14.11.  Either way, the
        # configuration text is appended to the end of the file.
        if config_site:
            config_file = 'CONFIG_SITE'
            config_text = self.CONFIG_SITE_TEXT
        else:
            config_file = 'CONFIG'
            config_text = self.CONFIG_TEXT
        if self.cross_build:
            ARCH = configure.Architecture()
        else:
            ARCH = ''
        self.WriteFile(('configure', config_file),
            config_text % dict(
                ARCH = ARCH,
                CHECK_RELEASE = self.check_release and 'YES' or 'NO'),
            mode = 'a')


    def CreateDataFiles(self):
        # Note that the data files have to be generated after almost
        # everything else, as they can be generated by Initialise commands.
        self.CopyDataFiles(self.iocRoot, True)

    def __replace_macros(self, d, t):
        if '$(' in t:
            args = ['msi'] + ['-M%s=%s' % x for x in d.items()]
            p = subprocess.Popen(args, stdout = subprocess.PIPE,
                stdin = subprocess.PIPE)
            return p.communicate(t)[0]
        else:
            return t

    def CreateEdlFiles(self):
        # First we make a GuiBuilder object that knows how to make edm screens
        from dls_edm import GuiBuilder, SILENT
        gb = GuiBuilder(self.ioc_name, errors = SILENT)
        # Tell it what its paths are
        gb.RELEASE = os.path.join(self.iocRoot, 'configure/RELEASE')
        for m in sorted(libversion.ModuleBase.ListModules()):
            p = os.path.join(m.LibPath(), 'data')
            if os.path.isdir(p) and p not in gb.paths:
                gb.paths.append(p)
            for s in os.listdir(m.LibPath()):
                p = os.path.join(m.LibPath(), s, 'opi', 'edl')
                if os.path.isdir(p) and p not in gb.devpaths:
                    gb.devpaths.append(p)                
        # This is a list of prefixes, e.g. if our gui objects look like
        # CAM1.ARR, CAM1.CAM, ...
        # then prefixes will contain CAM1
        prefixes = []
        err = '''\
Meta tag should be one of the folowing:
# % gui, <name>, edm, <screen_filename>[, <macros>]
# % gui, <name>, edmembed, <screen_filename>[, <macros>]
# % gui, <name>, edmtab, <screen_filename>[, <macros>]
# % gui, <name>, shell, <command>
# % gui, <name>, status[, <pv>]
# % gui, <name>, sevr[, <pv>]
Supplied meta tag:
# % gui, '''
        # For each substitution file
        for s in recordset.AllSubstitutions():
            # For each gui meta tag
            for meta in getattr(s, 'guiTags', []):
                # substitute macros in meta tag
                meta = self.__replace_macros(s.args, meta)
                # check it's the right length
                parts = meta.split(',')
                assert len(parts) > 1, err + meta
                # the first section is the name of our gui object
                name = parts[0].strip(' ')
                # the second section tells use what kind of tag it is,
                # e.g. edm, edmembed, status
                # we're only interested in edm screens
                switch = parts[1].strip(' ')
                if switch in ['edm', 'edmembed', 'edmtab']:
                    assert len(parts) > 2, err + meta
                    # this dictionary will be passed to GBObject.addScreen
                    data = dict(filename = parts[2].strip(' '))
                    # prepare the macro list
                    if len(parts) > 3:
                        data['macros'] = ','.join(x.strip(' ') for x in parts[3:])
                    else:
                        data['macros'] = ''
                    # special cases for tab widgets and embedded displays
                    if switch == 'edmembed':
                        data['embedded'] = True
                    elif switch == 'edmtab':
                        data['tab'] = True
                    # If there's a dot in the name, add the first bit to
                    # the list of prefixes
                    if '.' in name and name.split('.')[0] not in prefixes:
                        prefixes.append(name.split('.')[0])
                    # If there isn't an object of this name, make one
                    if not gb.get(name):
                        gb.object(name)
                    # Add a screen to the objects
                    gb.get(name)[0].addScreen(**data)
        # Now create components out of these edm objects
        d = os.path.join(self.iocRoot, self.iocEdlDir)
        ignores = []
        # If we've got prefixes, make sub screens for them
        if prefixes:
            for pre in prefixes:
                obs = gb.get('%s.*' % pre)
                ignores += obs
                gb.object(pre, '%s Top' % pre, '', obs, d = d)
        # Now make a top level screen containing anything not in a sub screen
        obs = [x for x in gb.get('*') if x not in ignores]
        c = gb.object('%sTop' % self.ioc_name, '%s Top' % self.ioc_name, '',
            obs, preferEmbed = False, d = d)
        # Add a rule for installing edm screens
        self.makefile_edl.AddLine(
            'DATA += $(patsubst ../%, %, $(wildcard ../*.edl))')
        # And a startup script for the screens
        gb.startupScript(filename = '%s/st%s-gui' % (d,self.ioc_name),
            edl = c.macrodict['FILE'], setPort = False)
        self.makefile_edl.AddLine('SCRIPTS += ../st%s-gui' % self.ioc_name)

# functions to be called when generating Db/Makefile
_DbMakefileHooks = []

# This registers func as a Db/Makefile generation. It will be called just
# before the Db/Makefile is generated like this:
#   func(makefile, iocname, db_filename, expanded_filename)
def AddDbMakefileHook(func):
    _DbMakefileHooks.append(func)
