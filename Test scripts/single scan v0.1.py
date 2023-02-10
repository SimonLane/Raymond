# -*- coding: utf-8 -*-
"""
Created on Mon Jan 30 14:30:01 2023

@author: Simon

Simplified time averaged lightsheet test script
"""


import time, serial
import numpy as np
from thorlabs_tsi_sdk.tl_camera import TLCameraSDK
from PIL import Image
import matplotlib.pyplot as plt

# LASER CONNECTION

laser_board = serial.Serial(port='COM10', baudrate=115200, timeout=0.5)
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

# CAMERA FUNCTIONS 
            
def exposure(e):
    #convert milli to micro and set exposure time
    camera.exposure_time_us = int(e*1000.0)
    
def get_exposure():
    #convert micro to milli and return the exposure time
    return camera.exposure_time_us / 1000.0   

def frame_time(): #returns the combined time for exposure and readout (in ms)
    return camera.frame_time_us / 1000.0
        
def ext_mode(frames):
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

# CAMERA CONNECTION

SDK = TLCameraSDK()
TLcameras = SDK.discover_available_cameras()
if len(TLcameras) == 0:
    print('Error connecting to Camera')               
else:
    camera = SDK.open_camera(TLcameras[0])
    print('Connected to Camera')
    camera.frames_per_trigger_zero_for_unlimited = 1
    camera.operation_mode = 1       # HARDWARE_TRIGGERED
    camera.trigger_polarity = 1     # 1 = active high, 0 = active low
    camera.arm(1) # need to know how many frames to expect, e.g. for z scan / frame averaging

    exposure(500)      #1000ms exposure

# laser to I2C mode, (mode 1)
laser_board.write(bytes('/mode.1;','utf-8'))
# laser prep
laser_board.write(bytes('/488.65000;','utf-8'))
 

#grab frames
i=0
k=0
while i<5 and k<100:
    frame = camera.get_pending_frame_or_null()
    if frame:
# #display the frame
        grab = np.copy(frame.image_buffer)
        im = Image.fromarray(np.uint8(grab))
          # display the frame
        plt.imshow(im)
        plt.show() 
        i = i+1
    time.sleep(0.1) #(s)
    k=k+1

    
    
    
# close connection
print('close laser board connection')
# laser_board.write(bytes('/mode.0;','utf-8'))
# laser_board.write(bytes('/488.0;','utf-8'))
laser_board.close()
print('close connection to camera')
camera.dispose()
SDK.dispose()
