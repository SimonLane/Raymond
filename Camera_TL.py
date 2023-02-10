# -*- coding: utf-8 -*-
"""
Created on Mon May 10 17:49:12 2021

@author: Simon
"""
from PyQt5 import QtGui

class Camera_TL(QtGui.QWidget):
    def __init__(self, parent, cam_name, cam_number, SDK):
        super(Camera_TL, self).__init__(parent)
        self.flag_CONNECTED = False
        self.name = cam_name
        self.SDK = SDK
        self.cam_number = cam_number
        
    def connect(self):
        try:
            self.TLcameras = self.SDK.discover_available_cameras()  # holds list of TL camears connected to PC at startup
            if len(self.TLcameras) == 0:
                print('Error connecting to %s: Camera not found'%(self.name))
                
                return
            self.camera = self.SDK.open_camera(self.TLcameras[self.cam_number])
            self.flag_CONNECTED = True
            self.parent().information('Connected to %s, (s/n:%s)'%(self.name, self.TLcameras[self.cam_number]), 'g')
            self.parent().information('>> bit depth: %s' %(self.camera.bit_depth), 'g')
            return True
            
        except Exception as e:
            print('Error connecting to %s: %s'%(self.name,e))
            self.parent().information('Error connecting to %s: %s'%(self.name,e), 'r')
            return False
    
    def getFrame(self): # Function called periodically by a timer during live view mode
        frame = self.camera.get_pending_frame_or_null()
        return frame
            
    def exposure(self, e):
        #convert milli to micro and set exposure time
        self.camera.exposure_time_us = int(e)*1000
    
    def get_exposure(self):
        #convert micro to milli and return the exposure time
        return self.camera.exposure_time_us / 1000.0
    
    def hot_pixel_correction(self, b):
        self.camera.is_hot_pixel_correction_enabled = b
        print('hot pixel correction enabled: ', self.camera.is_hot_pixel_correction_enabled)
    
    def live_mode(self):
        self.camera.frames_per_trigger_zero_for_unlimited = 0
        self.camera.operation_mode = 0      #SOFTWARE_TRIGGERED
        self.camera.arm(2)                 # set buffer to hold 2 images
        self.camera.issue_software_trigger()
        
    
    def stop_live(self):
        self.camera.disarm()
            
    def grab_mode(self):
        self.camera.frames_per_trigger_zero_for_unlimited = 1
        self.camera.operation_mode = 0      #'SOFTWARE_TRIGGERED'
        self.camera.arm(2)                  # set buffer to hold 2 images
        self.camera.issue_software_trigger()
        
    def frame_time(self): #returns the combined time for exposure and readout
        return int(self.camera.frame_time_us / 1000.0)
        
    def ext_mode(self):
        self.camera.frames_per_trigger_zero_for_unlimited = 1
        self.camera.operation_mode = 1      #'HARDWARE_TRIGGERED'
        # self.camera.operation_mode = 2    #'BULB'
    
    def set_ROI(self,x,y,w,h):
        self.camera.roi = (x,y,x+w,y+h)
        
    def prepare_buffer(self, b):
        pass
    
    def binning(self, b):
        bins = [1,2,4,8]
        self.camera.binx = bins[b]
        self.camera.biny = bins[b]

    def close(self): 
        if self.flag_CONNECTED == True:
            self.camera.dispose()
            
            self.flag_CONNECTED = False
            print('Disconnected from %s'%(self.name))