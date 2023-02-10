# -*- coding: utf-8 -*-
"""
Created on Wed Jan 25 11:04:01 2023

@author: Ray Lee
"""

import time, serial
import numpy as np
from thorlabs_tsi_sdk.tl_camera import TLCameraSDK
from PIL import Image
import matplotlib.pyplot as plt


cam_name = 'CS2100-M-1'
laser_com = 'COM10'
microscope_com = 'COM5'

# =============================================================================
# SCAN PARAMETERS
# =============================================================================

frames      = 1               # always one for this test script, but could be more e.g. for z-stack
e           = 1000            # exposure (ms)
p           = 50              # power (%)
w           = 488             # wavelength
#~~~calc these on the uC
a           = 0.7             # scan mirror amplitude
f           = 1               # scan mirror freq. (Hz) TO DO - calc. from exposure

# =============================================================================
# LASERS
# =============================================================================

# FUNCTIONS 

def manual_galvo(): laser_board.write(bytes("/GM.1;\n",'utf-8'))
def auto_galvo(): laser_board.write(bytes("/GM.0;\n",'utf-8'))
          
def galvo_value(value):
    s = "/G1.%s;\n" %(value)
    laser_board.write(bytes(s,'utf-8'))
   
def I2Cmode(): laser_board.write(bytes("/mode.1;\n",'utf-8'))
def Serialmode(): laser_board.write(bytes("/mode.0;\n",'utf-8'))

def set_power(w, v):
    s = "/%s.%s;\n" %(w,int(v))
    laser_board.write(bytes(s,'utf-8')) # send the 16-bit value for the DAC
    print("sending command: %s" %s)
        
def shutter():
    laser_board.write(b'/stop;\n')

# CONNECTION 

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
    time.sleep(0.5)
    print('close connection')
    
I2Cmode()  # open board to I2C communications so it can be driven by the main control board

# =============================================================================
# CAMERA
# =============================================================================

# FUNCTIONS 
            
def exposure(e):
        #convert milli to micro and set exposure time
        camera.exposure_time_us = e*1000.0
    
def get_exposure():
    #convert micro to milli and return the exposure time
    return camera.exposure_time_us / 1000.0   

def frame_time(): #returns the combined time for exposure and readout (in ms)
    return camera.frame_time_us / 1000.0
        
def ext_mode():
    camera.frames_per_trigger_zero_for_unlimited = 1
    camera.operation_mode = 1      #'HARDWARE_TRIGGERED'
    camera.arm(frames) # need to know how many frames to expect, e.g. for z scan / frame averaging
    
def grab_frame():
    frame = camera.getFrame()
    if frame:
        return np.copy(frame.image_buffer)    # retreive a frame from camera buffer
                                                # call a suitable time (frame time^^) after triggering the camera
    else:
        print('error getting frame from buffer')
        return None

# CONNECTION 

SDK = TLCameraSDK()
TLcameras = SDK.discover_available_cameras()
if len(TLcameras) == 0:
    print('Error connecting to %s: Camera not found'%(cam_name))               
else:
    camera = SDK.open_camera(TLcameras[0])
    
    print('Connected to %s: '%(cam_name))
    
# =============================================================================
# MAIN BOARD
# =============================================================================

# FUNCTIONS

def single_scan(e,w,p):
#~~~~~~~~CAMERA~~~~~~~~#
    # set up the camera for exposure time e, external trigger
    ext_mode()
    exposure(e)
#~~~~~~~~MAIN BOARD~~~~~~~~#
# setup the mirror for single scans with Frequency f and amplitude a, external trigger
# power p, and wavelength w, laser off, external trigger
# send  commands via Teensy board? Y
    #microscope_board.write(b'/s.%s.%s.%s.%s.%s;\n' %(e,w,p,a,f)) 
    
# CONNECTION 

microscope_board = serial.Serial(port=microscope_com, baudrate=115200, timeout=0.5)
time.sleep(1) #essential to have this delay!
microscope_board.write(b'/hello;\n')                     #handshake
reply = microscope_board.readline().strip()
print('microscope reply: ', reply)
if reply == b'Raymond Driver Board':
    print('connection established')



# =============================================================================
# acqusition
# =============================================================================

 # set the laser board into slave mode. 
laser_board.write(bytes("/verbose.0;\n",'utf-8')) # turn off verbose mode
laser_board.write(bytes("/mode.1;\n",'utf-8')) # will now accept I2C commands from the main board
 # send info to the Main board to trigger the hardware
#single_scan(e,w,p,a,f)
 # allow time for exposure and readout
time.sleep(frame_time/1000) 

# wait for frame to be available

 # grab the frame
frame = grab_frame()
 # format the frame
im = Image.fromarray(np.uint8(frame))
 # display the frame
plt.imshow(im)
plt.show()


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
microscope_board.close()
print('close connection to raymond')



































