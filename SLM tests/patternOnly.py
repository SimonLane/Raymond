# -*- coding: utf-8 -*-
"""
Created on Fri Aug 18 14:58:07 2023
SLM pattern generation only, 
No laser or camera, no write to SLM device

@author: Simon
"""

import os, serial
import numpy as np

from ctypes import cdll, CDLL, c_uint, POINTER, c_ubyte, c_float, c_double, c_ulong

import imageio.v2 as imageio
from time import sleep
import ctypes
import matplotlib.pyplot as plt

image_dir = 'C:/Program Files/Meadowlark Optics/Blink 1920 HDMI/Image Files/'

# =============================================================================
# SLM setup
# =============================================================================
errorCode = ctypes.windll.shcore.SetProcessDpiAwareness(2)

cdll.LoadLibrary("C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\SDK\\Blink_C_wrapper")
slm_lib = CDLL("Blink_C_wrapper")

# Open the image generation library
cdll.LoadLibrary("C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\SDK\\ImageGen")
image_lib = CDLL("ImageGen")

# indicate that our images are RGB
RGB = c_uint(1);
is_eight_bit_image = c_uint(0);

# Call the SLM constructor
slm_lib.Create_SDK();
print("Blink SDK was successfully constructed");

height = c_uint(slm_lib.Get_Height());
width = c_uint(slm_lib.Get_Width());
depth = c_uint(slm_lib.Get_Depth());
bytpesPerPixel = 4; #RGBA
center_x = c_uint(width.value//2);
center_y = c_uint(height.value//2);
print('SLM:',height,width,depth,center_x,center_y)


#load the LUT wavelength calibration
success = 0;
success = slm_lib.Load_lut("C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\LUT Files\\19x12_8bit_linearVoltage.lut");
if success > 0: print("LoadLUT Successful")	
else: print("LoadLUT Failed")	

# Create two vectors to hold values for two SLM images
ImageOne = np.empty([width.value*height.value*bytpesPerPixel], np.uint8, 'C');
ImageTwo = np.empty([width.value*height.value*bytpesPerPixel], np.uint8, 'C');


# =============================================================================
# generate images for SLM
# =============================================================================
Xs = []
Ys = []
Zs = []
Is = []
n = 0
step = 200


target_image = np.zeros((1200, 1920), dtype='uint8')
for x in np.arange(200,1200,200):
    for y in np.arange(200,1200,200):
                Xs.append(x)
                Ys.append(y)
                Zs.append(0)
                Is.append(1)
                n+=1

# convert to ctype
XSpots = np.array(Xs, dtype='f');
YSpots = np.array(Ys, dtype='f');
ZSpots = np.array(Zs, dtype='f');
ISpots = np.array(Is, dtype='f');
N_spots = c_uint(n);
ApplyAffine = c_uint(0);

# Generate hologram
WFC = np.empty([width.value*height.value*bytpesPerPixel], np.uint8, 'C');

iterations = c_uint(20);
image_lib.Initialize_HologramGenerator(width.value, height.value, 
                                       depth.value, iterations, RGB);

image_lib.Generate_Hologram(ImageOne.ctypes.data_as(POINTER(c_ubyte)), 
                            WFC.ctypes.data_as(POINTER(c_ubyte)), 
                            XSpots.ctypes.data_as(POINTER(c_float)), 
                            YSpots.ctypes.data_as(POINTER(c_float)), 
                            ZSpots.ctypes.data_as(POINTER(c_float)), 
                            ISpots.ctypes.data_as(POINTER(c_float)), 
                            N_spots, ApplyAffine);

save_as = '%s/PY grid.bmp' %image_dir
imageio.imwrite(save_as, np.reshape(ImageOne.copy(), (1200,1920,4)))

# # generate fresnel lens 200mm
# lens_power = c_double(200);
# image_lib.Generate_FresnelLens(ImageTwo.ctypes.data_as(POINTER(c_ubyte)), 
#                             WFC.ctypes.data_as(POINTER(c_ubyte)),
#                             width.value, height.value, depth.value,
#                             center_x, center_y, 600,
#                             lens_power, 0, 0, 0)

# save_as = '%s/PY lens.bmp' %image_dir
# imageio.imwrite(save_as, np.reshape(ImageTwo.copy(), (1200,1920,4)))

# # superimpose
# Super = (ImageOne + ImageTwo) % 255

# save_as = '%s/PY grid+lens.bmp' %image_dir
# imageio.imwrite(save_as, np.reshape(Super.copy(), (1200,1920,4)))


# close SLM
slm_lib.Delete_SDK();
print('Disconnected from SLM')
