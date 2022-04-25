# -*- coding: utf-8 -*-
"""
Created on Tue Apr 12 14:55:04 2022

@author: Simon
"""

import imageio, serial
import numpy as np
from thorlabs_tsi_sdk.tl_camera import TLCameraSDK
from time import sleep


# Script to do basic z-stack on Raymond, using the stage
# =============================================================================
# Settings
# =============================================================================

save_location = 'D://Niall//20220421 z stack//scatter 488 5//'
n = 60 #number of images
z_sep = 0.2 #z-separation in um
b = 0 #binning   1=> 0, 2=>1
e = 100 #exposure ms
sd = 0.4 # stage delay (s)
port = 'COM9'
laser_wl = 488 # enter 405, 488, 561 or 660
power = 20 # % - 488 (40% fluorescence, 20% scattering), 561 (16% scattering)
true_z = True
f = np.cos((180/np.pi)*36.5)
# =============================================================================
# End settings
# =============================================================================

def set_power(w, p):
    s = "/%s.%s;\n" %(w,p)
    teensy.write(bytes(s,'utf-8'))
    print(s)
        
def shutter():
    teensy.write(b'/stop;\n')
    print("stop")
        

def binning(b):
    bins = [1,2,4,8]
    camera.binx = bins[b]
    camera.biny = bins[b]

def hot_pixel_correction(b):
    camera.is_hot_pixel_correction_enabled = b
    
def getFrame(): # Function called periodically by a timer during live view mode
    frame = camera.get_pending_frame_or_null()
    return frame
        
def exposure(e):
    #convert milli to micro and set exposure time
    camera.exposure_time_us = int(e)*1000            

def grab_mode():
    print(camera)
    camera.frames_per_trigger_zero_for_unlimited = 1
    camera.operation_mode = 0      #'SOFTWARE_TRIGGERED'
    camera.arm(10)                  # set buffer to hold n images
    

def move_rel(X=None,Y=None,Z=None):
    print('rel:',X,Y,Z)
#        accept inputs in (float) µm
    if X is not None or Y is not None or Z is not None:
        string = 'R'
        if X is not None: 
            string = string + ' X=%s' %(round(X*10,1))
        if Y is not None: 
            string = string + ' Y=%s' %(round(Y*10,1))
        if Z is not None: 
            string = string + ' Z=%s' %(round(Z*10,1))
        string = string + '\r'
        ASI.write(string.encode())
        ASI.readline()
        print('sent to ASI:', string)




# Instalise Camera  
TLsdk = TLCameraSDK()
TLcameras = TLsdk.discover_available_cameras()
camera = TLsdk.open_camera(TLcameras[0])

#  Instalise Stage
ASI = serial.Serial(port=port, baudrate=115200, timeout=0.2)
sleep(0.3)

# Instalise lasers
teensy = serial.Serial(port='COM11', baudrate=115200, timeout=0.5)
sleep(1) #essential to have this delay!

teensy.write(b'/hello;\n')
reply = teensy.readline().strip()

if reply == b'laser controller':
    print('connection established')


binning(b)
exposure(e)
hot_pixel_correction(True)
grab_mode()

set_power(laser_wl, power)

for i in range(n):
    camera.issue_software_trigger()
    sleep(float(camera.frame_time_us/1000000.0))
    frame = getFrame()
    if frame:
        print('n frames: ', frame.frame_count)
        image = np.copy(frame.image_buffer)
     # save image to disk
        # image = reshape(image, (1080,1920))
        imageio.imwrite('%s%s.tif' %(save_location,i), image)
        # move stage
        if true_z == False: move_rel(Z=z_sep)
        if true_z == True: move_rel(Z=z_sep, X=z_sep*f)
        sleep(sd)

shutter()

move_rel(Z=z_sep * (n+3) * -1, X=z_sep *f * (n+3) * -1) # return to start, and backwards three steps
sleep(0.3)
for i in range(3):
    move_rel(Z=z_sep, X=z_sep*f) #move forwards 3 steps (counter backlash)
    sleep(0.3)


camera.dispose()
TLsdk.dispose()
ASI.close()
teensy.close()