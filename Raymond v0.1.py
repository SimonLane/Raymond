# -*- coding: utf-8 -*-
"""
Created on Wed May  5 16:06:56 2021

@author: Ray Lee
"""



import sys
import pandas           as pd
import numpy            as np
import pyqtgraph        as pg
from PyQt5 import QtGui, QtWidgets




class Raymond(QtWidgets.QMainWindow):
    def __init__(self):
        super(Raymond, self).__init__()


# =============================================================================
#  Microscope properties - edit as needed
# =============================================================================
    # available filters
        self.filter_list = [
                "Empty",
                "610+-30, 650SP",
                "520+-20, 650SP",
                "Pol. V",
                "Pol. H",
                "Empty (Pete has 650SP)"
                ]
    # available imaging modalities
        self.imaging_mode_list = ["Scattering", "Fluoresence", "Musical", "SHG"]
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
        self.newSet = pd.DataFrame({'ID':0,'Act':False,'Nam':'name','Exp':10,'Fil':0,'Mod':0,'Mus':0,'Zed':True,
              'Wa1':True,'Wa2':False,'Wa3':False,'Wa4':False,'Wa5':False,'Wa6':False,
              'Wa7':False,'Wa8':False,'Wa9':False,'Wa10':False}, index=[-1])
    # basic properties for the UI
        self.GUI_colour = QtGui.QColor(75,75,75)
        self.GUI_font   = QtGui.QFont('Times',10)
        self.setFont(self.GUI_font)
    # The dataframe used to hold imaging parameters for all defined imaging sets
        self.ISmemory = "ImagingParameters.txt"
        self.ISheaders = ['ID','Act','Nam','Exp','Fil','Mod','Mus','Zed','Wa1','Wa2','Wa3','Wa4','Wa5','Wa6','Wa7','Wa8','Wa9']
# =============================================================================
# End editable properties      
# =============================================================================
        self.fromIndex = 0
        
# build the UI
        self.initUI()

# load in the imaging sets
        self.loadDataFrame()
        
   
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
               #Setup main Window
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def initUI(self):
        self.setScreenSize()
        self.setWindowTitle('Raymond V0.1')
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
        
        self.NameLabel       = QtWidgets.QLabel('Name:')
        self.ISetName            = QtWidgets.QLineEdit('name')
        self.ISetName.editingFinished.connect(self.updateISet)
        
        self.ModeLabel       = QtWidgets.QLabel('Imaging Mode:')
        self.ISetMode            = QtWidgets.QComboBox()
        self.ISetMode.addItems(self.imaging_mode_list)
        self.ISetMode.currentIndexChanged.connect(self.updateISet)
        
        self.FilterLabel       = QtWidgets.QLabel('Filter:')
        self.ISetFilter          = QtWidgets.QComboBox()
        self.ISetFilter.addItems(self.filter_list)
        self.ISetFilter.currentIndexChanged.connect(self.updateISet)
        
        self.ISetExposure        = QtWidgets.QLineEdit('10')
        self.ISetExposure.editingFinished.connect(self.updateISet)
        self.ExposureLabel       = QtWidgets.QLabel('Exposure(ms):')
        
        self.ISetZ               = QtWidgets.QCheckBox('Z-stack')
        self.ISetZ.clicked.connect(self.updateISet)
        
        self.ISetMusicalN        = QtWidgets.QLineEdit('50')
        self.ISetMusicalN.editingFinished.connect(self.updateISet)
        self.MusicalLabel        = QtWidgets.QLabel('Musical (n Frames):')
        
        self.LiveButton          = QtWidgets.QPushButton('Live')
        self.GrabButton          = QtWidgets.QPushButton('Grab')
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
        self.ImagingSettingsSubGroup.layout().addWidget(self.ExposureLabel,         4,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetExposure,          4,1,1,1)       
        self.ImagingSettingsSubGroup.layout().addWidget(self.MusicalLabel,          6,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetMusicalN,          6,1,1,1)
        
        self.ImagingSettingsSubGroup.layout().addWidget(self.LightsourceLabel,      1,2,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[0],    1,3,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[1],    2,3,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[2],    3,3,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[3],    4,3,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[4],    5,3,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[5],    6,3,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[6],    7,3,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[7],    8,3,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[8],    9,3,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.ISetlightsource[9],    10,3,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.LiveButton,            11,0,1,1)
        self.ImagingSettingsSubGroup.layout().addWidget(self.GrabButton,            11,1,1,1)

    # assembly                                                                # (y x h w)
        self.ExptBuildGroup     = QtWidgets.QGroupBox('Experiment Builder')
        self.ExptBuildGroup.setLayout(QtWidgets.QGridLayout())
        self.ExptBuildGroup.layout().addWidget(self.NewISetButton,               0,0,1,1)
        self.ExptBuildGroup.layout().addWidget(self.DelISetButton,               0,1,1,1)
        self.ExptBuildGroup.layout().addWidget(self.ISetListWidget,              1,0,5,3)
        self.ExptBuildGroup.layout().addWidget(self.ImagingSettingsSubGroup,     0,4,6,7)
        
        
        
        
#~~~~~~~~~~~~~~~ Image Display ~~~~~~~~~~~~~~~  
        self.ImageDisplayGroup  = QtWidgets.QGroupBox('Display')
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

#        self.imagewidget.ui.roiBtn.hide()
#        self.imagewidget.ui.menuBtn.hide()

        self.ImageDisplayGroup.setLayout(QtGui.QGridLayout())
        self.ImageDisplayGroup.layout().addWidget(self.view_modes[0],              0,0,1,2)
        self.ImageDisplayGroup.layout().addWidget(self.view_modes[1],              0,2,1,2)
        self.ImageDisplayGroup.layout().addWidget(self.view_colour_modes[0],       1,0,1,2)
        self.ImageDisplayGroup.layout().addWidget(self.view_colour_modes[1],       1,2,1,2)
        self.ImageDisplayGroup.layout().addWidget(self.saveImageButton,            0,6,1,2)

        self.ImageDisplayGroup.layout().addWidget(self.imagewidget,                2,0,10,10)

        
        
                

        
#==============================================================================
# Overall assembly
#==============================================================================
        OverallLayout = QtWidgets.QGridLayout()
#        using a 20x20 grid for flexible arrangement of the panels
#Right-hand column
                                                                  # (y x h w)
        OverallLayout.addWidget(self.ExptBuildGroup,                0,12,6,8)
        OverallLayout.addWidget(self.ImageDisplayGroup,             0,0,20,12) # (placeholder)
        

        self.MainArea = QtWidgets.QFrame()
        self.MainArea.setStyleSheet("""
               font: 10pt Modum;
        """)
        self.MainArea.setLineWidth(0)
        self.MainArea.setLayout(OverallLayout)
        self.setCentralWidget(self.MainArea)

# =============================================================================
#  Image Display Functions
# =============================================================================

    def saveSingleImage(self):
        pass
    
    def displayMode(self):
        pass
    

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
        self.fromIndex = self.ISetListWidget.currentRow()
        
    def ISetOrderChange(self, event):
        # Drag and drop event detected on the ISetListWidget. 
        # need to rearrange the ImagingSets row order to match
        n_items = self.ImagingSets.shape[0]
        from_ = int(self.fromIndex)
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
        self.saveDataFrame()
        pass
    
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    gui = Raymond()
    gui.show()
    app.exec_()