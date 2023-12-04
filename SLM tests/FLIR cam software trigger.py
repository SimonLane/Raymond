# -*- coding: utf-8 -*-
"""
Created on Tue Aug 15 16:05:12 2023

@author: Ray Lee
"""

import PySpin
import time, os
from PIL import Image
import numpy as np
import cv2
import matplotlib.pyplot as plt


output_dir = 'C:\\Users\\Ray Lee\\Documents\Simon\\SLM test'

#camera setup
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
    node_exposure_time.SetValue(10000)
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


system, cam, cam_list = connect_camera() 
set_trigger_software(cam) 
  
#  Begin acquiring images
cam.BeginAcquisition()
node_softwaretrigger_cmd = PySpin.CCommandPtr(cam.GetNodeMap().GetNode('TriggerSoftware'))

for i in range(3):
    node_softwaretrigger_cmd.Execute()
    time.sleep(1)
    image_result = cam.GetNextImage(1000)
    d = image_result.GetData()
    np_img = np.array(d, dtype='uint8').reshape((1280,1024))
    
    if image_result.IsIncomplete():
        print('Image incomplete with image status %d ...' % image_result.GetImageStatus())
    
    else:
        width = image_result.GetWidth()
        height = image_result.GetHeight()
        print('Grabbed Image %d, width = %d, height = %d' % (i, width, height))

    image_converted = image_result.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
    
    print(np_img)
    plt.imshow(np_img)
    plt.show()
    
    filename = "PySpin image %d.jpg" %i
    image_converted.Save(filename)
    print('Image saved at %s\n' % filename)
    image_result.Release()

    
cam.EndAcquisition()

set_trigger_normal(cam)
cam.DeInit()
del cam
del cam_list
system.ReleaseInstance()


# for i in range(3):
#     filename = "PySpin image %d.jpg" %i
#     image = cv2.imread(filename)
#     #print(image.shape)
#     plt.imshow(image)
#     plt.show()
#     print(i)