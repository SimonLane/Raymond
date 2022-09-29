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

save_location = 'D://Niall//'
n = 10 #number of images
z_sep = 0.1 #z-separation in um
b = 0 #binning   1=> 0, 2=>1
e = 100
sd = 0.1 # stage delay (s)
port = 'COM9'

# =============================================================================
# End settings
# =============================================================================


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


#  Instalise Stage
ASI = serial.Serial(port=port, baudrate=115200, timeout=0.2)
sleep(0.3)
# temporary test
for i in range(100):
    move_rel(Y=-1)
    sleep(0.1)


# Instalise Camera  
# TLsdk = TLCameraSDK()
# TLcameras = TLsdk.discover_available_cameras()
# camera = TLsdk.open_camera(TLcameras[0])





# binning(b)
# exposure(e)
# hot_pixel_correction(True)
# grab_mode()
# for i in range(n):
#     camera.issue_software_trigger()
#     sleep(float(camera.frame_time_us/1000000.0))
#     frame = getFrame()
#     if frame:
#         print('n frames: ', frame.frame_count)
#         image = np.copy(frame.image_buffer)
#      # save image to disk
#         # image = reshape(image, (1080,1920))
#         imageio.imwrite('%s%s.tif' %(save_location,i), image)
#         # move stage
#         move_rel(Z=z_sep)
#         sleep(sd)





# camera.dispose()
# TLsdk.dispose()
ASI.close()