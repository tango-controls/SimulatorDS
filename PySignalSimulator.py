#!/usr/bin/env python

#    "$Name:  $";
#    "$Header: /cvsroot/tango-ds/Simulators/PySignalSimulator/PySignalSimulator.py,v 1.4 2008/11/21 11:51:44 sergi_rubio Exp $";
#=============================================================================
#
# file :        PySignalSimulator.py
#
# description : Python source for the PySignalSimulator and its commands. 
#                The class is derived from Device. It represents the
#                CORBA servant object which will be accessed from the
#                network. All commands which can be executed on the
#                PySignalSimulator are implemented in this file.
#
# project :     TANGO Device Server
#
# $Author:  srubio@cells.es
#
# $Revision: 1.4 $
#
# $Log: PySignalSimulator.py,v $
# Revision 1.4  2008/11/21 11:51:44  sergi_rubio
# Adapted_to_fandango.dynamic.DynamicDS_template
#
# Revision 1.3  2008/11/21 11:46:30  sergi_rubio
# *** empty log message ***
#
# Revision 1.2  2008/01/21 14:46:30  sergi_rubio
# Solved default properties initialization
#
# Revision 1.1.1.1  2007/10/17 16:44:12  sergi_rubio
# A Simulator for attributes and states, using dynamic attributes
#
# $Log:  $
#
# copyleft :    Cells / Alba Synchrotron
#               Bellaterra
#               Spain
#
#############################################################################
##
## This file is part of Tango-ds.
##
## This is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This software is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.
###########################################################################


import sys,traceback,math,random,time
from re import match,search,findall
import numpy,scipy #Too Heavy, if you need them better use PyAttributeProcessor
from scipy.interpolate import interp1d as interpolate
import Signals

#try:import taurus
#except:pass

import PyTango,fandango
from fandango.dynamic import DynamicDS,DynamicDSClass,DynamicAttribute
from fandango.interface import FullTangoInheritance
from fandango.threads import wait
try: import PyTangoArchiving
except: PyTangoArchiving = None

def get_module_dict(module,ks=None):
    return dict((k,v) for k,v in module.__dict__.items() if (not ks or k in ks) and not k.startswith('__'))

#==================================================================
#   PySignalSimulator Class Description:
#
#         <p>This device requires <a href="http://www.tango-controls.org/Documents/tools/fandango/fandango">Fandango module<a> to be available in the PYTHONPATH.</p>
#         <p>
#         This Python Device Server will allow to declare dynamic attributes which values will depend on a given time-dependent formula:
#         </p>
#         <h5 id="Example:">Example:</h5>
#         <pre class="wiki">  Square=0.5+square(t) #(t = seconds since the device started)
#         NoisySinus=2+1.5*sin(3*t)-0.5*random()
#         SomeNumbers=DevVarLongArray([1000.*i for i in range(1,10)])
#         </pre><p>
#         Attributes are DevDouble by default, but any Tango type or python expression can be used for declaration. <br>
#         Format is specified at <a class="ext-link" href="http://www.tango-controls.org/Members/srubio/dynamicattributes"><span class="icon">tango-controls.org</span></a>
#         </p>
#         <p>
#         Signals that can be easily generated with amplitude between 0.0 and 1.0 are:
#         </p>
#         <blockquote>
#         <p>
#         rampt(t), sin(t), cos(t), exp(t), triangle(t), square(t,duty), random()
#         </p>
#         </blockquote>
#         <p>
#         The MaxValue/MinValue property for each Attribute will determine the State of the Device only if the property DynamicStates is not defined.
#         </p>
#         <p>
#         If defined, <strong>DynamicStates</strong> will use this format:
#         </p>
#         <pre class="wiki">  FAULT=2*square(0.9,60)
#         ALARM=NoisySinus
#         ON=1
#         </pre><p>
#         This device inherits from <strong>fandango.dynamic.DynamicDS</strong> Class
#         </p>
#
#==================================================================


class PySignalSimulator(PyTango.Device_4Impl):

    #--------- Add you global variables here --------------------------
    LIBS = [math,random,Signals]
    NAMES = [math,random,time,PyTango,PyTangoArchiving,
        DynamicAttribute,match,search,findall,wait,numpy,scipy,]
    OTHERS = dict((k,v) for k,v in 
        [('fandango',fandango.functional),('np',numpy),('interpolate',interpolate)]+
        [(f,getattr(fandango,f)) for f in dir(fandango.functional) if '2' in f or f.startswith('to')]
        )
    
    #------------------------------------------------------------------
    #    Device constructor
    #------------------------------------------------------------------
    def __init__(self,cl, name):
        #PyTango.Device_4Impl.__init__(self,cl,name)
        print 'IN PYSIGNALSIMULATOR.__INIT__'
        _locals = {}
        [_locals.update(get_module_dict(m)) for m in self.LIBS]
        _locals.update((k.__name__,k) for k in self.NAMES if hasattr(k,'__name__'))
        _locals.update(self.OTHERS)
        #_locals.update(locals())
        #_locals.update(globals())
        DynamicDS.__init__(self,cl,name,_locals=_locals,useDynStates=True)
        PySignalSimulator.init_device(self)

    #------------------------------------------------------------------
    #    Device destructor
    #------------------------------------------------------------------
    def delete_device(self):
        print "[Device delete_device method] for device",self.get_name()


    #------------------------------------------------------------------
    #    Device initialization
    #------------------------------------------------------------------
    def init_device(self):
        print "In ", self.get_name(), "::init_device()"
        try: 
            DynamicDS.init_device(self) #New in Fandango 11.1
        except:
            self.get_DynDS_properties() #LogLevel is already set here
        if PyTangoArchiving and 'archiving' in str(self.DynamicAttributes): #+str(self.DynamicCommands):
            print 'Adding PyTangoArchiving support ...'
            self._locals['archiving'] = PyTangoArchiving.Reader()
        self.set_state(PyTango.DevState.ON)
        print "Out of ", self.get_name(), "::init_device()"

    #------------------------------------------------------------------
    #    Always excuted hook method
    #------------------------------------------------------------------
    def always_executed_hook(self):
        #print "In ", self.get_name(), "::always_excuted_hook()"
        DynamicDS.always_executed_hook(self)

#==================================================================
#
#    PySignalSimulator read/write attribute methods
#
#==================================================================
#------------------------------------------------------------------
#    Read Attribute Hardware
#------------------------------------------------------------------
    def read_attr_hardware(self,data):
        #print "In ", self.get_name(), "::read_attr_hardware()"
        if self.SimulationDelay>0:
            self.info('Delaying read_attribute by %f seconds'%self.SimulationDelay)
            wait(self.SimulationDelay)

#==================================================================
#
#    PySignalSimulator command methods
#
#==================================================================
    
#==================================================================
#
#    PySignalSimulatorClass class definition
#
#==================================================================
class PySignalSimulatorClass(PyTango.DeviceClass):

    #    Class Properties
    class_property_list = {
        }


    #    Device Properties
    device_property_list = {
        'DynamicAttributes':
            [PyTango.DevVarStringArray,
            "Attributes and formulas to create for this device.\n<br/>\nThis Tango Attributes will be generated dynamically using this syntax:\n<br/>\nT3=int(SomeCommand(7007)/10.)\n\n<br/>\nSee the class description to know how to make any method available in attributes declaration.",
            [ ] ],
        'DynamicStates':
            [PyTango.DevVarStringArray,
            "This property will allow to declare new States dinamically based on\n<br/>\ndynamic attributes changes. The function Attr will allow to use the\n<br/>\nvalue of attributes in formulas.<br/>\n\n\n<br/>\nALARM=Attr(T1)>70<br/>\nOK=1",
            [ ] ],
        'UseScipy':
            [PyTango.DevBoolean,
            "Disable numpy or scipy, NOT IMPLEMENTED YET",
            [ True ] ],
        'SimulationDelay':
            [PyTango.DevDouble,
            "Delay, in seconds, to be applied to each read_attribute call",
            [ 0.0 ] ],
        'PushEvents':
            [PyTango.DevDouble,
            "Set condition for pushing events, N or N>t=periodic; N>diff/rel for change event",
            [ 0.0 ] ],            
        }


    #    Command definitions
    cmd_list = {
        }


    #    Attribute definitions
    attr_list = {
        }


#------------------------------------------------------------------
#    PySignalSimulatorClass Constructor
#------------------------------------------------------------------
    def __init__(self, name):
        PyTango.DeviceClass.__init__(self, name)
        self.set_type(name);
        print "In PySignalSimulatorClass  constructor"

#==================================================================
#
#    PySignalSimulator class main method
#
#==================================================================
if __name__ == '__main__':
    try:
        py = PyTango.Util(sys.argv)
        # Adding all commands/properties from fandango.DynamicDS
        PySignalSimulator,PySignalSimulatorClass = FullTangoInheritance('PySignalSimulator',PySignalSimulator,PySignalSimulatorClass,DynamicDS,DynamicDSClass,ForceDevImpl=True)
        py.add_TgClass(PySignalSimulatorClass,PySignalSimulator,'PySignalSimulator')

        U = PyTango.Util.instance()
        fandango.dynamic.CreateDynamicCommands(PySignalSimulator,PySignalSimulatorClass)
        U.server_init()
        U.server_run()

    except PyTango.DevFailed,e:
        print '-------> Received a DevFailed exception:',traceback.format_exc()
    except Exception,e:
        print '-------> An unforeseen exception occured....',traceback.format_exc()
else:
    #Enabling subclassing
    PySignalSimulator,PySignalSimulatorClass = FullTangoInheritance('PySignalSimulator',PySignalSimulator,PySignalSimulatorClass,DynamicDS,DynamicDSClass,ForceDevImpl=True)
