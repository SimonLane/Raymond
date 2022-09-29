# -*- coding: utf-8 -*-
"""
Created on Fri Sep 02 17:00:52 2022

class for control of the ASI MS2000 with 3x LS-50 stages, configures as A, Y and XZ

@author: Simon
"""

import serial, time, struct
from PyQt5 import QtGui

class ETLens(QtGui.QWidget):
    def __init__(self, parent, name, port):
        super(ETLens, self).__init__(parent)
        self.flag_CONNECTED = False
        self.position = []
        self.port = port
        self.name = name
        self.baudrate=115200
        #default to Zero current
    
    def connect(self):
        try:
            self.ETL = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=1)
            time.sleep(0.3)
            self.flag_CONNECTED = True
            self.ETL.flush()
            
            self.firmware_type = self.get_firmware_type()
            self.firmware_version = self.get_firmware_version()
    
            self.device_id = self.get_device_id()
            self.max_output_current = self.get_max_output_current()
            self.set_temperature_limits(20, 40)
    
            self.mode = None
            self.refresh_active_mode()
    
            self.lens_serial = self.get_lens_serial_number()
            
            return True

        except Exception as e:
            print("Error connecting to '%s': %s" %(self.name,e))
            self.parent().information("Error connecting to '%s': %s" %(self.name,e), 'r')
            self.ETL.close()
            return False

    def close(self):
        if self.flag_CONNECTED == True:
            self.rapidMode(rapid=False)
            self.ASI.close()
            print("Disconnected from ASI stage")
            self.flag_CONNECTED = False
#modes
    def to_current_mode(self):
        self.send_command('MwDA', '>xxx')
        self.refresh_active_mode()
        
    def to_analog_mode(self):
        self.send_command('MwAA', '>xxx')
        self.refresh_active_mode()
        
    def to_focal_power_mode(self):
        error, max_fp_raw, min_fp_raw = self.send_command('MwCA', '>xxxBhh')
        min_fp, max_fp = min_fp_raw/200, max_fp_raw/200
        if self.firmware_type == 'A':
            min_fp, max_fp = min_fp - 5, max_fp - 5
        self.refresh_active_mode()
        return min_fp, max_fp
    
    def refresh_active_mode(self):
        self.mode = self.send_command('MMA', '>xxxB')[0]
        if self.mode == 1: mode = 'current'
        if self.mode == 5: mode = 'focal power'
        if self.mode == 6: mode = 'analog'
        
        self.parent().information(">> ETL mode: %s" %(mode), 'g')
        print('ETL set to %s mode' %(mode))
        return self.mode    

#temperature
    def get_temperature(self):
        return self.send_command(b'TCA', '>xxxh')[0] * 0.0625

    def set_temperature_limits(self, lower, upper):
        error, max_fp, min_fp = self.send_command(b'PwTA' + struct.pack('>hh', upper*16, lower*16), '>xxBhh')
        if self.firmware_type == 'A':
            return error, min_fp/200-5, max_fp/200-5
        else:
            return error, min_fp/200, max_fp/200

#current
    def get_current(self):
        return self.send_command(b'Ar\x00\x00', '>xh')[0] * self.max_output_current / 4095

    def set_current(self, current):
        if not self.mode == 1:
            raise Exception('Cannot set current when not in current mode')
        raw_current = int(current * 4095 / self.max_output_current)
        self.send_command(b'Aw' + struct.pack('>h', raw_current))

#focal power
    def get_diopter(self):
        raw_diopter, = self.send_command(b'PrDA\x00\x00\x00\x00', '>xxh')
        return raw_diopter/200 - 5 if self.firmware_type == 'A' else raw_diopter / 200

    def set_diopter(self, diopter):
        if not self.mode == 5:
            raise Exception('Cannot set focal power when not in focal power mode')
        raw_diopter = int((diopter + 5)*200 if self.firmware_type == 'A' else diopter*200)
        self.send_command(b'PwDA' + struct.pack('>h', raw_diopter) + b'\x00\x00')



    def get_lens_serial_number(self):
        return self.send_command('X', '>x8s')[0].decode('ascii')

    def crc_16(self, s):
        crc = 0x0000
        for c in s:
            crc = crc ^ c
            for i in range(0, 8):
                crc = (crc >> 1) ^ 0xA001 if (crc & 1) > 0 else crc >> 1
    
        return crc
    