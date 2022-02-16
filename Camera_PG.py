# -*- coding: utf-8 -*-
"""
Created on Mon May 10 17:49:12 2021

Class for Point Grey USB3 camera - used as a viewfinder
    low magnification, transmitted light

@author: Simon
"""
import PySpin
from PyQt5 import QtGui
import numpy as np

class Camera_PG(QtGui.QWidget):
    def __init__(self, parent, cam_name):
        super(Camera_PG, self).__init__(parent)
        self.flag_CONNECTED = False
        self.name = cam_name
        self.system = PySpin.System.GetInstance()
        self.cam_list = self.system.GetCameras()
        self.is_live = False
    def connect(self):
        try:
            if len(self.cam_list) == 0:
                print('Error connecting to %s: Camera not found'%(self.name))
                return
            self.camera = self.cam_list.GetByIndex(0)
            self.flag_CONNECTED = True
            self.camera.Init()
            print('Connected to %s'%(self.name))
            self.parent().information('Connected to %s'%(self.name), 'g')
                # get the newest image from the buffer by default
            sNodemap = self.camera.GetTLStreamNodeMap()
            node_bufferhandling_mode = PySpin.CEnumerationPtr(sNodemap.GetNode('StreamBufferHandlingMode'))
            node_newestonly = node_bufferhandling_mode.GetEntryByName('NewestOnly')
            node_newestonly_mode = node_newestonly.GetValue()
            node_bufferhandling_mode.SetIntValue(node_newestonly_mode)
            
            self.camera.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
            self.camera.ExposureMode.SetValue(PySpin.ExposureMode_Timed)
            self.exposure(6500)
            self.gain(18)
            self.parent().information('>> exposure: %sus '%(self.get_exposure()), 'g')
            return True
        except Exception as e:
            print('Error connecting to %s: %s'%(self.name,e))
            self.parent().information('Error connecting to %s: %s'%(self.name,e), 'r')
            return False
    
    def getFrame(self): # Function called periodically by a timer during live view mode
        if self.camera.IsStreaming():
            image = self.camera.GetNextImage(1000)
            if image.IsIncomplete():
                return []
            data = np.copy(image.GetData().reshape(1024,1280))
            image.Release()
            # Need to remove unused images so that the buffer doesn't clog
            return data
        else:
            return []
            
    def exposure(self, e):
        e = float(e) #camera requires a double
        if e>6500: e = 6500.0
        self.camera.ExposureTime.SetValue(e) 
        
        
    def gain(self, g):
        g = float(g) #camera requires a double
    # to do
    
    def get_exposure(self):
        return int(self.camera.ExposureTime())
    
    def get_gain(self):
        # to do
        pass
    
    def hot_pixel_correction(self, b):
        pass
    
    def live_mode(self):
        self.camera.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
        self.camera.BeginAcquisition()
        self.is_live = True
        
    def stop_live(self):
        self.camera.EndAcquisition()
        self.is_live = False

    def single_frame(self):
        pass
            
    def set_ROI(self,x,y,w,h):
        pass
    
    def binning(self, b):
        pass

    def close(self): 
        if self.flag_CONNECTED == True:
            # if camera in acquisition:
            if self.camera.IsStreaming() == True:
                print('interrupted %s acquisition during close' %(self.name))
                self.stop_live()
            
        # Deinitialize camera
            self.camera.DeInit()
            del self.camera
            self.cam_list.Clear()
            del self.cam_list
            self.system.ReleaseInstance()
            print('Disconnected from %s'%(self.name))
            self.flag_CONNECTED = False

            
            
            
            
            
            