.. contents::

Description
===========

This device requires  Fandango module to be available in the PYTHONPATH::

  https://github.com/tango-controls/fandango
    
This Python Device Servers will allow to declare dynamic attributes which values will depend on a given time-dependent formula:

To specify the code for each attribute we use python that has several advantages:

*    No compilation of code; just write, refresh() and see the result.
*    Easy syntax (users can tune it).
*    We can control what can be executed (we use a restricted python eval that only loads the modules/libraries we are interested in).
*    If you use PySignalSimulator it provides sin/square/triangle/ramp methods for generating common signal shapes.
*    If you use PyAttributeProcessor you have Numpy/Scipy plus FFT, GausePeak, PeakFit methods and the capability to load extra modules using the PYTHONPATH and ExtraModules properties.

More on fandango.DynamicDS syntax:

  https://github.com/tango-controls/fandango/blob/documentation/doc/recipes/DynamicDS_and_Simulators.rst

Example of DynamicAttributes property declaration
=================================================

The attributes are created after restarting the device or calling updateDynamicAttributes() ... do not use Init() to do it!::

  Square=0.5+square(t) #(t = seconds since the device started)
  NoisySinus=2+1.5*sin(3*t)-0.5*random()
  SomeNumbers=DevVarLongArray([1000.*i for i in range(1,10)])\

  AVERAGE = DevDouble((XATTR('a/tango/device/attribute')+XATTR('other/tango/device/attribute'))/2.)

  TEMPERATURE = 25+5*sin((1./60)*t)
  PRESSURE = 2.5e-5+1e-6*sin((1./60)*t)
  TEMPERATURES = DevVarDoubleArray([25+v*sin((1./k)*t) for v,k in [(5,60),(10,30),(15,45),(5,5)]])

  MAX_TEMPERATURE = max(TEMPERATURES)
  TEMP_LIMIT = READ and VAR('TEMP_LIMIT') or WRITE and VAR('TEMP_LIMIT',VALUE)

  HOT = DevBoolean(MAX_TEMPERATURE>VAR('TEMP_LIMIT'))
  COLD = DevBoolean(MAX_TEMPERATURE<15)
  TEMPERATE = DevBoolean(not HOT and not COLD)
  EXTREME = DevBoolean(HOT or COLD)

Right part of equality is the attribute name, type is DevDouble? by default but all tango types are available. READ,WRITE,VALUE,t,XATTR(),VAR() are reserved keywords to manage READ/WRITE access, time, external attribute reading and storing variables to be used in other attributes.

Signals that can be easily generated with amplitude between 0.0 and 1.0 are:

    rampt(t), sin(t), cos(t), exp(t), triangle(t), square(t,duty), random()

The MaxValue/MinValue property for each Attribute will determine the State of the Device only if the property DynamicStates is not defined.

If defined, DynamicStates will use this format::

  FAULT=2*square(0.9,60)>0.<br>
  ALARM=NoisySinus>3<br>
  ON=1<br>

Example using DynamicAttributes, DynamicStates and DynamicCommands
==================================================================

It will use a command to record a value in the 'C' variable, it can be returned from the C attribute and will affect the State.

DynamicAttributes::

  A = DevString("Hello World!")
  B = t
  C = DevLong(VAR('C'))

DynamicStates::

  STATE=ON if VAR('C') else OFF

DynamicCommands::

  test_command=str(VAR('C',int(ARGS[0])) or VAR('C'))

Setting Dynamic States
======================

For DynamicStates a boolean operation must be set to each state ... but the name of the State should match an standard Tango.DevState name (ON, FAULT, ALARM, OPEN, CLOSE, ...)

  ALARM=(SomeAttribute > MaxRange)
  ON=True

The "STATE" clause can be used also; forcing the state returned by the code. (NOTE: States are usable within formulas, so it should not be converted to string!)

  STATE=ON if Voltage>0 else OFF

Reading other Attribute Values
==============================

Values can be read from any attribute in the Tango Control System:

https://github.com/tango-controls/fandango/blob/documentation/doc/recipes/DynamicDS_and_Simulators.rst#reading-tango-attributes

The ExtraModules property (PyAttributeProcessor only): 
======================================================

        This property may contain "module", "module.*", "module.klass" or "module.klass as Alias" syntax

        Each of these calls will add you the module or module contents to the locals() dictionary used to evaluate attribute formulas.

 
Meta Variables
==============

Many keywords and special functions are available in the formulas:

https://github.com/tango-controls/fandango/blob/documentation/doc/recipes/DynamicDS_and_Simulators.rst#directives-and-keywords
