====================================================
Simulate a running Tango Control System in Few Steps
====================================================

.. contents

What is a SimulatorDS
=====================

A SimulatorDS Tango Device Server is a device that returns attribute values evaluated
by python formulas instead of reading/writing attributes from hardware.

The formulas for each simulator attribute, device or command can be stored in the Tango Database 
(as device properties) or as text files.

The declaration of formulas can be done directly by user (see SimulatorDS documentation), but this
how-to will help to generate them automatically. It will be done generating some template .txt
files for each class that wants to be simulated.

The .txt files will can then be copied to the tango database as device properties. This optional step
will allow the control engineer to tune or adapt the formulas to each device that is exported for the same class.

For example, all simulated PLC's may have the same commands or digital states, but the offset
of the temperatures can be configured to vary on different time cycles.

Creating the Simulators
=======================

The process will assume that you want to simulate the "XGUI" application, that access some
real Tango devices that are running on "prod01" host. The simulation instead will run on "sim03" host.

It's also assumed that fandango is installed and gen_simulation.py script is in your path.

 NOTE: "gen_simulation.py [args]" can also be called as "SimulatorDS --gen [args]"

The steps to follow will be:

* identify the devices to simulate
* export its attribute values and configuration to a .pck file
* move this file to the testing environment
* generate SimulatorDS devices from the .pck data
* launch the simulators
* launch your application
 
Using gen_simulation from bash
==============================

1. Export attributes from your production host
----------------------------------------------

We will use "gen_simulation.py export"  to read the configuration and attribute values 
of a list of devices and generate a pickle file (.pck) that can be easily copied 
to a testing environment.

You can use several methods:

* device_export: pass the list of devices to the script and the pickle filename as last argument:
 
.. code-block::
 
  gen_simulation.py device_export sys/tg_test/1 test/alarms/1 test_devs.pck
  
* export: parse your GUI source files for hardcoded device names.

.. code-block::

  gen_simulation.py export path/to/XGUI/*.py xgui_attributes.pck  

* find the list of devices using fandango and write it to a file so it can be parsed:
 
.. code-block::
 
   # Export devices to a file
   fandango -l find_devices "elin/*/*" > devices.txt
  
   # Edit the list if needed
   vi devices.txt
  
   # Then export all the devices configuration to a pickle file
   gen_simulation.py export devices.txt xgui_attributes.pck
 

In all cases you'll obtain a pickle file (.pck) containing all
the attribute configuration of the selected devices.

Now, copy this configuration file to your test environment:

.. code-block::

   scp /tmp/xgui_attributes.pck user@sim03:/home/user/test/


2. Generate simulators in your test environment
-----------------------------------------------

When loading the exported configuration you will be required to write the
name of the hostname of your TESTING Tango Database.

This name must be exactly equal to your TANGO_HOST environment variable, it is asked
to ensure that you're not overriding the production database by mistake.

.. code-block::

  cd /home/user/test #Or wherever
  #gen_simulation load [pickle file] [tango db host]
  gen_simulation.py load xgui_attributes.pck sim03.domain.com
  
When prompted, the most common options are::

  Enter a filter for device names: [*/*/*]
  Enter your instance name for the simulated servers:
  Do you want to split Simulators in several servers,one for each class (y/[n])?
  Keep original Class names (if not, all devices will be generated as SimulatorDS) (y/[n])
  Enter your server name (SimulatorDS/DynamicDS): [SimulatorDS]
  Creating new Tango Device X/Y/Z of class SimulatorDS in server SimulatorDS/<INSTANCE>
  
  X/Y/Z attribute formulas will be loaded from: <...>/SimulatorDS/<INSTANCE>_attributes.txt
  Do you want to copy them also to Tango DB so you can tune them manually ([y]/n)?
  
You can review the configuration in Jive, for more detail on how
to configure the devices see the SimulatorDS user guide in this docs.
  
Launch the simulation
---------------------
 
Now you're ready to launch the simulation::

  gen_simulation.py play xgui_test &
 
And test it against your application::

  git clone https://git..../XGUI
  cd XGUI && python main.py
  
You may configure events for your devices:

  gen_simulation.py push "elinac/*/*" 3000
  
----
  
Using gen_simulation from ipython
=================================

This example will explain how was generated the ESRF linac simulation for Vacca GUI testing:

  https://github.com/sergirubio/VACCA/blob/master/examples/elinac/README.rst

On the real system side
-----------------------

The first step is to write the list of devices to export into a .txt file::

  # fandango -l find_devices "elin/*/*" > elinac_devices.txt
  
Then, from python export all the attribute values and config to .pck files:

.. code:: python

  # ipython
  from SimulatorDS import gen_simulation
  gen_simulation.export_attributes_to_pck('elinac_devices.txt','elinac_devices.pck')
  
On the simulation side
----------------------

As the simulators will use the same device names than the original, do not reproduce this steps in your production database, but in your local/test tango host where you are running your tests:

.. code:: python

  # ipython
  from SimulatorDS import gen_simulation as gs
  
  # This step will convert attribute config into .txt files containing simulation formulas
  # Default formulas for each attribute type are defined in gen_simulation.py; you can edit them there
  
  gs.generate_class_properties('elinac_devices.pck',all_rw=True)
  
  # This step will create the simulators in the database
  # you can use a domains={'old':'new'} argument to create the devices on a different tree branch
  gs.create_simulators('elinac_devices.pck',instance='elinac_test',tango_host='testhost04')
  
  # Now you can verify and modify the device properties with jive
  
Once you're done, launch the SimulatorDS and your favourite GUI from console::

  # python SimulatorDS.py elinac_test &
  # vaccagui $VACCA_PATH/examples/elinac/elinac.py

----

Format of generated files
=========================

devices.txt will contain a list of either attributes or devices that will
be parsed by the script. As when parsing source files, the script simply
searchs for strings that look like tango names, and then it searches if
they exist in the Tango database.

If the names are found, then it proceeds to execute DeviceProxy.info(),
get_device_property(), get_attribute_list() and get_attribute_info() to
obtain all the information regarding device, server, class, types of
attributes and its format.

It collects other information like the current value, polling
periods and event configurations and it finally writes everything into a
nested dictionary, where the main keys are the device names and then
attributes and properties. For the attributes I try to mimic the structs
that are used internally in the get_attribute_config/set_attribute_config
commands of PyTango.

The format of the .pck file is arbitrary, just depends of the pickle
library that comes with python. That library allows to import/export
python objects to/from files. I could have used .json files instead and
probably I'll switch to that format in the future.

