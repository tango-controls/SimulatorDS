#!/usr/bin/env python

import json,sys,time,re
import fandango as fd

args,opts = fd.linos.sysargs_to_dict(split=True)

if 'json' in opts:
    f = opts.get('json')
    data = json.load(open(f))
else:
    print('getting instances from aws ...')
    data = fd.linos.shell_command('aws ec2 describe-instances')
    f = open('instances.json','w')
    f.write(data)
    f.close()
    data = json.loads(data)

data = data.values()[0]
rows = []

for t in data:
  t = t['Instances'][0]
  tags = t.get('Tags',[{'Value':'?'}])
  name = tags[0]['Value']
  dns = t['PublicDnsName']
  host = t['PrivateDnsName'].split('.')[0]
  iid = t['InstanceId']
  rows.append((name,host,iid,dns))
  
for row in sorted(rows):
  print('\t'.join(map(str,row)))







