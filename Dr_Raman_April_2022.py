# -*- coding: utf-8 -*-
"""
Outreach Spectrometer GUI


@author: Simon Lane
"""

#imports
from wasatch.WasatchBus    import WasatchBus
from wasatch.WasatchDevice import WasatchDevice
from wasatch.DeviceID      import DeviceID

from PyQt5 import QtGui, QtCore, Qt
import sys, time, serial, glob
import pyqtgraph as pg
import numpy as np
Polynomial = np.polynomial.Polynomial
import csv
import usb.core
import usb.util as ut

from usb.backend import libusb1

# Script modified from 2019 version....
# Wasatch Raman 532 spectrometer, with separate laser.


class WPSpec(QtGui.QMainWindow):
    def __init__(self):
        super(WPSpec, self).__init__()
        
        self.usb_backend_location = "/opt/anaconda3/envs/wasatch3/lib/python3.7/site-packages/libusb/_platform/_osx/x64/libusb-1.0.dylib"
        self.t = 150    #integration time
        self.p = 0      # laser power (%)
        self.a = 10     # averages
        
        
        try:        
            device_ids = self.find_usb_devices()
            print(device_ids[0])
            self.device = WasatchDevice(device_ids[0])
            print("connected to %s %s with %d pixels from (%.2f, %.2f) cm-1, @%.2f nm" % (
            self.device.settings.eeprom.model,
            self.device.settings.eeprom.serial_number,
            self.device.settings.pixels(),
            self.device.settings.wavenumbers[0],
            self.device.settings.wavenumbers[-1],
            self.device.settings.excitation()))
            self.spectimer = QtCore.QTimer()
            self.spectimer.setSingleShot(False)
            self.spectimer.timeout.connect(self.get_spectra)
            self.spectimer.start(250) # timer to get spectra at 4Hz, need to control laser too to get BG reading
        except Exception as e:
            print("Did not connect with spectrometer, ", e)
            sys.exit(0)
                
        #connect with arduino
        self.coms_list = self.serial_ports()

        self.initUI()
        time.sleep(2)   
        self.device.hardware.set_integration_time_ms(self.t)
        self.device.settings.state.scans_to_average = self.a
        self.device.settings.state.laser_power_perc = self.p
        self.device.settings.state.acquisition_laser_trigger_enable = True
        self.device.settings.state.raman_mode_enabled = False
        self.device.settings.state.free_running_mode = False
               
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
               #Setup main Window
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def initUI(self):

        self.setWindowTitle('Outreach Spectrometer GUI')
#        palette = QtGui.QPalette()
#        palette.setColor(QtGui.QPalette.Background, QtGui.QColor(80,80,80))
#        self.setPalette(palette)
        
        sizePolicyMin = QtGui.QSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Minimum)
        sizePolicyMin.setHorizontalStretch(0)
        sizePolicyMin.setVerticalStretch(0)
        screen       =  QtGui.QApplication.desktop().screenGeometry().getCoords()
        screenHeight = screen[-1]
        screenWidth  = screen[-2]
        self.setGeometry(0, 0, screenWidth*0.8, screenHeight*0.8)
        
        self.Coms                           = QtGui.QComboBox()
        self.Coms.addItems(self.coms_list)
        self.ConnectButton                  = QtGui.QPushButton('Connect')
        self.ConnectButton.clicked.connect(lambda: self.connect('C'))
        
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
               #Setup Panes/Tabs
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        
#BUTTON
        self.AdvanceButton                  = QtGui.QPushButton('') #later replace with big symbol
        self.AdvanceButton.clicked.connect(self.advance_stage)
        self.AdvanceButton.setIcon(QtGui.QIcon('./button.png'))
        self.AdvanceButton.setIconSize(QtCore.QSize(240,240))
        
        self.laser                          = Qt.QLineEdit('50')
        self.laser.setValidator(QtGui.QIntValidator(1,100))
        self.laser.returnPressed.connect(lambda: self.set_laser_power(int(self.laser.text())))
        self.int_time                       = Qt.QLineEdit('50')
        self.int_time.setValidator(QtGui.QIntValidator(10,100))
        self.int_time.returnPressed.connect(lambda: self.set_int_time(int(self.int_time.text())))

#OUTPUTs
        #TEXT
        self.Output                         = QtGui.QLabel('NO SIGNAL') #To do increase font size
        newfont = QtGui.QFont("Times", 90, QtGui.QFont.Bold) 
        self.Output.setFont(newfont)
        
        # graph
        self.imagewidget                    = pg.PlotWidget()
        self.imagewidget.setYRange(0,1)
        
    
#==============================================================================
# Overall assembly
#==============================================================================
        self.WidgetGroup                   = QtGui.QGroupBox('')
        self.WidgetGroup.setLayout(QtGui.QGridLayout())
        self.WidgetGroup.layout().addWidget(self.Coms,                       0,0,1,2)
        self.WidgetGroup.layout().addWidget(self.ConnectButton,              0,2,1,2)
        self.WidgetGroup.layout().addWidget(self.laser,                      0,4,1,1)
        self.WidgetGroup.layout().addWidget(self.int_time,                   0,5,1,2)
        self.WidgetGroup.layout().addWidget(self.imagewidget,                1,0,10,12) 
        self.WidgetGroup.layout().addWidget(self.AdvanceButton,              11,0,2,2) 
        
        self.WidgetGroup.layout().addWidget(self.Output,                     11,8,2,4) 
                       
        self.setCentralWidget(self.WidgetGroup)
               
#==============================================================================
# Spectra Functions
#==============================================================================       
    def decide(self, spectra):
        Acetyl_score    = (spectra[185]*4) + (spectra[360]*3) + (spectra[310]*2)
        PTFE_score      = (spectra[133]*4) + (spectra[13]*3)  + (spectra[38]*2)
        PP_score        = (spectra[164]*4) + (spectra[256]*3) + (spectra[309]*2)
        PMMA_score      = (spectra[97]*4)  + (spectra[440]*3) + (spectra[201]*2)
        
        threshold = 3
        max_score = max([threshold,Acetyl_score,PTFE_score,PP_score,PMMA_score])
#        print(max_score)
        if Acetyl_score == max_score:   self.Output.setText("Acetyl detected")
        if PTFE_score   == max_score:   self.Output.setText("PTFE detected")
        if PP_score     == max_score:   self.Output.setText("PP detected")
        if PMMA_score   == max_score:   self.Output.setText("PMMA detected")
        if max_score    == threshold:   self.Output.setText("No signal detected")

    
    def normalise(self, _in):
#        assumes a 1 dimensional array (spectra) as input
        pfit, stats = Polynomial.fit(_in, self.wavenumber, 1, full=True, window=(min(_in), max(_in)),domain=(min(_in), max(_in)))
        grad, c = pfit
        for p in range(len(_in)):
            pass
#        todo adjust each point using grad and c
        m = np.max(_in,0)
        out = np.divide(_in,float(m))
        return out

#==============================================================================
# Spectrometer Functions
#==============================================================================       

    def find_usb_devices(self):
        device_ids = []
        be = usb.backend.libusb1.get_backend(find_library=lambda x: "%s" %self.usb_backend_location)
        for device in usb.core.find(find_all=True, backend=be):
            
            vid = int(device.idVendor)
            pid = int(device.idProduct)
            if vid in [0x24aa, 0x2457]:
                if vid == 0x24aa and pid in [ 0x1000, 0x2000, 0x4000 ]:
                    device_id = DeviceID(device=device)
                    device_ids.append(device_id)
                    print("DeviceListFID: discovered vid 0x%04x, pid 0x%04x (count %d)", vid, pid)
        return device_ids
    

    def get_spectra(self):
        try:
        # get spectrum with laser
            d = self.device.acquire_spectrum()
            spec_r = np.array(d.spectrum)
        # turn off laser
            self.device.settings.state.acquisition_laser_trigger_enable = False
        # get dark spectrum
            d = self.device.acquire_spectrum()
            spec_d = np.array(d.spectrum)
        # plot background subtracted data against wavenumber    # 
            # plt.plot(wvnm_r[0:-5],spec_r[0:-5]-spec_d[0:-5])
            # plt.plot(wvnm_r[0:-5],spec_r[0:-5])
            # plt.plot(wvnm_r[0:-5],spec_d[0:-5])
            self.display_spectra(spec_r[0:-5]-spec_d[0:-5])
            print('averaged:', d.averaged)
            print('integration: %s ms, averages: x%s, total: %s ms' %(self.device.settings.state.integration_time_ms, self.device.settings.state.scans_to_average, self.device.settings.state.integration_time_ms * self.device.settings.state.scans_to_average))
        except Exception as e:
            print('error:', e)        
        
   
    def display_spectra(self,spectra):
        norm = self.normalise(spectra)
        self.imagewidget.getPlotItem().clear()
        self.imagewidget.plot(x=self.wavenumber,y=norm)
        # self.decide(norm)
        
# =============================================================================
# Arduino Functions
# =============================================================================

    def connect(self, state):
        if state == "C":
            p = self.Coms.currentText()
            print(p)
            self.arduino = serial.Serial(port="%s" %p, baudrate=9600, timeout=0.5)
            time.sleep(2) #essential to have this delay!
            print('send: "hello"')
            self.arduino.write(str.encode("/hello;\n"))

            reply = self.arduino.readline().strip()
            print('reply:',reply)
            if reply == b'Hi there!':
                print('connection established')
                self.ConnectButton.setEnabled(False)
                self.Coms.setEnabled(False) 
            else:
                print('no connection')
                self.arduino.close()
                
    def laser_power(self, p):
        print('set laser power: %s %%' %p)
        self.arduino.write("/p.%s;" %p)
        
        
    def advance_stage(self):
        self.arduino.write("/advance;")
        print("move wheel one position")
          

    def closeEvent(self, event): #to do upon GUI being closed
        self.device.disconnect()
        self.laser_off()
        ut.dispose_resources(self.dev)

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
        return result

if __name__ == '__main__':
    app = 0
    app = QtGui.QApplication(sys.argv)
    gui = WPSpec()
    gui.show()
    app.exec_()
