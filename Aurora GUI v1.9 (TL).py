# -*- coding: utf-8 -*-
"""
Created on 05/02/2019

Adapted from LS GUI v1.1 - improvements for speed, added back ability to timelapse and multi-position

Improvements:
    ASI stage added
    No longer uses nested loops for imaging , uses a list of images and works through the list instead
    -Allows arbitary sorting of the image list (using pandas) to set the aquisition order
    -Hardware preparation is done in separate threads, as is image saving. Big speed improvement
    - Added z-stack ability but not YXZ positioning (uses manual)

TO DO - This version 
    - Add stage functionallity
        DONE-XYZ position storage
        -incorporate positons into the imaging loop
        DONE-stage escape function for sample loading
        DONE-safe limits for stage movement

FUTURE VERSION
    - Add imaging mode suitable for MUSICAL
    - Add option to crop images
        -A: use ROI, best option
        -B: crop image after acquire
    @author: Simon Lane
"""

#imports
import              sys, pickle, time, datetime, threading , Queue, os, math, glob, ctypes
import pyqtgraph    as pg
import pandas       as pd
import numpy        as np
from PyQt4          import QtGui, QtCore
from collections    import deque

#from skimage import io
import warnings
import skimage.external.tifffile as tf
from skimage.transform import resize
from skimage import io


#micromanger core python wrapper :/
import MMCorePy

#My Classes
from Connection_Widget import Connection_Widget
from Camera_TL      import Camera_TL
from Filter2        import Filter2  #filter uses signal to indicate when it has moved
from Arduino        import Arduino
from USB_HUB        import USB_HUB
from Maitai         import Maitai
from SolsTiS        import SolsTiS
from Cairn          import Cairn
from HWP            import HWP
from ASI            import ASI
#import TileScan     as TS

class LScontroller(QtGui.QMainWindow):
    def __init__(self):
        super(LScontroller, self).__init__()
#        self.setStyleSheet("QLabel {font: 10pt Comic Sans MS}")
        self.verbose = False #use this to toggle on/off the debugging printout statements
        self.mutex = QtCore.QMutex()
        self.working_folder = ""
        self.coordinate_mode = 1
        self.in_experiment = False
        self.filter_list = ["Empty", "610+-30, 650SP", "520+-20, 650SP","Pol. V","Pol. H","Empty (Pete has 650SP)"]
        self.NDfilter_list = ["2","7","11","17","26","34","100"]
        self.lightsource_list = ['LED', '405', '488', '561', '660', 'SolsTiS', 'MaiTai']
        self.image_order_list = ['Z-W-P','Z-P-W','W-Z-P','W-P-Z','P-Z-W','P-W-Z']
        self.binning_list = ['1x1','2x2','4x4']
        self.hardware_change_flags = {'Solstis':False,'Maitai':False,'Filter':False,'Zstage':False,'HWP':False,'Servo':False}
        self.hardware_flag_lock = threading.Lock()
        self.illumination = 0 #LED by default
        self.GUI_colour = QtGui.QColor(75,75,75)
        
        self.mmc = MMCorePy.CMMCore()

        
#        self.Camera         = Camera(self,  "Flash 4", self.mmc)
        self.Camera         = Camera_TL(self,  "TSICam", self.mmc)
        self.Filter         = Filter2(self, "Filter", "COM6")
        self.Arduino        = Arduino(self, "Arduino", self.mmc)
        self.USB_HUB        = USB_HUB(self, "Resonant Scanner", self.mmc)
        self.ASI            = ASI(self,     "ASI stage", "COM13")
        self.Maitai         = Maitai(self,  "Maitai")
        self.SolsTiS        = SolsTiS(self, "SolsTiS")
        self.Cairn          = Cairn(self,   "CairnIO", self.mmc)
        self.HWP            = HWP(self,     "HWP", "COM12")

        self.initUI()
        
        print(datetime.datetime.now())
        
        self.camera_widgets     = [self.GrabButton, self.LiveButton,self.setExposure,self.binningMenu,self.scanMode,self.DisplayGroup]
        self.filter_widgets     = [self.setFilter]
        self.visible_widgets    = [self.lightsource[1],self.lightsource[2],self.lightsource[3],self.lightsource[4],self.slider405,self.slider488,self.slider561,self.slider660,self.edit405,self.edit488,self.edit561,self.edit660,]
        self.maitai_widgets     = [self.lightsource[6],self.sliderMaitai,self.editMaitai]
        self.solstis_widgets    = [self.lightsource[5],self.sliderSolstis,self.editSolstis]
        self.arduino_widgets    = [self.IlluminationGroup]
        self.stage_widgets      = []
        self.global_stopwatch   = 0
        self.MTwavTracker       = -1 #for keeping track of MT wavelength during timelapse
        
        for item in self.camera_widgets: item.setEnabled(False)
        for item in self.filter_widgets: item.setEnabled(False)
        for item in self.arduino_widgets: item.setEnabled(False)
        for item in self.visible_widgets: item.setEnabled(False)
        for item in self.maitai_widgets: item.setEnabled(False)
        for item in self.solstis_widgets: item.setEnabled(False)
        for item in self.stage_widgets: item.setEnabled(False)

        self.unpickle_Table(self.Table_presets)
        self.Thread_to_Gui = Queue.Queue()
        self.Image_saveQ = Queue.Queue()
        self.Image_displayQ = Queue.Queue() #This queue is for the imaging thread to dump the most recent image for display. 
        self.Gui_to_Thread = deque(['','','',''], maxlen=4)

        self.Q_checker = QtCore.QTimer()
        self.Q_checker.setInterval(100)
        self.Q_checker.timeout.connect(self.check_Qs)
        self.Q_checker.start()
#        Q_checker also appends a timestamp to Gui_to_Thread[0] to assure the imaging thread that main thread is still running, 1Hz

  
        self.J_dx = 0
        self.J_dy = 0
        self.left_pressed = False
        self.last_scroll = time.time()
        self.drift_ref_img = []
        
        self.unpickle_positions()
        
#        self.connect_startup(6)#try to connect the first x devices automatically

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
               #Setup main Window
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def initUI(self):
        self.setScreenSize()
        self.setWindowTitle('Python Aurora Rayleigh V1.7')
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Background, self.GUI_colour)
        self.setPalette(palette)

        sizePolicyMin = QtGui.QSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Minimum)
        sizePolicyMin.setHorizontalStretch(0)
        sizePolicyMin.setVerticalStretch(0)
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
               #Setup Panes
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        self.DetectionGroup     = QtGui.QGroupBox('Detection')
        self.IlluminationGroup  = QtGui.QGroupBox('Illumination')
        self.ConnectionGroup    = QtGui.QGroupBox('Connections')
        self.DisplayGroup       = QtGui.QGroupBox('Display')
        self.BuilderGroup       = QtGui.QGroupBox('Experiment builder')
        self.FileGroup          = QtGui.QGroupBox('Save Options')
        self.TimingGroup        = QtGui.QGroupBox('Timing')
        self.ZSlice             = QtGui.QGroupBox('Z-stack')
        self.StageGroup         = QtGui.QGroupBox('XZ stage')
        self.LambdaGroup        = QtGui.QGroupBox('Lambda scan')
        self.PolGroup           = QtGui.QGroupBox('Polorisation scan')
        self.MusicalGroup       = QtGui.QGroupBox('Musical')
        self.InfoGroup          = QtGui.QGroupBox('Experiment')
        
#==============================================================================
# Detection Group
#==============================================================================
#create widgits
        self.GrabButton                     = QtGui.QPushButton('Grab')
        self.GrabButton.released.connect(self.Camera.grab_frame)

        self.LiveButton                     = QtGui.QPushButton('Live')
        self.LiveButton.setCheckable(True)
        self.LiveButton.clicked.connect(self.Camera.live_view)
        self.LiveButton.state               = 0

        self.CaptureLabel2                  = QtGui.QLabel('Filter: ')
        self.setFilter                      = QtGui.QComboBox()
        self.setFilter.addItems(self.filter_list)
        self.setFilter.currentIndexChanged.connect(self.detection_settings)
        self.CaptureLabel3                  = QtGui.QLabel('Exposure: ')
        self.setExposure                    = QtGui.QLineEdit('50')
        self.setExposure.setValidator(QtGui.QIntValidator(5,10000))
        self.setExposure.returnPressed.connect(self.detection_settings)
        self.binningLabel                   = QtGui.QLabel('Binning')
        self.binningMenu                    = QtGui.QComboBox()
        self.binningMenu.addItems(('1','2','4'))
        self.binningMenu.currentIndexChanged.connect(self.detection_settings)
        self.scanMode                       = QtGui.QCheckBox("Fast Readout Mode (higher noise)")

#add widgets to group
        self.DetectionGroup.setLayout(QtGui.QGridLayout())
        self.DetectionGroup.layout().addWidget(self.GrabButton,             0,0,1,2)
        self.DetectionGroup.layout().addWidget(self.LiveButton,             0,2,1,2)           
        self.DetectionGroup.layout().addWidget(self.CaptureLabel2,          1,0,1,2)
        self.DetectionGroup.layout().addWidget(self.setFilter,              1,2,1,2)
        self.DetectionGroup.layout().addWidget(self.CaptureLabel3,          2,0,1,2)
        self.DetectionGroup.layout().addWidget(self.setExposure,            2,2,1,2)
        self.DetectionGroup.layout().addWidget(self.binningLabel,           3,0,1,2)
        self.DetectionGroup.layout().addWidget(self.binningMenu,            3,2,1,2)
        self.DetectionGroup.layout().addWidget(self.scanMode,               4,0,1,2)
        

#==============================================================================
# Illumination Group
#==============================================================================
#create widgits
        self.IGLabel1b                  = QtGui.QLabel('%')
        self.IGLabel2b                  = QtGui.QLabel('%')
        self.IGLabel3b                  = QtGui.QLabel('%')
        self.IGLabel4b                  = QtGui.QLabel('%')
        self.IGLabel5b                  = QtGui.QLabel('%')
        self.IGLabel6b                  = QtGui.QLabel('nm')
        self.IGLabel7b                  = QtGui.QLabel('nm')
        self.Maitai_tuned               = QtGui.QLabel()
        self.Maitai_tuned.setPixmap(QtGui.QPixmap('light_r.png'))
        self.Solstis_tuned               = QtGui.QLabel()
        self.Solstis_tuned.setPixmap(QtGui.QPixmap('light_r.png'))
        self.IGLabel8                   = QtGui.QLabel('ND filter (%Tx)')
        self.IGLabel9                   = QtGui.QLabel('Pol (deg)')
        self.sliderLED                  = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.slider405                  = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.slider488                  = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.slider561                  = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.slider660                  = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.sliderSolstis              = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.sliderMaitai               = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.sliderND                   = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.sliderPol                  = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.editLED                    = QtGui.QLineEdit('50')
        self.edit405                    = QtGui.QLineEdit('50')
        self.edit488                    = QtGui.QLineEdit('50')
        self.edit561                    = QtGui.QLineEdit('50')
        self.edit660                    = QtGui.QLineEdit('50')
        self.editSolstis                = QtGui.QLineEdit('710')
        self.editSolstis.setValidator(QtGui.QIntValidator(700,1000))
        self.editMaitai                 = QtGui.QLineEdit('710')
        self.editMaitai.setValidator(QtGui.QIntValidator(710,990))
        self.labelND                    = QtGui.QLabel('100')
        self.editPol                    = QtGui.QLineEdit('0')
        self.editPol.setValidator(QtGui.QIntValidator(-180,180))
        
        self.editLED.setFixedWidth(60)
        self.edit405.setFixedWidth(60)
        self.edit488.setFixedWidth(60)
        self.edit561.setFixedWidth(60)
        self.edit660.setFixedWidth(60)
        self.editSolstis.setFixedWidth(60)
        self.editMaitai.setFixedWidth(60)
        self.editPol.setFixedWidth(60)
        
        self.sliders = [self.sliderLED, self.slider405, self.slider488, self.slider561, self.slider660, self.sliderSolstis, self.sliderMaitai, self.sliderND, self.sliderPol]
        self.edits = [self.editLED, self.edit405, self.edit488, self.edit561, self.edit660, self.editSolstis, self.editMaitai, self.editPol, self.editPol] # editPol is entered twice to create a spacer to keep indexing correct (there is no edit for ND)
                
        for slider in self.sliders[0:5]:
            slider.setMaximum(100)
            slider.setMinimum(0)
            slider.setValue(50)
            slider.setPageStep(5)
        self.sliders[5].setMaximum(1000)
        self.sliders[5].setMinimum(700)
        self.sliders[5].setValue(710)
        self.sliders[5].setPageStep(5)
        
        self.sliders[6].setMaximum(990)
        self.sliders[6].setMinimum(710)
        self.sliders[6].setValue(740)
        self.sliders[6].setPageStep(5)
        
        self.sliders[7].setMaximum(len(self.NDfilter_list)-1)
        self.sliders[7].setMinimum(0)
        self.sliders[7].setValue(len(self.NDfilter_list)-1)
        self.sliders[7].setPageStep(1)
        self.sliders[7].setTickPosition(QtGui.QSlider.TicksBelow)
        self.sliders[7].setTickInterval(1)
        
        self.sliders[8].setMaximum(180)
        self.sliders[8].setMinimum(-180)
        self.sliders[8].setValue(0)
        self.sliders[8].setPageStep(10)
        self.sliders[8].setTickPosition(QtGui.QSlider.TicksBelow)
        self.sliders[8].setTickInterval(45)
        
        self.NDminiGroup = QtGui.QWidget()
        self.NDminiGroup.setLayout(QtGui.QGridLayout())
        self.NDminiGroup.layout().addWidget(self.sliderND, 0,0,1,len(self.NDfilter_list))
        for i,l in enumerate(self.NDfilter_list):
            tickMark = QtGui.QLabel('%s' % l)
            self.NDminiGroup.layout().addWidget(tickMark, 1,i,1,1)
        self.NDminiGroup.layout().setHorizontalSpacing(15)
        
        
        self.PolminiGroup = QtGui.QWidget()
        self.PolminiGroup.setLayout(QtGui.QGridLayout())
        self.PolminiGroup.layout().addWidget(self.sliderPol, 0,0,1,10)
        for i in range(-180,225,45):
            tickMark = QtGui.QLabel('%s' % i)
            tick_x_pos = (i + 180)/45
            self.PolminiGroup.layout().addWidget(tickMark, 1,tick_x_pos,1,1)
        self.PolminiGroup.layout().setHorizontalSpacing(15)
        
            
        self.lightsource = [
                QtGui.QRadioButton('LED'),
                QtGui.QRadioButton('405'),
                QtGui.QRadioButton('488'),
                QtGui.QRadioButton('561'),
                QtGui.QRadioButton('660'),
                QtGui.QRadioButton('SolsTiS'),
                QtGui.QRadioButton('MaiTai')
                ]
        self.lightsource[0].setChecked(True)

        self.lightsource[0].released.connect(lambda: self.illumination_source(0))
        self.lightsource[1].released.connect(lambda: self.illumination_source(1))
        self.lightsource[2].released.connect(lambda: self.illumination_source(2))
        self.lightsource[3].released.connect(lambda: self.illumination_source(3))
        self.lightsource[4].released.connect(lambda: self.illumination_source(4))
        self.lightsource[5].released.connect(lambda: self.illumination_source(5))
        self.lightsource[6].released.connect(lambda: self.illumination_source(6))
    
        
        self.sliderLED.valueChanged.connect(    lambda: self.illumination_settings(0,self.sliderLED.value()))
        self.slider405.valueChanged.connect(    lambda: self.illumination_settings(1,self.slider405.value()))
        self.slider488.valueChanged.connect(    lambda: self.illumination_settings(2,self.slider488.value()))
        self.slider561.valueChanged.connect(    lambda: self.illumination_settings(3,self.slider561.value()))
        self.slider660.valueChanged.connect(    lambda: self.illumination_settings(4,self.slider660.value()))
        self.sliderSolstis.valueChanged.connect(lambda: self.illumination_settings(5,self.sliderSolstis.value()))
        self.sliderMaitai.valueChanged.connect( lambda: self.illumination_settings(6,self.sliderMaitai.value()))
        self.sliderND.valueChanged.connect(     lambda: self.illumination_settings(7,self.sliderND.value()))
        self.sliderPol.valueChanged.connect(    lambda: self.illumination_settings(8,self.sliderPol.value()))
        self.editLED.returnPressed.connect(     lambda: self.illumination_settings(0,self.editLED.text()))
        self.edit405.returnPressed.connect(     lambda: self.illumination_settings(1,self.edit405.text()))
        self.edit488.returnPressed.connect(     lambda: self.illumination_settings(2,self.edit488.text()))
        self.edit561.returnPressed.connect(     lambda: self.illumination_settings(3,self.edit561.text()))
        self.edit660.returnPressed.connect(     lambda: self.illumination_settings(4,self.edit660.text()))
        self.editSolstis.returnPressed.connect( lambda: self.illumination_settings(5,self.editSolstis.text()))
        self.editMaitai.returnPressed.connect(  lambda: self.illumination_settings(6,self.editMaitai.text()))
        self.editPol.returnPressed.connect(     lambda: self.illumination_settings(8,self.editPol.text()))

#add widgets to group
        self.IlluminationGroup.setLayout(QtGui.QGridLayout())
        self.IlluminationGroup.layout().addWidget(self.lightsource[0],          0,0,1,2)
        self.IlluminationGroup.layout().addWidget(self.lightsource[1],          1,0,1,2)
        self.IlluminationGroup.layout().addWidget(self.lightsource[2],          2,0,1,2)
        self.IlluminationGroup.layout().addWidget(self.lightsource[3],          3,0,1,2)
        self.IlluminationGroup.layout().addWidget(self.lightsource[4],          4,0,1,2)
        self.IlluminationGroup.layout().addWidget(self.lightsource[5],          5,0,1,2)
        self.IlluminationGroup.layout().addWidget(self.lightsource[6],          6,0,1,2)
        self.IlluminationGroup.layout().addWidget(self.IGLabel8,                7,0,1,2)
        self.IlluminationGroup.layout().addWidget(self.IGLabel9,                9,0,1,1)
        
        self.IlluminationGroup.layout().addWidget(self.sliderLED,               0,2,1,3)
        self.IlluminationGroup.layout().addWidget(self.slider405,               1,2,1,3)
        self.IlluminationGroup.layout().addWidget(self.slider488,               2,2,1,3)
        self.IlluminationGroup.layout().addWidget(self.slider561,               3,2,1,3)
        self.IlluminationGroup.layout().addWidget(self.slider660,               4,2,1,3)
        self.IlluminationGroup.layout().addWidget(self.sliderSolstis,           5,2,1,3)
        self.IlluminationGroup.layout().addWidget(self.sliderMaitai,            6,2,1,3)
        self.IlluminationGroup.layout().addWidget(self.NDminiGroup,             8,1,1,5)  
        self.IlluminationGroup.layout().addWidget(self.PolminiGroup,            10,1,1,5)

        self.IlluminationGroup.layout().addWidget(self.editLED,                 0,5,1,1)
        self.IlluminationGroup.layout().addWidget(self.edit405,                 1,5,1,1)
        self.IlluminationGroup.layout().addWidget(self.edit488,                 2,5,1,1)
        self.IlluminationGroup.layout().addWidget(self.edit561,                 3,5,1,1)
        self.IlluminationGroup.layout().addWidget(self.edit660,                 4,5,1,1)
        self.IlluminationGroup.layout().addWidget(self.editSolstis,             5,5,1,1)
        self.IlluminationGroup.layout().addWidget(self.editMaitai,              6,5,1,1)
        self.IlluminationGroup.layout().addWidget(self.editPol,                 9,2,1,1)
        
        self.IlluminationGroup.layout().addWidget(self.IGLabel1b,               0,6,1,1)
        self.IlluminationGroup.layout().addWidget(self.IGLabel2b,               1,6,1,1)
        self.IlluminationGroup.layout().addWidget(self.IGLabel3b,               2,6,1,1)
        self.IlluminationGroup.layout().addWidget(self.IGLabel4b,               3,6,1,1)
        self.IlluminationGroup.layout().addWidget(self.IGLabel5b,               4,6,1,1)
        self.IlluminationGroup.layout().addWidget(self.IGLabel6b,               5,6,1,1)
        self.IlluminationGroup.layout().addWidget(self.Solstis_tuned,           5,6,1,1)
        self.IlluminationGroup.layout().addWidget(self.IGLabel7b,               6,6,1,1)
        self.IlluminationGroup.layout().addWidget(self.Maitai_tuned,            6,6,1,1)
        
#==============================================================================
# Connection Group
#==============================================================================
        self.ConnectAll     = QtGui.QPushButton("Connect All")
        self.ConnectAll.released.connect(self.connectAll)
        self.ConnCamera     = Connection_Widget(self,'Camera', self.Camera)
        self.ConnUSB_HUB    = Connection_Widget(self,'Resonant scanner', self.USB_HUB)
        self.ConnASI        = Connection_Widget(self,'ASI stage', self.ASI)
        self.ConnFilter     = Connection_Widget(self,'Filter Wheel', self.Filter)
        self.ConnArduino    = Connection_Widget(self,'Arduino', self.Arduino)
        self.ConnHWP        = Connection_Widget(self,'Half wave plate', self.HWP)
#        first 6 connections will try to connect automatically on startup
        self.ConnCairn      = Connection_Widget(self,'Visible lasers', self.Cairn)
        self.ConnMaitai     = Connection_Widget(self,'Maitai laser', self.Maitai)
        self.ConnSolsTiS    = Connection_Widget(self,'SolsTiS laser', self.SolsTiS)
        
        
        
        self.ConnectionGroup.setLayout(QtGui.QGridLayout())
#        self.ConnectionGroup.setFixedHeight(200)
        self.ConnectionGroup.layout().addWidget(self.ConnectAll,            5,0,1,2)
        self.ConnectionGroup.layout().addWidget(self.ConnCamera.row,        0,0,1,3)
        self.ConnectionGroup.layout().addWidget(self.ConnArduino.row,       1,0,1,3)
        self.ConnectionGroup.layout().addWidget(self.ConnFilter.row,        2,0,1,3)
        self.ConnectionGroup.layout().addWidget(self.ConnUSB_HUB.row,       4,0,1,3)
        self.ConnectionGroup.layout().addWidget(self.ConnASI.row,           3,0,1,3)
        self.ConnectionGroup.layout().addWidget(self.ConnHWP.row,           3,2,1,3)
        self.ConnectionGroup.layout().addWidget(self.ConnMaitai.row,        0,2,1,3)
        self.ConnectionGroup.layout().addWidget(self.ConnSolsTiS.row,       1,2,1,3)
        self.ConnectionGroup.layout().addWidget(self.ConnCairn.row,         2,2,1,3)
        
#==============================================================================
# Display Group
#==============================================================================

        self.saveImageButton            = QtGui.QPushButton("Save image")
        self.saveImageButton.released.connect(self.saveSingleImage)
        self.imagewidget                = pg.ImageView(view=pg.PlotItem())

        self.view_modes                 = [QtGui.QRadioButton('Auto'),QtGui.QRadioButton('Manual')]
        self.view_colour_modes          = [QtGui.QRadioButton('Greyscale'),QtGui.QRadioButton('Colour')]
        self.view_modes[0].setChecked(True)
        self.view_colour_modes[0].setChecked(True)
        self.view_modes_group           = QtGui.QButtonGroup()
        self.view_colour_modes_group    = QtGui.QButtonGroup()
        for rb in range(2):
            self.view_modes[rb].released.connect(self.Camera.displayMode)
            self.view_modes_group.addButton(self.view_modes[rb],rb)
            self.view_colour_modes[rb].released.connect(self.Camera.displayMode)
            self.view_colour_modes_group.addButton(self.view_colour_modes[rb],rb)

#        self.imagewidget.ui.roiBtn.hide()
#        self.imagewidget.ui.menuBtn.hide()

        self.DisplayGroup.setLayout(QtGui.QGridLayout())
        self.DisplayGroup.layout().addWidget(self.view_modes[0],              0,0,1,2)
        self.DisplayGroup.layout().addWidget(self.view_modes[1],              0,2,1,2)
        self.DisplayGroup.layout().addWidget(self.view_colour_modes[0],       1,0,1,2)
        self.DisplayGroup.layout().addWidget(self.view_colour_modes[1],       1,2,1,2)
        self.DisplayGroup.layout().addWidget(self.saveImageButton,            0,6,1,2)

        self.DisplayGroup.layout().addWidget(self.imagewidget,                2,0,10,10)


#==============================================================================
# Builder Group
#==============================================================================

#Create Models
        headings = [self.tr("In use"),self.tr("Name"),self.tr("Ill."),
                    self.tr("ND"),self.tr("Power"),self.tr("Wav."),self.tr("Pol."),
                    self.tr("Exp."),self.tr("Bin"),self.tr("Filter"),
                    self.tr("Z"),self.tr("Lam."), self.tr("Pol"), self.tr("Mus.")]
        
        column_spacing = [70,110,90,80,80,80,80,80,80,160,60,60,60,60]
# sub-classed QTableWidget to accept drops
        self.Table_presets = QtGui.QTableWidget() 

        self.Table_presets.setDragDropOverwriteMode(False)
        self.Table_presets.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
 
        self.Table_presets.objectName = 'Stored'
        self.Table_presets.setColumnCount(14)
        self.Table_presets.setHorizontalHeaderLabels(headings)
        self.Table_presets.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)

        for column in range(len(headings)):
            self.Table_presets.setColumnWidth(column, column_spacing[column])
        self.Table_presets.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.Table_presets.setFixedWidth(1215)

# other widgets
        self.UpButton                       = QtGui.QPushButton('^')
        self.UpButton.setFixedWidth(80)
        self.UpButton.released.connect(lambda: self.move_set(-1))
        
        self.DownButton                     = QtGui.QPushButton('v')
        self.DownButton.setFixedWidth(80)
        self.DownButton.released.connect(lambda: self.move_set(1))
        
        self.NewSetButton                   = QtGui.QPushButton('New')
        self.NewSetButton.setSizePolicy(sizePolicyMin)
        self.NewSetButton.released.connect(lambda: self.add_set())
        
        self.PullSetButton                  = QtGui.QPushButton('Pull')
        self.PullSetButton.setSizePolicy(sizePolicyMin)
        self.PullSetButton.released.connect(lambda: self.pull_set())
        
        self.PushSetButton                  = QtGui.QPushButton('Push')
        self.PushSetButton.setSizePolicy(sizePolicyMin)
        self.PushSetButton.released.connect(lambda: self.push_set())
        
        self.DelSetButton                   = QtGui.QPushButton('Delete')
        self.DelSetButton.setSizePolicy(sizePolicyMin)
        self.DelSetButton.released.connect(lambda: self.del_set())
        
        self.labelILO                       = QtGui.QLabel('Image loop order')
        self.ImageLoopOrder                 = QtGui.QComboBox()
        self.ImageLoopOrder.addItems(self.image_order_list)

        
        self.BuilderGroup.setLayout(QtGui.QGridLayout())
        
        self.BuilderGroup.layout().addWidget(self.Table_presets,        0,2,20,8)
        self.BuilderGroup.layout().addWidget(self.UpButton,             1,0,1,1)
        self.BuilderGroup.layout().addWidget(self.DownButton,           1,1,1,1)
        self.BuilderGroup.layout().addWidget(self.NewSetButton,         2,0,1,2)
        self.BuilderGroup.layout().addWidget(self.DelSetButton,         3,0,1,2)
        self.BuilderGroup.layout().addWidget(self.PushSetButton,        4,0,1,2)
        self.BuilderGroup.layout().addWidget(self.PullSetButton,        5,0,1,2)
        self.BuilderGroup.layout().addWidget(self.labelILO,             9,0,1,2)
        self.BuilderGroup.layout().addWidget(self.ImageLoopOrder,       10,0,1,2)

#==============================================================================
# File Group
#==============================================================================
#Fileing Widgets

        self.FileUserLabel                  = QtGui.QLabel('User:')
        self.FileUserList                   = QtGui.QComboBox()
#generate user list
        userList =  glob.glob('D:\\*')
        for item in userList:
            if os.path.isdir(item) and len(item) < 15 and item.find("$")==-1: #NOTE, folder names greater than 14 chars will not show!
                userName = item.split('\\')[-1]
                self.FileUserList.addItem(userName)
        self.FileExptNameLabel              = QtGui.QLabel('Expt. Name:')
        self.FileExptName                   = QtGui.QLineEdit('')
        self.FileExptName.returnPressed.connect(self.update_expt_name)
        self.FileExptName.textChanged.connect(self.update_expt_name)
        self.FileUserList.currentIndexChanged['QString'].connect(self.update_expt_name)
        self.FileAddress                    = QtGui.QLineEdit('')
        self.FileAddress.setReadOnly(True)
                
        self.cropCheckbox                   = QtGui.QCheckBox("Crop before save")
        self.eightCheckbox                  = QtGui.QCheckBox("Reduce to 8-bit")
        
# Add widgets to group
        self.FileGroup.setLayout(QtGui.QGridLayout())
        self.FileGroup.layout().addWidget(self.FileUserLabel,        0,0)
        self.FileGroup.layout().addWidget(self.FileUserList,         0,1)
        self.FileGroup.layout().addWidget(self.FileExptNameLabel,    1,0,1,1)
        self.FileGroup.layout().addWidget(self.FileExptName,         1,1,1,3)
        self.FileGroup.layout().addWidget(self.FileAddress,          2,0,1,4)
        self.FileGroup.layout().addWidget(self.cropCheckbox,         3,0,1,2)
        self.FileGroup.layout().addWidget(self.eightCheckbox,        3,2,1,2)
        
#==============================================================================
# Timing Group
#==============================================================================
#timing widgets
        self.TimingLabel1                   = QtGui.QLabel('No. Loops:')
        self.TimingLoops                    = QtGui.QLineEdit('1')
        self.TimingLabel2                   = QtGui.QLabel('Interval (s):')
        self.TimingInterval                 = QtGui.QLineEdit('300')
        self.TimingLabel3                   = QtGui.QLabel('Duration (hh:mm:ss):')
        self.TimingDuration                 = QtGui.QLineEdit('15 : 00 : 00')
        self.TimingDuration.setReadOnly(True)

        self.TimingLoops.setValidator(QtGui.QIntValidator(1,10000))
        self.TimingInterval.setValidator(QtGui.QIntValidator(1,10000))

        self.TimingLoops.returnPressed.connect(self.update_duration)
        self.TimingLoops.textChanged.connect(self.update_duration)
        self.TimingInterval.returnPressed.connect(self.update_duration)
        self.TimingInterval.textChanged.connect(self.update_duration)
# Add widgets to group

        self.TimingGroup.setLayout(QtGui.QGridLayout())
        self.TimingGroup.layout().addWidget(self.TimingLabel1,       0,0)
        self.TimingGroup.layout().addWidget(self.TimingLoops,        0,1)
        self.TimingGroup.layout().addWidget(self.TimingLabel2,       1,0)
        self.TimingGroup.layout().addWidget(self.TimingInterval,     1,1)
        self.TimingGroup.layout().addWidget(self.TimingLabel3,       2,0)
        self.TimingGroup.layout().addWidget(self.TimingDuration,     2,1)
        

#==============================================================================
# Z slice Group
#==============================================================================
        self.ZSlice.setLayout(QtGui.QGridLayout())

        self.ZLabel1                    = QtGui.QLabel('Slices:')
        self.ZSlices                    = QtGui.QLineEdit('11')
        self.ZLabel2                    = QtGui.QLabel('Separation:')
        self.ZSeparation                = QtGui.QLineEdit('10')
        self.ZLabel3                    = QtGui.QLabel('Span:')
        self.ZSpan                      = QtGui.QLineEdit('100')
        self.ZSlices.setValidator(QtGui.QIntValidator(1,1000))
        self.ZSeparation.setValidator(QtGui.QIntValidator(1,100))
        self.ZSpan.setValidator(QtGui.QIntValidator(0,1000))
        self.ZDemo                      = QtGui.QLabel('')
        
        
        self.ZSlices.setFixedWidth(100)
        self.ZSeparation.setFixedWidth(100)
        self.ZSpan.setFixedWidth(100)

        self.ZSlices.returnPressed.connect(lambda: self.adjustZStack(0))
        self.ZSeparation.returnPressed.connect(lambda: self.adjustZStack(1))
        self.ZSpan.returnPressed.connect(lambda: self.adjustZStack(2))

# Add widgets
        self.ZSlice.layout().addWidget(self.ZLabel1,            0,0,1,1)
        self.ZSlice.layout().addWidget(self.ZSlices,            0,1,1,2)
        self.ZSlice.layout().addWidget(self.ZLabel2,            1,0,1,1)
        self.ZSlice.layout().addWidget(self.ZSeparation,        1,1,1,2)
        self.ZSlice.layout().addWidget(self.ZLabel3,            2,0,1,1)
        self.ZSlice.layout().addWidget(self.ZSpan,              2,1,1,2)
        self.ZSlice.layout().addWidget(self.ZDemo,              3,0,1,3)
        

#==============================================================================
# Lambda scan Group
#==============================================================================
        self.LambdaGroup.setLayout(QtGui.QGridLayout())

        self.LambdaLabel1                    = QtGui.QLabel('Start:')
        self.LambdaStart                     = QtGui.QLineEdit('700')
        self.LambdaLabel2                    = QtGui.QLabel('End:')
        self.LambdaEnd                       = QtGui.QLineEdit('800')
        self.LambdaLabel3                    = QtGui.QLabel('Step:')
        self.LambdaStep                      = QtGui.QLineEdit('10')
        self.LambdaStart.setValidator(QtGui.QIntValidator(700,1000))
        self.LambdaEnd.setValidator(QtGui.QIntValidator(700,1000))
        self.LambdaStep.setValidator(QtGui.QIntValidator(0,200))
        self.LambdaDemo                     = QtGui.QLabel('[700,710,720, ... ,780,790,800]')
        
        self.LambdaStart.returnPressed.connect(self.adjustLambda)
        self.LambdaEnd.returnPressed.connect(self.adjustLambda)
        self.LambdaStep.returnPressed.connect(self.adjustLambda)
    
        
        self.LambdaStart.setFixedWidth(100)
        self.LambdaEnd.setFixedWidth(100)
        self.LambdaStep.setFixedWidth(100)

        self.LambdaCustom                    = QtGui.QLineEdit('')
        self.LambdaCheckbox                  = QtGui.QCheckBox('Custom')
        self.LambdaLabel4                    = QtGui.QLabel('(comma separated values)')
        
# Add widgets
        self.LambdaGroup.layout().addWidget(self.LambdaLabel1,       0,0,1,1)
        self.LambdaGroup.layout().addWidget(self.LambdaStart,        0,1,1,2)
        self.LambdaGroup.layout().addWidget(self.LambdaLabel2,       1,0,1,1)
        self.LambdaGroup.layout().addWidget(self.LambdaEnd,          1,1,1,2)
        self.LambdaGroup.layout().addWidget(self.LambdaLabel3,       2,0,1,1)
        self.LambdaGroup.layout().addWidget(self.LambdaStep,         2,1,1,2)
        self.LambdaGroup.layout().addWidget(self.LambdaDemo,         3,0,1,3)
        self.LambdaGroup.layout().addWidget(self.LambdaCheckbox,     4,0,1,1)
        self.LambdaGroup.layout().addWidget(self.LambdaCustom,       5,0,1,3)
        self.LambdaGroup.layout().addWidget(self.LambdaLabel4,       4,1,1,2)


#==============================================================================
# Polorisation Group
#==============================================================================
        self.PolGroup.setLayout(QtGui.QGridLayout())

        self.PolLabel1                    = QtGui.QLabel('Start:')
        self.PolStart                     = QtGui.QLineEdit('0')
        self.PolLabel2                    = QtGui.QLabel('End:')
        self.PolEnd                       = QtGui.QLineEdit('90')
        self.PolLabel3                    = QtGui.QLabel('Step:')
        self.PolStep                      = QtGui.QLineEdit('90')
        self.PolStart.setValidator(QtGui.QIntValidator(-180,180))
        self.PolEnd.setValidator(QtGui.QIntValidator(-180,180))
        self.PolStep.setValidator(QtGui.QIntValidator(1,180))
        self.PolDemo                      = QtGui.QLabel('[0,90]')
        
        self.PolStart.returnPressed.connect(self.adjustPol)
        self.PolEnd.returnPressed.connect(self.adjustPol)
        self.PolStep.returnPressed.connect(self.adjustPol)
        
        self.PolStart.setFixedWidth(100)
        self.PolEnd.setFixedWidth(100)
        self.PolStep.setFixedWidth(100)

# Add widgets
        self.PolGroup.layout().addWidget(self.PolLabel1,       0,0,1,1)
        self.PolGroup.layout().addWidget(self.PolStart,        0,1,1,2)
        self.PolGroup.layout().addWidget(self.PolLabel2,       1,0,1,1)
        self.PolGroup.layout().addWidget(self.PolEnd,          1,1,1,2)
        self.PolGroup.layout().addWidget(self.PolLabel3,       2,0,1,1)
        self.PolGroup.layout().addWidget(self.PolStep,         2,1,1,2)
        self.PolGroup.layout().addWidget(self.PolDemo,         3,0,1,3)

#==============================================================================
# Musical Group
#==============================================================================
        self.MusicalGroup.setLayout(QtGui.QGridLayout())

        self.MusicalLabel1                    = QtGui.QLabel('Frames:')
        self.MusicalNo                        = QtGui.QLineEdit('50')
        self.MusicalNo.setValidator(QtGui.QIntValidator(1,1000))
        
# Add widgets
        self.MusicalGroup.layout().addWidget(self.MusicalLabel1,       0,0,1,1)
        self.MusicalGroup.layout().addWidget(self.MusicalNo,           0,1,1,1)
#==============================================================================
# Stage Group
#==============================================================================
        self.xz_but_home                = QtGui.QPushButton('Home Z  0mm')
        self.xz_but_start               = QtGui.QPushButton('Home Z -2mm') 
        self.xz_but_escape              = QtGui.QPushButton('Escape')
        self.xz_but_home.released.connect(  lambda: self.ASI.preset_position(1))
        self.xz_but_start.released.connect( lambda: self.ASI.preset_position(2))
        self.xz_but_escape.released.connect(lambda: self.ASI.escape())
        
        self.pos_labelX                 = QtGui.QLabel(' X:')
        self.pos_labelY                 = QtGui.QLabel(' Y:')
        self.pos_labelXZ                = QtGui.QLabel('XZ:')
# position storing widgets        
        self.add_pos_but                 = QtGui.QPushButton('Add position')
        self.add_pos_but.released.connect(self.add_position)
        
        self.xz_but_clear              = QtGui.QPushButton('Clear All')
        self.xz_but_clear.released.connect(self.clear_all_positions)
        
        pos_headings = [self.tr(""),self.tr("X"),self.tr("Y"),self.tr("XZ"),self.tr('Del.'),self.tr("Go To")]
        pos_column_spacing = [40,100,100,100,80,80]
        self.Table_positions = QtGui.QTableWidget()
        self.Table_positions.objectName = 'PosStore'
        self.Table_positions.setColumnCount(6)
        self.Table_positions.setHorizontalHeaderLabels(pos_headings)
        self.Table_positions.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        for column in range(6):
            self.Table_positions.setColumnWidth(column, pos_column_spacing[column])
        self.Table_positions.setFixedWidth(520)
        self.Table_positions.cellDoubleClicked.connect(self.pos_table_click)

        self.tile_scan_button                = QtGui.QPushButton('Tile Scan')
        self.tile_scan_button.released.connect(self.stage_scan)



# Add widgets        
        self.StageGroup.setLayout(QtGui.QGridLayout())
        self.StageGroup.layout().addWidget(self.xz_but_home,            0,0,1,1)
        self.StageGroup.layout().addWidget(self.xz_but_start,           1,0,1,1)
        self.StageGroup.layout().addWidget(self.xz_but_escape,          2,0,1,1)
     
        self.StageGroup.layout().addWidget(self.pos_labelX,             3,0,1,1)
        self.StageGroup.layout().addWidget(self.pos_labelY,             4,0,1,1)
        self.StageGroup.layout().addWidget(self.pos_labelXZ,            5,0,1,1)

        self.StageGroup.layout().addWidget(self.add_pos_but,            6,0,1,1)
        self.StageGroup.layout().addWidget(self.xz_but_clear,           8,0,1,1)
        self.StageGroup.layout().addWidget(self.Table_positions,        0,1,9,15)
        self.StageGroup.layout().addWidget(self.tile_scan_button,       0,16,1,1)

#==============================================================================
# Experiment Group
#==============================================================================
        self.Information_text_window = QtGui.QTextEdit()
        self.Information_text_window.setReadOnly(True)
        self.Information_text_window.setStyleSheet("background-color: rgb(75,75,75);")
        self.Alerts_text_window      = QtGui.QTextEdit()
        self.Alerts_text_window.setReadOnly(True)
        self.Alerts_text_window.setStyleSheet("background-color: rgb(75,75,75);")
        self.Information_text_window.insertHtml("<br><br><br><br><br><br><br><br><br>")

        self.Expt_Start_button             = QtGui.QPushButton('Start Experiment')
        self.Expt_Start_button.released.connect(self.Imaging)


        self.InfoGroup.setLayout(QtGui.QGridLayout())
# Add widgets
        self.InfoGroup.layout().addWidget(self.Expt_Start_button,           0,0,1,1)

        self.InfoGroup.layout().addWidget(self.Information_text_window,     1,0,5,4)
        self.InfoGroup.layout().addWidget(self.Alerts_text_window,          0,2,7,5)

#==============================================================================
# Overall assembly
#==============================================================================
        OverallLayout = QtGui.QGridLayout()
#        using a 20x20 grid for flexible arrangement of the panels
#first column
        OverallLayout.addWidget(self.DetectionGroup,                0,0,4,2)
        OverallLayout.addWidget(self.IlluminationGroup,             4,0,4,2)
        OverallLayout.addWidget(self.ConnectionGroup,               8,0,4,2)
        OverallLayout.addWidget(self.FileGroup,                     12,0,2,2)
        OverallLayout.addWidget(self.TimingGroup,                   14,0,2,2)

#second column
        OverallLayout.addWidget(self.DisplayGroup,                  0,2,16,7)

#third column
        OverallLayout.addWidget(self.BuilderGroup,                  0,12,6,7)
        OverallLayout.addWidget(self.ZSlice,                        6,12,2,3)
        OverallLayout.addWidget(self.LambdaGroup,                   6,15,2,2)
        OverallLayout.addWidget(self.PolGroup,                      6,17,1,2)
        OverallLayout.addWidget(self.MusicalGroup,                  7,17,1,2)
        OverallLayout.addWidget(self.StageGroup,                    8,12,4,7)
        OverallLayout.addWidget(self.InfoGroup,                     12,12,4,7)

        self.MainArea = QtGui.QFrame()
        self.MainArea.setStyleSheet("""
               font: 10pt Modum;
        """)
        self.MainArea.setLineWidth(0)
        self.MainArea.setLayout(OverallLayout)
        self.setCentralWidget(self.MainArea)

# =============================================================================
# PRE IMAGING SETUP
# =============================================================================

    def Imaging(self, command=None):
        if self.Expt_Start_button.text() == 'Stop Experiment':
            print 'stop button press'
            self.Expt_Start_button.setText('Stopping...')
            self.Gui_to_Thread[-1] = 'stop'
            self.ImagingLoopThread.join()
            
            
        if self.Expt_Start_button.text() == 'Start Experiment':
#                build full experimental imaging set
            self.pickle_Table() #save all settings and positions in case of crash whilst imaging
            self.pickle_positions()
            imaging_set = self.build_imaging_set() 
            timing_interval = int(self.TimingInterval.text())
            imaging_loops = int(self.TimingLoops.text())
            crop = self.cropCheckbox.isChecked()
            eight = self.eightCheckbox.isChecked()

#                test for disk space (in Gb)
            req_space = round((imaging_set[imaging_set.Binning == 0].shape[0]*0.008193) + 
                              (imaging_set[imaging_set.Binning == 1].shape[0]*0.002049) + 
                              (imaging_set[imaging_set.Binning == 2].shape[0]*0.000513),1)*imaging_loops*imaging_set['Location'].max()
            free_space = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p('D:'), None, None, ctypes.pointer(free_space))
            free_space = round(free_space.value/ (1024.0*1024.0*1024.0),1)

            if self.scanMode.isChecked(): readout_mode = 'fast'
            else: readout_mode = 'normal'
            can_image = True
#                CHECKLIST
            if free_space-1 < req_space:    self.information("Imaging not possible: %sGb required, %sGb available" %(req_space,free_space), 0)
            
            if self.Camera.live_imaging: #if camera is live imaging, then stop it
                self.Camera.live_view()
            if self.in_experiment:
                can_image = False
                self.information("Imaging not possible: previous experiment still running", 0)
#                    if a thread is still active from a previous experiment, then don't start a new one
            if not self.Camera.flag_CONNECTED:
                can_image = False # check camera is connected
                self.information("Imaging not possible: No camera connection", 0)
            if not self.HWP.flag_CONNECTED:
                can_image = False # check HWP is connected
                self.information("Imaging not possible: No HWP connection", 0)
            if imaging_set.shape[0] < 1:
                can_image = False # check there is at least one set of imaging parameters to capture
                self.information("Imaging not possible: No channels selected", 0)
            if not self.Filter.flag_CONNECTED:
                can_image = False
                self.information("Imaging not possible: No Filter wheel connection", 0)
            if not self.Arduino.flag_CONNECTED:
                can_image = False
                self.information("Imaging not possible: No Teensy connection", 0)                
            if imaging_set['Znumber'].max() > 0 and not self.USB_HUB.flag_CONNECTED:
                can_image = False # check that xz stage is available if there is a z stack
                self.information("Imaging not possible: XZ control required", 0) 
                
            if imaging_set[imaging_set.Illumination == 5].shape[0] > 0 and not self.SolsTiS.flag_CONNECTED:
                can_image = False # check that xz stage is available if there is a z stack
                self.information("Imaging not possible: SolsTiS connection required", 0)
            if imaging_set[imaging_set.Illumination == 6].shape[0] > 0 and not self.Maitai.flag_CONNECTED:
                can_image = False # check that xz stage is available if there is a z stack
                self.information("Imaging not possible: MaiTai connection required", 0)
                  
#                WARNINGS
            if not self.USB_HUB.flag_CONNECTED: self.information("WARNING: No scanning galvo connection", 2)
            if free_space < 100: self.information("WARNING: low disk space (%sGb remaining)" %free_space, 2)
            if not can_image:
                print('experiment not started')
                return # block further progression if checklist not satisfied

            print('starting experiment...')
            self.information("Starting Experiment: %sGb required, %sGb available" %(req_space,free_space), 1)
            self.GUI_access(False)
            self.ASI.set_speed()
#                self.ASI.joystick(False)
            self.Expt_Start_button.setText('Stop Experiment')

            self.update_expt_name()#                update save location to make sure it is unique
            self.working_folder = self.FileAddress.text()
            os.mkdir(self.working_folder)#                create file store location
            
            if self.SolsTiS.flag_CONNECTED: self.SolsTiS.timer.stop()  #These timers keep track of the lasers tuning status for the main GUI
            if self.Maitai.flag_CONNECTED: self.Maitai.timer.stop()
#            print 'starting imaging loop'
            self.ImagingLoopThread = threading.Thread(target=self.Imaging_thread, name="imaging",
                args=(imaging_set, self.working_folder, readout_mode, timing_interval, imaging_loops, crop, eight))
            
            self.in_experiment = True
            
            self.Gui_to_Thread[-1]=''

            self.Camera.clear_camera_buffer()
            self.Image_saveQ.empty()
            self.ImagingLoopThread.start()

        if command == 'stop': #experiment completed, command from end of imaging thread
            print('stopping experiment...')
            
            self.ASI.set_speed(X=1.36, Y=1.36, Z=1.8)
#            self.ASI.joystick(true)
            self.Expt_Start_button.setText('Start Experiment')
            
            self.Arduino.closeShutter()
            self.USB_HUB.galvo_off()
            if self.SolsTiS.flag_CONNECTED: self.SolsTiS.timer.start(500)
            if self.Maitai.flag_CONNECTED:  self.Maitai.timer.start(500)
            self.GUI_access(True)
            
                
    def servo_timer_function(self, from_, to_): #To be run in a thread!
        self.hardware_flag_lock.acquire()
        self.hardware_change_flags.update({'Servo':True})
        self.hardware_flag_lock.release()
        time_to_move = ((abs(from_-to_)* self.Arduino.spacing * self.Arduino.speed) +0.02) #plus 20ms for 1 duty cycle
        time.sleep(time_to_move) #set a timer (ms) to resest the flag when servo move (is anticipated to be) complete, no way to actually know withouth modding the servo
        self.hardware_flag_lock.acquire()
        self.hardware_change_flags.update({'Servo':False})
        self.hardware_flag_lock.release()

    def prep_hardware(self, row_number, imaging_set, prev_row_number=None):
        
#        print 'prepping hardware'
#        reset the hardware flags
        self.hardware_flag_lock.acquire()
        self.hardware_change_flags = {'Solstis':False,'Maitai':False,'Filter':False,'Stage':False,'HWP':False,'Servo':False}
        self.hardware_flag_lock.release()
        if prev_row_number == None:                #If the previous position of hardware is unknown, then assume everything moves
            prev_row={'Solstis':-1,'Maitai':-1,'Filter':-1,'Xlocation':-99999,'Ylocation':-99999,'Zposition':-1,'Polarisation':999,'Illumination':-1,'ND':-5,'Wavelength':-1}
        else:
            prev_row = imaging_set.iloc[prev_row_number]
        row = imaging_set.iloc[row_number]

        if row['Polarisation'] != prev_row['Polarisation']:
            self.HWP.set_position(row['Polarisation'])
            self.hardware_flag_lock.acquire()
            self.hardware_change_flags.update({'HWP':True})
            self.hardware_flag_lock.release()
            self.HWPThread = threading.Thread(target=self.HWP.wait_for_device, name="HWPposition", args=(row['Polarisation'],), kwargs=dict(timeout=0.6))
            self.HWPThread.start()

        self.Arduino.clear_buffer()

        if row['Filter'] != prev_row['Filter']:
            self.Arduino.reset_filter_flag()
            self.Filter.set_position(row['Filter'])
            self.hardware_flag_lock.acquire()
            self.hardware_change_flags.update({'Filter':True})
            self.hardware_flag_lock.release()
   
        if row['Xlocation'] != prev_row['Xlocation'] or row['Ylocation'] != prev_row['Ylocation'] or row['Zposition'] != prev_row['Zposition']:
            self.Arduino.reset_stage_flag()
            self.hardware_flag_lock.acquire()
            self.hardware_change_flags.update({'Stage':True})
            self.hardware_flag_lock.release()
            
            if row['Znumber'] == 0: # the first or only z in a position or channel - use backlash correction
                self.ASI.backlash_compensation(True)
                self.ASI.move_to(X=row['Xlocation'], Y=row['Ylocation'], Z=row['Zposition']) 
            if row['Znumber'] > 0: # progressing through a Z-stack witihn a channel and or position, don;t use backlash correction
                self.ASI.backlash_compensation(False)
                self.Arduino.trigger_stage()

#has the servo moved?
        if row['Illumination'] == 0 and prev_row['Illumination'] !=0: #switched to LED
            self.Arduino.set_servo(7)
            self.Arduino.LS_select("L")
            self.Arduino.set_LED_power(row['Power'])
            self.servo_timer_function(prev_row['ND'],7)
            self.ServoThread = threading.Thread(target=self.servo_timer_function, name="Servowait", args=(prev_row['ND'],7))
            self.ServoThread.start()
            
        if row['Illumination'] != 0 and prev_row['Illumination'] ==0: #switched from LED
            self.Arduino.set_servo(6-row['ND'])
            self.ServoThread = threading.Thread(target=self.servo_timer_function, name="Servowait", args=(prev_row['ND'],7))
            self.ServoThread.start()
            
        if row['Illumination'] != 0 and prev_row['Illumination'] !=0 and row['ND'] != prev_row['ND']: #changed ND filter, not from LED 
            self.Arduino.set_servo(6-row['ND'])
            self.ServoThread = threading.Thread(target=self.servo_timer_function, name="Servowait", args=(prev_row['ND'],row['ND']))
            self.ServoThread.start()

#change lightsource?
        if row['Illumination'] in [1,2,3,4]:  #Visible laser, this is fast, no timer needed
            self.Arduino.LS_select("V")
            self.Cairn.set_wavelength(row['Wavelength'])
            self.Cairn.power(row['Wavelength'],row['Power'])
                  
        if row['Illumination'] == 5: #SolsTiS
            self.Arduino.LS_select("S")
            if row['Wavelength'] != self.SolsTiS.wavelength:
#                self.SolsTiS.set_wavelength(row['Wavelength'], set_flag=True)  #now sent by the thread below
                self.SolstisThread = threading.Thread(target=self.SolsTiS.wait_for_tune, name="SolstisTune", args=(row['Wavelength'],))
                self.SolstisThread.start()
              
        if row['Illumination'] == 6:          #MaiTai
            self.Arduino.LS_select("M")
            if row['Wavelength'] != self.MTwavTracker:
                self.Maitai.clear_buffer()
                print 'set MT wavlength:', row['Wavelength']
                self.Maitai.set_wavelength(row['Wavelength'], set_flag=True)

                    

# if the next image does not use the maitai, tune the maitai to its next required wavelength
#        future_row_numbers = np.roll(np.arange(imaging_set.shape[0]),(row_number+1)*-1)[:-1]
#        if row['Illumination'] != 6: #Maitai not in use on the next image, but can start tuning it now anyway
#            for r in future_row_numbers:
#                if imaging_set.iloc[r]['Illumination']==6: #find the first future use of Maitai
#                    self.Maitai.clear_buffer()
#                    self.Maitai.set_wavelength(imaging_set.iloc[r]['Wavelength']) #set its wavelength, but don't set the hardware change flag, it will be set on the image before it is needed
#                    print 'FUTURE prep_hardware function:', 'Maitai to:', imaging_set.iloc[r]['Wavelength'], '(image:)', r
#                    break
## if the next image does not use the Solstis, tune the Solstis to its next required wavelength
#        if row['Illumination'] != 5: #Solstis not in use on the next image, but can start tuning it now anyway
#            for r in future_row_numbers:
#                if imaging_set.iloc[r]['Illumination']==6: #find the first future use of Solstis
#                    self.SolsTiS.set_wavelength(imaging_set.iloc[r]['Wavelength']) #set its wavelength, but don't set the hardware change flag, it will be set on the image before it is needed
#                    print 'FUTURE prep_hardware function:', 'Solstis to:', imaging_set.iloc[r]['Wavelength'], '(image:)', r
#                    break  

# =============================================================================
# #    This function is running in a separate thread!
# #    Thread communication with GUI via thread-safe queues
# =============================================================================

    def Imaging_thread(self, imaging_set, save_location, readout_mode, timing_interval, imaging_loops, crop, eight):
#        try:
        self.Thread_to_Gui.put(['alert','Experiment Started',2])
#  set hardware for first image        
        continue_experiment = True
        timepoints  = range(imaging_loops)
        last_timepoint_start = time.time()-timing_interval
#        make a MOVREL for the Z axis stage so that all future TTL pulses will utilize this z movement
        Zseparation = float(imaging_set.Zseparation.max()) #in µm
        self.ASI.move_rel(X=0.0, Y=0.0, Z=Zseparation)
        start_tune_time = time.time()
        self.prep_hardware(0,imaging_set,None) #set hardware change flags True for first image
        
        for t in timepoints:
            print 'timepoint ', t
            
            while time.time() < last_timepoint_start + timing_interval:
#                add escape clause for stop button press here
                if self.check_pause_stop(): continue_experiment = False
                if not continue_experiment: break
                remaining_time = round(last_timepoint_start + timing_interval - time.time(),1)
                self.Thread_to_Gui.put( ['timer',"Next timepoint in %ss" %remaining_time,9])
                time.sleep(0.05)
            last_timepoint_start = time.time()
            self.Thread_to_Gui.put( ['timer',"",8])
#           update GUI
            if self.check_pause_stop(): continue_experiment = False
            if not continue_experiment: break
        
            self.USB_HUB.galvo_on()

            nLs = int(imaging_set.Location.max()+1)
            nCs = int(imaging_set.Channel.max()+1)
            
            for index, row in imaging_set.iterrows():
#                print 'image:', row
                if self.check_pause_stop():
                    print 'expt stop true'
                    continue_experiment = False
                    self.Camera.set_exposure(5)
                    while self.mmc.isSequenceRunning():
                        self.Arduino.trigger()
                        time.sleep(0.01)
                    self.mmc.stopSequenceAcquisition()
                    break

                C = int(row['Channel'])
                L = int(row['Location'])
                Z = int(row['Znumber'])
                P = int(row['Pnumber'])
                W = int(row['Wnumber'])
                C_name = row['Name']
                
                nZs = int(imaging_set.loc[imaging_set['Channel'] == C].Znumber.max()+1)
                nPs = int(imaging_set.loc[imaging_set['Channel'] == C].Pnumber.max()+1)
                nWs = int(imaging_set.loc[imaging_set['Channel'] == C].Wnumber.max()+1)
              
#                capture a whole channel at once, because the number of iamges, exposure and binning can change between channels
               
# setup camera
                             
                
                if row['Musical'] > 0:              # Musical images
#                    print 'camera musical setup'
                    self.Camera.set_binning(row['Binning'])              #must set binning before camera goes to external mode, don't know why
                    self.Camera.set_exposure(row['Exposure'])
                    self.mmc.setAutoShutter(False)                       #must set before starting acquisition to enforce 
                    image_count = 0
                    n_images = row['Musical']
                    self.Camera.musical_mode()
                    self.mmc.initializeCircularBuffer()
                    self.mmc.clearCircularBuffer()
                    self.mmc.prepareSequenceAcquisition("TSICam")
                    self.mmc.startSequenceAcquisition("TSICam",n_images,5,False)
                    
                if Z+P+W == 0 and row['Musical'] == 0:      #it's the first image of a channel, and not musical
#                    print 'camera normal setup'
                    self.Camera.set_binning(row['Binning'])              #must set binning before camera goes to external mode, don't know why
                    self.Camera.set_exposure(row['Exposure'])
                    self.mmc.setAutoShutter(False)                       #must set before starting acquisition to enforce    
                    image_count = 0
                    n_images = nZs * nPs * nWs
                    self.Camera.external_mode()                    
                    self.mmc.initializeCircularBuffer()
                    self.mmc.clearCircularBuffer()
                    self.mmc.prepareSequenceAcquisition("TSICam")
                    self.mmc.startSequenceAcquisition("TSICam",n_images,5,False)


# check hardware is ready 
#   Filter and Stage    
#                print 'wait for hardware...',
                self.Arduino.wait_for_filter_n_stage()
#   Maitai

                self.hardware_flag_lock.acquire()
                if row['Illumination'] == 6 and self.MTwavTracker != int(row['Wavelength']): 
                    stable = False
                    self.Maitai.clear_buffer()
                else: stable = True
                self.hardware_flag_lock.release()

                while not stable:
                    stable =  self.Maitai.laser_stable()
                    time.sleep(0.1)
                self.MTwavTracker = row['Wavelength']
                
#other harware
                ready = False       
                while not ready:
                    ready = True
                    self.hardware_flag_lock.acquire()
                    if self.hardware_change_flags['HWP']:       ready = False
                    if self.hardware_change_flags['Servo']:     ready = False
                    if self.hardware_change_flags['Solstis']:   ready = False
                    self.hardware_flag_lock.release()                
                print 'tuning complete', time.time() - start_tune_time, 'ms'
                
# get the image
                image_capture_time = datetime.datetime.now()
                if row['Musical'] > 0:
                    self.Arduino.musical_start()      #capture image with musical
                    image_count += row['Musical']
                if row['Musical'] == 0:
                    print("start SC")
                    self.Arduino.sync_acquire(row['Exposure'])      #capture image with shutter sycn
                    image_count +=1
                start_wait = time.time() #used as a time out in case no image is available
                
#   update GUI scan progress
                if row['Musical'] == 0: self.Thread_to_Gui.put(['% progress',  [image_count, n_images], 1])
                print("Update GUI")
                self.Thread_to_Gui.put(['% progress',  [(t*imaging_set.shape[0])+index+1, imaging_set.shape[0]*imaging_loops], 2])
                self.Thread_to_Gui.put(['to progress', 'Zposition    %s of %s' %(Z+1, nZs), 3])
                self.Thread_to_Gui.put(['to progress', 'wavelength   %s of %s' %(W+1, nWs), 4])
                self.Thread_to_Gui.put(['to progress', 'polarisation %s of %s' %(P+1, nPs), 5])
                self.Thread_to_Gui.put(['to progress', 'channel      %s of %s (%s)' %(C+1, nCs,C_name), 6])
                self.Thread_to_Gui.put(['to progress', 'position:    %s of %s' %(L+1, nLs), 7])
                self.Thread_to_Gui.put(['to progress', 'time:        %s of %s' %(t+1, len(timepoints)), 8])  
                
#   prepare all metadata
                md = row.to_dict()
                md.update({'location':save_location,'time':str(image_capture_time),'readout_mode':readout_mode, 'Binning':self.binning_list[row['Binning']], 
                           'Filter':self.filter_list[row['Filter']], 'timepoint':t})
                    
                if row['Musical'] > 0: 
#                    print 'musical image save start'
                    #   wait for correct number of images to pass through the camera buffer
                    image_count = 0
                    while image_count < n_images:
                        if self.mmc.getRemainingImageCount() > 0:
#                            print 'got image', image_count
                            frame = self.mmc.popNextImage()
                            self.save_in_loop(frame, md.copy(), crop=crop, eight=eight, musical=image_count)
                            image_count+=1
                            self.Thread_to_Gui.put(['% progress',  [image_count, n_images], 1])
        #                   send image to GUI via threadsafe queue
                            self.Image_displayQ.put(frame)
                        if image_count == n_images:
                            self.Arduino.musical_end()
                            if index < imaging_set.shape[0]-1:  self.prep_hardware(index+1, imaging_set,prev_row_number=index) #prep for next image
#                    for last image in channel
                            else:                               self.prep_hardware(0,       imaging_set,prev_row_number=index) #prep for the first image of next channel
                            break
                            
                if row['Musical'] == 0:
                    #   wait for exposure to complete
                    print("A")
                    print(self.mmc.getRemainingImageCount())
                    capture_complete = self.Arduino.wait_for_exposure_end(start_wait + (float(row['Exposure'])/1000.0) + 0.2 )#alternativly wait for a serial confirmation from arduino that exposure is complete
                    print("B")
                    # immediatly set hardware in motion for next image 
                    if index < imaging_set.shape[0]-1:  
                        start_tune_time = time.time()
                        self.prep_hardware(index+1, imaging_set,prev_row_number=index) #prep for next image
#                    for last image in channel
                    else:                               self.prep_hardware(0,       imaging_set,prev_row_number=index) #prep for the first image of next channel
                    #   add the metadata for the image to save image queue
                    print("C")
                    while True: # wait for image to arrive in the camera buffer
                        if self.mmc.getRemainingImageCount() > 0: break  
                    frame = self.mmc.popNextImage()
                    print("D")
                    self.save_in_loop(frame, md, crop=crop, eight=eight, musical=-1)
#                   send image to GUI via threadsafe queue
                    self.Image_displayQ.put(frame)

# =============================================================================
# end image save routine                        
# =============================================================================
        
#end acqusition at the end of a channel, or if experiment is stopped
                if (Z+1)*(W+1)*(P+1) == n_images or row['Musical'] > 0:
#                    print 'stop camera'
                    self.mmc.stopSequenceAcquisition()
                    self.Camera.internal_mode()
                    self.mmc.setAutoShutter(True)

            self.USB_HUB.galvo_off()
            self.ASI.backlash_compensation(True)
        

        print 'imaging complete'

        self.Thread_to_Gui.put( ['imaging complete'])
        self.Thread_to_Gui.put(['% progress',  [1, 1], 1])
        
        if not continue_experiment:
            print 'thread trying to end'
            if self.mmc.isSequenceRunning:
                self.mmc.stopSequenceAcquisition()
                self.Camera.internal_mode()
                self.mmc.setAutoShutter(True)
            self.Arduino.closeShutter()
# return XZ stage to first position that is in use
        i_s = self.get_position_set()
        self.ASI.move_to(X=i_s[0][0],Y=i_s[0][1],Z=i_s[0][2])
        
        self.in_experiment = False
            

#_________________________END imaging loop_____________________

# =============================================================================
# imaging lop functions
# =============================================================================
        
        
    def save_in_loop(self, frame, md, crop=False, eight=False, musical=0):
        save_location = md.pop('location')
        c = md.pop('Channel')
        L = md.pop('Location')
        name = md['Name']
        
        if not os.path.exists('%s\\p%02d' %(save_location,L)):
            os.mkdir('%s\\p%02d' %(save_location,L))
            
        if not os.path.exists('%s\\p%02d\\c%02d-%s' %(save_location,L,c,name)):
            os.mkdir('%s\\p%02d\\c%02d-%s' %(save_location,L,c,name))
        #create filename with zs
        if musical == -1: filename = '%s\\p%02d\\c%02d-%s\\t%03d_z%03d_p%03d_w%s.tif' %(save_location,L,c,name,md['timepoint'],
                                                                                       md['Znumber'],md['Polarisation'],md['Wavelength'])
        if musical >= 0: filename = '%s\\p%02d\\c%02d-%s\\t%03d_z%03d_p%03d_w%s_m%03d.tif' %(save_location,L,c,name,md['timepoint'],
                                                                                       md['Znumber'],md['Polarisation'],md['Wavelength'],musical)
#                memory saving techniques
        if crop:#        crop
            if md['Binning'] == self.binning_list[0]: to_save = frame[100:1948,320:1344]
            if md['Binning'] == self.binning_list[1]: to_save = frame[50:974,160:672]
            if md['Binning'] == self.binning_list[2]: to_save = frame[25:487,80:336]
        else: to_save = frame            
        if eight:#        reduce bit-depth    
            to_save = (to_save/256).astype(np.uint8)
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore") # Use this to turn off image warnings, e.g. low contrast
            tf.imsave(filename, to_save, metadata=md)
        
        
        
    def check_pause_stop(self):         
#        imaging thread calls this function regularly to check if it should continue imaging
        #return True, which will cause imaging thread to leave imaging loop and complete cleanly
        main_window_checkin = self.Gui_to_Thread[0]
        if time.time() > main_window_checkin + 10:return True        
        if self.Gui_to_Thread[-1] == 'stop':
            self.Thread_to_Gui.put( ['alert','Experiment Stopped',2])
            return True
        return False

    def check_Qs(self):
#        a function for ensuring that the imaging thread can cause updates to the GUI in a threadsafe way
#        queues are implemented in a threadsafe way by qt4, so tasks are added to the queue as needed by the
#        thread and then removed from the queue by the GUI, which checks the queue every 100ms
        
        while self.Thread_to_Gui.qsize()>0:
            task = self.Thread_to_Gui.get()
                
            if task[0] == 'alert':
                self.information("%s" %(task[1]),task[2])
                
            if task[0] == 'imaging complete':
                self.information("Imaging complete", 2)
                self.Imaging(command='stop')

            if task[0] == 'to progress':
                self.progress(task[1],task[2])
                
            if task[0] == 'timer':
                self.progress(task[1],task[2])
                
            if task[0] == 'position':
                self.update_GUI_XYZ(task[1])
                
            if task[0] == '% progress':
                images_completed = float(task[1][0])
                n_images = float(task[1][1])
                progress = images_completed / n_images *100.0
                msg = '['
                for i in range(20):
                    if progress > i*5: msg = msg + '|'
                    else: msg = msg + '_'
                msg = msg + '] %s' %(round(progress,1))+ '%'
                self.progress(msg,task[2])
                
# display most recent image (not all images during rapid acqusitions)        
        if self.Image_displayQ.qsize() > 0: 
            self.current_img = self.Image_displayQ.get()     # take the most recent image and display it
            self.Camera.display_image(self.current_img)
            while self.Image_displayQ.qsize() > 0: 
                self.Image_displayQ.get()                    # delete unused images
# Add timestamp to this queue so the imaging thread can know main thread is still running
        self.Gui_to_Thread[0] = time.time()         


    def GUI_access(self, state):
        self.limit_widget_access_list = [self.DetectionGroup,self.IlluminationGroup,self.ConnectionGroup,
                                         self.FileGroup,self.BuilderGroup,self.ZSlice,self.StageGroup,
                                         self.LambdaGroup, self.MusicalGroup, self.PolGroup]

        for widget in self.limit_widget_access_list:
            widget.setEnabled(state)

#==============================================================================
#               ILLUMINATION and DETECTION FUNCTIONS
#==============================================================================
    def detection_settings(self):
        self.Filter.set_position(self.setFilter.currentIndex())
        self.Camera.set_exposure(int(self.setExposure.text()))
        self.Camera.set_binning(self.binningMenu.currentIndex())
        
        self.Camera.set_binning(self.binningMenu.currentIndex())
    
    def illumination_settings(self, index, val):#        update the GUI - interaction between slider and text box
        if index < 7 or index == 8:       #not ND filter
            self.sliders[index].setValue(int(val))
            self.edits[index].setText('%s' %int(val))
#    send commands to devices
        if index == 0: self.Arduino.set_LED_power(int(val)) #to implement after conversion to teensy (v4)
        if index == 1: self.Cairn.power('405',int(val))             #405
        if index == 2: self.Cairn.power('488',int(val))             #488
        if index == 3: self.Cairn.power('561',int(val))             #561
        if index == 4: self.Cairn.power('660',int(val))             #660
        if index == 5: self.SolsTiS.set_wavelength(int(val))        #Sosltis
        if index == 6: self.Maitai.set_wavelength(int(val))         #Maitai
        if index == 7: #ND filter
            if self.illumination > 0:
                self.Arduino.set_servo(6-val)
        if index == 8: self.HWP.set_position(int(val))              #Half wave plate
        
    def illumination_source(self, index):
        if index == 9: #source unknown, need to find which LS is checked
            for i, item in enumerate(self.lightsource):
                if item.isChecked():
                    index = i
                    break
        self.illumination = index
        if self.Arduino.flag_CONNECTED:
            if index == 0: 
                self.Cairn.set_wavelength(0)
                self.Arduino.LS_select("L")
                self.Arduino.set_servo(7)
            if index == 1:
                self.Cairn.set_wavelength(405)
                self.Arduino.LS_select("V")
                self.Arduino.LEDoff()
                self.Arduino.set_servo(self.sliderND.value())
            if index == 2:
                self.Cairn.set_wavelength(488)
                self.Arduino.LS_select("V")
                self.Arduino.LEDoff()
                self.Arduino.set_servo(self.sliderND.value())
            if index == 3:
                self.Cairn.set_wavelength(561)
                self.Arduino.LS_select("V")
                self.Arduino.LEDoff()
                self.Arduino.set_servo(self.sliderND.value())
            if index == 4:
                self.Cairn.set_wavelength(660)
                self.Arduino.LS_select("V")
                self.Arduino.LEDoff()
                self.Arduino.set_servo(self.sliderND.value())
            if index == 5:
                self.Cairn.set_wavelength(0)
                self.Arduino.LS_select("S")
                self.Arduino.LEDoff()
                self.Arduino.set_servo(self.sliderND.value())
            if index == 6:
                self.Cairn.set_wavelength(0)
                self.Arduino.LS_select("M")
                self.Arduino.LEDoff()
                self.Arduino.set_servo(self.sliderND.value())
            
#            if self.Camera.live_imaging: self.Arduino.openShutter()
#            else: self.Arduino.closeShutter()

 
# =============================================================================
# Functions for stage movement/positions
# =============================================================================

    def adjustZStack(self, m):
        span            = float(self.ZSpan.text())
        slices          = int(self.ZSlices.text())
        separation      = float(self.ZSeparation.text())

        if m==1:
            self.ZSlices.setText(str(int(round(span/separation))+1))
            self.adjustZStack(0)
        elif m==0:
            self.ZSeparation.setText(str(round((span/(slices-1)),2)))
        elif m==2:
            self.adjustZStack(0)
        zs = self.show_set(self.getZ_set()[0])
        self.ZDemo.setText('[%s] n=%s' %(zs,len(self.getZ_set()[0])))
            
    def goto_position(self, x,y,xz):
        self.ASI.backlash_compensation(True)
        print 'goto function', x,y,xz
        self.ASI.move_to(X=float(x), Y=float(y), Z=float(xz))
        
    def pos_table_click(self, r,c):
        if c == 4: # delete
            self.Table_positions.removeRow(r)
            print 'delete button click'
        if c == 5: # go to
            print 'goto button click'
            x     = float(self.Table_positions.cellWidget(r,1).text())
            y     = float(self.Table_positions.cellWidget(r,2).text())
            xz    = float(self.Table_positions.cellWidget(r,3).text())
            self.goto_position(x,y,xz)

    def validate_position(self, position):
        valid = 0
#        print 'validate:', position
        if position[0] > self.ASI.imaging_limits[0][1] and position[0] < self.ASI.imaging_limits[0][0]: valid +=1
#        else: print 'fail X'
        if position[1] > self.ASI.imaging_limits[1][1] and position[1] < self.ASI.imaging_limits[1][0]: valid +=1
#        else: print 'fail Y'
        if position[2] > self.ASI.imaging_limits[2][1] and position[2] < self.ASI.imaging_limits[2][0]: valid +=1
#        else: print 'fail XZ'
        
        if valid == 3: return True
        else: return False

    def add_position(self, position=None, in_use=None):
#        if position == None then use the current stage position, otherwise use supplied position (x,y,z)
        
        if position == None:
            if self.ASI.flag_CONNECTED:
                position = self.ASI.get_position() #returns current stage position in µm
            else:
                self.information("No stage connection",2)
                return

        if self.validate_position(position):
            row_number = self.Table_positions.rowCount()
            self.Table_positions.insertRow(row_number)
            inUse = QtGui.QCheckBox('')
            if in_use is not None:
                inUse.setChecked(in_use)
            else:
                inUse.setChecked(True)
            X = QtGui.QLineEdit()
            X.setText('%s' %position[0])
            X.setValidator(QtGui.QDoubleValidator(self.ASI.imaging_limits[0][1],self.ASI.imaging_limits[0][0],1))
            Y = QtGui.QLineEdit()
            Y.setText('%s' %position[1])
            Y.setValidator(QtGui.QDoubleValidator(self.ASI.imaging_limits[1][1],self.ASI.imaging_limits[1][0],1))
            XZ = QtGui.QLineEdit()
            XZ.setText('%s' %position[2])
            XZ.setValidator(QtGui.QDoubleValidator(self.ASI.imaging_limits[2][1],self.ASI.imaging_limits[2][0],1))
            del_ = QtGui.QLabel('delete')
            goto = QtGui.QLabel('go to')

            self.Table_positions.setCellWidget(row_number,  0, inUse)
            self.Table_positions.setCellWidget(row_number,  1, X)
            self.Table_positions.setCellWidget(row_number,  2, Y)
            self.Table_positions.setCellWidget(row_number,  3, XZ)
            self.Table_positions.setCellWidget(row_number,  4, del_)
            self.Table_positions.setCellWidget(row_number,  5, goto)
            self.information("Added new position X:%s Y:%s XZ:%s" %(position[0],position[1],position[2]),1)
        else:
            self.information("Position X:%s Y:%s XZ:%s not valid for imaging" %(position[0],position[1],position[2]),2)
        
            
    def pickle_positions(self):
        to_store = []
        for r in range(self.Table_positions.rowCount()):
            u = self.Table_positions.cellWidget(r,0).isChecked()
            x = self.Table_positions.cellWidget(r,1).text()
            y = self.Table_positions.cellWidget(r,2).text()
            z = self.Table_positions.cellWidget(r,3).text()
            to_store.append([u,x,y,z])
        pickle.dump(to_store, open("%s%s" %("",'positions'), 'wb'))


    def clear_all_positions(self):
        for i in range(self.Table_positions.rowCount()):
            self.Table_positions.removeRow(0)
        
    def unpickle_positions(self):
        try:
            to_load = pickle.load(open("%s%s" %("",'positions'), 'rb'))
            for r in range(len(to_load)):
                self.add_position(position = (float(to_load[r][1]),float(to_load[r][2]),float(to_load[r][3])), in_use=to_load[r][0])
        except Exception,e:
            print e
            self.information("position storage file not found",2)
      
    def get_position_set(self):
        imaging_positions = []
        rows = self.Table_positions.rowCount()
        for row in range(0,rows):
            if self.Table_positions.cellWidget(row,0).isChecked():
                x = float(self.Table_positions.cellWidget(row,1).text())
                y = float(self.Table_positions.cellWidget(row,2).text())
                xz = float(self.Table_positions.cellWidget(row,3).text())
                imaging_positions.append([x,y,xz])
        return imaging_positions
 
# =============================================================================
 # Functions for displaying information in the GUI
# =============================================================================

    def information(self, info, slot):
#        print(info, slot)
        self.Alerts_text_window.moveCursor(QtGui.QTextCursor.End)
        now=datetime.datetime.now()
        d = '%02d:%02d:%02d - '%(now.hour,now.minute,now.second)
        self.Alerts_text_window.insertHtml('<font color="white">%s</font>' %d)
        if slot == 0:
            self.Alerts_text_window.insertHtml('<font color="red"><b>%s</b></font><br>' %(str(info)))
        if slot == 1:
            self.Alerts_text_window.insertHtml('<font color="green"><b>%s</b></font><br>'%(str(info)))
        if slot == 2:
            self.Alerts_text_window.insertHtml('<font color="yellow"><b>%s</b></font><br>'%(str(info)))
        self.Alerts_text_window.moveCursor(QtGui.QTextCursor.End)

    def progress(self, info, line):
        self.Information_text_window.moveCursor(QtGui.QTextCursor.Start)
        for i in range(line):
            self.Information_text_window.moveCursor(QtGui.QTextCursor.Down)
        self.Information_text_window.moveCursor(QtGui.QTextCursor.Down, QtGui.QTextCursor.KeepAnchor)
        self.Information_text_window.insertHtml('<font color="white"><b>%s</b></font><br>' %(str(info)))
        
    def update_GUI_XYZ(self, position):
        self.pos_labelX.setText(' X:%s' %position[0])
        self.pos_labelY.setText(' Y:%s' %position[1])
        self.pos_labelXZ.setText('XZ:%s' %position[2])
        



    def set_Enabled(self,list_of_widgets,state):
        for item in list_of_widgets:
            item.setEnabled(state)

    def setScreenSize(self):
        screen       =  QtGui.QApplication.desktop().screenGeometry().getCoords()
        screenHeight = screen[-1]
        screenWidth  = screen[-2]
        self.setGeometry(30, 50, screenWidth*0.8, screenHeight-100)

    def update_expt_name(self):
        UserName    = self.FileUserList.currentText()
        ExptName    = self.FileExptName.text()
        startdate   = datetime.date.today()
        rootLocation = 'D:'
        if len(ExptName)>0:
            ExptName = ' (%s)' %(ExptName)
        i=0
        while True:
            i=i+1
            if i==1:
                StoreLocation = '%s\\%s\\%s%s' %(rootLocation,UserName,startdate,ExptName)
            else:
                StoreLocation = '%s\\%s\\%s (%s)%s' %(rootLocation,UserName,startdate,i,ExptName)
            if not os.path.exists(StoreLocation):
                self.FileAddress.setText(StoreLocation)
                break

    def saveSingleImage(self):
        for LS, item in enumerate(self.lightsource): 
            if item.isChecked(): break
        
        f = self.setFilter.currentText()
        e = self.setExposure.text()
        b = self.binningMenu.currentText()
        b = "%sx%s" %(b,b)
        l = self.lightsource_list[LS]


        if LS == 0: wl = 620 #LED in use
        if LS == 1: wl = 405 
        if LS == 2: wl = 488 
        if LS == 3: wl = 561 
        if LS == 4: wl = 660 
        if LS == 5: wl = self.SolsTiS.wavelength #SolsTiS in use
        if LS == 6: wl = self.Maitai.wavelength  #MaiTai in use
        
        suggested_name = "%snm %s %sms %s.tif" %(wl,f,e,b)

        name = QtGui.QFileDialog.getSaveFileName(self,"Save image as",suggested_name)
        if name[-4] != ".":  #if the file name does not already contains three letter extension then add '.tif'
            name = "%s.tif" %(name)
        md = dict(Lightsource=l, Wavlength=wl, Filter=f, Binning=b, Exposure=e)
        tf.imsave(name, self.Camera.current_img, metadata=md)

    def connectAll(self):
        for item in Connection_Widget.connection_list:
            item.checkbox.setChecked(True)
    
    def connect_startup(self, x):
        for item in Connection_Widget.connection_list[:x]:
            item.checkbox.setChecked(True)

    def show_set(self, a_set):
#        to output a representation of a lambda, polorisation or z range to allow user to confirm settings are correct
        string = ''
        if len(a_set) < 7:
            for item in a_set:
                string = string + ',%s' %item
        else:
            for item in a_set[0:3]: string = string + ',%s' %item
            string = string + ', ... ' 
            for item in a_set[-3:]: string = string + ',%s' %item
        return '%s' %(string[1:])
    
    def getZ_set(self):
        span = float(self.ZSpan.text())
        slices = int(self.ZSlices.text())
        separation = float(round((span/(slices-1)),2))
        z_set = []
        for i in range(slices):
            z_set.append(((span/2)-span) + (separation * i))
        return z_set, separation
    
    def getPol_set(self):
        start = int(self.PolStart.text())
        end = int(self.PolEnd.text())
        step = int(self.PolStep.text())
        pol_set = []
        k=abs(start-end)/(end-start)
        for p in range(start, end+(step*k), step*k):
            pol_set.append(int(round(p,0)))
        return pol_set

    def getLambda_set(self):
        Lambda_set = []
        if self.LambdaCheckbox.isChecked(): #use custom set
            str_set = self.LambdaCustom.text()
            str_set = str_set.split(',')
            print(str_set)
            for item in str_set:
                try:
                    if int(item) > 699 and int(item) < 1001:
                        Lambda_set.append(int(item))
                except: pass
            if len(Lambda_set) == 0:
                self.LambdaCheckbox.setChecked(False)
                Lambda_set = self.getLambda_set()   
        else: # build lambda set from the range and step size
            start = int(self.LambdaStart.text())
            end = int(self.LambdaEnd.text())
            k=abs(start-end)/(end-start)
            step = int(self.LambdaStep.text())*k
            for p in range(start, end+step, step):
                Lambda_set.append(int(round(p,0)))
        return Lambda_set

    def adjustLambda(self):
        start = int(self.LambdaStart.text())
        end = int(self.LambdaEnd.text())
        k=abs(start-end)/(end-start)
        step = int(self.LambdaStep.text())*k
        set_ = range(start, end+step, step)
        n = len(set_)
        set_ = self.show_set(set_)
        self.LambdaDemo.setText('[%s] n=%s' %(set_,n))

    def adjustPol(self):
        start = int(self.PolStart.text())
        end = int(self.PolEnd.text())
        k=abs(start-end)/(end-start)
        step = int(self.PolStep.text())*k
        set_ = range(start, end+step, step)
        n = len(set_)
        set_ = self.show_set(set_)
        self.PolDemo.setText('[%s] n=%s' %(set_,n))
# =============================================================================
# Functions for loop timing
# =============================================================================
    def update_duration(self):
        try:
            loops       = int(self.TimingLoops.text())
            interval    = int(self.TimingInterval.text())
            if(interval<1):
                interval = 1
                self.TimingInterval.setText(1)

            DurationH   = int(math.floor(interval*loops/3600))
            DurationM   = int(math.floor((interval*loops-(DurationH*3600))/60))
            DurationS   = int(math.floor((interval*loops-(DurationH*3600)-(DurationM*60))))
            self.TimingDuration.setText('%02d : %02d : %02d' %(DurationH,DurationM,DurationS))
            #timing has changed, send to imaging thread
            self.Gui_to_Thread[1] = [interval,loops]
        except:
            self.information("Please enter valid interval and loop values.", 0)

# =============================================================================
# Experiment builder functions    
# =============================================================================
# =============================================================================
#       Functions for imaging sets / channels
# =============================================================================
    def move_set(self,d):
        self.Table_presets.setFocus()
        if len(self.Table_presets.selectedItems()):
#get the rows that are selected
            selected = []
            for r in self.Table_presets.selectedItems():
                selected.append(r.row())           
#create a structure with all data
            data = []
            for r in range(self.Table_presets.rowCount()):
                in_use_         = self.Table_presets.cellWidget(r,0).isChecked()
                name_           = self.Table_presets.item(r,1).text()
                LS_used_        = self.Table_presets.cellWidget(r,2).currentIndex()
                ND_             = self.Table_presets.cellWidget(r,3).currentIndex()
                power_          = self.Table_presets.cellWidget(r,4).text()
                wavelength_     = self.Table_presets.cellWidget(r,5).text()
                polarisation_   = self.Table_presets.cellWidget(r,6).text()
                exposure_       = self.Table_presets.cellWidget(r,7).text()
                binning_        = self.Table_presets.cellWidget(r,8).currentIndex()
                filter_         = self.Table_presets.cellWidget(r,9).currentIndex()
                z_stacking_     = self.Table_presets.cellWidget(r,10).isChecked()
                lambda_stack_   = self.Table_presets.cellWidget(r,11).isChecked()
                pol_stack_      = self.Table_presets.cellWidget(r,12).isChecked()
                data.append([in_use_,name_,LS_used_,ND_,power_,wavelength_,polarisation_,exposure_,binning_,filter_,z_stacking_,lambda_stack_,pol_stack_])
#reorder the data
            if d == -1:
                if 0 in selected: return # top row selected, can't move up
                for r in range(self.Table_presets.rowCount()):
                    if r in selected:
#delete row
                        self.Table_presets.removeRow(r)
#insert row
                        self.add_set(data[r][0],data[r][1],data[r][2],data[r][3],data[r][4],data[r][5],data[r][6],data[r][7],
                                     data[r][8],data[r][9],data[r][10],data[r][11],data[r][12],insert_at = r + d)
            if d == 1:
                if self.Table_presets.rowCount()-1 in selected: return # bottom row selected, can't move down
                for r in range(self.Table_presets.rowCount(),0,-1):
                    if r in selected:
#delete row
                        self.Table_presets.removeRow(r)
#insert row
                        self.add_set(data[r][0],data[r][1],data[r][2],data[r][3],data[r][4],data[r][5],data[r][6],data[r][7],
                                     data[r][8],data[r][9],data[r][10],data[r][11],data[r][12],insert_at = r + d)
#select the rows            
            self.Table_presets.setSelectionMode(QtGui.QAbstractItemView.MultiSelection)
#            self.Table_presets.setSelectionBehavior(QtGui.QAbstractItemView.SelectItems)
            for item in selected:
                self.Table_presets.selectRow(item + d)
            self.Table_presets.setFocus()

    def builder_LS_change(self, row_number):                #LED and visible, no wavelength or lambda
        if self.Table_presets.cellWidget(row_number,2).currentIndex() < 5:
            self.Table_presets.cellWidget(row_number,4).setEnabled(True)
            self.Table_presets.cellWidget(row_number,5).setEnabled(False)
            self.Table_presets.cellWidget(row_number,11).setEnabled(False)
            self.Table_presets.cellWidget(row_number,11).setChecked(False)
            self.Table_presets.cellWidget(row_number,3).setEnabled(True)
        else:                                               #Solstis and MaiTai, no power control
            self.Table_presets.cellWidget(row_number,4).setEnabled(False)
            self.Table_presets.cellWidget(row_number,5).setEnabled(True)
            self.Table_presets.cellWidget(row_number,11).setEnabled(True)
#            self.Table_presets.cellWidget(row_number,11).setChecked(False)
            self.Table_presets.cellWidget(row_number,3).setEnabled(True)
            
        if self.Table_presets.cellWidget(row_number,2).currentIndex() == 0: #LED
            self.Table_presets.cellWidget(row_number,3).setEnabled(False)


    def add_set(self, in_use_ = True, name_='', LS_used_=1, ND_=6, power_=50, wavelength_=740, polarisation_=0, exposure_=150, binning_=1, 
                filter_=3, z_stacking_=False, lambda_stack_=False, pol_stack_=False, musical_stack_=False, insert_at=-1):
#        build a "table item" that can be inserted into the table, moved, stored deleted etc.
        row_number = self.Table_presets.rowCount()
        if insert_at!=-1: row_number = insert_at
        self.Table_presets.insertRow(row_number)
        in_use = QtGui.QCheckBox('')
        in_use.setChecked(in_use_)
        #name added direct to cell, no widget required
        light_source = QtGui.QComboBox()
        light_source.addItems(self.lightsource_list)
        light_source.setCurrentIndex(LS_used_)
        light_source.currentIndexChanged.connect(lambda: self.builder_LS_change(row_number))
        
        ND = QtGui.QComboBox()
        ND.addItems(self.NDfilter_list)
        ND.setCurrentIndex(ND_)

        power = QtGui.QLineEdit()
        power.setText(str(power_))
        power.setValidator(QtGui.QIntValidator(0,100))
        
        wavelength = QtGui.QLineEdit()
        wavelength.setText(str(wavelength_))
        wavelength.setValidator(QtGui.QIntValidator(710,990))
        
        polarisation = QtGui.QLineEdit()
        polarisation.setText(str(polarisation_))
        polarisation.setValidator(QtGui.QIntValidator(-180,180))
        
        exposure = QtGui.QLineEdit()
        exposure.setText(str(exposure_))
        exposure.setValidator(QtGui.QIntValidator(5,10000))
        
        binning = QtGui.QComboBox()
        binning.addItems(('1','2','4'))
        binning.setCurrentIndex(binning_)
        
        filters = QtGui.QComboBox()
        filters.addItems(self.filter_list)
        filters.setCurrentIndex(filter_)
        
        z_stacking = QtGui.QCheckBox('')
        z_stacking.setChecked(z_stacking_)
        
        lambda_stack = QtGui.QCheckBox('')
        lambda_stack.setChecked(lambda_stack_)
        
        pol_stack = QtGui.QCheckBox('')
        pol_stack.setChecked(pol_stack_)
        
        musical_stack = QtGui.QCheckBox('')
        musical_stack.setChecked(musical_stack_)
    
        if name_=='': name_ = row_number+1
        self.Table_presets.setCellWidget(row_number,  0, in_use)
        self.Table_presets.setItem(row_number,        1, QtGui.QTableWidgetItem(str(name_)))
        self.Table_presets.setCellWidget(row_number,  2, light_source)
        self.Table_presets.setCellWidget(row_number,  3, ND)
        self.Table_presets.setCellWidget(row_number,  4, power)
        self.Table_presets.setCellWidget(row_number,  5, wavelength)
        self.Table_presets.setCellWidget(row_number,  6, polarisation)
        self.Table_presets.setCellWidget(row_number,  7, exposure)
        self.Table_presets.setCellWidget(row_number,  8, binning)
        self.Table_presets.setCellWidget(row_number,  9, filters)
        self.Table_presets.setCellWidget(row_number,  10, z_stacking)
        self.Table_presets.setCellWidget(row_number,  11,lambda_stack)
        self.Table_presets.setCellWidget(row_number,  12,pol_stack)
        self.Table_presets.setCellWidget(row_number,  13,musical_stack)
        self.builder_LS_change(row_number) 
        self.information("Added new imaging set '%s'" %(name_),1)

    def push_set(self):
        if len(self.Table_presets.selectedItems()):
            row = self.Table_presets.selectedItems()[0].row()
            name_           = self.Table_presets.item(row,1).text()
            LS_used_        = self.Table_presets.cellWidget(row,2).currentIndex()
            ND_             = self.Table_presets.cellWidget(row,3).currentIndex()
            power_          = int(self.Table_presets.cellWidget(row,4).text())
            wavelength_     = int(self.Table_presets.cellWidget(row,5).text())
            polarisation_   = int(self.Table_presets.cellWidget(row,6).text())
            exposure_       = int(self.Table_presets.cellWidget(row,7).text())
            binning_        = self.Table_presets.cellWidget(row,8).currentIndex()
            filter_         = self.Table_presets.cellWidget(row,9).currentIndex()
            
            self.lightsource[LS_used_].setChecked(True)
            
            self.sliderND.setValue(ND_)                 #set ND GUI value
            self.illumination_settings(7,ND_)           #set the physical polariser, need to set before calling illumination_source()
            self.sliderPol.setValue(polarisation_)      #set polariser GUI values
            self.editPol.setText('%s' %polarisation_)
            self.illumination_settings(8,polarisation_) #set the physical polariser
            
            
            self.illumination_source(LS_used_)          #sets lightsource, sets ND filter to position set in memory (likely wrong)
            if LS_used_ < 5:
                self.sliders[LS_used_].setValue(power_)
                self.edits[LS_used_].setText('%s' %power_)
            else:
                self.sliders[LS_used_].setValue(wavelength_)
                self.edits[LS_used_].setText('%s' %wavelength_)
            
            
            self.binningMenu.setCurrentIndex(binning_)
            self.setExposure.setText('%s' %exposure_)
            self.setFilter.setCurrentIndex(filter_)
            self.detection_settings() #sets the binning, exposure and filter
            self.information('pushing imaging settings from %s' %name_,1)
        
    def pull_set(self):
        if len(self.Table_presets.selectedItems()):
            row = self.Table_presets.selectedItems()[0].row()
            for i, item in enumerate(self.lightsource):
                if item.isChecked():
                    index = i
                    break
            self.Table_presets.cellWidget(row,2).setCurrentIndex(index)
            if index < 5:
                power_ = self.sliders[index].value()
                self.Table_presets.cellWidget(row,4).setText('%s' %power_)
            else:
                wavelength_ = self.sliders[index].value()
                self.Table_presets.cellWidget(row,5).setText('%s' %wavelength_)
            filter_ = self.setFilter.currentIndex()
            self.Table_presets.cellWidget(row,9).setCurrentIndex(filter_)
            exposure_ = self.setExposure.text()
            self.Table_presets.cellWidget(row,7).setText('%s' %exposure_)
            binning_ = self.binningMenu.currentIndex()
            self.Table_presets.cellWidget(row,8).setCurrentIndex(binning_)
            ND_ = self.sliderND.value()
            self.Table_presets.cellWidget(row,3).setCurrentIndex(ND_) 
            Pol_ = self.sliderPol.value()
            self.Table_presets.cellWidget(row,6).setText('%s' %Pol_) 
            self.builder_LS_change(row)
            
    def del_set(self):
        rows = self.Table_presets.selectedItems()
        rows.reverse()
        for row in rows:
            self.Table_presets.removeRow(row.row())

    def pickle_Table(self):
        to_store = []
        for r in range(self.Table_presets.rowCount()):
            in_use_         = self.Table_presets.cellWidget(r,0).isChecked()
            name_           = self.Table_presets.item(r,1).text()
            LS_used_        = self.Table_presets.cellWidget(r,2).currentIndex()
            ND_             = self.Table_presets.cellWidget(r,3).currentIndex()
            power_          = self.Table_presets.cellWidget(r,4).text()
            wavelength_     = self.Table_presets.cellWidget(r,5).text()
            polarisation_   = self.Table_presets.cellWidget(r,6).text()
            exposure_       = self.Table_presets.cellWidget(r,7).text()
            binning_        = self.Table_presets.cellWidget(r,8).currentIndex()
            filter_         = self.Table_presets.cellWidget(r,9).currentIndex()
            z_stacking_     = self.Table_presets.cellWidget(r,10).isChecked()
            lambda_stack_   = self.Table_presets.cellWidget(r,11).isChecked()
            pol_stack_      = self.Table_presets.cellWidget(r,12).isChecked()
            musical_stack_  = self.Table_presets.cellWidget(r,13).isChecked()
            
            to_store.append([in_use_,name_,LS_used_,ND_,power_,wavelength_,polarisation_,exposure_,binning_,filter_,z_stacking_,
                             lambda_stack_,pol_stack_,musical_stack_])
        pickle.dump(to_store, open("%s%s" %("",'presets'), 'wb'))
        to_store = []
        to_store.append(self.ZSlices.text())
        to_store.append(self.ZSeparation.text())
        to_store.append(self.ZSpan.text())
        to_store.append(self.LambdaStart.text())
        to_store.append(self.LambdaEnd.text())
        to_store.append(self.LambdaStep.text())
        to_store.append(self.LambdaCustom.text())
        to_store.append(self.LambdaCheckbox.isChecked())
        to_store.append(self.PolStart.text())
        to_store.append(self.PolEnd.text())
        to_store.append(self.PolStep.text())
        to_store.append(self.ImageLoopOrder.currentIndex())        
        to_store.append(self.MusicalNo.text())
        pickle.dump(to_store, open("%s%s" %("",'settings'), 'wb'))
        

    def unpickle_Table(self, output_):
        try:
            to_load = pickle.load(open("%s%s" %("",'presets'), 'rb'))
            for r in range(len(to_load)):
                self.add_set(to_load[r][0],to_load[r][1],to_load[r][2],to_load[r][3],to_load[r][4],to_load[r][5],to_load[r][6],to_load[r][7],
                             to_load[r][8],to_load[r][9],to_load[r][10],to_load[r][11],to_load[r][12],to_load[r][13])
                
            to_load = pickle.load(open("%s%s" %("",'settings'), 'rb'))
            self.ZSlices.setText(to_load[0])
            self.ZSeparation.setText(to_load[1])
            self.ZSpan.setText(to_load[2])
            self.LambdaStart.setText(to_load[3])
            self.LambdaEnd.setText(to_load[4])
            self.LambdaStep.setText(to_load[5])
            self.LambdaCustom.setText(to_load[6])
            self.LambdaCheckbox.setChecked(to_load[7])
            self.PolStart.setText(to_load[8])
            self.PolEnd.setText(to_load[9])
            self.PolStep.setText(to_load[10])
            self.ImageLoopOrder.setCurrentIndex(to_load[11])
            self.MusicalNo.setText(to_load[12])
            
            self.adjustLambda()
            self.adjustZStack(2)
            self.adjustPol()

        except Exception,e:
            self.information("preset file not found or error %s" %e,0)
            
    def build_imaging_set(self, tile_scan=False):
#        This function goes through the experiment builder and calculates all permutations of images that need to be captured in one time point
#        It then adds all relevant parameters for each image to a series (row) of a pandas data frame
#        The series (rows/images) are then sorted according to the specified aquisition order, e.g. prioritising looping through  Z position over wavelength
#        returns the sorted pandas data frame
        
#make empty master imaging set (pandas structure)
        imaging_set = pd.DataFrame(data=None,columns=['Name','Illumination','ND','Power','Wavelength','Polarisation',
                                                      'Exposure','Binning','Filter','Zposition','Znumber','Musical'])
#get possible sets for z,w,p
        lambda_set          = self.getLambda_set()
        pol_set             = self.getPol_set()
        z_set, separation   = self.getZ_set()
        location_set        = self.get_position_set()
        
        if tile_scan:
            row=0
            name_           = self.Table_presets.item(row,1).text()
            LS_             = self.Table_presets.cellWidget(row,2).currentIndex()
            power_          = int(self.Table_presets.cellWidget(row,4).text())
            exposure_       = int(self.Table_presets.cellWidget(row,7).text())
            if exposure_ < 5: exposure_ = 5
            binning_        = self.Table_presets.cellWidget(row,8).currentIndex()
            filter_         = self.Table_presets.cellWidget(row,9).currentIndex()
            settings = {'Name':name_,'Illumination':int(LS_),'Power':int(power_),
                     'Exposure':int(exposure_),'Binning':int(binning_),'Filter':filter_}
            return settings
  
        for L, location in enumerate(location_set):
#loop through 'channels'       
            rows = self.Table_presets.rowCount()
            channel = -1
            for row in range(0,rows):             
                    
                if self.Table_presets.cellWidget(row,0).isChecked(): #the channel is in use
                    channel += 1
                    name_           = self.Table_presets.item(row,1).text()
                    LS_             = self.Table_presets.cellWidget(row,2).currentIndex()
                    ND_             = self.Table_presets.cellWidget(row,3).currentIndex()
                    power_          = int(self.Table_presets.cellWidget(row,4).text())
                    exposure_       = int(self.Table_presets.cellWidget(row,7).text())
                    if exposure_ < 5: exposure_ = 5
                    binning_        = self.Table_presets.cellWidget(row,8).currentIndex()
                    filter_         = self.Table_presets.cellWidget(row,9).currentIndex()
                    if LS_ == 0: ND_ =  -1 #If LED in use, set ND to false (force hardware change during imaging)
    #for each channel set required list of Zs, Ps and Ws
                    Zs = [0]
                    Zseparation = 0 #set to zero by default to avoid stage crash
                    
                    if LS_ in [1,2,3,4]: #visible lasers
                        Ws = [int(self.lightsource_list[LS_])]
                    elif LS_ == 0:
                        Ws = [620]
                    else:
                        Ws = [int(self.Table_presets.cellWidget(row,5).text())]
                    Ps = [int(self.Table_presets.cellWidget(row,6).text())]
                    
                    if self.Table_presets.cellWidget(row,10).isChecked(): 
                        Zs = z_set
                        Zseparation = separation
                        
                    if self.Table_presets.cellWidget(row,11).isChecked(): Ws = lambda_set
                    if self.Table_presets.cellWidget(row,12).isChecked(): Ps = pol_set
                    Ms = 0
                    if self.Table_presets.cellWidget(row,13).isChecked(): Ms = self.MusicalNo.text()
    #build the full set
                    for z_num, z_pos in enumerate(Zs):
                        for w_num, w in enumerate(Ws):
                            for p_num, p in enumerate(Ps):
                                image = {'Name':name_,'Illumination':int(LS_),'ND':int(ND_),'Power':int(power_),'Wavelength':int(w),'Wnumber':int(w_num),
                                         'Polarisation':int(p),'Pnumber':int(p_num),'Exposure':int(exposure_),'Binning':int(binning_),'Filter':filter_,
                                         'Zposition':float(z_pos + location[2]),'Znumber':int(z_num),'Zseparation': Zseparation, 'Channel':int(channel),
                                         'Xlocation':location[0],'Ylocation':location[1], 'Location':L, 'Musical':int(Ms)}
    #append to the master imaging set
                                imaging_set = imaging_set.append(image, ignore_index=True)
#sort this list according to desired loop priority order
        if self.ImageLoopOrder.currentIndex() == 0: imaging_set = imaging_set.sort_values(by=['Location','Channel','Zposition','Wavelength','Polarisation'])
        if self.ImageLoopOrder.currentIndex() == 1: imaging_set = imaging_set.sort_values(by=['Location','Channel','Zposition','Polarisation','Wavelength'])
        if self.ImageLoopOrder.currentIndex() == 2: imaging_set = imaging_set.sort_values(by=['Location','Channel','Wavelength','Zposition','Polarisation'])
        if self.ImageLoopOrder.currentIndex() == 3: imaging_set = imaging_set.sort_values(by=['Location','Channel','Wavelength','Polarisation','Zposition'])
        if self.ImageLoopOrder.currentIndex() == 4: imaging_set = imaging_set.sort_values(by=['Location','Channel','Polarisation','Zposition','Wavelength'])
        if self.ImageLoopOrder.currentIndex() == 5: imaging_set = imaging_set.sort_values(by=['Location','Channel','Polarisation','Wavelength','Zposition'])

        imaging_set = imaging_set.reset_index()
        imaging_set = imaging_set.drop(columns=['index'])
        
        pd.options.display.max_columns=50
        pd.set_option('display.width',200)
#        print imaging_set.head(50)
        return imaging_set
    
# =============================================================================
# tile scan functinos
# =============================================================================
    def stage_scan(self, w=100, h=100, d=300, z_separation=30):
        self.tile_scan_thread = threading.Thread(target=self.do_stage_scan, name="tile scan", args=(self,))
        self.in_experiment = True
        self.tile_scan_thread.start()   
    
    #3D version - running in thread
    def do_stage_scan(self, width=500, height=500, depth=300, z_separation=30):
    #        this function moves across a large field performing a crude z-stack at each position
    #        Image data can then be built into a larger map to aid with sample finding
    #        accepts a single position to use as the center, and a set of dimension for the 
    #        overall scan volume
        return
        FOV = 302
        width = 500
    #         use current position as center
        [Cx,Cy,Cz] = self.ASI.get_position()
    #         use the imaging limits and user settings to limit the total scan area
        limits = self.ASI.imaging_limits
        start_x = int(max(limits[0][1],Cx-(width/2)))
        start_y = int(max(limits[1][1],Cy-(height/2)))
        end_x   = min(start_x + width,limits[0][0])
        end_y   = min(start_y + height,limits[1][0])
        x_set = range(start_x,end_x+FOV,FOV)
        x_numbers = range(0,len(x_set)*FOV,FOV)
        y_set = range(start_y,end_y+FOV,FOV)
        y_numbers = range(0,len(y_set)*FOV,FOV)
        z_set = range(max(int(Cz)-(depth/2),limits[2][1]),min(int(Cz)+(depth/2),limits[2][0]),z_separation)
        z_numbers = range(len(z_set))
        
    #                   X,Y,Z real, X,Y,Z map
    

        position_list = []
        for nx, x in enumerate(x_set):
            for ny, y in enumerate(y_set):
                for nz, z in enumerate(z_set):
                    position_list.append([x-z,y,z,x_numbers[nx],y_numbers[ny],z_numbers[nz]])
                z_set.reverse()
                z_numbers.reverse()
            y_set.reverse()
            y_numbers.reverse()
        if len(position_list) == 0:
            print "stage position outside of imaging limits"
            self.information("Tile scan not possible: stage position outside of imaging limits", 0)  
            return
        
        self.image_map = np.zeros((FOV*len(x_set),FOV*len(x_set),len(z_set)))
        
        self.LEDmask = io.imread('tile_mask.tif')
    #set up camera
        settings = self.build_imaging_set(tile_scan=True)                 
        self.Camera.set_binning(0)
        self.Camera.set_exposure(settings['Exposure'])
        
        self.Arduino.set_servo(7)
        self.Arduino.LS_select('L')
        self.Arduino.set_LED_power(settings['Power'])
        self.Filter.set_position(settings['Filter'])
        self.ASI.set_speed()
        self.ASI.backlash_compensation(False)
        self.Arduino.reset_stage_flag()
        self.ASI.move_to(X=position_list[0][0],Y=position_list[0][1],Z=position_list[0][2])
        self.Arduino.wait_for_stage(timeout=1000) #blocking function
        self.ASI.backlash_compensation(False)
#        self.mmc.setProperty("Flash 4", "ScanMode","2")
        self.Camera.external_mode()
        self.mmc.initializeCircularBuffer()
        self.mmc.prepareSequenceAcquisition("TSICam")
        self.mmc.startSequenceAcquisition("TSICam",len(position_list),settings['Exposure'],False)
    
        self.position_saveQ = Queue.Queue()
        wt = threading.Thread(target=self.image_worker, name='tile_scan_worker')
        wt.start()
        t0 = time.time()
        
        prev_x=-99999
        prev_y=-99999
        prev_z=-99999
    #move through the positions
       
        for position in position_list:
            
            self.Arduino.reset_stage_flag()
            if position[0]!=prev_x: 
                print 'x', position[0]
                self.ASI.move_to(X=position[0]) 
                prev_x=position[0]
            if position[1]!=prev_y: 
                print 'y', position[1]
                self.ASI.move_to(Y=position[1]) 
                prev_y=position[1]
            if position[2]!=prev_z: 
                print 'z', position[2]
                self.ASI.move_to(Z=position[2]) 
                prev_z=position[2]
            t0 = time.time()
            self.Arduino.wait_for_stage(timeout=300) #blocking function
            print 'wait for stage', time.time() - t0
            start_wait = time.time()
            self.Arduino.sync_acquire(settings['Exposure'])

            self.position_saveQ.put(position) 
            self.Arduino.wait_for_exposure_end(start_wait + (float(settings['Exposure'])/1000.0) + 0.2)

    
        self.ASI.backlash_compensation(True)
        self.Arduino.closeShutter()
        self.ASI.move_to(X=Cx,Y=Cy,Z=Cz)
        self.mmc.stopSequenceAcquisition()
        self.Camera.internal_mode()
#        self.mmc.setProperty("TSICam", "ScanMode","1")
        self.mmc.setAutoShutter(True)
        while self.mmc.getRemainingImageCount() > 0: pass
    
        self.in_experiment = False
        wt.join()
        print 'total tile time:', time.time() - t0
    
    def image_worker(self):
#        count = 0
        while self.in_experiment:
            if self.mmc.getRemainingImageCount() > 0:
                
                p = self.position_saveQ.get()
                tile = self.mmc.popNextImage() 
                tile = np.rot90(np.fliplr(tile),1)
#                temp save images
#                filename = 'bg_%s.tif' %count
#                tf.imsave(filename, tile)
                tile = resize(tile, (302, 302)) #* self.LEDmask
                self.image_map[p[3]:p[3]+302,p[4]:p[4]+302,p[5]] = tile 
                self.Image_displayQ.put(np.transpose(self.image_map, (0,1,2))) 
#                count +=1
    
    
    def closeEvent(self, event): #to do upon GUI being closed
#        print threading.enumerate()
        self.Gui_to_Thread[-1] = "stop"
        self.in_experiment = False
        self.Q_checker.stop()
        self.pickle_Table()
        self.pickle_positions()
        self.Camera.close()
        self.Maitai.close()
        self.Filter.close()
        self.Arduino.close()
        self.USB_HUB.close()
        self.ASI.close()
        self.HWP.close()
        self.mmc.unloadAllDevices()
        self.mmc.reset()
        
if __name__ == '__main__':
    app = 0
    app = QtGui.QApplication(sys.argv)
    gui = LScontroller()
    gui.show()
    app.exec_()