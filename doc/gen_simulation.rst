==============================================
Simplified Steps to generate a fast simulation
==============================================

The process will assume that you want to simulate the XGUI application, 
real devices are running on prod01 host and simulation will run on sim03 host.

It's also assumed that fandango is installed and gen_simulation.py is in your path.

The steps to follow will be:

 * identify the devices to simulate
 * export its attribute values and configuration to a .pck file
 * move this file to the testing environment
 * generate SimulatorDS devices from the .pck data
 * launch the simulators
 * launch your application

Export attributes from your production host
-------------------------------------------

You can use two methods, either write a file with the list of devices to export
or directly parse the source files for hardcoded device names.

::
  ssh prod01
  cd /tmp/
  #Run gen_simulation, parse sources, and export to .pck
  gen_simulation.py export path/to/XGUI/*.py xgui_attributes.pck
  #Copy the result to your simulation environment
  scp /tmp/xgui_attributes.pck user@sim03:/home/user/test/

Generate simulators in your test environment
--------------------------------------------

::

  cd /home/user/test #Or wherever
  #gen_simulation load [pickle file] [tango db host]
  gen_simulation.py load xgui_attributes.pck sim03
  
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

  gen_simulation.py xgui_test &
 
And test it against your application::

  git clone https://git..../XGUI
  cd XGUI && python main.py
