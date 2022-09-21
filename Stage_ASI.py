# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 17:00:52 2020

class for control of the ASI MS2000 with 3x LS-50 stages, configures as A, Y and XZ

@author: Simon
"""

from PyQt5 import QtGui
import serial, time


class Stage_ASI(QtGui.QWidget):
    def __init__(self, parent, name, port):
        super(Stage_ASI, self).__init__(parent)
        self.flag_CONNECTED = False
        self.position = []
        self.port = port
        self.name = name
        self.imaging_limits     = [[10000,-10000],[10000,-10000],[2000,-10000]] #X +- 10mm  Y +- 10mm  Z +2mm -10mm
        self.escape_limits      = [[1500,-15000],[21000,-4000],[1000,-21000]]
        self.override_limits    = [[20000,-20000],[20000,-20000],[20000,-10000]]
        self.limits             = self.imaging_limits
        self.home_position      = [0,0,0]
        self.start_position     = [0,0,-2000]
        self.escape_position    = [-14000,0,-21000]
        self.prev_position      = [0,0,-2000]

    def connect(self):
        try:
            self.ASI = serial.Serial(port=self.port, baudrate=115200, timeout=0.2)
            time.sleep(0.3)

            self.flag_CONNECTED = True
     
#            set some defaults
            self.ASI.write(b"UM X=10000 Y=10000 Z=10000\r")  #(per mm) set the movement units to tenths µm(default is 10000, tenths of µm)
            self.ASI.write(b"R X=0 Y=0 Z=10\r")              # Relative move - Convert to tenths of µm, default 1 micron
            self.ASI.write(b'RT Y=0.1\r')                    # TTL pulse width
            self.ASI.write(b'AC Z=10\r')                     # Acceleration (ms to reach max speed)
            self.ASI.write(b'TTL X=2 Y=2 F=1\r')             # TTL modes
            self.ASI.write(b"PC Z=0.005\r")                  # How close should the position be to the target to conside the move complete
            self.ASI.write(b'E Z=0.0001\r')                  # Drift correction error
            self.ASI.readline()
            self.ASI.readline()
            self.ASI.readline()
            self.ASI.readline()
            self.ASI.readline()
            self.ASI.readline()
            self.ASI.readline()
            self.position = self.get_position()
            self.parent().information("Connected to %s" %(self.name), 'g')
            self.set_speed(X=1.36, Y=1.36, Z=1.8)            # Max speed (mm/s) - limit appears to 1.92mm/s
            self.backlash_compensation(True)                 # Backlash compensation distance
            self.parent().information(">> Stage position: %s" %(self.position), 'g')
            self.set_limits(self.limits)
            self.rapidMode(rapid=False)
            return True

        except Exception as e:
            print("Error connecting to '%s': %s" %(self.name,e))
            self.parent().information("Error connecting to '%s': %s" %(self.name,e), 'r')
            self.ASI.close()
            return False

    def close(self):
        if self.flag_CONNECTED == True:
            self.rapidMode(rapid=False)
            self.ASI.close()
            print("Disconnected from ASI stage")
            self.flag_CONNECTED = False

    def controller_enable(self, E):
        if E:
            self.ASI.write(b"J X+ Y+ Z+")
            self.ASI.readline()
        else:
            self.ASI.write(b"J X- Y- Z-")
            self.ASI.readline()
            
            
    def move_to(self, X=None,Y=None,Z=None):
        # print('abs:', X,Y,Z)
#        accept inputs in (float) µm
        if X is not None or Y is not None or Z is not None:
            string = 'M'
            if X is not None: 
                string = string + ' X=%s' %(round(X*10,1))
                self.position[0] = X
            if Y is not None: 
                string = string + ' Y=%s' %(round(Y*10,1))
                self.position[1] = Y
            if Z is not None: 
                string = string + ' Z=%s' %(round(Z*10,1))
                self.position[2] = Z
            string = string + '\r'
            self.ASI.write(string.encode())
            self.ASI.readline()
            # self.parent().thread_to_GUI.put(['position',self.position])            
            # print('sent to ASI:', string)
            
    def move_rel(self, X=None,Y=None,Z=None):
        print('rel:',X,Y,Z)
#        accept inputs in (float) µm
        if X is not None or Y is not None or Z is not None:
            string = 'R'
            if X is not None: 
                string = string + ' X=%s' %(round(X*10,1))
                self.position[0] += X
            if Y is not None: 
                string = string + ' Y=%s' %(round(Y*10,1))
                self.position[1] += Y
            if Z is not None: 
                string = string + ' Z=%s' %(round(Z*10,1))
                self.position[2] += Z
            string = string + '\r'
            self.ASI.write(string.encode())
            self.ASI.readline()
            print('sent to ASI:', string)
            
    def clear_buffer(self):
        # print 'clear buffer', self.ASI.inWaiting(), 'bytes'
        self.ASI.reset_input_buffer()
        self.ASI.reset_output_buffer()
        # print 'clear buffer', self.ASI.inWaiting(), 'bytes'
        while self.ASI.inWaiting() > 0:
            self.ASI.read()
        
    def get_position(self):
        self.clear_buffer()
        a=0
        if a==0: self.ASI.write(b"W X Y Z\r") #current stage position
        a+=1
        in_ = self.ASI.readline().decode().split(' ')
        if len(in_) == 5:
            p = []
            for item in in_[1:-1]:
                p.append(float(item)/10.0)
            self.position = p
            return p
        else: 
#            returns position in µm
            return self.get_position()

    def backlash_compensation(self, value):
        self.parent().information(">> Backlash compensation: %s" %(value), 'g')
        if value:   
            self.ASI.write(b'B Z=0.02\r')
        else:       
            self.ASI.write(b'B Z=0\r')
        self.ASI.readline()
    
    def escape(self):
        self.set_limits(self.escape_limits)
        self.set_speed(X=1.36,Y=1.36,Z=1.36)
        self.move_to(X=self.escape_position[0],Y=self.escape_position[1],Z=self.escape_position[2])


    def home(self, X=True, Y=True, Z=True):
        string = 'M'
        if X: string = string + ' X=0'
        if Y: string = string + ' Y=0'
        if Z: string = string + ' Z=0'
        string = string + '\r'
        self.ASI.write(string.encode())
        self.ASI.readline()
        self.set_limits(self.imaging_limits)

    def disable_zero_button(self):
        pass
    
    def set_limits(self, limits):
        self.limits = limits
        string = "SU X=%s Y=%s Z=%s\r" %(limits[0][0]/1000.0,limits[1][0]/1000.0,limits[2][0]/1000.0)
        self.parent().information(">> upper limits: %s" %(string), 'g')
        self.ASI.write(string.encode())
        self.ASI.readline()        
        string = "SL X=%s Y=%s Z=%s\r" %(limits[0][1]/1000.0,limits[1][1]/1000.0,limits[2][1]/1000.0)
        self.parent().information(">> lower limits: %s" %(string), 'g')
        self.ASI.write(string.encode())
        self.ASI.readline()
    
    def set_speed(self, X=None,Y=None,Z=None):
        if X is not None or Y is not None or Z is not None:
            string = 'S'
            if X is not None: string = string + ' X=%s' %(X)
            if Y is not None: string = string + ' Y=%s' %(Y)
            if Z is not None: string = string + ' Z=%s' %(Z)
            self.parent().information(">> stage speed: %s" %(string), 'g')
            string = string + '\r'
            self.ASI.write(string.encode())
            
        else:
            self.ASI.write(b'S X=1.36 Y=1.36 Z=1.36\r') #default to 70% speed
            self.parent().information('>> stage speed: X=1.36 Y=1.36 Z=1.36', 'g')
        self.ASI.readline()
        
    def is_moving(self):
        self.clear_buffer()
        self.ASI.write('/\r'.encode())
        while self.ASI.inWaiting() < 1: pass
        s = self.ASI.readline().decode("utf-8")
        if s[0] == 'B': #moving
            return True
        else: return False
    
    def rapidMode(self, rapid=False):
        if rapid: #for use in tile scanning
            self.parent().information(">> stage mode: Rapid", 'g')
            self.ASI.write('MC X+ Y+ Z+\r'.encode()) #enable all axes
            self.ASI.write('S X=1.85 Y=1.85 Z=1.36\r'.encode()) #Max speed
            self.ASI.write('AC X=25 Y=25 Z=25\r'.encode()) #acceleration
            self.ASI.write('B X=0 Y=0 Z=0\r'.encode()) #backlash
            self.ASI.write('PC X=0.004 Y=0.004 Z=0.004\r'.encode()) #position tolerance
        if not rapid: 
            self.parent().information(">> stage mode: Standard", 'g')
            self.ASI.write('S X=1.36 Y=1.36 Z=1.36\r'.encode())
            self.ASI.write('AC X=70 Y=70 Z=70\r'.encode()) #acceleration
            self.ASI.write('B X=0.01 Y=0.01 Z=0.01\r'.encode()) #backlash
            self.ASI.write('PC X=0.000006 Y=0.000006 Z=0.000006\r'.encode()) #position tolerance
            
            
    def joystick(self, enable=True):
        self.parent().information("Joystick enabled: : %s" %(enable), 'y')
        if enable:
            self.ASI.write('J X+ Y+ Z+\r')
        else:
            self.ASI.write('J X- Y- Z-\r')
            
            
            