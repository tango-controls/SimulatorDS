Noise and ripples
-----------------

An easy way to emulate an attribute is adding a ripple around a fixed value:

::

   # Use amp=0.1 for 0.1 ripple or rel=0.05 for 5%
   DOUBLE = float(ripple(5, amp=0.1))

Using pick/dump methods
-----------------------

::

    # gen_simulation.py export sys/tg_test/1 test.pck

Then, loading an array into a simulated attribute:

::

    # This code will pickle the file once, then reuse the stored value
    ARRAY=DevVarShortImage(SET('ARRAY',GET('ARRAY') or pick('test/test.pck',['sys/tg_test/1','attrs','ushort_image','value'])))
    
