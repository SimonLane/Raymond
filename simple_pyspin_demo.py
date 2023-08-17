# -*- coding: utf-8 -*-
"""
Created on Tue Aug  8 12:17:03 2023

@author: Ray Lee
"""

# manual_setup.py

from simple_pyspin import Camera
from PIL import Image
import os

# Make a directory to save some images
output_dir = 'C:\\Users\\Ray Lee\\Documents\Simon\\SLM test'
cam = Camera()
cam.init()

cam.start() # Start recording
imgs = [cam.get_array()] # Get a frame
cam.stop() # Stop recording
cam.close()

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

print("Saving images to: %s" % output_dir)
for n, img in enumerate(imgs):
    Image.fromarray(img).save(os.path.join(output_dir, '%04d.png' % n))


# from example:
# with Camera() as cam: # Initialize Camera
#     # Set the area of interest (AOI) to the middle half
#     cam.Width = cam.SensorWidth // 2
#     cam.Height = cam.SensorHeight // 2
#     cam.OffsetX = cam.SensorWidth // 4
#     cam.OffsetY = cam.SensorHeight // 4

#     # To change the frame rate, we need to enable manual control
#     cam.AcquisitionFrameRateAuto = 'Off'
#     cam.AcquisitionFrameRateEnabled = True
#     cam.AcquisitionFrameRate = 20

#     # To control the exposure settings, we need to turn off auto
#     cam.GainAuto = 'Off'
#     # Set the gain to 20 dB or the maximum of the camera.
#     gain = min(20, cam.get_info('Gain')['max'])
#     cam.Gain = gain
#     cam.ExposureAuto = 'Off'
#     cam.ExposureTime = 10000 # microseconds

#     cam.start() # Start recording
#     # imgs = [cam.get_array() for n in range(10)] # Get 10 frames
    
#     imgs = [cam.get_array()] # Get a frame
#     cam.stop() # Stop recording


# if not os.path.exists(output_dir):
#     os.makedirs(output_dir)

# print("Saving images to: %s" % output_dir)
# for n, img in enumerate(imgs):
#     Image.fromarray(img).save(os.path.join(output_dir, '%04d.png' % n))