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


@author: Simon
"""
import sys, time
import pandas           as pd
import numpy            as np
import pyqtgraph        as pg
from PyQt5 import QtGui, QtWidgets, QtCore
from thorlabs_tsi_sdk.tl_camera import TLCameraSDK

# my classes
from Camera_TL          import Camera_TL
from Camera_PG          import Camera_PG

            
class Raymond(QtWidgets.QMainWindow):
    def __init__(self):
        super(Raymond, self).__init__()

# =============================================================================
#  Microscope properties - edit as needed
# =============================================================================
    # available filters and binning modes
        self.filter_list = [
                "Empty",
                "610+-30, 650SP",
                "520+-20, 650SP",
                "Pol. V",
                "Pol. H",
                "Empty (Pete has 650SP)"
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
        self.GUI_colour = QtGui.QColor(75,75,75)
        self.GUI_font   = QtGui.QFont('Times',10)
        self.setFont(self.GUI_font)
    # The dataframe used to hold imaging parameters for all defined imaging sets
        self.ISmemory = "ImagingParameters.txt"
        self.ISheaders = ['ID','Act','Nam','Exp','Fil','Bin','Mod','Mus','Zed','Wa1','Wa2','Wa3','Wa4','Wa5','Wa6','Wa7','Wa8','Wa9']
        self.PGcamSerial = '15322921'
# =============================================================================
# End editable properties      
# =============================================================================
        self.ListWidgetfromIndex = 0    # keeps track of the last clicked item in inaging set list widget
        self.liveImaging = False        # Keeps track of if microsocpe is currently streaming from the camera
        self.currentImage = None        # Most recently acquired image, to be displayed on the GUI
        self.display_mode = 0           # color rendering of the GUI image window
        self.VF_image = None            # Most recent image from camera 3
        
# build the UI
        self.initUI()

# load in the imaging sets
        self.loadDataFrame()
     
# connect to cameras
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

        
# Timers
        self.frametimer = QtCore.QTimer() # A timer for grabbing images from the camera buffer during live view mode
        
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
               #Setup Application Window
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def initUI(self):
        self.setScreenSize()
        self.setWindowTitle('Raymond V0.2')
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
        self.ISetListWidget.itemClicked.connect(self.set_ISetValues_to_GUI)
        self.ISetListWidget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.ISetListWidget.itemEntered.connect(self.storeFromIndex)
        self.ISetListWidget.model().rowsMoved.connect(self.ISetOrderChange)
        
        self.ISetActive          = QtWidgets.QCheckBox('active')
        self.ISetActive.clicked.connect(self.updateISet)
        
        self.NameLabel           = QtWidgets.QLabel('Name:')
        self.ISetName            = QtWidgets.QLineEdit('name')
        self.ISetName.editingFinished.connect(self.updateISet)
        
        self.ModeLabel           = QtWidgets.QLabel('Imaging Mode:')
        self.ISetMode            = QtWidgets.QComboBox()
        self.ISetMode.addItems(self.imaging_mode_list)
        self.ISetMode.currentIndexChanged.connect(self.updateISet)
        
        self.FilterLabel         = QtWidgets.QLabel('Filter:')
        self.ISetFilter          = QtWidgets.QComboBox()
        self.ISetFilter.addItems(self.filter_list)
        self.ISetFilter.currentIndexChanged.connect(self.updateISet)
        
        self.BinningLabel        = QtWidgets.QLabel('Binning:')
        self.ISetBinning         = QtWidgets.QComboBox()
        self.ISetBinning.addItems(self.binning_list)
        self.ISetBinning.currentIndexChanged.connect(self.updateISet)
        
        self.ISetExposure        = QtWidgets.QLineEdit('10')
        self.ISetExposure.editingFinished.connect(self.updateISet)
        self.ExposureLabel       = QtWidgets.QLabel('Exposure(ms):')
        
        self.ISetZ               = QtWidgets.QCheckBox('Z-stack')
        self.ISetZ.clicked.connect(self.updateISet)
        
        self.ISetMusicalN        = QtWidgets.QLineEdit('50')
        self.ISetMusicalN.editingFinished.connect(self.updateISet)
        self.MusicalLabel        = QtWidgets.QLabel('Musical (n Frames):')
        
        self.LiveButton          = QtWidgets.QPushButton('Live')
        self.LiveButton.pressed.connect(self.liveView)
        self.GrabButton          = QtWidgets.QPushButton('Grab')
        self.GrabButton.pressed.connect(self.grabFrame)
        self.LightsourceLabel    = QtWidgets.QLabel('Wavelengths:')
        self.wavelengthButtonGroup = QtWidgets.QButtonGroup()
        for item in self.ISetlightsource:
            self.wavelengthButtonGroup.addButton(item)
            item.stateChanged.connect(self.updateISet)
        self.wavelengthButtonGroup.setExclusive(True)

    # sub-assembly                                                                # (y x h w)    
        self.ImagingSettingsSubGroup     = QtWidgets.QGroupBox('Settings')
        self.ImagingSettingsSubGroup.setLayout(QtWidgets.QGridLayout())
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
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[0],    2,2,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[1],    3,2,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[2],    4,2,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[3],    5,2,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[4],    6,2,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[5],    2,3,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[6],    3,3,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[7],    4,3,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[8],    5,3,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[9],    6,3,1,1)
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
        self.ImageDisplayGroup          = QtWidgets.QGroupBox('Display')
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
            self.view_modes[rb].released.connect(self.displayMode)
            self.view_modes_group.addButton(self.view_modes[rb],rb)
            self.view_colour_modes[rb].released.connect(self.displayMode)
            self.view_colour_modes_group.addButton(self.view_colour_modes[rb],rb)

        self.imagewidget.ui.roiBtn.hide()
        self.imagewidget.ui.menuBtn.hide()

        self.ImageDisplayGroup.setLayout(QtGui.QGridLayout())
        self.ImageDisplayGroup.layout().addWidget(self.view_modes[0],              0,0,1,2)
        self.ImageDisplayGroup.layout().addWidget(self.view_modes[1],              0,2,1,2)
        self.ImageDisplayGroup.layout().addWidget(self.view_colour_modes[0],       1,0,1,2)
        self.ImageDisplayGroup.layout().addWidget(self.view_colour_modes[1],       1,2,1,2)
        self.ImageDisplayGroup.layout().addWidget(self.saveImageButton,            0,6,1,2)

        self.ImageDisplayGroup.layout().addWidget(self.imagewidget,                2,0,10,10)

#~~~~~~~~~~~~~~~ View Finder ~~~~~~~~~~~~~~~  
        self.ViewFinderGroup          = QtWidgets.QGroupBox('View Finder')
        self.viewFindButton           = QtGui.QPushButton("Live")
        self.viewFindButton.released.connect(self.showViewFinder)
        
        self.viewFinderImageWidget    = pg.ImageView(view=pg.PlotItem())
        self.viewFinderImageWidget.ui.roiBtn.hide()
        self.viewFinderImageWidget.ui.menuBtn.hide()
        self.ViewFinderGroup.setLayout(QtGui.QGridLayout())
        self.mapImageWidget    = pg.ImageView(view=pg.PlotItem())
        
        self.mapImageWidget.ui.roiBtn.hide()
        self.mapImageWidget.ui.menuBtn.hide()
        self.ViewFinderGroup.setLayout(QtGui.QGridLayout())                  
                                                                             # (y x h w)
        self.ViewFinderGroup.layout().addWidget(self.viewFinderImageWidget,     0,0,10,10)
        self.ViewFinderGroup.layout().addWidget(self.mapImageWidget,            0,11,10,10)
        self.ViewFinderGroup.layout().addWidget(self.viewFindButton,            11,0,1,5)
#==============================================================================
# Overall assembly
#==============================================================================
        OverallLayout = QtWidgets.QGridLayout()
#        using a 20x20 grid for flexible arrangement of the panels
#Right-hand column
                                                                  # (y x h w)
        OverallLayout.addWidget(self.ExptBuildGroup,                0,12,6,8)
        OverallLayout.addWidget(self.ViewFinderGroup,               7,12,6,8)
        OverallLayout.addWidget(self.ImageDisplayGroup,             0,0,20,12) # (placeholder)
        

        self.MainArea = QtWidgets.QFrame()
        self.MainArea.setStyleSheet("""
               font: 10pt Modum;
        """)
        self.MainArea.setLineWidth(0)
        self.MainArea.setLayout(OverallLayout)
        self.setCentralWidget(self.MainArea)

# =============================================================================
#   ViewFinder functions
# =============================================================================

    def showViewFinder(self):
        if self.camera3.flag_CONNECTED:
            if not self.liveImaging:
                print('starting viewfinder')
                # set exposure
                self.camera3.exposure(200)
                self.camera3.live_mode()
                self.frametimer.setSingleShot(False)
                self.frametimer.timeout.connect(self.grabImageFromVF)
                self.frametimer.start(1000)
                self.viewFindButton.setText('Stop')
                self.liveImaging = True
            else:
                print('stopping viewfinder')
                self.frametimer.stop()
                self.camera3.stop_live()
                self.viewFindButton.setText('Live')
                self.liveImaging = False
                
    def grabImageFromVF(self):
        image = self.camera3.getFrame()
        if len(image) != 0:
            self.display_image(image)
    
                
# =============================================================================
#  Image Display Functions
# =============================================================================

    def saveSingleImage(self):
        pass
    
    def displayMode(self):
        pass
    
    def liveView(self):
        if self.liveImaging == False:
            print('Starting Live view')
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
            print('Stopping Live view')
            # stop the camera
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
        else:
            print('No image available from camera')
            
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
#         if n_axes == 3:
# #            image arleady flipped
#             self.imagewidget.setImage(image, autoLevels=levels, axes={'t':2, 'x':0, 'y':1})
            
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

    def updateISet(self):
        # run this function when any part of the settings box is changed. 
        # position of the ISet to be updated (in the WidgetList, and in the ImagingSets)
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
        for i, item in enumerate(self.ISetlightsource):
            self.ImagingSets.at[n,'Wa%s' %str(i+1)] = item.isChecked()
        
        # Push the changes into the ISet list widget (to capture name change, mode change, or active change)
        self.ISetListWidget.currentItem().setText('%s \t\t %s' %(self.ISetName.text(),self.ISetMode.currentText())) #update name

        if self.ISetActive.isChecked():
            self.ISetListWidget.currentItem().setBackground(QtGui.QBrush(QtGui.QColor('green')))
        else:
            self.ISetListWidget.currentItem().setBackground(QtGui.QBrush(QtGui.QColor('light grey')))       
        # set Values to GUI - deals with changes in mode
        self.set_ISetValues_to_GUI()
        
    def set_ISetValues_to_GUI(self):
        n = self.ISetListWidget.currentRow()
        IS = self.ImagingSets.loc[n]
        self.ISetActive.setChecked(bool(IS['Act']))
        self.ISetName.setText('%s' %IS['Nam'])
        self.ISetMode.setCurrentIndex(IS['Mod'])
        if IS['Mod'] == 0: #scattering mode - allows multiple wavelengths
            self.wavelengthButtonGroup.setExclusive(False)
        else:
            self.wavelengthButtonGroup.setExclusive(True)
        self.ISetFilter.setCurrentIndex(IS['Fil'])
        self.ISetBinning.setCurrentIndex(IS['Bin'])
        self.ISetExposure.setText('%s' %IS['Exp'])
        self.ISetZ.setChecked(bool(IS['Zed']))
        self.ISetMusicalN.setText('%s' %IS['Mus'])
        for i, item in enumerate(self.ISetlightsource):
            item.setChecked(bool(IS['Wa%s' %str(i+1)]))
            
    def loadDataFrame(self):
        self.ImagingSets = pd.read_csv(self.ISmemory, index_col=0)
        # build the imaging set list widget
        self.ISetListWidget.clear()
        for n in range(self.ImagingSets.shape[0]):
            IS = self.ImagingSets.loc[n]
            i = QtWidgets.QListWidgetItem()
            i.setText('%s \t\t %s' %(IS['Nam'], self.imaging_mode_list[IS['Mod']]))
            if IS['Act']:   i.setBackground(QtGui.QBrush(QtGui.QColor('green')))
            else:           i.setBackground(QtGui.QBrush(QtGui.QColor('light grey')))
            self.ISetListWidget.insertItem(n,i)
        #select first set by default
        self.ISetListWidget.setCurrentRow(0)
        self.set_ISetValues_to_GUI()
  
    def saveDataFrame(self):
        self.ImagingSets.to_csv(self.ISmemory, mode='w', index=True)
                  
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
        self.camera1.close()
        self.TLsdk.dispose()
        self.camera3.close()
    
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    gui = Raymond()
    gui.show()
    app.exec_()