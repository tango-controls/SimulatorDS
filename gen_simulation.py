#!/usr/bin/env python

import os,sys,threading,pickle,time,traceback,random,math
import PyTango,fandango as fn
from fandango import check_device,check_attribute,Struct,defaultdict
import fandango.tango as ft

__doc__ = """

gen_simulation.py: script to export Tango devices and generate simulators

Usage:
    gen_simulation.py [command] [arguments]
    SimulatorDS --gen [command] [arguments]
    
Typical usage:
    # Exporting devices
    cd your/shared/export/folder
    gen_simulation.py find my/devices/*
    gen_simulation.py export devices.txt output.pck
    
    # Loading devices
    export TANGO_HOST=test_host:10000
    gen_simulation.py generate output.pck
    gen_simulation.py load output.pck test_host:10000
    
    # And start them
    gen_simulation.py play your_instance_name
"""

DEFAULT_STATE = lambda c=None,d=None,a=None,f='ON': "%s" % str(f)
DEFAULT_WRITE = lambda c=None,d=None,a=None,f=None: (
    "VAR('%s',default=%s) if not WRITE else VAR('%s',VALUE,default=%s)" 
    % (a,f,a,f))
DEFAULT_DOUBLE = lambda c=None,d=None,a=None,f=1.: (
    'ripple(%s, rel=0.05)'%str(f) )
DEFAULT_INT = (lambda c=None,d=None,a=None,f=1.: 
    'int(ripple(%s, 1))'%str(f))
DEFAULT_STRING = lambda c=None,d=None,a=None,f=None: ( 
    "%s" % str(f or "'%s/%s'"%(d,a)))
DEFAULT_BOOL = lambda c=None,d=None,a=None,f=None: (
    f or 'randint(0,1)')
DEFAULT_ARGS = lambda c=None,d=None,a=None,f=None: (
    'ARGS and (%s)' % str(f))

DEFAULT_STATES = [
    "MOVING=t%randint(15,30)>randint(1,15)",
    "ALARM=t%randint(1,30)<randint(1,6)",
    "ON=1"]

RAWS = set()
ARGS = set()
OPTS = set()

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
    sd = fn.ServersDict(server)
    news = []
    devs = sd.get_all_devices()
    print('%s/%s contains %d devices'%(sname,instance,len(devs)))
    ff = lambda d,*args: '%s-%s'%(instance.strip('*'),d.split('/')[1])
    rule = fn.notNone(rule,ff)
        
        
    for d in devs:
        k = sd.get_device_class(d)
        news.append(sname+'/'+rule(d,sname,devs))
        print('%s(%s) => %s'%(k,d,news[-1]))
        fn.tango.add_new_device(news[-1],k,d)
        
    return dict((k,news.count(k)) for k in set(news))

def export_devices_from_application(*args):
    print('export_devices:'+str(args))
    exported = 'ui_exported_devices.txt'
    exported2 = 'ui_exported_attributes.txt'
    assert args,'Usage:  simulation.py list filename.py main_method_name'
    filename,method_name = args[0],(args[1:] or [''])[0]
    args = args[3:]

    main_thread = threading.Thread(target=run_app,
                                   args=(filename,method_name,args))
    print('*'*80)
    print('app ready to launch, '
        'type the seconds to wait before exporting your devices')
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
    for f,l in [(exported,factory.getExistingDevices()),
                (exported2,factory.getExistingAttributes())]:
        print('list saved to %s'%f)
        txt = '\n'.join(l.keys())
        if '-v' in OPTS:
            print(txt)
        f = open(f,'w')
        f.write(txt)
        f.close()
            
    return(exported)

def export_devices_from_sources(*files,**options):
    """ Parses source files and returns devices
    :param files: source files to inspect
    :param check: return only existing devices
    """
    print('export_devices_from_sources(%s,%s)'%(str(files),str(options)))
    
    import re, fandango.tango as ft
    import os.path
    matches = []
    for n in files:
        print(n)
        print(os.path.abspath(n))
        
        with open(n) as f:
            txt = f.read()
            matches.extend(re.findall(ft.retango,txt))
    devs = [t for m in matches for t in m if '/' in t]

    if options.get('check',None):
        all_devs = ft.get_all_devices()
        devs = [d for d in devs 
            if ft.get_normal_name(ft.get_dev_name(d.lower())) in all_devs]
    return devs

def export_attributes_to_pck(filein='ui_exported_devices.txt',
                             fileout='ui_attribute_values.pck'):

    print('export_attributes_to_pck(%s)'%str((filein,fileout)))
    assert fileout.endswith('.pck'), 'output must be a pickle file!'

    devs = []
    filein = fn.toList(filein)
    if any(os.path.isfile(f) for f in filein):
        devs = export_devices_from_sources(*filein,check=True)
    else:
        devs = filein
        
    print('devices to export: %s'%str(devs))
        
    proxies = dict((d,PyTango.DeviceProxy(d)) for d in devs)
    devs = defaultdict(Struct)

    for d,dp in sorted(proxies.items()):
        print('%s (%d/%d)' % (d,1+len(devs),len(proxies)))
        obj = devs[d]
        obj.dev_class,obj.attrs,obj.comms = '',defaultdict(Struct),{}
        obj.props = dict((k,v if not 'vector' in str(type(v)).lower() 
                    else list(v)) for k,v in 
                    fn.tango.get_matching_device_properties(d,'*').items() 
                    if 'dynamicattributes' not in k.lower())
      
        if fn.check_device(d):
            devs[d].name = d
            devs[d].dev_class = dp.info().dev_class
            for c in dp.command_list_query():
                if c.cmd_name.lower() not in ('state','status','init'):
                    obj.comms[c.cmd_name] = (str(c.in_type),str(c.out_type))
            for a in dp.get_attribute_list():
                if a.lower() == 'status':
                    continue
            obj.attrs[a] = fn.tango.export_attribute_to_dict(d,a,as_struct=True)
      
    pickle.dump(devs,open(fileout,'w'))
    print('\n%s has been generated, now copy it to your test environment [host] and'
          ' execute:\n\n\tpython gen_simulation.py load %s [tango test_db host]\n'
          % (fileout,fileout))
          
    return(fileout)

def generate_class_properties(filein='ui_attribute_values.pck',all_rw=False,
                              classnames = [], max_array = 0):
    """
    This method will load device/attribute/values from a .pck file
    
    It will build a new classes dictionary grouping all different attr/value
    combinations for each Tango class.
    
    @TODO: an alternate method should allow to export different attribute
    lists for each class device.
    
    classes.devs keeps the instantiated devices
    classes.attrs keeps the generic formulas
    """
    print('generate_class_properties(%s)' % str(filein))
    f = open(filein)
    pck = pickle.load(f)
    f.close()

    classes = defaultdict(Struct)

    if classnames:
        filters = [s.dev_class for s in pck.values() 
                   if s.dev_class not in classnames]
    else:
        print('classes in %s are: %s' 
              % (filein,sorted(set(s.dev_class for s in pck.values()))))
        filters = (raw_input(
            'Do you want to filter out some classes? [PyStateComposer]') 
            or 'PyStateComposer')
        
    max_array = max_array or int(raw_input(
        'Enter the maximum array length [128]:').strip() or 128)
    
    #use_pick = raw_input('Do you want to use pickle to load array values?[Yn]')
    #if use_pick.lower().strip() in ('y','yes'):
        #use_pick = True
        #raw_input('Remember to set device property:\n\t'
            #'PCKFILE = "/path/to/file.pck"\n\npress enter')    
        
    for d,s in pck.items()[:]:
        if s.dev_class.lower() not in filters:
            print('\t%s' % s.dev_class)
            cs = classes[s.dev_class]
            if not hasattr(cs,'attrs'):
                cs.attrs, cs.devs, cs.comms = {}, {}, {}
                cs.states, cs.status = fn.SortedDict(), []
                cs.values, cs.types = defaultdict(list), {}

            cs.devs[d] = s
            for a, t in s.attrs.items():
                if a.lower() == 'state':
                    sv = str(ft.DevState.values[t.value]
                            if ft.isNumber(t.value) else t.value)
                    cs.states[sv] = t.value
                if a.lower() == 'status':
                    cs.status.append(t.value)
                else:
                    cs.attrs[a] = t # str(t.writable)
                    cs.values[a].append(t.value)
                    tt = t.get('data_type',t.get('datatype'))
                    f = getattr(t,'format',None)
                    if f == 'SPECTRUM':
                        tt = tt.replace('Dev','DevVar')+'Array'
                    elif f == 'IMAGE':
                        tt = tt.replace('Dev','DevVar')+'Image'
                    cs.types[a] = tt

            for c, t in s.comms.items():
                if c.lower() not in ('state','status'):
                    cs.comms[c] = None
                    cs.types[c+'()'] = t # in_type / out_type tuple
                    # s.values[c].append(t.value) # Not saved
                
    for c, s in sorted(classes.items()):

        for d in sorted(s.devs):

            for a in sorted(s.attrs):
                #print(d,a)
                 #classes[s.dev_class].values[a]
                formula = generate_formula(a,s['types'][a],
                    writable=(getattr(s.attrs[a],'writable',False) or all_rw), 
                    values=s['values'][a], max_array = max_array), #use_pick=use_pick)
                s.attrs[a] = a + '=' + formula

            for c in sorted(s.comms):
                print(d,c)
                formula = generate_formula(c,s['types'][c+'()'],
                        max_array = max_array) #, use_pick=use_pick)
                s.comms[c] = c + '=' + formula
                
            for i, st in enumerate(s.states):
                s.states[st] = '%s = (t %% %d) == %d' % (st, len(s.states), i)
         
        #s.states = DEFAULT_STATES
        print('%s\nattrs: %s\ncomms: %s\nstates: %s\n' % 
              (c, s.attrs.keys(), s.comms.keys(), s.states))
      
    for k,t in classes.items():
        print('\nWriting %s attributes ([%d])\n'%(k,len(t.attrs)))
        f = open('%s_attributes.txt'%k,'w')
        for a in sorted(t.attrs.values()):
                #print('%s'%a)
                f.write('%s\n'%a)
        f.close()
        print('\nWriting %s commands ([%d])\n'%(k,len(t.comms)))
        f = open('%s_commands.txt'%k,'w')
        for a in sorted(t.comms.values()):
                #print('%s'%a)
                f.write('%s\n'%a)
        f.close()
        print('\nWriting %s states ([%d])\n'%(k,len(t.states)))
        f = open('%s_states.txt'%k,'w')
        for a in t.states.values():
                #print('%s'%a)
                f.write('%s\n'%a)
        f.close()  

    return(filein)            
            
def generate_formula(a, datatype, writable = False, 
                     values = [], max_array = 256):
    """ 
    It returns the appropiate (datatype, formula) for the attribute 
    """
    if isinstance(datatype,tuple) and len(datatype) == 2:
        # Generate commands formulas
        # Input values are actually ignored
        
        if fn.isMapping(datatype):
            datatype = datatype['in_type'], datatype['out_type']

        if datatype[0] == datatype[1] and datatype[0] != 'DevVoid':
            formula = '%s(ARGS[0])' % datatype[0]
            
        else:
            datatype = ('DevString',datatype[1])[datatype[1]!= 'DevVoid']
                
            if 'bool' in datatype.lower(): 
                formula = DEFAULT_BOOL()
            elif 'state' in datatype.lower(): 
                formula = DEFAULT_STATE()
            elif 'string' in datatype.lower(): 
                formula = DEFAULT_STRING(d='?',a=a)
            elif 'double' in datatype.lower() or 'float' in datatype.lower(): 
                formula = DEFAULT_DOUBLE()
            else: 
                formula = DEFAULT_INT()

            if 'Array' in datatype: 
                formula = "[%s for i in range(10)]"%formula
            if 'DevVoid' not in t[0]: 
                formula = DEFAULT_ARGS(f=formula)
        
    else:
        # Standard attributes
        datatype, values = str(datatype), fn.toList(values)
        # Get first stored value
        value = len(values) and values[0] or None

        if fn.isSequence(value): 
            datatype = datatype.replace('Dev','DevVar')+'Array'
            values = [fn.toList(v)[:max_array] for v in values]
            if len(value) and fn.isSequence(value[0]):
                dataformat = 'IMAGE'
                values = [[w[:max_array] for w in v][:max_array] for v in values]
                #values = [[[w[:max_array] for w in ww] for ww 
                #in fn.toList(v)[:max_array]] for v in values]
                value = value[0]
            else:
                dataformat = 'SPECTRUM'
            value = value[:max_array]
        else:
            dataformat = 'SCALAR'
            
        m,args = fn.matchMap((
            ('*bool*', (DEFAULT_BOOL,{'f':'choice(%s or [0])' % values})),
            ('state*', (DEFAULT_STATE,{'f':'choice(%s or [0])' % values})),
            ('*string*',(DEFAULT_STRING, 
                {'d':'?','a':a,'f':'choice(%s or [0])' % values})),
            ('*(double|float)*', (DEFAULT_DOUBLE, 
                {'f':'choice(%s)' % (values)})),
            ('*', (DEFAULT_INT, {'f':'choice(%s or [0])' % (values)})),
            ), datatype)
            
        #@@ TODO: implement get data from pickle
        #if t.data_format != 'SCALAR': 
            #formula = "[%s for i in range(10)]"%formula
            #if use_pick:
                #vv = ("pick(PGET('PCKFILE'),"
                    #"['%s','attrs','%s','value'])" % (d,a))
            #else:
                #vv = str(random.choice(values))

            #formula = "ripple(%s)" % vv # It will respect non-numbers            

        if 'Array' in datatype and 'f' in args: 
            args['f'] = 'choice(%s)' % args['f']
            if dataformat == 'IMAGE':
                args['f'] = 'choice(%s)' % args['f']
                
        formula = m(**args)
        if 'Array' in datatype:
            formula = "[%s for i in range(%d)]" % (formula, len(value))
        try:
            eval(formula,{'PROPERTY': (lambda v:0), 't': 1, 
              'choice': random.choice, 'randint': random.randint, 
              'sin': math.sin})
        except Exception as e:
            print('NotEvaluable! %s = %s' % (a,formula[:80]))
        
        if writable not in ('READ',False):
            #or 'UNKNOWN' in t.writable and 'Array' not in datatype: 
            formula = DEFAULT_WRITE(a=a,f=formula)
            
        formula = '%s(%s)' % (datatype, formula)            
            
        #classes[s.dev_class].attrs[a] = '%s = %s(%s)'%(a,datatype,formula)
        
        print(str((a,datatype,formula))[:80])
            
    return formula

def create_simulators(filein,instance='',path='',domains={},
        server='',tango_host='',filters='',override=True): 
        #domains = {'wr/rf':'test/rf'}
        
    path = path or os.path.abspath(os.path.dirname(filein))+'/'
    print('create_simulators:'+str((filein,instance,path,domains,tango_host)))
    print()
    files = fn.listdir(path)
    
    ## CHECK IS MANDATORY, YOU SHOULD EXPORT AND SIMULATE IN DIFFERENT HOSTS
    assert tango_host and tango_host in str(fn.tango.get_tango_host()),\
                'Tango Host (%s!=%s) does not match!'%(tango_host,fn.tango.get_tango_host())
    
    devs,org = {},pickle.load(open(filein if '/' in filein else path+filein))
    done = []
    
    all_devs = fn.get_all_devices()
    
    print('>'*80)
    
    if not filters:
      print('%d devices in %s: %s'%(len(org),filein,sorted(org.keys())))
      filters=raw_input('\nEnter a filter for device names: [*/*/*]').lower()
      
    for d,t in org.items():
        k = ('/'.join(d.split('/')[-3:])).lower() #Removing tango host from the name
        for a,b in domains.items():
            if k.startswith(a): k = k.replace(a,b)
        if not filters or fn.matchCl(filters,d) or fn.matchCl(filters,org[d].dev_class):
            devs[k] = t
            
    if override is not False:
      dds = [d for d in devs if ('/'.join(d.split('/')[-3:])).lower() in all_devs]
      if dds:
        print('%d devices already exist: %s'%(len(dds),sorted(dds)))
        override=raw_input(
            '\nDo you want to override existing properties (y/[n])? '
                ).lower().startswith('y')
      else: override = False
      
    if not instance:          
        instance = raw_input('\nEnter your instance name for the simulated servers:')
        
        multiinst = raw_input('\nDo you want to split Simulators in several servers,'
          'one for each class (y/[n])? ').lower().startswith('y')
        if multiinst: 
            instance += '-'
        else:
            instance.strip('-')
            
    elif '/' in instance:
      server,instance = instance.split('/')
      
    keepclass = 'y' in raw_input(
        '\nKeep original Class names (if not, all devices will be '
        'generated as SimulatorDS) (y/[n])? ').lower()
    
    suffix = raw_input(
        '\nIf wanted, type a suffix for generated device servers:'
        ).lower().strip()   
    
    if keepclass:
        server = 'SimulatorDS'
    elif not server:
        server = raw_input(
            '\nEnter your server name (SimulatorDS/DynamicDS): [SimulatorDS]') \
                or 'SimulatorDS'
        
    print('>'*80)
    klassdone = []
    instances = set()

    for d,t in sorted(devs.items()):
        print('\n')
        t.dev_class = t.dev_class or d.split('/')[-1]
        if t.dev_class == 'PyStateComposer':
            klass = t.dev_class
        elif keepclass:
            klass = t.dev_class+'_sim'
        else:
            klass = 'SimulatorDS'

        instance_temp = '%s%s'%(instance,t.dev_class) if '-' in instance else instance
        instances.add(instance_temp)
        
        its_new = ('/'.join(('dserver',server,instance_temp))).lower() not in all_devs or d.lower() not in all_devs
        
        orgklass = t.dev_class
        shortname = ft.get_normal_name(d).replace('/','_')

        desc = [f for f in (orgklass+'_attributes.txt',
                            shortname+'_attributes.txt')
                if f in files]

        if orgklass not in klassdone:
            print('*'*80 + '\nChecking %s Tango Class ... ' % orgklass)
            if desc:
                q = raw_input('\nProperty files for Tango class %s already exist:\n [%s],\n'
                'Do you want to regenerate them (y/[n])? '%(orgklass,desc))
            else: 
                q = 'y'
            if q.lower().startswith('y'):
                cur = os.path.abspath(os.curdir)
                os.chdir(path)
                generate_class_properties(filein,classnames=[orgklass])
                os.chdir(cur)        
            klassdone.append(orgklass)
            
        org,d = d,d+suffix

        if its_new or override: 
            print('\n' + '*'*80)
            print('%s/%s:%s , "%s" => %s '%(server,instance_temp,d,t.dev_class,klass))
            print('Creating new Tango Device %s of class %s in server %s/%s' % 
                  (d,klass,server,instance_temp))
            print()
                        
            fn.tango.add_new_device('%s/%s'%(server,instance_temp),klass,d)

            t.props['LoadFromFile'] = path+'%s_attributes.txt'%t.dev_class
            for p,v in t.props.items():
                if not p.startswith('__'): 
                    #p not in ('DynamicCommands','DynamicStates','LoadFromFile','DevicesList') and 
                    fn.tango.put_device_property(d,p,v)         
                    print('\tAdded property: %s/%s [%d]' % (d,p,len(v or [])))
                
            ov_dynattrs = not raw_input(
                '%s attribute formulas will be loaded from:\n\t%s\n\nDo '
                'you want to copy them also to Tango DB so you can tune them '
                'manually ([y]/n)? ' % (d,t.props['LoadFromFile'])
                    ).lower().startswith('n')
                    
            #Overriding Dynamic* properties
            def load_prop_from_file(d,prop,f,path):
                v = filter(bool,map(str.strip,open(f).readlines()))
                fn.tango.put_device_property(d,prop,v)
                print('\tAdded property: %s/%s [%d] from %s' 
                      % (d,prop,len(v or []),f))
            try:
                if ov_dynattrs:
                    load_prop_from_file(d,'DynamicAttributes',
                        path+'%s_attributes.txt'%t.dev_class,path)
                load_prop_from_file(d,'DynamicCommands',
                    path+'%s_commands.txt'%t.dev_class,path)
                load_prop_from_file(d,'DynamicStates',
                    path+'%s_states.txt'%t.dev_class,path)
            except: 
                print('Unable to configure %s(%s) properties '%(d,t.dev_class))
                traceback.print_exc()
                print()
        
        fn.tango.put_device_property(d,'OFFSET',random.randint(0,len(devs)))
        done.append(d)

    exported = fn.get_all_devices(exported=True)
    update = [d for d in done if d in exported]
    print('Updating %d Devices ...'%len(update))
    for d in update:
        if fn.check_device(d):
            print('Updating %s ...'%d)
            try: fn.get_device(d).updateDynamicAttributes()
            except Exception,e: print(e)
        else:
            print('%s failed!'%d)
        time.sleep(.2)
    print('%d devices creation done'%len(done))
    print(done[0],exported[0])
    s = '\n\nTo start the simulators, use any of these commands:\n'
    for i in instances:
        s += ('\n\tpython gen_simulation.py play %s\n'
        '\n\tSimulatorDS %s\n'%(i,i))
    print(s)
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
    devs = fn.get_matching_devices(filein)
    for d in devs[:]:
        if not check_device(d):
            q = raw_input('Unable to configure events for %s, '
                          'do you wish to continue?'%d).lower()
            if 'y' not in q: return
            devs.remove(d)
            
    if devs:
        devs = dict((d,fn.Struct(
            {'attrs':fn.get_device(d).get_attribute_list()})) for d in devs)
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
    all_sims = fn.Astor('*Simulator*/*').get_all_devices()
    devs = [d for d in pickle.load(open(filein)) if d in all_sims]
    db = PyTango.Database()
    for d in devs:
        props = get_all_properties(d)
        [db.delete_property(d,p) for p in props]
        db.delete(d)

CMD_LIST = (
    ('find','[regexp0 regexp1 regexp2 ... filename]',
            'Finds matching devices and stores its names'
            '  in a text file.'),
    ('live_export','[main.py main_method filename]',
            'export device/attributes names from a running application '
            'to a file'),
    
    ('export','[source.py attributes.txt output.pck]',
            'export device config/values from text/source files'
            ' into a .pck file'),
    ('device_export','[regexp0 regexp1 regexp2 ... output.pck]',
            'Finds matching devices and exports its config '
            'and values to a .pck file'),
    
    ('generate','[...]',
            'create the property files for simulators'),
    ('load','[file.pck tango_db_host [domains] ]',
            'create simulators from files'),
    ('play','[...]',
            'run the simulators'),
    ('push','[...]',
            'configure simulators event pushing'),
    )  
    
__doc__ += '\nCommand\tArguments\tDescription\n'
for t in CMD_LIST:
    __doc__ += '%s\t%s\n\n\t%s\n' % (t[0],t[1],t[2])
__doc__ += ('\nadding "-v" to the command will print out'
            'results in stdout.\n')
       
def main(args):
    cmds = [t[0] for t in CMD_LIST]
    cmds = [a for a in args if a in cmds]
    
    if not args or len(args)<2 or not cmds:
        print(__doc__)
        sys.exit(1)
  
    print('\nExecuting the generic simulation script ...\n'+'-'*80)
    
    raws = args
    args = [a for a in args if a not in cmds]
    [OPTS.add(a) for a in args if a.startswith('-')]
    args = [a for a in args if a not in OPTS]
    check = lambda s: s in str(cmds)
    filename = args[-1]

    if check('find'):
        devs = sorted(fn.join(map(ft.get_matching_devices,args[:-1])))
        if '-v' in OPTS:
            print('\n'.join(sorted(devs)))
        with open(args[-1],'w') as f:
            f.write('\n'.join(devs))
    
    if check('live_export'):
        filename = export_devices_from_application(*args[:2])
        
    #if check('device_export'):
        #devs = sorted(fn.join(map(ft.get_matching_devices,args[:-1])))
        #filename = export_attributes_to_pck(devs,fileout=args[-1])

    if check('export') or check('device_export'):
        devs = []
        args, filename = args[:-1],filename
        for a in args:
            if not os.path.exists(a) and '*' in a:
                devs.extend(ft.find_devices(a))
            else:
                devs.append(a)
        filename = export_attributes_to_pck(devs, filename)
     
    #############################################################################

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
        
    print('\n\n%s done'%str(cmds))
    sys.exit()

    #if raw_input('do you want to export attribute/config values to file?').lower().startswith('y'):
    # export_attributes(f)

if __name__ == '__main__':
  import sys
  args = sys.argv[1:]
  main(args)
  
