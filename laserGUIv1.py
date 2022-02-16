#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Dec 10 16:06:20 2021

@author: sil1r12
"""

import sys, time, glob, serial

from PyQt5 import QtGui, QtWidgets, QtCore


class laser_line():
    def __init__(self, parent, wavelength, minSP, maxSP, control_type, calibration):

        self.wavelength = wavelength
        self.calibration = calibration
        self.parent = parent
        self.laser_on = False
        
        
#    if(control == 0){channel = laserChannel;} //NIR and 405
#    if(control == 1){channel = AOTFchannel;}  //488, 561, 660
        if(control_type == 0):                              #405, NIR diodes
            self.label                  = QtWidgets.QLabel('laser power:')
        if(control_type == 1):                              #488, 561, 660nm - (660nm need to specify laser power too!)
            self.label                  = QtWidgets.QLabel(' AOTF power:')   

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


    def selectChannel(self, w):
        if w == self.wavelength:
            self.box.setStyleSheet("background: lightgreen")
        else:
            self.box.setStyleSheet("background: lightgrey")
#        update GUI - colour the box?
#        send serial commands to the µC
        
    def changePower(self):
        p = self.power_slider.value()
        mW = p * self.calibration
        self.label2.setText("%s" %p + " %")
        self.label3.setText("%.2f" %mW + " mW")
        if self.laser_on:
#            call to main class
            self.parent.set_power(self.wavelength,p)
        
    def buttonPress(self): 
        if self.laser_on:#            laser already on, turn off
            self.parent.changeLaser(wavelength = self.wavelength)
            self.parent.set_power(self.wavelength,0)
        else:
            self.parent.shutter()
            self.parent.changeLaser(wavelength = self.wavelength)
            self.box.setStyleSheet("background: lightgreen")
            self.parent.set_power(self.wavelength,self.power_slider.value())
            self.channelSelect.setChecked(True)
            self.laser_on = True
            
    

class Lasers(QtWidgets.QMainWindow):
    def __init__(self):
        super(Lasers, self).__init__()
    # basic properties for the UI
        self.GUI_colour = QtGui.QColor(75,75,75)
        self.GUI_font   = QtGui.QFont('Times',10)        
        self.coms_list = self.serial_ports()
        self.initUI()
        self.connection = False
#        self.Teensy = serial.Serial(port='/dev/tty.usbmodem4305501', baudrate=115200, timeout=0.2)
        
    def serial_ports(self):
        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Unsupported platform')    
        result = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass
        print(result)
        return result
    
    def changeLaser(self, wavelength=0):
        for l in self.lines:
            if l.laser_on:
                l.laser_on = False
            l.channelSelect.setChecked(False)
            l.box.setStyleSheet("background: lightgrey")
#        print('')
    
    def set_power(self, w, p):
        if self.connection:
            s = "/%s.%s;\n" %(w,p)
            self.teensy.write(bytes(s,'utf-8'))
#            print(s)
        
        
    def shutter(self):
        if self.connection:
            self.teensy.write(b'/stop;\n')
#            print("stop")
        self.changeLaser() #use this to turn off all lines from the GUI pov

    def initUI(self):
        
        self.setWindowTitle('Laser Controller')
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Background, self.GUI_colour)
        self.setPalette(palette)
# LASERS TAB        
        self.lasers = [[405,0,4095,0,0.06],
                       [488,0,4095,1,0.04],
                       [561,0,4095,1,0.05],
                       [660,0,4095,1,0.03],
                       [780,0,2047,1,0.10]
                       ]
        self.lines = []
        self.button_group = QtWidgets.QButtonGroup()
        
        for l in self.lasers:
            self.lines.append(laser_line(self,l[0],l[1],l[2],l[3],l[4]))
            
        for l in self.lines:
            self.button_group.addButton(l.channelSelect)
        self.button_group.setExclusive(False)
            
        self.stopButton = QtWidgets.QPushButton('STOP')
        self.stopButton.pressed.connect(self.shutter)
        self.stopButton.setStyleSheet("background: salmon; font: bold 15pt; color: white;")
        self.stopButton.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        
# settings tab

        self.Settings_table = QtWidgets.QTableWidget()
        self.Settings_table.objectName = 'LaserSettings'
        self.Settings_table.setColumnCount(4)
        self.Settings_table.setHorizontalHeaderLabels(['Wav.', 'Min.V',
                                                        'Max.V', 'Cal.(mW/V)'])
        # self.Settings_table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        column_spacing = [65,65,65,100]
        for column in range(4):
            self.Settings_table.setColumnWidth(column, column_spacing[column])
        self.Settings_table.setFixedWidth(300)
        
        
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
        self.tab1.layout.addWidget(self.stopButton,                            0,0,1,1)

        for i, l in enumerate(self.lines):
            self.tab1.layout.addWidget(self.lines[i].box,                    i+1,0,1,1)
        self.tab1.setLayout(self.tab1.layout)

#TAB2
        self.Coms                           = QtWidgets.QComboBox()
        self.Coms.addItems(self.coms_list)
        self.ConnectButton                  = QtWidgets.QPushButton('Connect')
        self.DisconnectButton               = QtWidgets.QPushButton('Disconnect')
        self.ConnectButton.clicked.connect(lambda: self.connect('C'))
        self.DisconnectButton.clicked.connect(lambda: self.connect('D'))
        self.DisconnectButton.setEnabled(False)
        self.connectionStatus               = QtWidgets.QLabel('No connection')
        self.connectionStatus.setStyleSheet("color: white;")
        
        self.tab2.layout.addWidget(self.ConnectButton,                      0,0,1,1)
        self.tab2.layout.addWidget(self.DisconnectButton,                   1,0,1,1)
        self.tab2.layout.addWidget(self.Coms,                               2,0,1,1)
        self.tab2.layout.addWidget(self.connectionStatus,                   3,0,1,1)
        self.tab2.layout.addWidget(self.Settings_table,                     4,0,10,1)
        
        self.setCentralWidget(self.tabs)
        self.tab2.setLayout(self.tab2.layout)
        self.setGeometry(0, 30, 300, (len(self.lines)*100)+150)   
           
    def connect(self, state):
        if state == "C":
            p = self.Coms.currentText()
#            print(p)
            self.teensy = serial.Serial(port=p, baudrate=115200, timeout=0.5)
            time.sleep(1) #essential to have this delay!

            self.teensy.write(b'/hello;\n')
            reply = self.teensy.readline().strip()
#            print(reply)
            if reply == b'laser controller':
#                print('connection established')
                self.ConnectButton.setEnabled(False)
                self.DisconnectButton.setEnabled(True)
                self.Coms.setEnabled(False)
                self.connection = True
                self.connectionStatus.setText('Connection established')

            else:
                self.teensy.close()
#                print('closed')
        if state == "D":
            self.teensy.close()
            self.ConnectButton.setEnabled(True)
            self.DisconnectButton.setEnabled(False)
            self.Coms.setEnabled(True)
            self.connection = False
            self.connectionStatus.setText('No connection')
       
    def closeEvent(self, event):
        if self.connection:
            self.teensy.write(b'/stop;\n')
            self.connect('D')
    
if __name__ == '__main__':
    app = 0
    app = QtWidgets.QApplication(sys.argv)
    gui = Lasers()
    gui.show()
    app.exec_()        
        
        
        
        
    