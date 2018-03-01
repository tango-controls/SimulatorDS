#!/usr/bin/env python

import os,sys,threading,pickle,time,traceback,random
import PyTango,fandango as fd
from fandango import check_device,check_attribute,Struct,defaultdict

DEFAULT_STATE = lambda c=None,d=None,a=None,f='ON': "%s"%f
DEFAULT_WRITE = lambda c=None,d=None,a=None,f=None: "VAR('%s',default=%s) if not WRITE else VAR('%s',VALUE)"%(a,f,a)
DEFAULT_DOUBLE = lambda c=None,d=None,a=None,f=1.: '%s * (1+2*sin((int(PROPERTY("OFFSET"))+t)%%3.14))'%f
DEFAULT_INT = lambda c=None,d=None,a=None,f=1.: 'int(PROPERTY("OFFSET"))+randint(0,10) * %s'%f
DEFAULT_STRING = lambda c=None,d=None,a=None,f=None: "%s"%(f or "'%s/%s'"%(d,a))
DEFAULT_BOOL = lambda c=None,d=None,a=None,f=None: 'randint(0,1)'
DEFAULT_ARGS = lambda c=None,d=None,a=None,f=None: 'ARGS and %s'%f

DEFAULT_STATES = [
    "MOVING=t%randint(15,30)>randint(1,15)",
    "ALARM=t%randint(1,30)<randint(1,6)",
    "ON=1"]

def run_app(filename,method_name,args):
 print('run_app:'+str((filename,method_name,args)))
 try:
  import imp
  module = filename.split('/')[-1].split('.')[0]
  print('loading %s.%s(%s) ...'%(module,method_name,args))
  sys.argv = [filename]
  print ('load_source(%s,%s)'%(module,filename))
  f = imp.load_source(module,filename)
  print(dir(f))
  if method_name: getattr(f,method_name)(*args)
 except:
  traceback.print_exc()
  
def split_server_by(server,rule=None):
    """
    Rule must be a callable that returns the name of new instance
    Rule would be a callable with *args:
     - device, [[server,] device_list]

    If no rule is passed, instance-family is used
    """
    sname,instance = server.split('/',1)
    sd = fd.ServersDict(server)
    news = []
    devs = sd.get_all_devices()
    print('%s/%s contains %d devices'%(sname,instance,len(devs)))
    ff = lambda d,*args: '%s-%s'%(instance.strip('*'),d.split('/')[1])
    rule = fd.notNone(rule,ff)
        
        
    for d in devs:
        k = sd.get_device_class(d)
        news.append(sname+'/'+rule(d,sname,devs))
        print('%s(%s) => %s'%(k,d,news[-1]))
        fd.tango.add_new_device(news[-1],k,d)
        
    return dict((k,news.count(k)) for k in set(news))

def export_devices_from_application(*args):
    print('export_devices:'+str(args))
    exported = 'ui_exported_devices.txt'
    exported2 = 'ui_exported_attributes.txt'
    assert args,'Usage:  simulation.py list filename.py main_method_name'
    filename,method_name = args[0],(args[1:] or [''])[0]
    args = args[3:]

    main_thread = threading.Thread(target=run_app,args=(filename,method_name,args))
    print('*'*80)
    print('app ready to launch, type the seconds to wait before exporting your devices')
    print('*'*80)
    try:
        timeout = raw_input('enter timeout (in seconds): ')
    except:
        traceback.print_exc()
        timeout = 30.
    timeout = int(timeout)
    main_thread.setDaemon(True)
    main_thread.start()
    for i in range(timeout): 
        print(timeout-i)
        time.sleep(1.)

    import taurus
    factory = taurus.Factory()
    print('*'*80)
    for f,l in [(exported,factory.getExistingDevices()),(exported2,factory.getExistingAttributes())]:
        print('list saved to %s'%f)
        f = open(f,'w')
        txt = '\n'.join(l.keys())
        f.write(txt)
        print(txt)
        f.close()
    print('*'*80)
    return(exported)

def export_devices_from_sources(*files,**options):
    """ Parses source files and returns devices
    :param files: source files to inspect
    :param check: return only existing devices
    """
    import re, fandango.tango as ft
    matches = []
    for n in files:
        with open(n) as f:
            txt = f.read()
            matches.extend(re.findall(ft.retango,txt))
    devs = [t for m in matches for t in m if '/' in t]

    if options.get('check',None):
        all_devs = ft.get_all_devices()
        devs = [d for d in devs if d.lower() in all_devs]
    return devs

def export_attributes_to_pck(filein='ui_exported_devices.txt',
                             fileout='ui_attribute_values.pck'):

    print('export_attributes from:'+str((filein,fileout)))
    assert fileout.endswith('.pck'), 'output must be a pickle file!'

    all_devs = fd.tango.get_all_devices()
    filein = fd.toList(filein)
    if all(d.lower() in all_devs for d in filein):
        devs = filein
    else:
        devs = export_devices_from_sources(*filein,check=True)
        
    print('devices to export: %s'%str(devs))
        
    proxies = dict((d,PyTango.DeviceProxy(d)) for d in devs)
    devs = defaultdict(Struct)

    for d,dp in sorted(proxies.items()):
      print('%s (%d/%d)' % (d,1+len(devs),len(proxies)))
      obj = devs[d]
      obj.dev_class,obj.attrs,obj.comms = '',defaultdict(Struct),{}
      obj.props = dict((k,v if not 'vector' in str(type(v)).lower() else list(v)) for k,v in fd.tango.get_matching_device_properties(d,'*').items() if 'dynamicattributes' not in k.lower())
      if fd.check_device(d):
        devs[d].name = d
        devs[d].dev_class = dp.info().dev_class
        for c in dp.command_list_query():
         if c.cmd_name.lower() not in ('state','status','init'):
          obj.comms[c.cmd_name] = (str(c.in_type),str(c.out_type))
        for a in dp.get_attribute_list():
         if a.lower() == 'status':
          continue
         obj.attrs[a] = fd.tango.export_attribute_to_dict(d,a,as_struct=True)
      
    pickle.dump(devs,open(fileout,'w'))
    return(fileout)

def generate_class_properties(filein='ui_attribute_values.pck',all_rw=False):
  
    print('generate_class_properties:'+str(filein))
    devs = pickle.load(open(filein))

    classes = defaultdict(Struct)
    print('classes in %s are: %s'%(filein,sorted(set(s.dev_class for s in devs.values()))))
    filters=raw_input('Do you want to filter out some classes? [PyStateComposer]') or 'PyStateComposer'
    for d,s in devs.items():
     if s.dev_class in filters: continue
     classes[s.dev_class].attrs = {}
     classes[s.dev_class].comms = {}
     classes[s.dev_class].values = defaultdict(set)
     
    for d,s in devs.items():

      if s.dev_class in filters: 
        continue
      
      for a,t in s.attrs.items():
        t['datatype'] = t.get('data_type','DevDouble')
        if not isinstance(t,Struct): t = Struct(t)
        
        if t.value is not None and not any(x in t.datatype.lower() for x in ('array',)):
          try:
            classes[s.dev_class].values[a].add(t.value)
          except:
            print d,s.dev_class,a,t

    for d,s in devs.items():
      
      if s.dev_class in filters: 
        continue
     
      #Iterate attributes
      for a,t in s.attrs.items():
       
        if a.lower() in ('state','status'):
          continue
     
        if t.value is None and a in classes[s.dev_class].attrs:
          continue
     
        else:
          if t.value is None: 
            datatype,formula = 'DevDouble','NaN'
         
          else:
            datatype = t.datatype if t.data_format=='SCALAR' else t.datatype.replace('Dev','DevVar')+'Array'
            if 'bool' in datatype.lower(): formula = DEFAULT_BOOL()
            elif 'state' in datatype.lower(): formula = DEFAULT_STATE(f='choice(%s or [0])'%list(classes[s.dev_class].values[a]))
            elif 'string' in datatype.lower(): formula = DEFAULT_STRING(d=d,a=a,f='choice(%s or [0])'%list(classes[s.dev_class].values[a]))
            elif 'double' in datatype.lower() or 'float' in datatype.lower(): formula = DEFAULT_DOUBLE(f=random.choice(list(classes[s.dev_class].values[a]) or [0]))
            else: formula = DEFAULT_INT(f='choice(%s or [0])'%list(classes[s.dev_class].values[a]))
            if 'Array' in datatype: formula = "[%s for i in range(10)]"%formula
            if all_rw or 'WRITE' in t.writable: formula = DEFAULT_WRITE(a=a,f=formula)
            classes[s.dev_class].attrs[a] = '%s = %s(%s)'%(a,datatype,formula)
         
      #Iterate commands
      for c,t in s.comms.items():
        
        if fd.isMapping(t):
          t = t['in_type'],t['out_type']
        datatype = t[1] if t[1]!='DevVoid' else 'DevString'
        if 'bool' in datatype.lower(): formula = DEFAULT_BOOL()
        elif 'state' in datatype.lower(): formula = DEFAULT_STATE()
        elif 'string' in datatype.lower(): formula = DEFAULT_STRING(d=d,a=c)
        elif 'double' in datatype.lower() or 'float' in datatype.lower(): formula = DEFAULT_DOUBLE()
        else: formula = DEFAULT_INT()
        if 'Array' in datatype: formula = "[%s for i in range(10)]"%formula
        if 'DevVoid' not in t[0]: formula = DEFAULT_ARGS(f=formula)
        classes[s.dev_class].comms[c] = '%s = %s(%s)'%(c,datatype,formula)
         
      classes[s.dev_class].states = DEFAULT_STATES
      
    for k,t in classes.items():
      print('\nWriting %s attributes ([%d])\n'%(k,len(t.attrs)))
      f = open('%s_attributes.txt'%k,'w')
      for a in sorted(t.attrs.values()):
        print('%s'%a)
        f.write('%s\n'%a)
      f.close()
      print('\nWriting %s commands ([%d])\n'%(k,len(t.comms)))
      f = open('%s_commands.txt'%k,'w')
      for a in sorted(t.comms.values()):
        print('%s'%a)
        f.write('%s\n'%a)
      f.close()
      print('\nWriting %s states ([%d])\n'%(k,len(t.states)))
      f = open('%s_states.txt'%k,'w')
      for a in t.states:
        print('%s'%a)
        f.write('%s\n'%a)
      f.close()  

    return(filein)

def create_simulators(filein,instance='',path='',domains={},
        server='',tango_host='',filters='',override=True): 
        #domains = {'wr/rf':'test/rf'}
        
    path = path or os.path.abspath(os.path.dirname(filein))+'/'
    print('create_simulators:'+str((filein,instance,path,domains,tango_host)))
    files = fd.listdir(path)
    if not any(f.endswith('_attributes.txt') for f in files):
        q = raw_input('Property files do not exist yet,\n'
            'Do you want to generate them? (y/n)')
        if q.lower().startswith('y'):
            cur = os.path.abspath(os.curdir)
            os.chdir(path)
            generate_class_properties(filein)
            os.chdir(cur)
    
    ## CHECK IS MANDATORY, YOU SHOULD EXPORT AND SIMULATE IN DIFFERENT HOSTS
    assert tango_host and tango_host in str(fd.tango.get_tango_host()),\
                'Tango Host (%s!=%s) does not match!'%(tango_host,fd.tango.get_tango_host())
    
    devs,org = {},pickle.load(open(filein if '/' in filein else path+filein))
    done = []
    
    all_devs = fd.get_all_devices()
    
    print('>'*80)
    
    if not filters:
      print('%d devices in %s: %s'%(len(org),filein,sorted(org.keys())))
      filters=raw_input('Enter a filter for device names: [*/*/*]').lower()
      
    for d,t in org.items():
        k = ('/'.join(d.split('/')[-3:])).lower() #Removing tango host from the name
        for a,b in domains.items():
            if k.startswith(a): k = k.replace(a,b)
        if not filters or fd.matchCl(filters,d) or fd.matchCl(filters,org[d].dev_class):
            devs[k] = t
            
    if override is not False:
      dds = [d for d in devs if ('/'.join(d.split('/')[-3:])).lower() in all_devs]
      if dds:
        print('%d devices already exist: %s'%(len(dds),sorted(dds)))
        override=raw_input('Do you want to override existing properties? (y/n)'
                ).lower().startswith('y')
      else: override = False
      
    if not instance:
      instance = raw_input('Enter your instance name for the simulated server (use "instance-" to use multiple instances):')
    elif '/' in instance:
      server,instance = instance.split('/')
      
    keepclass = 'y' in raw_input('Keep original Class names?').lower()
    
    if keepclass:
        server = 'SimulatorDS'
    elif not server:
        server = raw_input(
            'Enter your server name (SimulatorDS/DynamicDS): [SimulatorDS]') \
                or 'SimulatorDS'
        
    print('>'*80)

    for d,t in sorted(devs.items()):
        t.dev_class = t.dev_class or d.split('/')[-1]
        if t.dev_class == 'PyStateComposer':
            klass = t.dev_class
        elif keepclass:
            klass = t.dev_class+'_sim'
        else:
            klass = 'SimulatorDS'

        instance_temp = '%s%s'%(instance,t.dev_class) if '-' in instance else instance
        print('%s/%s:%s , "%s" => %s '%(server,instance_temp,d,t.dev_class,klass))
        its_new = ('/'.join(('dserver',server,instance_temp))).lower() not in all_devs or d.lower() not in all_devs

        if its_new or override: 
            print('writing ... %s(%s)'%(type(t),d))            
            fd.tango.add_new_device('%s/%s'%(server,instance_temp),klass,d)
            for p,v in t.props.items():
                if not p.startswith('__'): #p not in ('DynamicCommands','DynamicStates','LoadFromFile','DevicesList') and 
                    fd.tango.put_device_property(d,p,v)         
            #Overriding Dynamic* properties
            try:
                fd.tango.put_device_property(d,'LoadFromFile',
                    path+'%s_attributes.txt'%t.dev_class)
                fd.tango.put_device_property(d,'DynamicAttributes',
                    filter(bool,map(str.strip,open(path+'%s_attributes.txt'%t.dev_class).readlines())))
                fd.tango.put_device_property(d,'DynamicCommands',
                    filter(bool,map(str.strip,open(path+'%s_commands.txt'%t.dev_class).readlines())))
                fd.tango.put_device_property(d,'DynamicStates',
                    filter(bool,map(str.strip,open(path+'%s_states.txt'%t.dev_class).readlines())))
            except: 
                print('Unable to configure %s(%s) properties '%(d,t.dev_class))
                #traceback.print_exc()
        
        fd.tango.put_device_property(d,'OFFSET',random.randint(0,len(devs)))
        done.append(d)

    exported = fd.get_all_devices(exported=True)
    update = [d for d in done if d in exported]
    print('Updating %d Devices ...'%len(update))
    for d in update:
        if fd.check_device(d):
            print('Updating %s ...'%d)
            try: fd.get_device(d).updateDynamicAttributes()
            except Exception,e: print(e)
        else:
            print('%s failed!'%d)
        time.sleep(.2)
    print('%d devices creation done'%len(done))
    print(done[0],exported[0])
    return instance

def run_dynamic_server(instance):
    print('run_dynamic_server:'+str(instance))
    from fandango.dynamic import DynamicServer
    if '/' in instance: 
        server,instance = instance.split('/')
        sys.argv = [server,instance] #,'-v1']
        print(sys.argv)
        pyds = DynamicServer(server+'/'+instance,log='',add_debug=False)
        pyds.main()
        
    else:
        server = 'SimulatorDS' #'DynamicDS'
        import SimulatorDS
        SimulatorDS.main(['SimulatorDS',instance])
        
    time.sleep(10.)
    
def set_push_events(filein,period=3000,diff=1e-5):
    print('set_push_events(%s,%s,%s)'%(filein,period,diff))
    devs = fd.get_matching_devices(filein)
    for d in devs[:]:
        if not check_device(d):
            q = raw_input('Unable to configure events for %s, '
                          'do you wish to continue?'%d).lower()
            if 'y' not in q: return
            devs.remove(d)
            
    if devs:
        devs = dict((d,fd.Struct(
            {'attrs':fd.get_device(d).get_attribute_list()})) for d in devs)
    else:
        devs = pickle.load(open(filein))
    for d,t in sorted(devs.items()):
        print('Setting events (%s,%s) for %s'%(period,diff,d))
        try:
            dp = PyTango.DeviceProxy(d)
            for a in t.attrs:
                dp.poll_attribute(a,int(period))
                if period>0:
                    ac = dp.get_attribute_config(a)
                    cei = PyTango.ChangeEventInfo()
                    cei.rel_change = str(diff)
                    ac.events.ch_event = cei
                    try: dp.set_attribute_config(ac)
                    except: pass
        except:
            q = raw_input('Unable to configure events for %s, '
                          'do you wish to continue?'%d)
            if 'y' not in q.lower():
                break
    print('done')
      
        
def delete_simulators(filein):
    #NOTE THIS METHOD SHOUL DELETE ONLY PYSIGNALSIMULATOR INSTANCES, NOT ANYTHING ELSE!
    raise 'NotImplementedYet!'
    all_sims = fd.Astor('*Simulator*/*').get_all_devices()
    devs = [d for d in pickle.load(open(filein)) if d in all_sims]
    db = PyTango.Database()
    for d in devs:
        props = get_all_properties(d)
        [db.delete_property(d,p) for p in props]
        db.delete(d)
        
def main(args):
  print('Welcome to the generic simulation script')
  print('-'*80)
  cmd_list = (
      ('find','[regexp filename]',
            'TODO: finds matching devices and stores them in filename.'),
      ('list','[main.py main_method]',
            'export device/attribute lists from application into a file'),
      ('export','[source.py attributes.txt output.pck]',
            'export devices from source files into a .pck file'),
      ('generate','[...]',
            'create the property files for simulators'),
      ('load','[file.pck tango_db_host [domains] ]',
            'create simulators from files'),
      ('play','[...]',
            'run the simulators'),
      ('push','[...]',
            'configure simulators event pushing'),
      )

  cmds = [t[0] for t in cmd_list]
  cmds = [a for a in args if a in cmds]
  
  if not args or len(args)<2 or not cmds:
      print('\n\nUsage:\n\t'
          'simulation.py %s file_input/instance '
            '[main_method/polling_period/domain_alias]\n\n%s'%(
                str(cmds),'\n'.join(map(str,cmd_list))))
      sys.exit(1)
  
  args = [a for a in args if a not in cmds]
  check = lambda s: s in str(cmds)
  filename = args[-1]
  
  if check('list'):
    filename = export_devices_from_application(*args[:2])

  elif check('export'):
    if len(args)>=1: args = (args[:-1],filename)
    filename = export_attributes_to_pck(*args)

  elif check('generate'):
    filename = generate_class_properties(filename)

  elif check('load'):
    filename = create_simulators(args[0],
        tango_host=args[1],
        domains=args[2:] and eval(args[1]) or {})

  elif check('play'):
    run_dynamic_server(filename)

  elif check('push'):
    set_push_events(*args) #filename,period,diff
    #if len(args)>2: run_app(*args[:-1])
    
  print('%s done'%str(cmds))
  sys.exit()

  #if raw_input('do you want to export attribute/config values to file?').lower().startswith('y'):
  # export_attributes(f)

if __name__ == '__main__':
  import sys
  args = sys.argv[1:]
  main(args)
  
