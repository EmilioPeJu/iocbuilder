'''A miscellaneous collection of fairly generic utilities.'''

import itertools
import os, os.path
import sys
import fnmatch
import types
import re

__all__ = ['Singleton', 'autosuper', 'AutoRegisterClass', 'SameDirFile']


def ExportModules(globals, *modulenames):
    '''This helper routine is used by __init__.py to selectively export only
    those names announced for export by each sub-module.  Each sub-module
    passed is imported, and each name listed in its __all__ list is added to
    the given global context, and returned.'''
    names = []
    for modulename in modulenames:
        module = __import__(modulename, globals, locals(), [])
        if hasattr(module, '__all__'):
            for name in module.__all__:
                globals[name] = getattr(module, name)
            names.extend(module.__all__)
    return names

    
def ExportAllModules(globals):
    '''This automatically exports all sub-modules.'''
    allfiles = [filename[:-3]
        for moduledir in globals['__path__']
        for filename in fnmatch.filter(os.listdir(moduledir), '*.py')
        if filename != '__init__.py']
    return ExportModules(globals, *allfiles)


def CreateModule(module_name):
    '''Creates a fully qualified module from thin air and adds it to the
    module table.'''
    module = types.ModuleType(module_name)
    sys.modules[module_name] = module
    return module


def SameDirFile(first_file, *filename):
    '''Returns a full filename of a file with the given filename in the same
    directory as first_file.  Designed to be called as
        path = SameDirFile(__file__, filename)
    to return a path to a file in the same directory as the calling module.'''
    return os.path.join(os.path.dirname(first_file), *filename)


def take(iter, n):
    '''Returns the first n elements from iter as an iterator.'''
    for i in range(n):
        yield iter.next()
    

def choplist(list, size):
    '''This support routine chops the given list into segments no longer
    than size.'''
    return [list[i:i+size] for i in range(0, len(list), size)]


def countChars(start='A', stop='Z'):
    '''Returns a sequence of letters.'''
    return iter(map(chr, range(ord(start), ord(stop) + 1)))


unsafe_chars = re.compile(r'[\\"\1-\37]')

def quote_c_string(s):
    '''Converts a string into a form suitable for interpretation by the IOC
    shell -- actually, all we do is ensure that dangerous characters are
    quoted appropriately and enclose the whole thing in quotes.'''

    def replace(match):
        # Replaces dodgy characters with safe replacements
        start, end = match.span()
        ch = s[start:end]
        try:
            table = {
                '\\': r'\\',    '"': r'\"',
                '\t': r'\t',    '\n': r'\n',    '\r': r'\r' }
            return table[ch]
        except KeyError:
            return r'\x%02x' % ord(ch)

    return '"%s"' % unsafe_chars.sub(replace, s)



# The role of this Singleton class is a little unclear.  It can readily be
# argued that a Singleton class is functionally identical to a module.  Very
# true, but there are differences in syntax and perhaps in organisation.  

class Singleton(object):
    '''The Singleton class has *no* instances: instead, all of its members are
    automatically converted into class methods, and attempts to create
    instances simply return the original class.  This behaviour is pretty
    transparent.
    '''

    # The SingletonMeta class is a type class for building singletons: it
    # simply converts all of the methods of the class into class bound
    # methods.  This means that all the data for classes generated by this
    # type is stored in the class, and no instances are created.
    class SingletonMeta(type):
        def __new__(cls, name, bases, dict):
            for n,v in dict.items():
                if isinstance(v, types.FunctionType):
                    dict[n] = classmethod(v)
            singleton = type.__new__(cls, name, bases, dict)
            singleton.__init__()
            return singleton

    __metaclass__ = SingletonMeta

    def __init__(self):
        '''The __init__ method of a singleton class is called as the class is
        being declared.'''
        pass

    def __call__(self):
        '''The default call method emulates dummy instance creation, ie just
        return the class itself.'''
        return self

    def __new__(self, cls, *argv, **argk):
        # Simply delegate __new__ to the __call__ method: this produces the
        # right behaviour, either the subclass is called or our dummy instance
        # is returned.
        #     Note that self is passed twice, because __new__ becomes
        # transformed from a static method into a class method. 
        return cls.__call__(*argv, **argk)


# This class definition is taken from
#   http://www.python.org/2.2.3/descrintro.html#metaclass_examples
class autosuper(type):
    '''Meta-class to implement __super attribute in all subclasses.  To use
    this define the metaclass of the appropriate base class to be autosuper
    thus:

        class A:
            __metaclass__ = autosuper

    Then in any sub-class of A the __super attribute can be used instead of
    writing super(cls,name) thus:

        class B(A):
            def __init__(self):
                self.__super.__init__()
                # instead of
                # super(B, self).__init__()

    The point being, of course, that simply writing
                A.__init__(self)
    will not properly interact with calling order in the presence of multiple
    inheritance: it may be necessary to call a sibling of B instead of A at
    this point!

    Note that this trick does not work properly if a) the same class name
    appears more than once in the class hierarchy, and b) if the class name
    is changed after it has been constructed.'''

    def __init__(cls, name, bases, dict):
        super(autosuper, cls).__init__(name, bases, dict)
        name = name.lstrip('_')
        setattr(cls, "_%s__super" % name, super(cls))
        setattr(cls, "_%s__super_cls" % name,
            classmethod(lambda subcls: super(cls, subcls)))


def AutoRegisterClass(register, ignoreParent=True, superclass=type):
    '''This returns a meta-class which will call the given register function
    each time a sub-class instance is created.  If ignoreParent is True then
    the first class registered will be ignored.'''

    firstRegister = [ignoreParent]
    class DoRegister(superclass):
        def __init__(cls, name, bases, dict):
            super(DoRegister, cls).__init__(name, bases, dict)
            if firstRegister[0]:
                firstRegister[0] = False
            else:
                register(cls, name)

    return DoRegister
