# Example usage of Blink_C_wrapper.dll
# Meadowlark Optics Spatial Light Modulators
# September 12 2019

import os, serial, time
import numpy as np
from ctypes import cdll, CDLL, c_uint, POINTER, c_ubyte, c_float
from scipy import misc
from time import sleep
import pandas as pd
import ctypes

################################ MAKE SURE THE WINDOW SHOWS UP IN THE WRITE PLACE FOR THE DPI SETTINGS#############




def set_power(w, p):
    v = get_val16(w,p) #convert percentage to 16-bit DAC value
    s = "/%s.%s;\n" %(w,int(v))
    laser_board.write(bytes(s,'utf-8')) # send the 16-bit value for the DAC
    print("sending laser command: %s" %s)

def get_val16(w,p): #supply wavelength and percentage to retreive the DAC value
    for r in lasers:
        print(r[0])
        if w == r[0]:
            # print(w,'is', r[0], 'Min lase value is', r[1])
            DAC = ((2**16 - r[1]) * (p/100)) + r[1]
            return DAC    
# =============================================================================
# # LASER 
# =============================================================================
lasers = [] 
laser_com       = 'COM10'
address = "/Users/Ray Lee/Documents/GitHub/Raymond/"

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



# =============================================================================
# SLM
# =============================================================================

awareness = ctypes.c_int()
errorCode = ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(awareness))
print(awareness.value)

# Set DPI Awareness  (Windows 10 and 8)
errorCode = ctypes.windll.shcore.SetProcessDpiAwareness(2)
# the argument is the awareness level, which can be 0, 1 or 2:
# for 1-to-1 pixel control I seem to need it to be non-zero (I'm using level 2)

# Set DPI Awareness  (Windows 7 and Vista)
success = ctypes.windll.user32.SetProcessDPIAware()
# behaviour on later OSes is undefined, although when I run it on my Windows 10 machine, it seems to work with effects identical to SetProcessDpiAwareness(1)
#######################################################################################################################


# Load the DLL
# Blink_C_wrapper.dll, HdmiDisplay.dll, ImageGen.dll, freeglut.dll and glew64.dll
# should all be located in the same directory as the program referencing the
# library
cdll.LoadLibrary("C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\SDK\\Blink_C_wrapper")
slm_lib = CDLL("Blink_C_wrapper")

# Open the image generation library
cdll.LoadLibrary("C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\SDK\\ImageGen")
image_lib = CDLL("ImageGen")

# indicate that our images are RGB
RGB = c_uint(1);
is_eight_bit_image = c_uint(0);

# Call the constructor
slm_lib.Create_SDK();
print ("Blink SDK was successfully constructed");

height = c_uint(slm_lib.Get_Height());
width = c_uint(slm_lib.Get_Width());
depth = c_uint(slm_lib.Get_Depth());
bytpesPerPixel = 4; #RGBA
print(height,width,depth)
center_x = c_uint(width.value//2);
center_y = c_uint(height.value//2);

#***you should replace linear.LUT with your custom LUT file***
#but for now open a generic LUT that linearly maps input graylevels to output voltages
#***Using linear.LUT does NOT give a linear phase response***
success = 0;
if height.value == 1152:
    success = slm_lib.Load_lut("C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\LUT Files\\1920x1152_linearVoltage.lut");
if (height.value == 1200)and(depth.value == 8):
    success = slm_lib.Load_lut("C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\LUT Files\\19x12_8bit_linearVoltage.lut");
if (height.value == 1200)and(depth.value == 10):
    success = slm_lib.Load_lut("C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\LUT Files\\19x12_10bit_linearVoltage.lut");

if success > 0: 
    print ("LoadLUT Successful")	
else:
	print("LoadLUT Failed")
	
# Create two vectors to hold values for two SLM images
ImageOne = np.empty([width.value*height.value*bytpesPerPixel], np.uint8, 'C');
ImageTwo = np.empty([width.value*height.value*bytpesPerPixel], np.uint8, 'C');

# Create a blank vector to hold the wavefront correction
WFC = np.empty([width.value*height.value*bytpesPerPixel], np.uint8, 'C');

# Generate phase gradients
VortexCharge = 5;
image_lib.Generate_LG(ImageOne.ctypes.data_as(POINTER(c_ubyte)), WFC.ctypes.data_as(POINTER(c_ubyte)), 
                      width.value, height.value, depth.value, VortexCharge, center_x.value, center_y.value, 0, RGB);
VortexCharge = 3;
image_lib.Generate_LG(ImageTwo.ctypes.data_as(POINTER(c_ubyte)), WFC.ctypes.data_as(POINTER(c_ubyte)), 
                      width.value, height.value, depth.value, VortexCharge, center_x.value, center_y.value, 0, RGB);

# test ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#image_lib.Generate_Hologram.argtypes = ctypes.c_ubyte,ctypes.c_ubyte, ctypes.c_float,ctypes.c_float,ctypes.c_float,ctypes.c_float,ctypes.c_int,ctypes.c_int

iterations = 5 # number of iterations used to generate the hologram
RGB = True # True for HDMI interface
image_lib.Initialize_HologramGenerator(width, height, depth, iterations, RGB)


x_locations = np.arange(-100.0, 200.0, 100.0, dtype=np.float32)
y_locations = np.arange(-100.0, 200.0, 100.0, dtype=np.float32)
z_locations = np.arange(-100.0, 200.0, 100.0, dtype=np.float32)

image_lib.Generate_Hologram(ImageOne.ctypes.data_as(POINTER(c_ubyte)), 
                            WFC.ctypes.data_as(POINTER(c_ubyte)),
                            x_locations.ctypes.data_as(POINTER(c_float)),
                            y_locations.ctypes.data_as(POINTER(c_float)),
                            z_locations.ctypes.data_as(POINTER(c_float)),
                            ctypes.c_int(1),  # intensities
                            ctypes.c_int(len(x_locations)),  #length of array/number of points
                            ctypes.c_int(0))

# end test ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

set_power(488, 5)     # (wavelngth, percentage)


# Loop between our images
for x in range(2):
    slm_lib.Write_image(ImageOne.ctypes.data_as(POINTER(c_ubyte)), is_eight_bit_image);
    sleep(0.5); # This is in seconds
    slm_lib.Write_image(ImageTwo.ctypes.data_as(POINTER(c_ubyte)), is_eight_bit_image);
    sleep(0.5); # This is in seconds

# Always call Delete_SDK before exiting
slm_lib.Delete_SDK();
laser_board.write(b'/stop;\n')
laser_board.close()