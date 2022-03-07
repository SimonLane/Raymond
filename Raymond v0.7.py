# -*- coding: utf-8 -*-
"""
Created on Wed May  5 16:06:56 2021
v0.1
    Contains a dataframe for holding the experiment imaging parameters, and a ListWidget 
    for displaying the settings. Drag and Drop implemented to allow re-ordering of the
    different imaging sets
v0.2
    Added image viewer window and implemented live view from the Thorlabs camera 
    and the Chameleon camera
v0.3
    DONE
        get display settings working
        Add Timing, file controls
        Add information panel
        Create a separate panel or window for tile scan, allow zoom?
        display a map of the imaging area, with various settings
        User dependant config files
    TO-DO
        Create Connection indicator - currently output to the info log
        laser power settings into experiment builder and into data structure
        Save all settings to config file, not just the experiment builder
        Add GUI section for environmental information
        Add GUI section for Rayleigh image processing options
        Load calibration file for laser powers

@author: Simon
"""


import sys, time, threading, datetime, queue, glob, os, math, ctypes
import pandas           as pd
import numpy            as np
import pyqtgraph        as pg
from PyQt5 import QtGui, QtWidgets, QtCore
from scipy.ndimage.filters import gaussian_filter

if sys.platform == "win32":
    from thorlabs_tsi_sdk.tl_camera import TLCameraSDK
# my classes
    from Camera_TL          import Camera_TL
    from Camera_PG          import Camera_PG
    from Stage_ASI          import Stage_ASI

 
           
class Raymond(QtWidgets.QMainWindow):
    def __init__(self):
        super(Raymond, self).__init__()
        # self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Force GUI to stay on top
        
# =============================================================================
#  Microscope properties - edit as needed
# =============================================================================
    # GUI appearance
        self.font_size = 9
        self.border_size = 1
        self.GUI_colour = QtGui.QColor(75,75,75)
        self.GUI_font   = QtGui.QFont('Times',self.font_size)
        self.setFont(self.GUI_font)
        
        self.userList= []               # List of valid users, created at startup from list of folders in the save root directory 
        if sys.platform == "win32":
            self.demo_mode = False
            self.user_directory = 'D:'
            self.userList = glob.glob('D:\\**\\', recursive=False)
            print(self.userList)
            for i, item in enumerate(self.userList):
                self.userList[i] = item.split('\\')[-2]
        if sys.platform == "darwin":  
            self.demo_mode = True
            print('OS: ', sys.platform)
            self.user_directory = 'Users'
            self.userList = glob.glob('/Users/**/', recursive=False)
            for i, item in enumerate(self.userList):
                self.userList[i] = item.split('/')[-2]
        

    # available filters and binning modes
        self.filter_list = [
                "Empty",
                "610+-30, 650SP",
                "520+-20, 650SP",
                "Pol. V",
                "Pol. H",
                "Empty"
                ]
        self.binning_list = ['1','2','4','8']
    # available imaging modalities
        self.imaging_mode_list = ["Scattering", "Fluoresence", "MUSICAL", "SHG"]
    # available wavelengths
        self.ISetlightsource = [
                QtWidgets.QCheckBox('405'),
                QtWidgets.QCheckBox('488'),
                QtWidgets.QCheckBox('561'),
                QtWidgets.QCheckBox('660'),
                QtWidgets.QCheckBox('720'),
                QtWidgets.QCheckBox('760'),
                QtWidgets.QCheckBox('795'),
                QtWidgets.QCheckBox('830'),
                QtWidgets.QCheckBox('850'),
                QtWidgets.QCheckBox('910')
                ]
        
        
        
    # default settings applied to new imaging set
        self.newSet = pd.DataFrame({'ID':0,'Act':False,'Nam':'name','Exp':10,'Fil':0,'Bin':0,'Mod':0,'Mus':0,'Zed':True,
              'Wa1':True,'Wa2':False,'Wa3':False,'Wa4':False,'Wa5':False,'Wa6':False,
              'Wa7':False,'Wa8':False,'Wa9':False,'Wa10':False}, index=[-1])
    # basic properties for the UI
        
    # The dataframe used to hold imaging parameters for all defined imaging sets
        self.ISmemory = "ImagingParameters.txt"
        self.BSmemory = "Settings.txt"
        self.ISheaders = ['ID','Act','Nam','Exp','Fil','Bin','Mod','Mus','Zed','Wa1','Wa2','Wa3','Wa4','Wa5','Wa6','Wa7','Wa8','Wa9']
        self.PGcamSerial = '15322921'
    # Tile area options
        self.tileAreaNames = [
            '~5x5mm     (~2s)',
            '~8x8mm     (~10s)',
            '~14x14mm   (~25s)',
            '~22x22mm   (~70s)']    
        self.tileAreas          = [(2,1),(3,2),(5,3),(8,5)]
        self.tileDisplayLimits  = [(2.8),(4.5),(7.0),(11.1)]
# =============================================================================
# End editable properties      
# =============================================================================
        
        self.window_title = os.path.basename(__file__)
        self.ListWidgetfromIndex = 0    # keeps track of the last clicked item in inaging set list widget
        self.liveImaging = False        # Keeps track of if microsocpe is currently streaming from the camera
        self.currentImage = None        # Most recently acquired image, to be displayed on the GUI
        self.display_mode = 0           # color rendering of the GUI image window
        self.VF_image = []              # Most recent image from camera 3
        self.VFmap = np.zeros((231*23,231*23),dtype=np.float32)   # Holds the tiled viewfider image
        self.modifier_image = np.load('VFModifier.npy')
        self.display_mode = 0           # Update for each image (0) or maintain the current brightness (1)
        self.display_colour_mode = 0    # Use greyscale (0) or colourmap (1) LUT
        self.colourcmap = pg.ColorMap([0.0,0.25,0.50,0.75,1.0],[[0,0,0,255],[0,0,255,255],[0,255,0,255],[255,0,0,255],[255,255,255,255]])
        self.limitscmap = pg.ColorMap([0.0,0.01,0.99,1.0],[[0,255,0,255],[0,0,0,255],[255,255,255,255],[255,0,0,255]])
        self.defaultcmap = pg.ColorMap([0.0,1.0],[[0,0,0,255],[255,255,255,255]])
        self.max_pixel_value = 255                                              #default to 255, then update after querying camera
# =============================================================================
# Queues and threads
# =============================================================================
        self.tileScanQ = queue.Queue()
        self.tileScanQChecker = QtCore.QTimer()
        self.tileScanQChecker = QtCore.QTimer()
        self.tileScanQChecker.setInterval(10)
        self.tileScanQChecker.timeout.connect(self.imageToMap)

# =============================================================================
# Data Structures
# =============================================================================


# ~~~~~~~~~~~~~~~end~~~~~~~~~~~~~~

# build the UI
        self.initUI()
        self.information("Loaded GUI from: %s" %(__file__), 'g')
        
#  set blank image to the map
        self.mapImageWidget.setImage(self.VFmap, autoLevels=False, 
                    levels=(15,240), scale=(1/231,1/231), 
                    pos=(-11.9,-11.6), autoRange=False)
        
# connect to devices
        if not self.demo_mode:
        # ThorLabs
            self.TLsdk = TLCameraSDK()
            self.camera1        = Camera_TL(self, 'CS2100-M-1', 0, self.TLsdk)
            # self.camera2        = Camera_TL(self, 'CS2100-M-2', self.TLcameras[1], self.TLsdk)
            self.camera1.connect()
            self.camera1.hot_pixel_correction(True)
            # self.camera2.connect()
        # Point Grey
            self.camera3        = Camera_PG(self, 'Chameleon3')
            self.camera3.connect()
        # ASI Stage
            self.stage          = Stage_ASI(self, 'ASI Stage', 'COM9')
            self.stage.connect()
#  setup current user
            self.BasicSettings = pd.read_csv(self.BSmemory, index_col=0)# open settings file
            i = self.FileUserList.findText(self.BasicSettings.at[0,'LastUser'])# get the last user

        
        if self.demo_mode:
            self.information('Loaded interface in DEMO mode. No devices attached.', 'r')
            self.BasicSettings = pd.read_csv(self.BSmemory, index_col=0)# open settings file
            i = self.FileUserList.findText('Demo')# force last user to Demo in demo mode
            # if i == -1: i = self.FileUserList.findText('Simon')
        self.FileUserList.setCurrentIndex(i)# set user in file settings pane
        self.loadDataFrame() # load in the imaging sets

        
# Timers
        self.frametimer = QtCore.QTimer() # A timer for grabbing images from the camera buffer during live view mode
        
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
               #Setup Application Window
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def initUI(self):
        self.setScreenSize()
        self.setWindowTitle(self.window_title)
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Background, self.GUI_colour)
        self.setPalette(palette)
        
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
               #Setup Panes
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#~~~~~~~~~~~~~~~ Experiment Builder ~~~~~~~~~~~~~~~
    # widgets       
        self.NewISetButton       = QtWidgets.QPushButton('+')
        self.DelISetButton       = QtWidgets.QPushButton('-')
        self.NewISetButton.released.connect(lambda: self.addISet())
        self.DelISetButton.released.connect(lambda: self.deleteISet())
        
        self.ISetListWidget      = QtWidgets.QListWidget()
        self.ISetListWidget.itemClicked.connect(self.dataframe_to_GUI)
        self.ISetListWidget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.ISetListWidget.itemEntered.connect(self.storeFromIndex)
        self.ISetListWidget.model().rowsMoved.connect(self.ISetOrderChange)
        
        self.ISetActive          = QtWidgets.QCheckBox('active')
        self.ISetActive.clicked.connect(self.GUI_to_dataframe)
        
        self.NameLabel           = QtWidgets.QLabel('Name:')
        self.ISetName            = QtWidgets.QLineEdit('name')
        self.ISetName.editingFinished.connect(self.GUI_to_dataframe)
        
        self.ModeLabel           = QtWidgets.QLabel('Imaging Mode:')
        self.ISetMode            = QtWidgets.QComboBox()
        self.ISetMode.addItems(self.imaging_mode_list)
        self.ISetMode.currentIndexChanged.connect(self.update_imaging_mode)
        
        self.FilterLabel         = QtWidgets.QLabel('Filter:')
        self.ISetFilter          = QtWidgets.QComboBox()
        self.ISetFilter.addItems(self.filter_list)
        self.ISetFilter.currentIndexChanged.connect(self.GUI_to_dataframe)
        self.ISetFilter.setFixedWidth(90)
        
        self.BinningLabel        = QtWidgets.QLabel('Binning:')
        self.ISetBinning         = QtWidgets.QComboBox()
        self.ISetBinning.addItems(self.binning_list)
        self.ISetBinning.currentIndexChanged.connect(self.GUI_to_dataframe)
        
        self.ISetExposure        = QtWidgets.QLineEdit('10')
        self.ISetExposure.editingFinished.connect(self.GUI_to_dataframe)
        self.ExposureLabel       = QtWidgets.QLabel('Exposure(ms):')
        
        self.ISetZ               = QtWidgets.QCheckBox('Z-stack')
        self.ISetZ.clicked.connect(self.GUI_to_dataframe)
        
        self.ISetMusicalN        = QtWidgets.QLineEdit('50')
        self.ISetMusicalN.editingFinished.connect(self.GUI_to_dataframe)
        self.MusicalLabel        = QtWidgets.QLabel('Musical (n Frames):')
        
        self.LiveButton          = QtWidgets.QPushButton('Live')
        self.LiveButton.pressed.connect(self.liveView)
        self.GrabButton          = QtWidgets.QPushButton('Grab')
        self.GrabButton.pressed.connect(self.grabFrame)
        self.LightsourceLabel    = QtWidgets.QLabel('Wavelengths:')
        self.wavelengthButtonGroup = QtWidgets.QButtonGroup()

        self.ISetlightpower = []
        self.ISetlightpowerlabel = []
   
        self.ImagingSettingsSubGroup     = QtWidgets.QGroupBox('Settings')
        self.ImagingSettingsSubGroup.setLayout(QtWidgets.QGridLayout())
        
        for i, item in enumerate(self.ISetlightsource):
            self.wavelengthButtonGroup.addButton(item)
            item.stateChanged.connect(self.GUI_to_dataframe)
            self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[i],        i+2,2,1,1)
            
            self.ISetlightpower.append(QtWidgets.QSlider())
            self.ISetlightpower[i].setOrientation(QtCore.Qt.Horizontal)
            self.ISetlightpower[i].setMinimum(0)
            self.ISetlightpower[i].setMaximum(100)
            self.ISetlightpower[i].setTickInterval(5)
            self.ISetlightpower[i].setTickPosition(QtWidgets.QSlider.TicksBelow)
            self.ISetlightpower[i].setValue(0)
            self.ISetlightpower[i].valueChanged.connect(lambda: self.adjustLaserPower())
            
            self.ISetlightpowerlabel.append(QtWidgets.QLineEdit())
            self.ISetlightpowerlabel[i].setText('0')
            self.ISetlightpowerlabel[i].setFixedWidth(30)
            self.ISetlightpowerlabel[i].setReadOnly(True)
            
            self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightpower[i],         i+2,4,1,3)
            self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightpowerlabel[i],    i+2,3,1,1)

        self.wavelengthButtonGroup.setExclusive(True)

    # sub-assembly                                                                # (y x h w)    
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetActive,            0,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetZ,                 0,2,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.NameLabel,             1,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetName,              1,1,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ModeLabel,             2,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetMode,              2,1,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.FilterLabel,           3,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetFilter,            3,1,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.BinningLabel,          4,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetBinning,           4,1,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ExposureLabel,         5,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetExposure,          5,1,1,1)       
        self.ImagingSettingsSubGroup.layout().addWidget(self.MusicalLabel,          6,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetMusicalN,          6,1,1,1)
        
        self.ImagingSettingsSubGroup.layout().addWidget(self.LightsourceLabel,      1,2,1,1)

        self.ImagingSettingsSubGroup.layout().addWidget(self.LiveButton,            8,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.GrabButton,            8,1,1,1)

    # assembly                                                                # (y x h w)
        self.ExptBuildGroup     = QtWidgets.QGroupBox('Experiment Builder')
        self.ExptBuildGroup.setLayout(QtWidgets.QGridLayout())
        self.ExptBuildGroup.layout().addWidget(self.NewISetButton,               0,0,1,1)
        self.ExptBuildGroup.layout().addWidget(self.DelISetButton,               0,1,1,1)
        self.ExptBuildGroup.layout().addWidget(self.ISetListWidget,              1,0,5,3)
        self.ExptBuildGroup.layout().addWidget(self.ImagingSettingsSubGroup,     0,4,6,7)
        
#~~~~~~~~~~~~~~~ Image Display ~~~~~~~~~~~~~~~  
        self.ImageDisplayGroup              = QtWidgets.QGroupBox('Display')
        self.saveImageButton                = QtGui.QPushButton("Save image")
        self.saveImageButton.released.connect(self.saveSingleImage)
        self.imagewidget                    = pg.ImageView(view=pg.PlotItem())

        self.view_modes                     = [QtGui.QRadioButton('Auto'),QtGui.QRadioButton('Manual')]
        self.view_colour_modes              = [QtGui.QRadioButton('Greyscale'),QtGui.QRadioButton('Colour'),QtGui.QRadioButton('Limits')]
        self.view_modes[0].setChecked(True)
        self.view_colour_modes[0].setChecked(True)
        self.view_modes_group               = QtGui.QButtonGroup()
        self.view_colour_modes_group        = QtGui.QButtonGroup()
        for rb in range(2):
            self.view_modes[rb].released.connect(self.displayMode)
            self.view_modes_group.addButton(self.view_modes[rb],rb)
        for rb in range(3):
            self.view_colour_modes[rb].released.connect(self.displayMode)
            self.view_colour_modes_group.addButton(self.view_colour_modes[rb],rb)

        self.imagewidget.ui.roiBtn.hide()
        self.imagewidget.ui.menuBtn.hide()

        self.ImageDisplayGroup.setLayout(QtGui.QGridLayout())
        self.ImageDisplayGroup.layout().addWidget(self.view_modes[0],              0,0,1,2)
        self.ImageDisplayGroup.layout().addWidget(self.view_modes[1],              0,2,1,2)
        self.ImageDisplayGroup.layout().addWidget(self.view_colour_modes[0],       1,0,1,2)
        self.ImageDisplayGroup.layout().addWidget(self.view_colour_modes[1],       1,2,1,2)
        self.ImageDisplayGroup.layout().addWidget(self.view_colour_modes[2],       1,4,1,2)
        self.ImageDisplayGroup.layout().addWidget(self.saveImageButton,            0,6,1,2)

        self.ImageDisplayGroup.layout().addWidget(self.imagewidget,                2,0,10,10)

#~~~~~~~~~~~~~~~ View Finder ~~~~~~~~~~~~~~~  
        self.ViewFinderGroup            = QtWidgets.QGroupBox('Stage Map')
        self.viewFindButton             = QtGui.QPushButton("Live")
        self.viewFindButton.released.connect(self.showViewFinder)
        
        self.VFModButton                = QtGui.QPushButton("set BG")
        self.VFModButton.released.connect(self.update_modifier_image)
        
        self.tileAreaSelection          = QtGui.QComboBox()
        for item in self.tileAreaNames:
            self.tileAreaSelection.addItem(item)
        self.mapPlot = pg.PlotItem()
        self.mapImageWidget             = pg.ImageView(view = self.mapPlot)

        # proxy = pg.SignalProxy(self.mapPlot.scene().sigMouseClicked,
        #                         rateLimit=60, slot=self.on_click_event)
        self.mapImageWidget.getImageItem().mouseClickEvent = self.on_click_event
        
        self.mapImageWidget.ui.roiBtn.hide()
        self.mapImageWidget.ui.menuBtn.hide()
        # self.mapImageWidget.ui.histogram.hide()
        self.mapImageWidget.view.setXRange(-11, 11, padding=0)
        self.mapImageWidget.view.setYRange(-11, 11, padding=0)
        self.mapImageWidget.view.setFixedHeight(350)
        self.mapImageWidget.view.setFixedWidth(350)
        
        self.tileScanButton             = QtGui.QPushButton("Tile Scan")
        self.tileScanButton.released.connect(self.setupTileScan)
                                                                              # (y x h w)
        self.ViewFinderGroup.setLayout(QtGui.QGridLayout())
        self.ViewFinderGroup.layout().addWidget(self.mapImageWidget,            0,0,10,10)
        self.ViewFinderGroup.layout().addWidget(self.viewFindButton,            11,0,1,2)
        self.ViewFinderGroup.layout().addWidget(self.VFModButton,               11,2,1,2)
        self.ViewFinderGroup.layout().addWidget(self.tileAreaSelection,         11,4,1,3)
        self.ViewFinderGroup.layout().addWidget(self.tileScanButton,            11,7,1,2)

#~~~~~~~~~~~~~~~ Information Pane ~~~~~~~~~~~~~~~ 

        self.Information_text_window = QtGui.QTextEdit()
        self.Information_text_window.setReadOnly(True)
        self.Information_text_window.setStyleSheet("background-color: rgb(75,75,75);")
        self.Information_text_window.insertHtml("")

# Add widgets
        self.InfoGroup          = QtGui.QGroupBox('Information')
        self.InfoGroup.setLayout(QtGui.QGridLayout())
        self.InfoGroup.layout().addWidget(self.Information_text_window,         1,0,1,1)

#~~~~~~~~~~~~~~~ Experiment progress Pane ~~~~~~~~~~~~~~~ 
        self.Expt_Start_button   = QtGui.QPushButton('Start Experiment')
        self.Expt_Start_button.released.connect(self.Imaging_setup)
        self.progress_c          = QtGui.QProgressBar()
        self.progress_c.setFixedHeight(10)
        self.progress_c.setFixedWidth(200)

        self.progress_z          = QtGui.QProgressBar()
        self.progress_p          = QtGui.QProgressBar()
        self.progress_t          = QtGui.QProgressBar()
        self.progress_c_label    = QtWidgets.QLabel('        channel:')
        self.progress_z_label    = QtWidgets.QLabel('      z-positon:')
        self.progress_p_label    = QtWidgets.QLabel('stage position:')
        self.progress_t_label    = QtWidgets.QLabel('      timepoint:')

        self.ProgressGroup       = QtGui.QGroupBox('Experiment Progress')
        self.ProgressGroup.setLayout(QtGui.QGridLayout())
        self.ProgressGroup.layout().addWidget(self.Expt_Start_button,           0,0,1,3)
        self.ProgressGroup.layout().addWidget(self.progress_c_label,            1,0,1,2)
        self.ProgressGroup.layout().addWidget(self.progress_z_label,            2,0,1,2)
        self.ProgressGroup.layout().addWidget(self.progress_p_label,            3,0,1,2)
        self.ProgressGroup.layout().addWidget(self.progress_t_label,            4,0,1,2)
        self.ProgressGroup.layout().addWidget(self.progress_c,                  1,2,1,4)
        self.ProgressGroup.layout().addWidget(self.progress_z,                  2,2,1,4)
        self.ProgressGroup.layout().addWidget(self.progress_p,                  3,2,1,4)
        self.ProgressGroup.layout().addWidget(self.progress_t,                  4,2,1,4)

#~~~~~~~~~~~~~~~ File save Pane ~~~~~~~~~~~~~~~ 
#Fileing Widgets

        self.FileUserLabel                  = QtGui.QLabel('User:')
        self.FileUserList                   = QtGui.QComboBox()
#generate user list
        
        for item in self.userList:
            if not item.__contains__('.') and len(item) < 15:
                self.FileUserList.addItem(item)
                print(item)
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
        self.FileGroup          = QtGui.QGroupBox('Save Options')
        self.FileGroup.setLayout(QtGui.QGridLayout())
        self.FileGroup.layout().addWidget(self.FileUserLabel,                   0,0)
        self.FileGroup.layout().addWidget(self.FileUserList,                    0,1)
        self.FileGroup.layout().addWidget(self.FileExptNameLabel,               1,0,1,1)
        self.FileGroup.layout().addWidget(self.FileExptName,                    1,1,1,3)
        self.FileGroup.layout().addWidget(self.FileAddress,                     2,0,1,4)
        self.FileGroup.layout().addWidget(self.cropCheckbox,                    3,0,1,2)
        self.FileGroup.layout().addWidget(self.eightCheckbox,                   3,2,1,2)        

#~~~~~~~~~~~~~~~ Timing Pane ~~~~~~~~~~~~~~~ 

#timing widgets
        self.TimingLabel1                   = QtGui.QLabel('No. Loops:')
        self.TimingLoops                    = QtGui.QLineEdit('1')
        self.TimingLabel2                   = QtGui.QLabel('Interval (s):')
        self.TimingInterval                 = QtGui.QLineEdit('300')
        self.TimingLabel3                   = QtGui.QLabel('Duration (hh:mm:ss):')
        self.TimingDuration                 = QtGui.QLineEdit('15:00:00')
        self.TimingDuration.setReadOnly(True)
        self.TimingLoops.setFixedWidth(60)
        self.TimingInterval.setFixedWidth(60)
        self.TimingDuration.setFixedWidth(60)
        
        self.TimingLoops.setValidator(QtGui.QIntValidator(1,10000))
        self.TimingInterval.setValidator(QtGui.QIntValidator(1,10000))

        self.TimingLoops.returnPressed.connect(self.update_duration)
        self.TimingLoops.textChanged.connect(self.update_duration)
        self.TimingInterval.returnPressed.connect(self.update_duration)
        self.TimingInterval.textChanged.connect(self.update_duration)
# Add widgets to group
        self.TimingGroup        = QtGui.QGroupBox('Timing')
        self.TimingGroup.setLayout(QtGui.QGridLayout())
        self.TimingGroup.layout().addWidget(self.TimingLabel1,                  0,0,1,1)
        self.TimingGroup.layout().addWidget(self.TimingLoops,                   0,1,1,1)
        self.TimingGroup.layout().addWidget(self.TimingLabel2,                  1,0,1,1)
        self.TimingGroup.layout().addWidget(self.TimingInterval,                1,1,1,1)
        self.TimingGroup.layout().addWidget(self.TimingLabel3,                  2,0,1,1)
        self.TimingGroup.layout().addWidget(self.TimingDuration,                2,1,1,1)
    

#~~~~~~~~~~~~~~~ Z-stack Pane ~~~~~~~~~~~~~~~ 
        

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
        self.ZSlices.setFixedWidth(50)
        self.ZSeparation.setFixedWidth(50)
        self.ZSpan.setFixedWidth(50)

        self.ZSlices.returnPressed.connect(lambda: self.adjustZStack(0))
        self.ZSeparation.returnPressed.connect(lambda: self.adjustZStack(1))
        self.ZSpan.returnPressed.connect(lambda: self.adjustZStack(2))

# Add widgets
        self.ZSlice             = QtGui.QGroupBox('Z-stack')
        self.ZSlice.setLayout(QtGui.QGridLayout())
        self.ZSlice.layout().addWidget(self.ZLabel1,                            0,0,1,1)
        self.ZSlice.layout().addWidget(self.ZSlices,                            0,1,1,2)
        self.ZSlice.layout().addWidget(self.ZLabel2,                            1,0,1,1)
        self.ZSlice.layout().addWidget(self.ZSeparation,                        1,1,1,2)
        self.ZSlice.layout().addWidget(self.ZLabel3,                            2,0,1,1)
        self.ZSlice.layout().addWidget(self.ZSpan,                              2,1,1,2)
        self.ZSlice.layout().addWidget(self.ZDemo,                              3,0,1,3)
        
#==============================================================================
# Overall assembly
#==============================================================================
        OverallLayout = QtWidgets.QGridLayout()
#        using a 20x20 grid for flexible arrangement of the panels
#Left-hand column                                                             # (y x h w)
        OverallLayout.addWidget(self.ImageDisplayGroup,                         0,0,17,12)
#Right-hand column                                                                                
        OverallLayout.addWidget(self.ExptBuildGroup,                            0,12,6,9)
        OverallLayout.addWidget(self.ViewFinderGroup,                           6,15,10,6)
# bottom section        
        OverallLayout.addWidget(self.FileGroup,                                 17,0,3,4)
        OverallLayout.addWidget(self.TimingGroup,                               17,4,3,4)
        OverallLayout.addWidget(self.ZSlice,                                    17,8,3,3)
        OverallLayout.addWidget(self.ProgressGroup,                             17,11,3,3)
        OverallLayout.addWidget(self.InfoGroup,                                 17,14,3,7)
        for item in [self.ImageDisplayGroup,self.ExptBuildGroup,self.ViewFinderGroup,self.FileGroup,
                      self.ProgressGroup,self.TimingGroup,self.ZSlice,self.InfoGroup]:
            item.setFlat(True)
        self.ImageDisplayGroup.setFlat(True)
        
        self.MainArea = QtWidgets.QFrame()
        self.MainArea.setStyleSheet("""font: %dpt Modum;""" %(self.font_size))
        self.MainArea.setLineWidth(self.border_size)
        self.MainArea.setLayout(OverallLayout)
        self.setCentralWidget(self.MainArea)

# =============================================================================
#   Main imaging Loop - Setup
# =============================================================================
# Prepare for imaging
    # Build experiment
    def Imaging_setup(self):
        if self.Expt_Start_button.text() == 'Stop Experiment':
            print('stop button press')
            self.Expt_Start_button.setText('Stopping...')
#            self.Gui_to_Thread[-1] = 'stop'
#            self.ImagingLoopThread.join()
            
        if self.Expt_Start_button.text() == 'Start Experiment':
            self.pickle_Table() #save all settings and positions in case of crash whilst imaging
            self.pickle_positions()
            imaging_set = self.build_imaging_set() 
            timing_interval = int(self.TimingInterval.text())
            imaging_loops = int(self.TimingLoops.text())
            crop = self.cropCheckbox.isChecked()
            eight = self.eightCheckbox.isChecked()
# test for disk space (in Gb)
            if not self.demo_mode:
                req_space = round((imaging_set[imaging_set.Binning == 0].shape[0]*0.008193) + 
                                  (imaging_set[imaging_set.Binning == 1].shape[0]*0.002049) + 
                                  (imaging_set[imaging_set.Binning == 2].shape[0]*0.000513),1)*imaging_loops*imaging_set['Location'].max()
                free_space = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p('D:'), None, None, ctypes.pointer(free_space))
                free_space = round(free_space.value/ (1024.0*1024.0*1024.0),1)
                if free_space-1 < req_space:    self.information("Imaging not possible: %sGb required, %sGb available" %(req_space,free_space), 'r')
                else: self.information("Storage %sGb required, %sGb available" %(req_space,free_space), 'g')
# Test for required hardware
#            Camera
#            Microscope Control board
#            Laser Control board
#            Filter
#            ETL
#            Stage
#            Scan mirror
#            Visible lasers
#            NIR lasers
#            SLM

            self.Expt_Start_button.setText('Stop Experiment')
    # Start job in a new thread
    
    # Start threadsafe timers and queues to handle data flow and GUI updates
    
    # Send to Control board

# =============================================================================
#   Main imaging Loop - Imaging Thread
# =============================================================================
    def Imaging_loop(self, imaging_set):
        timepoints  = [0]
        positions   = [0]
        channels    = [0]
        z_slices    = [0]
        wavelengths = [0]
        
        
        for t in timepoints:
#            Timing gate
            for p in positions:
#                Stage positioning gate
                for c in channels:
                    for z in z_slices:
                        for w in wavelengths:
                            time.sleep(0.3)



# =============================================================================
#   ViewFinder functions
# =============================================================================

    def on_click_event(self, event):
        event.accept()
        if event.double():
            px = event.pos()
            print ('double click: ', int(px.x()),int(px.y()))
            print('um:', self.VFpx2um(px.x(), px.y()) )
            xum, yum = self.VFpx2um(px.x(), px.y())
            self.stage.move_to(X=xum, Y=yum )
    
    def setupTileScan(self):
        #set stage to 'rapid mode'
        self.stage.rapidMode(rapid=True)
        # start live imaging on camera 3
        self.showViewFinder()
        # start a timer to check for signals from the worker
        self.tileScanQChecker.start()
        #start the worker thread to control the stage
    # To Do - update visible range to match tiled area dimensions
        r = self.tileDisplayLimits[self.tileAreaSelection.currentIndex()]
        self.mapImageWidget.view.setXRange(-r, r, padding=0)
        self.mapImageWidget.view.setYRange(-r, r, padding=0)
        self.tileScanThread = threading.Thread(target=self.doTileScan,
                name="tile scan", args=())
        self.tileScanThread.start()    

    def VFum2px(self, umx,umy):
        pxx = (umx * 0.231) + (10.5*231)
        pxy = (231*23) - ((umy * 0.231) + (13.5*231))
        return list((round(pxx),round(pxy)))
    
    def VFpx2um(self, pxx,pxy):
        umx = ((pxx - 2656) / 0.231) - 1385
        umy = ((pxy - 2656) / -0.231) + 2217 
        return list((umx,umy))
    
    def doTileScan(self): # Runs in thread
        tilesX, tilesY = self.tileAreas[self.tileAreaSelection.currentIndex()]
        fp = True
        t = time.time()
        FOVx = 2770 #um
        FOVy = 4433 #um
        Xrange = (FOVx)*tilesX
        Yrange = (FOVy)*tilesY
        # currentX = 0 #To do - get current stage position
        # currentY = 0
        Xums = list(range(int(Xrange/-2)+int(FOVx*0.5),int(Xrange/2)+int(FOVx*0.5),FOVx)) #in microns
        Yums = list(range(int(Yrange/-2)+int(FOVy*0.5),int(Yrange/2)+int(FOVy*0.5),FOVy)) #in microns
        z  = 0 #to do - update to current Z position
        for yn, y in enumerate(Yums):
            for xn, x in enumerate(Xums):
                self.stage.move_to(x,y,z)
                while(True):
                    if not self.camera3.is_live or not self.stage.flag_CONNECTED:
                        self.tileScanQChecker.stop()
                        self.stage.rapidMode(rapid=False)
                        print("tile scan aborted")
                        return
                    s = self.stage.is_moving()
                    if s: time.sleep(0.1)
                    else:
                        self.tileScanQ.put(self.VFum2px(x,y))
                        if fp: 
                            t = time.time()
                            fp = False
                        break
            Xums.reverse()
        time.sleep(0.1)
        self.showViewFinder() #turn off live view
        self.tileScanQChecker.stop()
        self.stage.rapidMode(rapid=False)
        print("tile scan complete: ", time.time() - t, "s")
    
    def showViewFinder(self):
        if self.camera3.flag_CONNECTED:
            if not self.liveImaging:
                print('starting viewfinder')
                # set exposure
                self.camera3.exposure(5000)
                self.camera3.live_mode()
                self.frametimer.setSingleShot(False)
                self.frametimer.timeout.connect(self.grabImageFromVF)
                self.frametimer.start(30)
                self.viewFindButton.setText('Stop')
                self.liveImaging = True
            else:
                print('stopping viewfinder')
                self.frametimer.stop()
                self.camera3.stop_live()
                self.viewFindButton.setText('Live')
                self.liveImaging = False                
                
    def grabImageFromVF(self):
        image = self.camera3.getFrame() #is this the newest frame in the buffer or the oldest?
        # image = np.flip(np.rot90(image),1)
        if len(image) != 0:
            self.display_image(image)
            self.VF_image = image.astype('float32') #keep a copy of the last image in memory for use in the map
 
    def updateViewFindExposure(self):
        e = self.viewFindExposure.text()
        self.camera3.exposure(e)
    
    def update_modifier_image(self):
        image = self.VF_image[640:1280,:] + 1
        mean = np.mean(image)
        print("mean image value: ", mean)
        flat_image = np.ones((640,1024),dtype=np.float32) * mean
        self.modifier_image = gaussian_filter(flat_image/image,sigma=3)
        np.save("VFmodifier",self.modifier_image)
        print("modifier image updated")
        
    def imageToMap(self):
        if(self.tileScanQ.qsize() > 0):
            x,y = self.tileScanQ.get() #in pixels
            image = self.VF_image[640:1280,:]
            # print('____________________')
            # print('new image shape: ', image.shape)
            # print('map shape:       ', self.VFmap.shape)
            # print('image position:  ', x,y)
            self.VFmap[x:x+image.shape[0], y:y+image.shape[1]] = image * self.modifier_image
            #set to the map
            self.mapImageWidget.setImage(self.VFmap, autoLevels=False, 
                    levels=(15,240), scale=(1/231,1/231), 
                    pos=(-11.9,-11.6), autoRange=False)
            
            
# =============================================================================
#  Image Display Functions
# =============================================================================

    def saveSingleImage(self):
        # to do - get image metadata and use it to gereate the file name
        #md = dict(Lightsource=l, Wavlength=wl, Filter=f, Binning=b, Exposure=e)
        #suggested_name = "%snm %s %sms %s.tif" %(wl,f,e,b)

        #name = QtGui.QFileDialog.getSaveFileName(self,"Save image as",suggested_name)
        #if name[-4] != ".":  #if the file name does not already contains three letter extension then add '.tif'
       #     name = "%s.tif" %(name)
        
        #tf.imsave(name, self.Camera.current_img, metadata=md)
        pass
    
    def displayMode(self):
        self.display_mode = self.view_modes_group.checkedId()
        self.display_colour_mode = self.view_colour_modes_group.checkedId()
        if self.display_colour_mode == 0:
            self.imagewidget.setColorMap(self.defaultcmap)
        if self.display_colour_mode == 1:
            self.imagewidget.setColorMap(self.colourcmap)
        if self.display_colour_mode == 2:
            self.imagewidget.setColorMap(self.limitscmap)
    
    def liveView(self):
        if self.liveImaging == False:
        # disable access to the imaging settings whilst imaging
            
        # send relevant settings to the camera
            row = self.ISetListWidget.currentRow()
            # self.camera1.set_ROI(x, y, w, h) #to implement later
            self.camera1.binning(self.ImagingSets.at[row, 'Bin'])
            self.camera1.exposure(self.ImagingSets.at[row, 'Exp'])
            
            # TO DO LATER - send relveant commands to other hardware, 
            #       e.g. illumination on
            #       scanner y to resonant scan mode???
            #       scanner z to z position
            #       ETL to z
            #       Filter
            
            # set camera to live mode
            self.camera1.live_mode()
            # start a timer to poll the camera for image 
            self.frametimer.setSingleShot(False)
            self.frametimer.timeout.connect(self.grabImageFromCameraBuffer)
            self.frametimer.start(30) #attempt to display images at ~30fps in this mode
            
            # set button to read 'STOP'
            self.LiveButton.setText('Stop')
            self.liveImaging = True
        else:  # Camera is already performing live imaging
            print('Stopping Live view')            # stop the camera
            self.camera1.stop_live()
            # stop the frametimer
            self.frametimer.stop()
            # permit access to the imaging settings
            
            # set the button to read 'Live'
            self.LiveButton.setText('Live')
            self.liveImaging = False
            
    def grabImageFromCameraBuffer(self): 
        # Function called periodically by a timer during live view mode
        frame = self.camera1.getFrame()
        if frame:
            # print('n frames: ', frame.frame_count)
            #display it in GUI
            self.currentImage = np.copy(frame.image_buffer)
            self.display_image(self.currentImage)
            
    def grabFrame(self): #Grab a single frame, using the current settings, and display to the GUI
        # TO DO check if camera already running
        row = self.ISetListWidget.currentRow()
        self.camera1.binning(self.ImagingSets.at[row, 'Bin'])
        self.camera1.exposure(self.ImagingSets.at[row, 'Exp'])
        # TO DO LATER - send relveant commands to other hardware, 
            #       e.g. illumination on
            #       scanner y to resonant scan mode???
            #       scanner z to z position
            #       ETL to z
            #       Filter
            
        # TO DO - wait for signal that all hardware finished moving
        self.camera1.grab_mode()
        time.sleep(self.camera1.frame_time()/1000.0)
        self.grabImageFromCameraBuffer()
        self.camera1.stop_live()
        
    def display_image(self, image):
                #get 'mode' from radio state (manual, auto, saturation check)
        if self.display_mode == 0: levels = True
        if self.display_mode == 1: levels = False
        n_axes = len(image.shape)
        if n_axes == 2: 
            # image = numpy.rot90(numpy.fliplr(image),1) #        image flip (horizontal axis) and rotation (90 deg anti-clockwise)
            # image = np.fliplr(image)
            self.imagewidget.setImage(image, autoLevels=levels)
        if n_axes == 3:
            self.imagewidget.setImage(image, autoLevels=levels, axes={'t':2, 'x':0, 'y':1})

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
            self.TimingDuration.setText('%02d:%02d:%02d' %(DurationH,DurationM,DurationS))

            #timing has changed, send to imaging thread
            # self.Gui_to_Thread[1] = [interval,loops]

        except:
            self.information("Please enter valid interval and loop values.", 'y')
            
# =============================================================================
#  Experiment Builder functions
# =============================================================================

    def addISet(self):
        # add a new Iset to the top of the list Widget,
        self.ISetListWidget.insertItem(0, str(self.ISetListWidget.count()))

        # select the new ISet in the list widget
        self.ISetListWidget.setCurrentRow(0)
        # Prepare to add to the dataframe
        # create a blank/default set of imaging parameters
        # add the new set to the pandas dataframe and use indexing to put it at the top
        self.ImagingSets = self.ImagingSets.append(self.newSet, ignore_index=False)
        self.ImagingSets = self.ImagingSets.sort_index().reset_index(drop=True)
        self.ImagingSets = self.ImagingSets.reindex(axis=1)
        self.ImagingSets['ID'] = range(self.ImagingSets.shape[0])
        # set the new (blank) values to the GUI
        self.set_ISetValues_to_GUI()
                       
    def deleteISet(self):
        d = self.ISetListWidget.currentRow()
        #delete from dataframe
        self.ImagingSets = self.ImagingSets.drop(axis = 0, labels=d)
        for i in range(self.ImagingSets.shape[0]): self.ImagingSets.iloc[[i],[0]] = i
        # sort index by ID
        self.ImagingSets = self.ImagingSets.sort_values(by='ID',ascending=True)
        # reset the main leftmost index
        self.ImagingSets = self.ImagingSets.reset_index(drop=True)
        self.saveDataFrame()
        #delete from ListWidget
        self.ISetListWidget.takeItem(d)
        self.ISetListWidget.setCurrentRow(min(d,self.ImagingSets.shape[0]))
        self.set_ISetValues_to_GUI()
    
    def storeFromIndex(self): #store index of last clicked iten in the list view
        self.ListWidgetfromIndex = self.ISetListWidget.currentRow()
        
    def ISetOrderChange(self, event):
        # Drag and drop event detected on the ISetListWidget. 
        # need to rearrange the ImagingSets row order to match
        n_items = self.ImagingSets.shape[0]
        from_ = int(self.ListWidgetfromIndex)
        to_ = int(self.ISetListWidget.currentIndex().row())
        # shift 'ID' to reflect changes from the drag and drop
        a = np.arange(n_items)
        a = np.delete(a,to_)
        a = np.insert(a,from_,to_)
        #apply new IDs
        for i, val in enumerate(a):
            self.ImagingSets.loc[[i],['ID']] = val
        # sort index by ID
        self.ImagingSets = self.ImagingSets.sort_values(by='ID',ascending=True)
        # reset the main leftmost index
        self.ImagingSets = self.ImagingSets.reset_index(drop=True)

    def GUI_to_dataframe(self):
        pass
        # run this function to push settings from the GUI into the dataframe 
        n = self.ISetListWidget.currentRow()
        # Push the changes into the data frame
        self.ImagingSets.at[n,'Act'] = self.ISetActive.isChecked()
        self.ImagingSets.at[n,'Nam'] = self.ISetName.text()
        self.ImagingSets.at[n,'Mod'] = self.ISetMode.currentIndex()
        self.ImagingSets.at[n,'Fil'] = self.ISetFilter.currentIndex()
        self.ImagingSets.at[n,'Bin'] = self.ISetBinning.currentIndex()
        self.ImagingSets.at[n,'Exp'] = self.ISetExposure.text()
        self.ImagingSets.at[n,'Zed'] = self.ISetZ.isChecked()
        self.ImagingSets.at[n,'Mus'] = self.ISetMusicalN.text()
        s = False
        for i, item in enumerate(self.ISetlightsource):
            if s == False or self.ISetMode.currentIndex() == 0:
                self.ImagingSets.at[n,'Wa%s' %str(i+1)] = item.isChecked()
                self.ImagingSets.at[n,'Po%s' %str(i+1)] = self.ISetlightpower[i].value()
            if item.isChecked:
                s = True

        # set Values to GUI - deals with changes in mode
        self.dataframe_to_GUI()
        
    def dataframe_to_GUI(self):
        # get values from the dataframe and apply to the widgets in the GUI
        n = self.ISetListWidget.currentRow()
        IS = self.ImagingSets.loc[n]
        self.ISetListWidget.currentItem().setText('%s \t\t %s' %(IS['Nam'],self.imaging_mode_list[IS['Mod']])) #update name
        theFont = QtGui.QFont()
        if bool(IS['Act']) == True:
            self.ISetListWidget.currentItem().setBackground(QtGui.QBrush(QtGui.QColor('green')))
            theFont.setBold(True)
            theFont.setUnderline(True)
        else:
            self.ISetListWidget.currentItem().setBackground(QtGui.QBrush(QtGui.QColor('light grey')))
            theFont.setBold(False)
            theFont.setUnderline(False)
        self.ISetListWidget.currentItem().setFont(theFont)
        self.ISetActive.setChecked(bool(IS['Act']))
        self.ISetName.setText('%s' %IS['Nam'])
        self.ISetMode.setCurrentIndex(IS['Mod'])
        self.ISetFilter.setCurrentIndex(IS['Fil'])
        self.ISetBinning.setCurrentIndex(IS['Bin'])
        self.ISetExposure.setText('%s' %IS['Exp'])
        self.ISetZ.setChecked(bool(IS['Zed']))
        self.ISetMusicalN.setText('%s' %IS['Mus'])
        print()
        print('-----%s-----' %IS['Nam'])
        for i, item in enumerate(self.ISetlightsource):
            item.setChecked(bool(IS['Wa%s' %str(i+1)])) #set each wavelength on or off according to the dataframe
            if IS['Wa%s' %str(i+1)] == True:
                self.ISetlightpower[i].setEnabled(True)
                self.ISetlightpowerlabel[i].setText('%s' %IS['Po%s' %str(i+1)])
                self.ISetlightpower[i].setValue(int(IS['Po%s' %str(i+1)]))
            else:
                self.ISetlightpower[i].setEnabled(False)
                self.ISetlightpowerlabel[i].setText('0')
                self.ISetlightpower[i].setValue(0)
        
        if IS['Mod'] == 0: #scattering mode - allows multiple wavelengths
            self.wavelengthButtonGroup.setExclusive(False)
        else:
            
            self.wavelengthButtonGroup.setExclusive(True)      
       
    def update_imaging_mode(self):
        pass
        n = self.ISetListWidget.currentRow()
        IS = self.ImagingSets.loc[n]
        # remove all but first wavelength selected
        a = False 
        for i, item in enumerate(self.ISetlightsource):
            if a == False and IS['Wa%s' %str(i+1)] == True:
                a = True # skip the first encoutered active wavelength
                print(i, 'T', IS['Wa%s' %str(i+1)], IS['Po%s' %str(i+1)])
                item.setChecked(True)
                self.ISetlightpowerlabel[i].setText('%s' %(IS['Po%s' %str(i+1)]))
                self.ISetlightpower[i].setValue(IS['Po%s' %str(i+1)])
            else:
                print(i, 'F', IS['Wa%s' %str(i+1)], IS['Po%s' %str(i+1)])
                IS['Wa%s' %str(i+1)] = 0
                IS['Po%s' %str(i+1)] = 0
                item.setChecked(False)
                self.ISetlightpowerlabel[i].setText('0')
                self.ISetlightpower[i].setValue(0)   
        self.GUI_to_dataframe()
        
            
    def loadDataFrame(self):
        address = self.BasicSettings.at[0,'LastUserAddress']
        if self.demo_mode: address = '/Users/Demo/'
        self.ImagingSets = pd.read_csv("%sImagingParameters.txt" %(address), index_col=0)
        # build the imaging set list widget
        self.ISetListWidget.clear()
        theFont = QtGui.QFont()
        for n in range(self.ImagingSets.shape[0]):
            IS = self.ImagingSets.loc[n]
            i = QtWidgets.QListWidgetItem()
            i.setText('%s \t\t %s' %(IS['Nam'], self.imaging_mode_list[IS['Mod']]))
            if IS['Act']:   
                i.setBackground(QtGui.QBrush(QtGui.QColor('green')))
                theFont.setBold(True)
                theFont.setUnderline(True)
            else:           
                i.setBackground(QtGui.QBrush(QtGui.QColor('light grey')))
                theFont.setBold(False)
                theFont.setUnderline(False)
            i.setFont(theFont)
            self.ISetListWidget.insertItem(n,i)
            

        #select first set by default
        self.ISetListWidget.setCurrentRow(0)
        self.dataframe_to_GUI()
  
    def saveDataFrame(self):
        address = self.BasicSettings.at[0,'LastUserAddress']
        if self.demo_mode: address = '/Users/Demo/'
        self.ImagingSets.to_csv("%sImagingParameters.txt" %(address), mode='w', index=True)


    def adjustLaserPower(self):
        for i, item in enumerate(self.ISetlightpower):
            p = item.value()
            self.ISetlightpowerlabel[i].setText(str(p))
        self.GUI_to_dataframe()
        
# =============================================================================
 # Functions for displaying information in the GUI
# =============================================================================

    def information(self, info, colour):
        self.Information_text_window.moveCursor(QtGui.QTextCursor.End)
        now=datetime.datetime.now()
        d = '%02d:%02d:%02d - '%(now.hour,now.minute,now.second)
        self.Information_text_window.insertHtml('<font color="white">%s</font>' %d)
        if colour == 'r':
            self.Information_text_window.insertHtml('<font color="red"><b>%s</b></font><br>' %(str(info)))
            print(str(info))
        if colour == 'g':
            self.Information_text_window.insertHtml('<font color="green"><b>%s</b></font><br>'%(str(info)))
        if colour == 'y':
            self.Information_text_window.insertHtml('<font color="yellow"><b>%s</b></font><br>'%(str(info)))
        self.Information_text_window.moveCursor(QtGui.QTextCursor.End)

    def update_expt_name(self):
        self.UserName    = self.FileUserList.currentText()
        if self.UserName != self.BasicSettings.at[0,'LastUser']:
            self.saveDataFrame()
            self.BasicSettings.at[0,'LastUser'] ="%s" %(self.UserName)
            self.BasicSettings.at[0,'LastUserAddress'] ="%s\\%s\\" %(self.user_directory,self.UserName)
            self.loadDataFrame()
        self.ExptName    = self.FileExptName.text()
        startdate   = datetime.date.today()
        if len(self.ExptName)>0:
            self.ExptName = ' (%s)' %(self.ExptName)
        i=0
        while True:
            i=i+1
            if i==1:
                self.StoreLocation = '%s\\%s\\%s%s' %(self.user_directory,self.UserName,startdate,self.ExptName)
            else:
                self.StoreLocation = '%s\\%s\\%s (%s)%s' %(self.user_directory,self.UserName,startdate,i,self.ExptName)
            if not os.path.exists(self.StoreLocation):
                self.FileAddress.setText(self.StoreLocation)
                break
        self.BasicSettings.at[0,'LastUserAddress'] ="%s\\%s\\" %(self.user_directory,self.UserName)
        self.BasicSettings.at[0,'LastUser'] ="%s" %(self.UserName)
        self.BasicSettings.to_csv(self.BSmemory, mode='w', index=True)
# =============================================================================
#  Minor functions
# =============================================================================
    def setScreenSize(self):
        screen = app.primaryScreen()
        w = screen.size().width()
        h = screen.size().height()
        self.setGeometry(0, 50, int(w*0.8), int(h-100))   
    
    def closeEvent(self, event): #to do upon GUI being closed
        self.frametimer.stop()
        self.saveDataFrame()
        if not self.demo_mode:
            self.camera1.close()
            self.TLsdk.dispose()
            self.camera3.close()
            self.stage.close()
    
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    gui = Raymond()
    gui.show()
    app.exec_()