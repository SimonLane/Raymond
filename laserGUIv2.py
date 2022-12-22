#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Dec 10 16:06:20 2021

@author: sil1r12
"""

import sys, time, serial
import pandas as pd
from PyQt5 import QtGui
from PyQt5 import QtWidgets
from PyQt5 import QtCore

class laser_line():
    def __init__(self, parent, wavelength, minV, maxV, minuW, maxuW, eqn, p1, p2):
        self.parent = parent
        self.wavelength = wavelength
        self.min_value = minV
        self.max_value = maxV
        self.min_microWatt = minuW
        self.max_microWatt = maxuW
        self.equation_type = eqn
        self.parameter_1 = p1
        self.parameter_2 = p2
        self.laser_on = False
        self.firmware_verbose = False #Store whether the firmware was in verbose mode, set back when closing connection
        self.percentage = 0
        self.microWatts = 0
        self.value_16   = 0
        
        self.label                      = QtWidgets.QLabel('laser power:')
        self.channelSelect              = QtWidgets.QRadioButton()
        self.channelSelect.setChecked(False)
        self.channelSelect.released.connect(self.buttonPress)
        self.power_slider               = QtWidgets.QSlider()
        self.power_slider.setOrientation(QtCore.Qt.Horizontal)
        self.power_slider.setMinimum(0)
        self.power_slider.setMaximum(100)
        self.power_slider.setTickInterval(10)
        self.power_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.power_slider.setValue(0)
        self.power_slider.valueChanged.connect(lambda: self.changePower())
        
        self.label2                     = QtWidgets.QLabel('0 %')
        self.label3                     = QtWidgets.QLabel('(0.00 mW)')

        self.box                        = QtWidgets.QGroupBox('%s nm' %wavelength) #main container
        self.box.setStyleSheet("background: lightgrey")
        self.box.setLayout(QtWidgets.QGridLayout())
        self.box.layout().addWidget(self.label,           0,0,1,2)
        self.box.layout().addWidget(self.power_slider,    0,2,1,5)
        self.box.layout().addWidget(self.label2,          0,7,1,2)
        self.box.layout().addWidget(self.channelSelect,   1,0,1,1)
        self.box.layout().addWidget(self.label3,          1,7,1,2)

    def buttonPress(self): 
        if self.laser_on:#                           laser already on, turn off
            self.parent.changeLaser(wavelength = 0)
            self.parent.set_power(self.wavelength,0)
        else:                           #            laser off, turn on, and turn off all others
            self.parent.changeLaser(wavelength = self.wavelength)
            self.laser_on = True
            self.changePower()

    def changePower(self):
        p,v,w = self.percent_to_16_bit()
        self.label2.setText("%s" %p + " %")
        self.label3.setText("(%.2f μW)"%w)
        if self.laser_on:
            self.parent.set_power(self.wavelength,v)

    def percent_to_16_bit(self): #percentage, 16-bit value, wattage    
        p = self.power_slider.value() #percentage
        if(p==0):
            self.microWatts, w = 0,0
            self.percentage, p = 0,0
            self.value_16, v   = 0,0
        else:
            #map percentage to 16-bit value
            m = (self.max_value-self.min_value)/(100)
            v = (m*p) + self.min_value
            #convert 16-bit value to power
            if(self.equation_type == 'lin'): 
                w = (v*self.parameter_1) + self.parameter_2
            if(self.equation_type == 'pow'): 
                w = ((pow(v,self.parameter_2)) * self.parameter_1)
                self.microWatts = w
                self.percentage = p
                self.value_16   = v
        return p,v,w
        
class Lasers(QtWidgets.QMainWindow):
    def __init__(self):
        super(Lasers, self).__init__()
    # basic properties for the UI
        self.GUI_colour = QtGui.QColor(75,75,75)
        self.GUI_font   = QtGui.QFont('Times',10)
        self.laserCalibration = ''
        self.address = "/Users/Ray Lee/Documents/GitHub/Raymond/"
        self.port = 'COM10'
        self.initUI()
        self.connection = False
        try:
            self.connect('C', port = self.port)
        except:
            print('Failed to connect on port %s' %(self.port))
            

    def changeLaser(self, wavelength=0): 
        for l in self.lines:
            #turn off all
            l.box.setStyleSheet("background: lightgrey")
            if l.laser_on: l.laser_on = False
            l.channelSelect.setChecked(False)
            if l.wavelength == wavelength:
                l.box.setStyleSheet("background: lightgreen")
                l.channelSelect.setChecked(True)

    
    def set_power(self, w, v):
        if self.connection:
            s = "/%s.%s;\n" %(w,int(v))
            self.teensy.write(bytes(s,'utf-8')) # send the 16-bit value for the DAC
            print("sending command: %s" %s)
            
    def shutter(self):
        if self.connection:
            self.teensy.write(b'/stop;\n')
#            print("stop")
        self.changeLaser() #use this to turn off all lines from the GUI pov

    def initUI(self):
        self.setGeometry(0, 50, 300, 1500) # doesn't work, why?
        self.setWindowTitle('Laser Controller')
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Background, self.GUI_colour)
        self.setPalette(palette)
# =============================================================================
# # LASERS TAB        
# =============================================================================
        
        #LOAD IN THE DATA
        self.dataframe = pd.read_csv("%sLaserCalibration.txt" %(self.address), header=0, index_col=0, sep ='\t')
        self.lines = []
        self.lasers = []
        for row in range(self.dataframe.shape[0]):
            l = self.dataframe.iloc[row, :]
            self.lasers.append(l)
            #               ['Wav.','Min.V','Max.V','Min.uW','Max.uW','Eqn.','P.1','P.2']
            self.lines.append(laser_line(self,l[0],l[1],l[2],l[3],l[4],l[5],l[6],l[7]))
        
        self.button_group = QtWidgets.QButtonGroup()
        for l in self.lines:
            self.button_group.addButton(l.channelSelect)
        self.button_group.setExclusive(False)
            
        self.stopButton = QtWidgets.QPushButton('STOP')
        self.stopButton.pressed.connect(self.shutter)
        self.stopButton.setStyleSheet("background: salmon; font: bold 15pt; color: white;")
        self.stopButton.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

# galvo control
        self.galvo_slider               = QtWidgets.QSlider()
        self.galvo_slider.setOrientation(QtCore.Qt.Horizontal)
        self.galvo_slider.setMinimum(0)
        self.galvo_slider.setMaximum(4095)
        self.galvo_slider.setTickInterval(100)
        self.galvo_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.galvo_slider.setValue(2100)
        self.galvo_slider.setEnabled(False)
        self.galvo_slider.valueChanged.connect(lambda: self.galvo_value(self.galvo_slider.value()))
        self.galvo_checkbox             = QtWidgets.QCheckBox('Manual Override')
        self.galvo_checkbox.setChecked(False)
        self.galvo_checkbox.stateChanged.connect(self.manual_galvo)
        self.g_spinbox                  = QtWidgets.QSpinBox()
        self.g_spinbox.setRange(0,4095)
        self.g_spinbox.setSingleStep(1)
        self.g_spinbox.setValue(2000)
        self.g_spinbox.editingFinished.connect(lambda: self.galvo_value(self.g_spinbox.value()))
        self.g_spinbox.setEnabled(False)

        self.g_box                      = QtWidgets.QGroupBox('Galvo 1') #main container
        self.g_box.setStyleSheet("background: lightgrey")
        self.g_box.setLayout(QtWidgets.QGridLayout())
        self.g_box.layout().addWidget(self.galvo_slider,              0,0,1,9)
        self.g_box.layout().addWidget(self.g_spinbox,                 1,6,1,2)
        self.g_box.layout().addWidget(self.galvo_checkbox,            1,0,1,2)

        
# =============================================================================
# # settings tab
# =============================================================================

        self.Settings_table = QtWidgets.QTableWidget()
        self.Settings_table.objectName = 'LaserSettings'
        self.Settings_table.setColumnCount(8)
        self.Settings_table.setRowCount(len(self.dataframe.index))
        self.Settings_table.setHorizontalHeaderLabels(
            ['Wav.', 'Min.V', 'Max.V', 'Min. uW', 'Max. uW', 'Eqn.', 'P.1', 'P.2'])
        # self.Settings_table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        column_spacing = [40,40,40,60,60,40,50,50]
        for column in range(8):
            self.Settings_table.setColumnWidth(column, column_spacing[column])
        self.Settings_table.setFixedWidth(380)
        for i in range(len(self.dataframe.index)):
            for j in range(len(self.dataframe.columns)):
                item = QtWidgets.QTableWidgetItem(str(self.dataframe.iloc[i, j]))
                item.setFlags(item.flags() &~ QtCore.Qt.ItemIsEditable)
                self.Settings_table.setItem(i,j,item)

        
#==============================================================================
# Overall assembly
#==============================================================================
      
        self.tabs = QtWidgets.QTabWidget()
        self.tab1 = QtWidgets.QWidget()
        self.tab2 = QtWidgets.QWidget()
        self.tabs.resize(300,500)
        self.tabs.addTab(self.tab1,"Lasers")
        self.tabs.addTab(self.tab2,"Settings")
        self.tab1.layout = QtWidgets.QGridLayout()
        self.tab2.layout = QtWidgets.QGridLayout()

#TAB1
        self.tab1.layout.addWidget(self.stopButton,                         0,0,1,1)
        count = 0
        for i, l in enumerate(self.lines):
            count+=1
            self.tab1.layout.addWidget(self.lines[i].box,                 i+1,0,1,1)
        self.tab1.layout.addWidget(self.g_box,                        count+1,0,1,1)
        self.tab1.setLayout(self.tab1.layout)

#TAB2
        self.ILboardMode = QtWidgets.QCheckBox('Illumination board I2C mode')
        self.ILboardMode.setChecked(False)
        self.ILboardMode.stateChanged.connect(self.I2Cmode)
        self.connectionStatus = QtWidgets.QLabel('No connection')
        self.connectionStatus.setStyleSheet("color: black;")
        
        self.tab2.layout.addWidget(self.connectionStatus,                   0,0,1,1)
        self.tab2.layout.addWidget(self.ILboardMode,                        1,0,1,1)
        self.tab2.layout.addWidget(self.Settings_table,                     5,0,10,1)
        
        self.setCentralWidget(self.tabs)
        self.tab2.setLayout(self.tab2.layout)
        self.setGeometry(0, 30, 300, (len(self.lines)*100)+150)   
    
    def save_calibration(self):
        headings = ["wav.","minVal","maxVal","minPow","maxPow","Eqn.","P1","P2"]
        self.dataframe.to_csv("%sLaserCalibration.txt" %(self.address), mode='w', header=headings, index=True, sep ='\t')


    def connect(self, state, port='COM10'):
        if state == "C":
            
            self.teensy = serial.Serial(port=port, baudrate=115200, timeout=0.5)
            time.sleep(1) #essential to have this delay!
            
            self.teensy.write(b'/hello;\n')                     #handshake
            reply = self.teensy.readline().strip()
            print(reply)
            if reply == b'lasers':
#                print('connection established')
                self.connection = True
                self.connectionStatus.setText('Connection established: %s' %(port))
                #put the illuminiation board into mode 0 (turns off the trigger)
                self.teensy.write(bytes("/mode.0;\n",'utf-8'))
            elif  b'Over Serial' in reply:
                print('verbose mode detected')
                #The laser control board is in verbose mode, needs to not be for serial communication.
                self.firmware_verbose = True
                self.teensy.write(bytes("/verbose.0;\n",'utf-8'))   #turn off verbose mode 
                print('verbose mode off command')
                reply = self.teensy.readline().strip()
                print(reply)
                self.teensy.close()
                time.sleep(0.5)
                print('close connection')
                self.connect('C')
            else:
                self.teensy.close()
                print('close connection')
                
        if state == "D":
            self.teensy.close()
            self.connection = False
            self.connectionStatus.setText('No connection')
    
    def manual_galvo(self):
        if self.galvo_checkbox.isChecked(): #override galvo
            self.galvo_slider.setEnabled(True)
            self.g_spinbox.setEnabled(True)
            self.teensy.write(bytes("/GM.1;\n",'utf-8'))
        else:                               #normal galvo function
            self.galvo_slider.setEnabled(False)
            self.g_spinbox.setEnabled(False)
            self.teensy.write(bytes("/GM.0;\n",'utf-8'))
    
    def I2Cmode(self):
        if self.ILboardMode.isChecked():
            self.teensy.write(bytes("/mode.1;\n",'utf-8'))
        else:
            self.teensy.write(bytes("/mode.0;\n",'utf-8'))
            
            
            
    def galvo_value(self, value):
        # update the widgets
        self.g_spinbox.setValue(value)
        self.galvo_slider.setValue(value)
        # send to hardware
        s = "/G1.%s;\n" %(value)
        self.teensy.write(bytes(s,'utf-8'))
    
    def closeEvent(self, event):
        if self.connection:
            self.teensy.write(b'/GM.0;\n') #return galvo mirror to automatic control
            self.teensy.write(b'/stop;\n') #turn off all lasers, set galvo to safe position
            self.connect('D')
            self.save_calibration()
    
if __name__ == '__main__':
    app = 0
    app = QtWidgets.QApplication(sys.argv)
    gui = Lasers()
    gui.show()
    app.exec_()        
        
        
        
        
    