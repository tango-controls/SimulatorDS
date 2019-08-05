import math, time, pickle, traceback
import fandango as fn
from math import fmod
from math import pi    

from fandango.objects import pick, dump
  
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
    if fn.isSequence(value):
        return [ripple(v,amp,rel,t,period) for v in value]
    try:
        value = float(value)
        t = t or time.time()
        if rel:
            if value:
                amp = value * rel
            else:
                amp = 1e-12
        return value + amp*sin(t,period)
    except:
        return value

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
