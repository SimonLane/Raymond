# -*- coding: utf-8 -*-
"""
Created on Wed Apr 26 13:57:19 2023

Test script for Meadowlark SLM - Blaze gratings

@author: Simon Lane
"""

import os, serial
import numpy as np
import pandas as pd
from ctypes import cdll, CDLL, c_uint, POINTER, c_ubyte, c_float, c_double, c_ulong
from scipy import misc
import imageio.v2 as imageio
from time import sleep
import ctypes

import PySpin
from PIL import Image
import matplotlib.pyplot as plt

laser_com       = 'COM10'
address = "/Users/Ray Lee/Documents/GitHub/Raymond/"
output_dir = 'C:\\Users\\Ray Lee\\Documents\Simon\\SLM test'
image_dir = 'C:/Program Files/Meadowlark Optics/Blink 1920 HDMI/Image Files/'
lasers = [] 
do_cam = True 

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

# =============================================================================
# CAMERA FUNCTIONS
# =============================================================================
def connect_camera():
    system = PySpin.System.GetInstance()
    cam_list = system.GetCameras()
    cam = cam_list[0]
    cam.Init()
    
        # turn off auto-exposure
    nodemap = cam.GetNodeMap()
    node_exposure_auto = PySpin.CEnumerationPtr(nodemap.GetNode('ExposureAuto'))
    entry_exposure_auto_off = node_exposure_auto.GetEntryByName('Off')
    exposure_auto_off = entry_exposure_auto_off.GetValue()
    node_exposure_auto.SetIntValue(exposure_auto_off)

    # Set Exposure Time 
    node_exposure_time = PySpin.CFloatPtr(nodemap.GetNode('ExposureTime'))
    node_exposure_time.SetValue(5000)
    return system, cam, cam_list

  
# Set up for software trigger
def set_trigger_software(cam):
    nodemap = cam.GetNodeMap()
    node_trigger_mode = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerMode'))
    node_trigger_mode_off = node_trigger_mode.GetEntryByName('Off')
    node_trigger_mode.SetIntValue(node_trigger_mode_off.GetValue())    
    node_trigger_selector= PySpin.CEnumerationPtr(nodemap.GetNode('TriggerSelector'))
    node_trigger_selector_framestart = node_trigger_selector.GetEntryByName('FrameStart')
    node_trigger_selector.SetIntValue(node_trigger_selector_framestart.GetValue())
    node_trigger_source = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerSource'))
    node_trigger_source_software = node_trigger_source.GetEntryByName('Software')
    node_trigger_source.SetIntValue(node_trigger_source_software.GetValue())
    node_trigger_mode_on = node_trigger_mode.GetEntryByName('On')
    node_trigger_mode.SetIntValue(node_trigger_mode_on.GetValue())
    node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
    node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
    acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()
    node_acquisition_mode.SetIntValue(acquisition_mode_continuous)

def set_trigger_normal(cam):
    #return camera to normal (non triggered) mode
    nodemap = cam.GetNodeMap()
    node_trigger_mode = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerMode'))
    node_trigger_mode_off = node_trigger_mode.GetEntryByName('Off')
    node_trigger_mode.SetIntValue(node_trigger_mode_off.GetValue())


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

print('SLM:',height,width,depth)

center_x = c_uint(width.value//2);
center_y = c_uint(height.value//2);

#load the LUT wavelength calibration
success = 0;
success = slm_lib.Load_lut("C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\LUT Files\\19x12_8bit_linearVoltage.lut");
if success > 0: print("LoadLUT Successful")	
else: print("LoadLUT Failed")	

# Create two vectors to hold values for two SLM images
ImageOne = np.empty([width.value*height.value*bytpesPerPixel], np.uint8, 'C');
ImageTwo = np.empty([width.value*height.value*bytpesPerPixel], np.uint8, 'C');


#start camera
system, cam, cam_list = connect_camera() 
set_trigger_software(cam) 
cam.BeginAcquisition()
node_softwaretrigger_cmd = PySpin.CCommandPtr(cam.GetNodeMap().GetNode('TriggerSoftware'))

# =============================================================================
# # LASER 
# =============================================================================
laser_board = serial.Serial(port=laser_com, baudrate=115200, timeout=0.5)
sleep(1) #essential to have this delay!
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
# dataframe = pd.read_csv("%sLaserCalibration.txt" %(address), header=0, index_col=0, sep ='\t')
# for row in range(dataframe.shape[0]):
#     l = dataframe.iloc[row, :]
#     lasers.append(l)
#     #['Wav.','Min.V','Max.V','Min.uW','Max.uW','Eqn.','P.1','P.2']

# turn on laser
laser_board.write(bytes('/488.8323;','utf-8'))     # (wavelngth, percentage)
sleep(0.2)


# =============================================================================
# generate images for SLM
# =============================================================================
Xs = []
Ys = []
Zs = []
Is = []
n = 0
step = 45
range = 270
target_image = np.zeros((1200, 1920), dtype='uint8')
for x in np.arange(int(600 - (range/2)), int(600 + (range/2)+step), step):
    for y in np.arange(int(960 - (range/2)), int(960 + (range/2)+step), step):
        for x2 in [-4,-3,-2,-1,0,1,2,3,4]:
            for y2 in [-4,-3,-2,-1,0,1,2,3,4]:
                Xs.append(x+x2)
                Ys.append(y+y2)
                Zs.append(0)
                Is.append(1)
                n+=1
                target_image[x+x2,y+y2] = 255
        

plt.imshow(target_image)
plt.show()
# convert to ctype
XSpots = np.array(Xs, dtype='f');
YSpots = np.array(Ys, dtype='f');
ZSpots = np.array(Zs, dtype='f');
ISpots = np.array(Is, dtype='f');
N_spots = c_uint(n);
ApplyAffine = c_uint(0);

# Generate hologram
WFC = np.empty([width.value*height.value*bytpesPerPixel], np.uint8, 'C');
iterations = c_uint(10);
image_lib.Initialize_HologramGenerator(width.value, height.value, depth.value, iterations, RGB);
image_lib.Generate_Hologram(ImageOne.ctypes.data_as(POINTER(c_ubyte)), 
                            WFC.ctypes.data_as(POINTER(c_ubyte)), 
                            XSpots.ctypes.data_as(POINTER(c_float)), 
                            YSpots.ctypes.data_as(POINTER(c_float)), 
                            ZSpots.ctypes.data_as(POINTER(c_float)), 
                            ISpots.ctypes.data_as(POINTER(c_float)), 
                            N_spots, ApplyAffine);

save_as = '%s/pyGenHolo.bmp' %image_dir
imageio.imwrite(save_as, np.reshape(ImageOne.copy(), (1200,1920,4)))

# generate fresnel lens 200mm
lens_power = c_double(200);
image_lib.Generate_FresnelLens(ImageTwo.ctypes.data_as(POINTER(c_ubyte)), 
                            WFC.ctypes.data_as(POINTER(c_ubyte)),
                            width.value, height.value, depth.value,
                            center_x, center_y, 600,
                            lens_power, 0, 0, 0)
save_as = '%s/pyGenLens.bmp' %image_dir
imageio.imwrite(save_as, np.reshape(ImageTwo.copy(), (1200,1920,4)))

# superimpose
Super = (ImageOne + ImageTwo) % 255
out = np.reshape(Super.copy(), (1920 * 1200,4))[:,0]


save_as = '%s/pySuper.bmp' %image_dir
imageio.imwrite(save_as, np.reshape(Super.copy(), (1200,1920,4)))
# =============================================================================
#  Write images to SLM
# =============================================================================

print('write bmp directly') # import image from a file
test_image = imageio.imread(os.path.join(image_dir, 'centergrid_FL+200.bmp'))
new_image = np.reshape(test_image[:,:,0].copy(), 1200*1920)
slm_lib.Write_image(new_image.ctypes.data_as(POINTER(c_ubyte)), 1)
sleep(1)
node_softwaretrigger_cmd.Execute() # trigger camera
sleep(1)
image_result = cam.GetNextImage(5500) # Get frame
image_converted = image_result.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
filename = "SLM from image.jpg"
image_converted.Save(filename)
d = image_result.GetData()
np_img = np.array(d, dtype='uint8').reshape((1280,1024))
plt.imshow(np_img)
plt.show()
image_result.Release()

print('create image in python') # image generated on the fly
slm_lib.Write_image(Super.copy().ctypes.data_as(POINTER(c_ubyte)), 1)
sleep(1)
node_softwaretrigger_cmd.Execute() # trigger camera
sleep(1)

image_result = cam.GetNextImage(5500) # Get frame
image_converted = image_result.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
filename = "SLM generated.jpg"
image_converted.Save(filename)
d = image_result.GetData()
np_img = np.array(d, dtype='uint8').reshape((1280,1024))
plt.imshow(np_img)
plt.show()
image_result.Release() 



cam.EndAcquisition()
# calculate PSF across all dots


# generate score



# # turn off laser
shutter()
laser_board.close()
print('close connection to laser board')

# close camera

set_trigger_normal(cam)
cam.DeInit()
del cam
del cam_list
system.ReleaseInstance()

# close SLM
slm_lib.Delete_SDK();
print('Disconnected from SLM')











