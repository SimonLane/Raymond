# -*- coding: utf-8 -*-
"""
Created on Wed Jan 25 11:04:01 2023

@author: Simon Lane
"""
from thorlabs_tsi_sdk.tl_camera import TLCameraSDK
import time, serial, math, os, imageio
import numpy as np
import pandas as pd

# from PIL import Image
# import matplotlib.pyplot as plt


# =============================================================================
# SCAN PARAMETERS
# =============================================================================

e           = 50           # exposure (ms)
p           = 100            # power (%)
w           = 488           # wavelength
z_step      = 0.05           # Z step size in microns
z_range     = 10             # in microns

rootLocation = "D:\\Simon\\Z-stacks"
ExptName = 'test2'

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
n_steps     = int((z_range/z_step) + 1)


# =============================================================================
# HARDWARE CONNECTIONS
# =============================================================================

cam_name        = 'CS2100-M-1'
laser_com       = 'COM10'
ASI_com         = 'COM9'
laserCalibration = ''
address = "/Users/Ray Lee/Documents/GitHub/Raymond/"
lasers = []  

# Laser board
laser_board = serial.Serial(port=laser_com, baudrate=115200, timeout=0.5)
time.sleep(1) #essential to have this delay!
laser_board.write(b'/hello;\n')                     #handshake
reply = laser_board.readline().strip()
print('laser reply: ', reply)
if reply == b'lasers':
    print('connected to laser board')
    #put the illuminiation board into mode 0 (turns off the trigger)
    laser_board.write(bytes("/mode.0;\n",'utf-8'))
elif  b'Over Serial' in reply:
    print('verbose mode detected')
    #The laser control board is in verbose mode, needs to not be for serial communication.
    laser_board.write(bytes("/verbose.0;\n",'utf-8'))   #turn off verbose mode 
    print('verbose mode off command')
    reply = laser_board.readline().strip()
    print(reply)
    laser_board.close()
    print('close connection')

# laser data
dataframe = pd.read_csv("%sLaserCalibration.txt" %(address), header=0, index_col=0, sep ='\t')
for row in range(dataframe.shape[0]):
    l = dataframe.iloc[row, :]
    lasers.append(l)
    #['Wav.','Min.V','Max.V','Min.uW','Max.uW','Eqn.','P.1','P.2']
            
# Camera
SDK = TLCameraSDK()
TLcameras = SDK.discover_available_cameras()
if len(TLcameras) == 0:
    print('Error connecting to %s: Camera not found'%(cam_name))               
else:
    camera = SDK.open_camera(TLcameras[0])
    print('Connected to %s: '%(cam_name))
    camera.frames_per_trigger_zero_for_unlimited = 1
    camera.operation_mode = 0      #SOFTWARE_TRIGGERED
    # camera.operation_mode = 1      #HARDWARE_TRIGGERED
    camera.arm(2)                  # set buffer to hold 2 images


# ASI Stage
ASI = serial.Serial(port=ASI_com, baudrate=115200, timeout=0.2)
time.sleep(0.5)
ASI.write(b"UM X=10000 Y=10000 Z=10000\r")  #(per mm) set the movement units to tenths µm(default is 10000, tenths of µm)
ASI.write(b"R X=0 Y=0 Z=0\r")               # Relative move - Convert to tenths of µm, default 1 micron
ASI.write(b'RT Y=0.1\r')                    # TTL pulse width
ASI.write(b'AC Z=10\r')                     # Acceleration (ms to reach max speed)
ASI.write(b'TTL X=2 Y=2 F=1\r')             # TTL modes
ASI.write(b"PC Z=0.005\r")                  # How close should the position be to the target to conside the move complete
ASI.write(b'E Z=0.0001\r')                  # Drift correction error
ASI.write(b'B Z=0.02\r')                    # Backlash correction error
ASI.write(b'S X=1.36 Y=1.36 Z=1.36\r')      # Default to 70% max speed
for i in range(9): ASI.readline()           # clear incoming buffer

# =============================================================================
# LASERS FUNCTIONS 
# =============================================================================

def manual_galvo(): laser_board.write(bytes("/GM.1;\n",'utf-8'))
def auto_galvo(): laser_board.write(bytes("/GM.0;\n",'utf-8'))
          
def galvo_value(value):
    s = "/G1.%s;\n" %(value)
    laser_board.write(bytes(s,'utf-8'))
   
def I2Cmode(): 
    laser_board.write(bytes("/verbose.0;\n",'utf-8'))   # turn off verbose mode
    laser_board.write(bytes("/mode.1;\n",'utf-8'))      # accept I2C commands, no serial
    
def Serialmode(): 
    laser_board.write(bytes("/verbose.0;\n",'utf-8'))   # turn off verbose mode
    laser_board.write(bytes("/mode.0;\n",'utf-8'))      # accept serial commands, no I2C

def set_power(w, v):
    s = "/%s.%s;\n" %(w,int(v))
    laser_board.write(bytes(s,'utf-8')) # send the 16-bit value for the DAC
    print("sending command: %s" %s)
        
def shutter():
    laser_board.write(b'/stop;\n')
    
def get_val16(w,p): #supply wavelength and percentage to retreive the DAC value
    for r in lasers:
        
        if w == r[0]:
            print(w,'is', r[0], 'Min lase value is', r[1])
            DAC = ((2**16 - r[1]) * (p/100)) + r[1]
            return DAC
            

# =============================================================================
# CAMERA FUNCTIONS 
# =============================================================================
          
def exposure(e):
        #convert milli to micro and set exposure time
        camera.exposure_time_us = int(e*1000)
    
def get_exposure():
    #convert micro to milli and return the exposure time
    return int(camera.exposure_time_us / 1000.0)

def frame_time(): #returns the combined time for exposure and readout (in ms)
    return int(camera.frame_time_us / 1000.0)
        
def ext_mode(frames):
    camera.frames_per_trigger_zero_for_unlimited = 1
    camera.operation_mode = 1      #'HARDWARE_TRIGGERED'
    camera.arm(frames) # need to know how many frames to expect, e.g. for z scan / frame averaging
    
def grab_frame():
    frame = camera.get_pending_frame_or_null()
    if frame:
        return np.copy(frame.image_buffer)    # retreive a frame from camera buffer
                                                # call a suitable time (frame time^^) after triggering the camera
    else:
        print('error getting frame from buffer')
        return None

def save_image(frame, location, z):
    imageio.imwrite('%s\\z%03d.tif' %(StoreLocation, z), frame)

  
# =============================================================================
# STAGE FUNCTIONS
# =============================================================================
def move_to(X=None,Y=None,Z=None):
#   accept input in (float) µm
    print('abs:', X,Y,Z)
    if X is not None or Y is not None or Z is not None:
        string = 'M'
        if X is not None: 
            string = string + ' X=%s' %(round(X*10,4))
        if Y is not None: 
            string = string + ' Y=%s' %(round(Y*10,4))
        if Z is not None: 
            string = string + ' Z=%s' %(round(Z*10,4))
        string = string + '\r'
        ASI.write(string.encode())
        print(string)
        ASI.readline()
            
def move_rel(X=None,Y=None,Z=None):
#   accept input in (float) µm
    if X is not None or Y is not None or Z is not None:
        string = 'R'
        if X is not None: 
            string = string + ' X=%s' %(round(X*10,4))
        if Y is not None: 
            string = string + ' Y=%s' %(round(Y*10,4))
        if Z is not None: 
            string = string + ' Z=%s' %(round(Z*10,4))
        string = string + '\r'
        ASI.write(string.encode())
        ASI.readline()
        print('sent to ASI:', string)

def move_diag(d):   #in um
# new way using non-cartesean z-axis
    move_rel(Z=d)
# old way using combined x and z movement
    # x = d*math.sin(math.radians(53.2)) 
    # z = d*math.cos(math.radians(53.2))
    # move_rel(X=x,Z=z)

def get_position():
    clear_buffer()
    ASI.write(b"W X Y Z\r") #current stage position
    in_ = ASI.readline().decode().split(' ')
    if len(in_) == 5:
        p = []
        for item in in_[1:-1]:
            p.append(float(item)/10.0)
        return p
    else: 
#            returns position in µm
        return get_position()

def is_moving():
    debug = False
    ASI.write('/\r'.encode())
    time.sleep(0.05)
    if ASI.inWaiting() > 0:
        s = ASI.readline().decode("utf-8")
        if s[0] == 'N': # not busy
            if debug: print(s[0], 'stage not busy')
            return False
        elif s[0] == 'B': # moving (busy)
            if debug: print(s[0], 'stage busy')
            return True
        elif s[0] == ':': # error message
            if debug: print(s[0], 'stage error')
            return True
    return True
    
def clear_buffer():
    # print 'clear buffer', self.ASI.inWaiting(), 'bytes'
    ASI.reset_input_buffer()
    ASI.reset_output_buffer()
    # print 'clear buffer', self.ASI.inWaiting(), 'bytes'
    while ASI.inWaiting() > 0:
        ASI.read()
# =============================================================================
# acqusition
# =============================================================================

Serialmode() # laser will now accept serial commands

# setup laser
DAC_value = get_val16(w,p)  #convert percentage into 16-bit value scaled for lasing threshold
set_power(w, 58982)     #turn on the laser
time.sleep(0.3)

# setup the camera
exposure(e)
frameTime = frame_time() # combined exposure and readout time

#update save location to make sure it is unique
i=0
while True:    
    StoreLocation = '%s\\%s(%s)-%snm,%sum' %(rootLocation,ExptName,i,w,z_step)
    i=i+1
    if not os.path.exists(StoreLocation): break
os.mkdir(StoreLocation) # create folder

# setup the stage
pre_start = get_position()      #get stage start position to return to later
move_diag((z_range/-0.5)-z_step) #move to one position before the start (to eliminate backlash)
while is_moving(): pass # poll stage for movement
move_diag(z_step) #move to start position
while is_moving(): pass # poll stage for movement

# do the scan
for i in range(n_steps): # in nm
    camera.issue_software_trigger() # trigger camera to take image
    time.sleep(frameTime/1000)      # delay whilst image exposed
    frame = grab_frame()            # get frame from camera buffer
    save_image(frame, StoreLocation, i) # save image to disk
    # plt.imshow(frame)
    # plt.show()
# move stage
    move_diag(z_step)
    time.sleep(0.25)
    # while is_moving(): pass # poll stage for movement

move_to(Z=pre_start[2]) # put stage back where it came from
while is_moving(): pass # poll stage for movement

print('start:', pre_start)
print('end:  ', get_position())
# =============================================================================
# make safe and close connections 
# =============================================================================

shutter()                                       #turn off all lasers, galvo to safe position
Serialmode()                                    #prevent laser board responding to I2C commands from main board
laser_board.close()
print('close connection to laser board')
camera.dispose()
SDK.dispose()
print('close connection to camera')
ASI.close()
print('close connection to ASI stage')


































