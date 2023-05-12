# -*- coding: utf-8 -*-
"""
Created on Wed Apr 26 13:57:19 2023

Test script for Meadowlark SLM - Blaze gratings

@author: Simon Lane
"""

import os, serial, time
import numpy
import pandas as pd
from ctypes import cdll, CDLL, c_uint, POINTER, c_ubyte
from scipy import misc
from time import sleep
import ctypes

laser_com       = 'COM10'
address = "/Users/Ray Lee/Documents/GitHub/Raymond/"
lasers = []  

def set_power(w, p):
    v = get_val16(w,p) #convert percentage to 16-bit DAC value
    s = "/%s.%s;\n" %(w,int(v))
    laser_board.write(bytes(s,'utf-8')) # send the 16-bit value for the DAC
    print("sending laser command: %s" %s)
        
def shutter():
    laser_board.write(b'/stop;\n')
    
def get_val16(w,p): #supply wavelength and percentage to retreive the DAC value
    for r in lasers:
        print(r[0])
        if w == r[0]:
            # print(w,'is', r[0], 'Min lase value is', r[1])
            DAC = ((2**16 - r[1]) * (p/100)) + r[1]
            return DAC
            




# awareness = ctypes.c_int()
# errorCode = ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(awareness))
errorCode = ctypes.windll.shcore.SetProcessDpiAwareness(2)

# cdll.LoadLibrary("C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\SDK\\Blink_C_wrapper")
slm_lib = CDLL("Blink_C_wrapper")

# Open the image generation library
# cdll.LoadLibrary("C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\SDK\\ImageGen")
image_lib = CDLL("ImageGen")

# indicate that our images are RGB
RGB = c_uint(1);
is_eight_bit_image = c_uint(0);

# Call the constructor
slm_lib.Create_SDK();
print("Blink SDK was successfully constructed");

height = c_uint(slm_lib.Get_Height());
width = c_uint(slm_lib.Get_Width());
depth = c_uint(slm_lib.Get_Depth());
bytpesPerPixel = 4; #RGBA

print(height,width,depth)

center_x = c_uint(width.value//2);
center_y = c_uint(height.value//2);


#load the LUT wavelength calibration
success = 0;
success = slm_lib.Load_lut("C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\LUT Files\\19x12_8bit_linearVoltage.lut");
if success > 0: print("LoadLUT Successful")	
else: print("LoadLUT Failed")	

# Laser board connection 
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

# generate matrix of dots as hologram
slm_lib.Initialize_GerchbergSaxton()
slm_lib.Destruct_GerchbergSaxton()
# generate fresnel lens 200mm


# superimpose


# turn on laser
set_power(488, 5)     # (wavelngth, percentage)

# send image to SLM


# grab image from chameleon


# turn off laser
shutter()
laser_board.close()
print('close connection to laser board')

# calculate PSF across all dots


# generate score


slm_lib.Delete_SDK();











