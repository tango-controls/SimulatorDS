==============================================
Simplified Steps to generate a fast simulation
==============================================

The process will assume that you want to simulate the "XGUI" application, 
real devices are running on "prod01" host and simulation will run on "sim03" host.

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

Export attributes from your production host
-------------------------------------------

You can use two methods, either write a file with the list of devices to export
or directly parse the source files for hardcoded device names.

::

  ssh prod01
  cd /tmp/
  
  # Export devices to a file
  fandango -l find_devices "elin/*/*" > devices.txt
  gen_simulation.py export devices.txt xgui_attributes.pck
  
  # Or parse sources with, parse sources, and export to .pck
  gen_simulation.py export path/to/XGUI/*.py xgui_attributes.pck
  
  #Copy the result to your simulation environment
  scp /tmp/xgui_attributes.pck user@sim03:/home/user/test/

Generate simulators in your test environment
--------------------------------------------

::

  cd /home/user/test #Or wherever
  #gen_simulation load [pickle file] [tango db host]
  gen_simulation.py load xgui_attributes.pck sim03.domain.com
  
When prompted, the most common options are::

  generate property files? yes
  filter classes? [enter]
  filter devices? [enter]
  override devices? yes
  instance to use? xgui_test
  server? SimulatorDS
  
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
 


