import math, time, pickle, traceback
from math import fmod
from math import pi    

def pick(filename, keys = []):
    f = open(filename)
    v = pickle.load(f)
    f.close()
    if keys:
        try:
            for k in keys:
                v = v.get(k)
        except:
            traceback.print_exc()
    return v

def dump(filename, value):
    f = open(filename, 'w')
    pickle.dump(f, value)
    f.close()   
    
def triangle(t,period=2.*pi):
    t = fmod(t,period) ;
    delta = fmod(t,.25*period)/(.25*period)
    if t <= .25*period:
        return delta
    elif t <= .5*period:
        return 1.-delta
    elif t <= .75*period:
        return 0.-delta    
    else:
        return -1.+delta
    
def ripple(value, amp=0., rel=0., t=0, period=2*pi):
    value = float(value)
    t = t or time.time()
    if rel:
        amp = value * rel
    return value + amp*sin(t,period)

def sin(t,period=2*pi):
    '''sinus when t=period should be equal to sinus 2*pi'''
    return math.sin(2*pi*(t/period))

def cos(t,period=2*pi):
    '''sinus when t=period should be equal to sinus 2*pi'''
    return math.cos(2*pi*(t/period))

def square(t,duty=0.5,period=2.*pi):
    t = fmod(t,period) ;
    return ((t <= duty*period) and 1. or 0.)
    if t <= duty*period:
        return 1.
    else:
        return 0.

def ramp(t,duty=1.,period=2.*pi):
    t = fmod(t,period);
    delta = t/(duty*period)
    if t<= duty*period:
        return delta
    else:
        return 0.
