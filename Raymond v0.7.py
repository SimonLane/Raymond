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
        laser power settings into experiment builder and into data structure
    TO-DO
        Create Connection indicator - currently output to the info log
        Save all settings to config file, not just the experiment builder
        Add GUI section for environmental information
        Add GUI section for Rayleigh image processing options
        Add GUI section for locations, and button to load in saved locations
        Load calibration file for laser powers
        
        On start Expt. output a file (to the experiment directory) with all the imaging parameters and stage positions as an excel file
        Ability to load back the settings and/or positions
        
        
@author: Simon
"""


import sys, time, threading, datetime, queue, glob, os, math, ctypes
import pandas           as pd
import numpy            as np
import pyqtgraph        as pg

from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtCore import Qt
from collections    import deque
from scipy.ndimage.filters import gaussian_filter

if sys.platform == "win32":
    from thorlabs_tsi_sdk.tl_camera import TLCameraSDK
# my classes
    from Camera_TL          import Camera_TL
    from Camera_PG          import Camera_PG
    from Stage_ASI          import Stage_ASI


class CheckableComboBox(QtWidgets.QComboBox):
    def __init__(self, parent = None):
        super(CheckableComboBox, self).__init__(parent)
        self.view().pressed.connect(self.handleItemPressed)
        self.setModel(QtGui.QStandardItemModel(self))

    def handleItemPressed(self, index):
        item = self.model().itemFromIndex(index)
        if item.checkState() == Qt.Checked:
            item.setCheckState(Qt.Unchecked)
        else:
            item.setCheckState(Qt.Checked)
        self.parent().GUI_to_dataframe()
            
            
class Raymond(QtWidgets.QMainWindow):
    def __init__(self):
        super(Raymond, self).__init__()
        # self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Force GUI to stay on top
        
# =============================================================================
#  Microscope properties - edit as needed
# =============================================================================
        self.demo_mode = True # If true loads GUI without connecting to any hardware, for development only
        self.verbose   = True # Prints more information to the console, for debugging
        
    # GUI appearance
        self.font_size = 9
        self.border_size = 1
        self.GUI_colour = QtGui.QColor(75,75,75)
        self.GUI_font   = QtGui.QFont('Times',self.font_size)
        self.setFont(self.GUI_font)
        
    # available filters and binning modes
        self.filter_list = [
                QtWidgets.QCheckBox("490 +-10"),
                QtWidgets.QCheckBox("610 +-30, 650SP"),
                QtWidgets.QCheckBox("520 +-20, 650SP"),
                QtWidgets.QCheckBox("Pol. V"),
                QtWidgets.QCheckBox("Pol. H"),
                QtWidgets.QCheckBox("Empty")
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
        self.newSet = pd.DataFrame({'ID':0,'Act':False,'Nam':'name','Exp':10,'Bin':0,'Mod':0,'Mus':0,'Zed':True,
              'Wa1':True,'Wa2':False,'Wa3':False,'Wa4':False,'Wa5':False,'Wa6':False,'Wa7':False,'Wa8':False,'Wa9':False,'Wa10':False,
              'Po1':0,'Po2':0,'Po3':0,'Po4':0,'Po5':0,'Po6':0,'Po7':0,'Po8':0,'Po9':0,'Po10':0,
              'Fi1':True,'Fi2':False,'Fi3':False,'Fi4':False,'Fi5':False,'Fi6':False}, index=[-1])
        
    # default settings applied to new stage position
        self.newPosSet = pd.DataFrame({'ID':0,'Act':True,'X':0,'Y':0,'Z':0}, index=[-1])

    # The dataframe used to hold imaging parameters for all defined imaging sets
        self.ISmemory = "ImagingParameters.txt"
        self.BSmemory = "Settings.txt"
        # self.stagePositions = 'lastStagePositions.xlsx'
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
        self.userList= []               # List of valid users, created at startup from list of folders in the save root directory 
        if sys.platform == "win32":
            self.user_directory = 'D:'
            self.userList = glob.glob('D:\\**\\', recursive=False)
            for i, item in enumerate(self.userList):
                self.userList[i] = item.split('\\')[-2]
        if sys.platform == "darwin":  
            self.demo_mode = True
            self.user_directory = 'Users'
            self.userList = glob.glob('/Users/**/', recursive=False)
            for i, item in enumerate(self.userList):
                self.userList[i] = item.split('/')[-2]
        print('OS: ', sys.platform)
        print('Demo mode: ', self.demo_mode)
        print('User list: ', self.userList)        
                
        self.window_title = os.path.basename(__file__)
        self.ListWidgetfromIndex = 0    # keeps track of the last clicked item in imaging set list widget
        self.liveImaging = False        # Keeps track of if microsocpe is currently streaming from the camera
        self.in_experiment = False      # Flag for tracking if experiment is ongoing
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
        self.updatingGUI = False                                                 #to only allow GUI to be updated by only a single function at a time
# =============================================================================
# Queues and timers for inter-thread thread-safe task handling
# =============================================================================
        self.tileScanQ = queue.Queue()
        self.tileScan_timer = QtCore.QTimer()
        self.tileScan_timer = QtCore.QTimer()
        self.tileScan_timer.setInterval(10)
        self.tileScan_timer.timeout.connect(self.imageToMap)
        
        #For imaging thread to update the GUI
        self.thread_to_GUI = queue.Queue()
        self.thread_to_GUI_timer = QtCore.QTimer()
        self.thread_to_GUI_timer = QtCore.QTimer()
        self.thread_to_GUI_timer.setInterval(10)
        self.thread_to_GUI_timer.timeout.connect(self.thread_to_GUI_QCheck)
        
        self.GUI_to_thread = deque(['','','',''], maxlen=4)
        self.countdown_timer = 0
        
# =============================================================================
# Data Structures
# =============================================================================

        self.ImagingSets = pd.DataFrame()   #Stores al imaging settings, populated from file stored in user folder
        self.PositionList = pd.DataFrame()  #Stores user selected stage positions, can also be loaded from a file (in case of crash)

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
        self.FileUserList.setCurrentIndex(i)# set user in file settings pane
        self.loadDataFrame() # load in the imaging sets
        # select first item in experiment builder
 
# Timers
        self.frametimer = QtCore.QTimer() # A timer for grabbing images from the camera buffer during live view mode
        self.update_expt_name()
        
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
        self.ISetMode.currentIndexChanged.connect(self.GUI_to_dataframe)
        
        self.FilterLabel         = QtWidgets.QLabel('Filter(s):')
        self.filterButtonGroup = QtWidgets.QButtonGroup()
        
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
        self.LightsourceLabel    = QtWidgets.QLabel('Wavelength(s):')
        self.wavelengthButtonGroup = QtWidgets.QButtonGroup()

        self.ISetlightpower = []
        self.ISetlightpowerlabel = []
   
        self.ImagingSettingsSubGroup     = QtWidgets.QGroupBox()
        self.ImagingSettingsSubGroup.setLayout(QtWidgets.QGridLayout())
        
        for i, item in enumerate(self.filter_list):
            self.filterButtonGroup.addButton(item)
            item.stateChanged.connect(self.GUI_to_dataframe)
            self.ImagingSettingsSubGroup.layout().addWidget(self.filter_list[i],        i+2,1,1,1)
        self.filterButtonGroup.setExclusive(True)
        
        for i, item in enumerate(self.ISetlightsource):
            self.wavelengthButtonGroup.addButton(item)
            item.stateChanged.connect(self.GUI_to_dataframe)

            self.ISetlightpower.append(QtWidgets.QSlider())
            self.ISetlightpower[i].setOrientation(QtCore.Qt.Horizontal)
            self.ISetlightpower[i].setMinimum(0)
            self.ISetlightpower[i].setMaximum(100)
            self.ISetlightpower[i].setTickInterval(5)
            self.ISetlightpower[i].setTickPosition(QtWidgets.QSlider.TicksBelow)
            self.ISetlightpower[i].setValue(0)
            self.ISetlightpower[i].valueChanged.connect(self.GUI_to_dataframe)
            
            self.ISetlightpowerlabel.append(QtWidgets.QLineEdit())
            self.ISetlightpowerlabel[i].setText('0')
            self.ISetlightpowerlabel[i].setFixedWidth(35)
            self.ISetlightpowerlabel[i].setReadOnly(True)
            
            self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[i],        i+2,2,1,1)
            self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightpowerlabel[i],    i+2,3,1,1)
            self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightpower[i],         i+2,4,1,3)
        self.wavelengthButtonGroup.setExclusive(True)

    # sub-assembly                                                                # (y x h w)    
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetActive,            0,4,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetZ,                 0,2,1,2)
        self.ImagingSettingsSubGroup.layout().addWidget(self.NameLabel,             0,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetName,              0,1,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ModeLabel,             1,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetMode,              1,1,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.FilterLabel,           2,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.BinningLabel,          8,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetBinning,           8,1,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ExposureLabel,         9,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetExposure,          9,1,1,1)       
        self.ImagingSettingsSubGroup.layout().addWidget(self.MusicalLabel,          10,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetMusicalN,          10,1,1,1)
        
        self.ImagingSettingsSubGroup.layout().addWidget(self.LightsourceLabel,      1,2,1,2)

        self.ImagingSettingsSubGroup.layout().addWidget(self.LiveButton,            11,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.GrabButton,            11,1,1,1)

    # assembly                                                                # (y x h w)
        self.ExptBuildGroup     = QtWidgets.QGroupBox('Experiment Builder')
        self.ExptBuildGroup.setLayout(QtWidgets.QGridLayout())
        self.ExptBuildGroup.layout().addWidget(self.NewISetButton,               0,0,1,1)
        self.ExptBuildGroup.layout().addWidget(self.DelISetButton,               0,1,1,1)
        self.ExptBuildGroup.layout().addWidget(self.ISetListWidget,              1,0,3,2)
        self.ExptBuildGroup.layout().addWidget(self.ImagingSettingsSubGroup,     0,3,5,9)
        
#~~~~~~~~~~~~~~~ Image Display ~~~~~~~~~~~~~~~  
        self.ImageDisplayGroup              = QtWidgets.QGroupBox('Camera')
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

        self.ImageDisplayGroup.setLayout(QtGui.QGridLayout())                   # (y x h w)
        self.ImageDisplayGroup.layout().addWidget(self.view_modes[0],              0,0,1,1)
        self.ImageDisplayGroup.layout().addWidget(self.view_modes[1],              0,1,1,1)
        self.ImageDisplayGroup.layout().addWidget(self.view_colour_modes[0],       0,5,1,1)
        self.ImageDisplayGroup.layout().addWidget(self.view_colour_modes[1],       0,6,1,1)
        self.ImageDisplayGroup.layout().addWidget(self.view_colour_modes[2],       0,7,1,1)
        self.ImageDisplayGroup.layout().addWidget(self.saveImageButton,            0,3,1,1)

        self.ImageDisplayGroup.layout().addWidget(self.imagewidget,                1,0,10,10)

#~~~~~~~~~~~~~~~ View Finder ~~~~~~~~~~~~~~~  
        self.ViewFinderGroup            = QtWidgets.QGroupBox('Stage Map')
        self.viewFindButton             = QtGui.QPushButton("Live")
        self.viewFindButton.setFixedWidth(60)
        self.viewFindButton.released.connect(self.showViewFinder)
        
        self.VFModButton                = QtGui.QPushButton("set BG")
        self.VFModButton.released.connect(self.update_modifier_image)
        self.VFModButton.setFixedWidth(60)
        self.tileAreaSelection          = QtGui.QComboBox()
        self.tileAreaSelection.setFixedWidth(60)
        for item in self.tileAreaNames:
            self.tileAreaSelection.addItem(item)
        self.mapPlot = pg.PlotItem()
        self.mapImageWidget             = pg.ImageView(view = self.mapPlot)

        # proxy = pg.SignalProxy(self.mapPlot.scene().sigMouseClicked,
        #                         rateLimit=60, slot=self.on_click_event)
        
        self.NewPButton       = QtWidgets.QPushButton('+')
        self.DelPButton       = QtWidgets.QPushButton('-')
        self.LoadPButton      = QtWidgets.QPushButton('Load')
        self.NewPButton.released.connect(lambda: self.addPos())
        self.DelPButton.released.connect(lambda: self.deletePos())
        self.LoadPButton.released.connect(self.loadPositions)
        self.PositionListWidget      = QtWidgets.QTableWidget()
        self.PositionListWidget.itemEntered.connect(self.storeFromIndexP)
        self.PositionListWidget.cellDoubleClicked.connect(self.pos_table_click)
        self.PositionListWidget.setColumnCount(6)
        self.PositionListWidget.setHorizontalHeaderLabels([self.tr("P"),self.tr("X"),self.tr("Y"),self.tr("Z"),self.tr(""),self.tr("")])
        pos_column_spacing = [25,45,45,45,30,20]
        for column in range(6):
            self.PositionListWidget.setColumnWidth(column, pos_column_spacing[column])
        self.PositionListWidget.setFixedWidth(230)
        
        self.mapImageWidget.getImageItem().mouseClickEvent = self.on_click_event
        
        self.mapImageWidget.ui.roiBtn.hide()
        self.mapImageWidget.ui.menuBtn.hide()
        self.mapImageWidget.ui.histogram.hide()
        self.mapImageWidget.view.setXRange(-11, 11, padding=0)
        self.mapImageWidget.view.setYRange(-11, 11, padding=0)
        self.mapImageWidget.view.setFixedHeight(350)
        self.mapImageWidget.view.setFixedWidth(350)
        
        self.tileScanButton             = QtGui.QPushButton("Tile Scan")
        self.tileScanButton.released.connect(self.setupTileScan)
        self.tileScanButton.setFixedWidth(60)                                 # (y x h w)
        self.ViewFinderGroup.setLayout(QtGui.QGridLayout())
        self.ViewFinderGroup.layout().addWidget(self.mapImageWidget,            0,0,10,6)
        self.ViewFinderGroup.layout().addWidget(self.PositionListWidget,        2,6,8,4)
        self.ViewFinderGroup.layout().addWidget(self.NewPButton,                1,6,1,1)
        self.ViewFinderGroup.layout().addWidget(self.DelPButton,                1,7,1,1)
        self.ViewFinderGroup.layout().addWidget(self.LoadPButton,               1,8,1,1)
        self.ViewFinderGroup.layout().addWidget(self.viewFindButton,            0,6,1,1)
        self.ViewFinderGroup.layout().addWidget(self.VFModButton,               0,7,1,1)
        self.ViewFinderGroup.layout().addWidget(self.tileAreaSelection,         0,8,1,2)
        self.ViewFinderGroup.layout().addWidget(self.tileScanButton,            0,9,1,1)

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
        self.progress_z          = QtGui.QProgressBar()
        self.progress_c          = QtGui.QProgressBar()
        self.progress_p          = QtGui.QProgressBar()
        self.progress_t          = QtGui.QProgressBar()
        self.progress_e          = QtGui.QProgressBar()
        
        for pb in [self.progress_z,self.progress_c,self.progress_p,
                   self.progress_t,self.progress_e]:
            pb.setFixedHeight(16)
            pb.setFormat("%v/%m")
            pb.setAlignment(Qt.AlignRight)
        self.progress_t.setFormat("%vs")
        self.progress_t.setInvertedAppearance(True)

        self.progress_z_label    = QtWidgets.QLabel('       Z-positons:')
        self.progress_c_label    = QtWidgets.QLabel('         Channels:')
        self.progress_p_label    = QtWidgets.QLabel('Stage positions:')
        self.progress_e_label    = QtWidgets.QLabel('      Timepoints:')
        self.progress_t_label    = QtWidgets.QLabel('             Timer:')
        self.ProgressGroup       = QtGui.QGroupBox('Experiment Progress')
        
        self.ProgressGroup.setLayout(QtGui.QGridLayout())
        self.ProgressGroup.layout().addWidget(self.Expt_Start_button,           0,0,1,3)
        self.ProgressGroup.layout().addWidget(self.progress_z_label,            1,0,1,2)
        self.ProgressGroup.layout().addWidget(self.progress_c_label,            2,0,1,2)
        self.ProgressGroup.layout().addWidget(self.progress_p_label,            3,0,1,2)
        self.ProgressGroup.layout().addWidget(self.progress_e_label,            4,0,1,2)
        self.ProgressGroup.layout().addWidget(self.progress_t_label,            5,0,1,2)
        self.ProgressGroup.layout().addWidget(self.progress_z,                  1,2,1,4)
        self.ProgressGroup.layout().addWidget(self.progress_c,                  2,2,1,4)
        self.ProgressGroup.layout().addWidget(self.progress_p,                  3,2,1,4)
        self.ProgressGroup.layout().addWidget(self.progress_e,                  4,2,1,4)
        self.ProgressGroup.layout().addWidget(self.progress_t,                  5,2,1,4)
        

#~~~~~~~~~~~~~~~ File save Pane ~~~~~~~~~~~~~~~ 
#Fileing Widgets
        self.FileUserLabel                  = QtGui.QLabel('User:')
        self.FileUserList                   = QtGui.QComboBox()
#generate user list
        for item in self.userList:
            if not item.__contains__('.') and len(item) < 15:
                self.FileUserList.addItem(item)
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
        self.ZLabel2                    = QtGui.QLabel('Separation (µm):')
        self.ZSeparation                = QtGui.QLineEdit('10')
        self.ZLabel3                    = QtGui.QLabel('Span (µm):')
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
        OverallLayout.addWidget(self.ImageDisplayGroup,                         0,0,12,12)
        OverallLayout.addWidget(self.ViewFinderGroup,                           12,0,8,12)

#Right-hand top                                                                                
        OverallLayout.addWidget(self.ExptBuildGroup,                            0,12,7,10)
        
# Right-hand bottom        
        OverallLayout.addWidget(self.FileGroup,                                 16,12,2,3)
        OverallLayout.addWidget(self.TimingGroup,                               16,15,2,3)
        OverallLayout.addWidget(self.ZSlice,                                    16,18,2,3)
        OverallLayout.addWidget(self.ProgressGroup,                             18,12,2,3)
        OverallLayout.addWidget(self.InfoGroup,                                 18,15,2,6)
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
        if self.in_experiment:
            self.Expt_Start_button.setText('Stopping...')
            self.GUI_to_thread[-1] = 'stop'
            print('before',self.thread_to_GUI.qsize())
            time.sleep(0.1)
            print('after',self.thread_to_GUI.qsize())
            self.thread_to_GUI_timer.stop()
            self.Expt_Start_button.setText('Start Experiment')
            for pb in [self.progress_z,self.progress_c,self.progress_p,
                   self.progress_t,self.progress_e]:
                pb.reset()
            return
            
        if not self.in_experiment:
# save all settings and positions in case of crash whilst imaging
            self.saveDataFrame()
            working_folder = self.BasicSettings.at[0,'LastUserAddress']
            if self.PositionList.shape[0] == 0: 
                self.information('Imaging not possible, no stage positions selected', 'r')
                return
            self.positionsToDataframe()
            imaging_set = self.build_imaging_set()
        
            if imaging_set.shape[0] == 0:
                self.information('Imaging not possible, no imaging modes selected', 'r')
                return
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

# Start threadsafe timers and queues to handle data flow and GUI updates
            self.GUI_to_thread[0] = time.time()
            self.thread_to_GUI_timer.start()
            
            self.Expt_Start_button.setText('Stop Experiment')
    # Start job in a new thread
            self.ImagingLoopThread = threading.Thread(target=self.Imaging_loop, 
                name="imaging",args=(imaging_set, working_folder, 
                    timing_interval, imaging_loops, self.PositionList,
                    crop, eight))
            print('Experiment starting')
            self.information('Experiment starting', 'g')
            self.in_experiment = True
            self.GUI_to_thread[-1]=''
            self.ImagingLoopThread.start()
    
    
    def build_imaging_set(self):
#make empty master imaging set (pandas structure)
        imaging_sets = pd.DataFrame(data=None,columns=[
            'Name','Filter','Wavelength','Power','Exposure',
            'Binning','Zstart','Znumber','Zseparation'])

# access the dataframe
        for n in range(self.ImagingSets.shape[0]):
            IS = self.ImagingSets.loc[n]
            if IS['Act']: 
                name      = IS['Nam']
                exposure  = IS['Exp']
                binning   = IS['Bin']                                  # loop through active modes
                if IS['Zed']:
                    znumber         = int(self.ZSlices.text())
                    zseparation     = float(self.ZSeparation.text())
                    zstart          = ((znumber-1) * zseparation)/-2.0
                else:
                    znumber         = 1
                    zseparation     = 0
                    zstart          = 0
                for f in range(1,7,1): # filters
                    if IS['Fi%s' %f]:
                        filter_ = f
                        for w in range(1,11,1): # wavelengths
                            if IS['Wa%s' %w]:
                                wavelength = w
                                power      = IS['Po%s' %w]                
                                set_ = [name,filter_,wavelength,power,exposure,
                                        binning,zstart,znumber,zseparation]    
                                imaging_sets.loc[len(imaging_sets.index)] = set_
            
        # TO DO - sort imaging order according to user selection
        
        return imaging_sets
# =============================================================================
#   Main imaging Loop - Imaging Thread
# =============================================================================
    def Imaging_loop(self, imaging_set, working_folder, 
                     timing_interval, timepoints, positions, crop, eight):
        
        continue_experiment = True
        self.progress_e.setRange(0,timepoints)
        self.progress_t.setRange(0,timing_interval)
        self.progress_p.setRange(0,len(positions))
        self.progress_c.setRange(0,len(imaging_set))

        next_timepoint = time.time()
        
        
        for t in range(timepoints):
            while time.time() < next_timepoint:
                if self.GUI_to_thread_Qcheck(): continue_experiment = False
                if not continue_experiment: break
            
            next_timepoint = next_timepoint + timing_interval
            self.thread_to_GUI.put(['t',next_timepoint])
            self.thread_to_GUI.put(['e',t])
            if next_timepoint < time.time() + timing_interval - 1:
                print('WARNING: Insufficient time for loop')
                self.thread_to_GUI.put( ['alert','WARNING: Insufficient time for loop','r'])

            for p in range(len(positions)):
                if self.GUI_to_thread_Qcheck(): continue_experiment = False
                if not continue_experiment: break
                self.thread_to_GUI.put(['p',p])
                
# set next stage position
                if not self.demo_mode: self.Stage_ASI.move_to(X=positions.at[p,'X'],Y=positions.at[p,'Y'],Z=positions.at[p,'Z'])
                if self.verbose: print('Stage move... X:',positions.at[p,'X'],' Y:',positions.at[p,'Y'],' Z:',positions.at[p,'Z'])

                for c in range(len(imaging_set)):
                    if self.GUI_to_thread_Qcheck(): continue_experiment = False
                    if not continue_experiment: break
                    self.thread_to_GUI.put(['c',c])
                    self.progress_z.setRange(0,imaging_set.loc[c].Znumber)
                    
# send command to microscope here
                    command = self.build_command(imaging_set.loc[c])
                    
                    for z in range(imaging_set.loc[c].Znumber):
                        if self.GUI_to_thread_Qcheck(): continue_experiment = False
                        if not continue_experiment: break
                        self.thread_to_GUI.put(['z',z])
                        
# get images from camera here

                        time.sleep(0.02)
                        
                        
                        self.thread_to_GUI.put(['z',z+1])
# delay for moving ETL and mirror
                        time.sleep(0.05)
                    self.thread_to_GUI.put(['c',c+1])
                    time.sleep(1)
# delay for moving filter wheel and changing laser
                self.thread_to_GUI.put(['p',p+1])
                time.sleep(1)
# delay for moving stage
            self.thread_to_GUI.put(['e',t+1])
            time.sleep(1)
# delay for timing gate here
        
        if continue_experiment:
            self.thread_to_GUI.put( ['alert','Experiment completed','g'])
        else:
            self.thread_to_GUI.put( ['alert','User ended experiment','y'])

        self.stop_experiment()
        self.Imaging_setup()
        self.in_experiment = False
        
        
    def stop_experiment(self):
        print('Imaging thread - hardware cleanup routine...')
        self.thread_to_GUI.put( ['alert','Imaging thread - hardware cleanup routine...','g'])
        #TO DO - do stuff before stopping the thread...
        # make sure lasers are off
        # galvo to safe position
        # release camera
        # set other hardware to safe/default positions
    
    # TO DO = move to Teensy class 
    def build_command(self, imaging_set):
        command = ""
    
    
    def GUI_to_thread_Qcheck(self):         
#        imaging thread calls this function regularly to check if it should continue imaging
        #return True, which will cause imaging thread to leave imaging loop and complete cleanly
        main_window_checkin = int(self.GUI_to_thread[0])

        if time.time() > main_window_checkin + 10:
            print('Imaging thread lost contact with the GUI')
            self.thread_to_GUI.put( ['alert','Imaging thread lost contact with the GUI','y'])
            return True        
        if self.GUI_to_thread[-1] == 'stop':
            return True
        return False
    
    def thread_to_GUI_QCheck(self):
        while self.thread_to_GUI.qsize()>0:
            task = self.thread_to_GUI.get()
            if task[0] == 'e': self.progress_e.setValue(int(task[1]))
            if task[0] == 't': self.countdown_timer = int(task[1])
            if task[0] == 'p': self.progress_p.setValue(int(task[1]))
            if task[0] == 'c': self.progress_c.setValue(int(task[1]))
            if task[0] == 'z': self.progress_z.setValue(int(task[1]))
            if task[0] == 'alert': 
                self.information(task[1],task[2])
                for pb in [self.progress_z,self.progress_c,self.progress_p,
                   self.progress_t,self.progress_e]:
                    pb.reset()
        # Add timestamp to G2T queue so the imaging thread can know 
        # main thread is still running
        self.GUI_to_thread[0] = time.time()
        # update countdown timer
        t = int((self.countdown_timer - time.time()))
        self.progress_t.setValue(t)
        
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
        self.tileScan_timer.start()
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
                        self.tileScanQ_timer.stop()
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
        self.tileScan_timer.stop()
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
        time.sleep(self.camera1.frame_time()/1000000.0)
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
            # self.GUI_to_thread[1] = [interval,loops]

        except:
            self.information("Please enter valid interval and loop values.", 'y')

# =============================================================================
# Z-stack functions            
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
            z_set.append(round(((span/2)-span) + (separation * i),2))
        return z_set, separation

# =============================================================================
#  Stage Position List functions
# =============================================================================
    def addPos(self, position=None, in_use=True, update=True):
        if position == None:
            position = [0,0,0]
        # add a new stage position to the bottom of the list Widget,
        # self.PositionListWidget.insertItem(self.PositionListWidget.count(), str(self.PositionListWidget.count()))
        row_number = self.PositionListWidget.rowCount()
        self.PositionListWidget.insertRow(row_number)
        self.PositionListWidget.setRowHeight(row_number, 15)
        inUse = QtGui.QCheckBox('')
        inUse.setChecked(bool(in_use))
        inUse.stateChanged.connect(self.positionsToDataframe)
        X = QtGui.QLineEdit()
        X.setText('%s' %position[0])
        # X.setValidator(QtGui.QDoubleValidator(self.ASI.imaging_limits[0][1],self.ASI.imaging_limits[0][0],1))
        X.textChanged.connect(self.positionsToDataframe)
        Y = QtGui.QLineEdit()
        Y.setText('%s' %position[1])
        # Y.setValidator(QtGui.QDoubleValidator(self.ASI.imaging_limits[1][1],self.ASI.imaging_limits[1][0],1))
        Y.textChanged.connect(self.positionsToDataframe)
        Z = QtGui.QLineEdit()
        Z.setText('%s' %position[2])
        # Z.setValidator(QtGui.QDoubleValidator(self.ASI.imaging_limits[2][1],self.ASI.imaging_limits[2][0],1))
        Z.textChanged.connect(self.positionsToDataframe)
        del_ = QtGui.QLabel('Delete')
        goto = QtGui.QLabel('Go')

        self.PositionListWidget.setCellWidget(row_number,  0, inUse)
        self.PositionListWidget.setCellWidget(row_number,  1, X)
        self.PositionListWidget.setCellWidget(row_number,  2, Y)
        self.PositionListWidget.setCellWidget(row_number,  3, Z)
        self.PositionListWidget.setCellWidget(row_number,  4, del_)
        self.PositionListWidget.setCellWidget(row_number,  5, goto)
        if update: self.positionsToDataframe()

    def pos_table_click(self, r,c):
        if c == 4: # delete
            self.PositionListWidget.removeRow(r)
            self.positionsToDataframe()
        if c == 5: # go to
            x     = float(self.PositionListWidget.cellWidget(r,1).text())
            y     = float(self.PositionListWidget.cellWidget(r,2).text())
            z    = float(self.PositionListWidget.cellWidget(r,3).text())
            print('move stage to position (x:%s, y:%s, z:%s)' %(x,y,z))
                   
    def deletePos(self):
        d = self.PositionListWidget.currentRow()
        self.PositionListWidget.removeRow(d)
        self.positionsToDataframe()
    
    def storeFromIndexP(self): #store index of last clicked iten in the list view
        self.PosListWidgetfromIndex = self.PositionListWidget.currentRow()

    def positionsToDataframe(self):
        self.PositionList = self.PositionList.iloc[0:0]
        for r in range(self.PositionListWidget.rowCount()):
            self.PositionList.at[r,'Act']    = self.PositionListWidget.cellWidget(r,0).isChecked()
            self.PositionList.at[r,'X']      = float(self.PositionListWidget.cellWidget(r,1).text())
            self.PositionList.at[r,'Y']      = float(self.PositionListWidget.cellWidget(r,2).text())
            self.PositionList.at[r,'Z']      = float(self.PositionListWidget.cellWidget(r,3).text())
        self.positionsToDisk()  
    
    def positionsToDisk(self):
        if self.PositionList.shape[0] != 0:
            self.PositionList.to_excel('%slastStagePositions.xlsx' %self.BasicSettings.at[0,'LastUserAddress'], columns=['Act','X','Y','Z'])
        
    def loadPositions(self):
        address = QtGui.QFileDialog.getOpenFileName(self, 'Select Position Storage File', self.BasicSettings.at[0,'LastUserAddress'],
                                                    "All files (lastStagePositions.xlsx stagePositions.xlsx)")
        self.PositionList = pd.read_excel(address[0], index_col=0)
        for r in range(self.PositionList.shape[0]):
            i = self.PositionList.at[r,'Act']
            p = [self.PositionList.at[r,'X'],self.PositionList.at[r,'Y'],self.PositionList.at[r,'Z']]
            self.addPos(position=p, in_use=i, update=False)
        
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
        self.dataframe_to_GUI()
                       
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
        self.dataframe_to_GUI()
    
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
        # run this function to push settings from the GUI into the dataframe 
        # function called by change in value/state of any widget for experimental settings
        n = self.ISetListWidget.currentRow()
        self.ImagingSets.at[n,'Act'] = self.ISetActive.isChecked()
        self.ImagingSets.at[n,'Nam'] = self.ISetName.text()
        self.ImagingSets.at[n,'Mod'] = self.ISetMode.currentIndex()
        self.ImagingSets.at[n,'Bin'] = self.ISetBinning.currentIndex()
        self.ImagingSets.at[n,'Exp'] = self.ISetExposure.text()
        self.ImagingSets.at[n,'Zed'] = self.ISetZ.isChecked()
        self.ImagingSets.at[n,'Mus'] = self.ISetMusicalN.text()
        
        if self.ISetMode.currentIndex() == 0:                                   #scattering mode - allows multiple wavelengths
            for i, item in enumerate(self.ISetlightsource):
                self.ImagingSets.at[n,'Wa%s' %str(i+1)] = item.isChecked()
                self.ImagingSets.at[n,'Po%s' %str(i+1)] = self.ISetlightpower[i].value()
            for i, item in enumerate(self.filter_list):
                self.ImagingSets.at[n,'Fi%s' %str(i+1)] = item.isChecked()
                
        else:                                                                   # Other modes
            first_checked = False
            for i, item in enumerate(self.ISetlightsource):                     # remove all but first selection from the dataframe
                if not item.isChecked() or first_checked:
                    self.ImagingSets.at[n,'Wa%s' %str(i+1)] = False
                    self.ImagingSets.at[n,'Po%s' %str(i+1)] = 0
                if item.isChecked() and first_checked == False:
                    first_checked = True
                    self.ImagingSets.at[n,'Wa%s' %str(i+1)] = True
                    self.ImagingSets.at[n,'Po%s' %str(i+1)] = self.ISetlightpower[i].value() 
            first_checked = False
            for i, item in enumerate(self.filter_list):                     # remove all but first selection from the dataframe
                if not item.isChecked() or first_checked:
                    self.ImagingSets.at[n,'Fi%s' %str(i+1)] = False
                if item.isChecked() and first_checked == False:
                    first_checked = True
                    self.ImagingSets.at[n,'Fi%s' %str(i+1)] = True
        self.dataframe_to_GUI()
        
    def dataframe_to_GUI(self):
        if self.updatingGUI: return
        self.updatingGUI = True
        # get values from the dataframe and apply to the widgets in the GUI
        n = self.ISetListWidget.currentRow()
        IS = self.ImagingSets.loc[n]
        self.ISetListWidget.currentItem().setText('%s \t\t %s' %(IS['Nam'],self.imaging_mode_list[IS['Mod']])) #update name
        theFont = QtGui.QFont()
        if bool(IS['Act']) == True:
            self.ISetListWidget.currentItem().setBackground(QtGui.QBrush(QtGui.QColor('green')))
            theFont.setBold(True)
        else:
            self.ISetListWidget.currentItem().setBackground(QtGui.QBrush(QtGui.QColor('light grey')))
            theFont.setBold(False)
        self.ISetListWidget.currentItem().setFont(theFont)
        self.ISetActive.setChecked(bool(IS['Act']))
        self.ISetName.setText('%s' %IS['Nam'])
        self.ISetMode.setCurrentIndex(IS['Mod'])
        self.ISetBinning.setCurrentIndex(IS['Bin'])
        self.ISetExposure.setText('%s' %IS['Exp'])
        self.ISetZ.setChecked(bool(IS['Zed']))
        self.ISetMusicalN.setText('%s' %IS['Mus'])
# set the laser related widgets
        self.wavelengthButtonGroup.setExclusive(False)
        self.filterButtonGroup.setExclusive(False) 
        for i, item in enumerate(self.ISetlightsource):
            pass
            #set each wavelength on or off according to the dataframe
            self.ISetlightsource[i].setChecked(bool(IS['Wa%s' %str(i+1)]))
            self.ISetlightpower[i].setEnabled(bool(IS['Wa%s' %str(i+1)]))
            self.ISetlightpowerlabel[i].setText('%s' %IS['Po%s' %str(i+1)])
            self.ISetlightpower[i].setValue(int(IS['Po%s' %str(i+1)]))
        for i, item in enumerate(self.filter_list):
            #set each wavelength on or off according to the dataframe
            self.filter_list[i].setChecked(bool(IS['Fi%s' %str(i+1)]))    
            
        if IS['Mod'] != 0: # not scattering mode - prevent multiple wavelengths
            self.wavelengthButtonGroup.setExclusive(True) 
            self.filterButtonGroup.setExclusive(True) 
        self.updatingGUI = False
        
    def loadDataFrame(self):
        address = self.BasicSettings.at[0,'LastUserAddress']
        if sys.platform == "darwin": address = '/Users/Demo/'
        self.ImagingSets = pd.read_table("%sImagingParameters.txt" %(address), index_col=0)
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
            else:           
                i.setBackground(QtGui.QBrush(QtGui.QColor('light grey')))
                theFont.setBold(False)
            i.setFont(theFont)
            self.ISetListWidget.insertItem(n,i)

        #select first set by default
        self.ISetListWidget.setCurrentRow(0)
        self.dataframe_to_GUI()
  
    def saveDataFrame(self):
        address = self.BasicSettings.at[0,'LastUserAddress']
        if sys.platform == "darwin": address = '/Users/Demo/'
        self.ImagingSets.to_csv("%sImagingParameters.txt" %(address), mode='w', index=True, sep ='\t')
        
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
            if sys.platform == "darwin": self.BasicSettings.at[0,'LastUserAddress'] ="/%s/%s/" %(self.user_directory,self.UserName)
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
                if sys.platform == "darwin": self.StoreLocation = '/%s/%s/%s%s' %(self.user_directory,self.UserName,startdate,self.ExptName)
            else:
                self.StoreLocation = '%s\\%s\\%s (%s)%s' %(self.user_directory,self.UserName,startdate,i,self.ExptName)
                if sys.platform == "darwin": self.StoreLocation = '/%s/%s/%s (%s)%s' %(self.user_directory,self.UserName,startdate,i,self.ExptName)
            if not os.path.exists(self.StoreLocation):
                self.StoreLocation = '%s\\%s\\%s (%s)%s' %(self.user_directory,self.UserName,startdate,i,self.ExptName)
                if sys.platform == "darwin": self.StoreLocation = '/%s/%s/%s (%s)%s' %(self.user_directory,self.UserName,startdate,i,self.ExptName)
                self.FileAddress.setText(self.StoreLocation)
                break
        
        self.BasicSettings.at[0,'LastUserAddress'] ="%s\\%s\\" %(self.user_directory,self.UserName)
        if sys.platform == "darwin": self.BasicSettings.at[0,'LastUserAddress'] ="/%s/%s/" %(self.user_directory,self.UserName)
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
        self.positionsToDisk()
        # TO DO - print warning if the imaging thread is still running
        active_threads = threading.enumerate()
        # print(active_threads)
        for thread in active_threads:
            if thread.name == 'imaging': print('WARNING, imaging thread still running, restart kernel')
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