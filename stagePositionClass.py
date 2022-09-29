# -*- coding: utf-8 -*-
"""
Created on Wed Jul 13 15:50:16 2022

@author: Ray Lee
"""


from PyQt5 import QtGui, QtCore

class QDoublePushButton(QtGui.QPushButton):
    doubleClicked = QtCore.pyqtSignal()
    clicked = QtCore.pyqtSignal()

    def __init__(self, *args, **kwargs):
        QtGui.QPushButton.__init__(self, *args, **kwargs)
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.clicked.emit)
        super().clicked.connect(self.checkDoubleClick)

    @QtCore.pyqtSlot()
    def checkDoubleClick(self):
        if self.timer.isActive():
            self.doubleClicked.emit()
            self.timer.stop()
        else:
            self.timer.start(250)

class ImagingLocation(QtGui.QWidget):
    def um2px(self, um):
        print(um, '!')
        return int((um + 10000) * (1/self.calibration))
    
    def px2um(self, px):
        return int(-10000 + (px * self.calibration))
    
    def __init__(self, parent, calibration, scene):
        super(ImagingLocation, self).__init__(parent)
        self.Xum = None
        self.Yum = None
        self.Zum = None
        self.Xpx = None
        self.Ypx = None
        
        self.scene = scene
        
        self.calibration = calibration
        self.pen = QtGui.QPen()
        self.pen.setWidth(10)
        self.pen.setColor(QtGui.QColor('red'))
         
        self.index = None
        self.active = True
        self.ID = self.parent().getLocationID()
        self.markGroup = self.scene.createItemGroup([])
        self.markNumber = QtGui.QGraphicsTextItem()
    # build widgets
        self.Xedit      = QtGui.QLineEdit()
        self.Yedit      = QtGui.QLineEdit()
        self.Zedit      = QtGui.QLineEdit()
        self.inUse      = QtGui.QCheckBox('')
        self.del_       = QDoublePushButton('Delete')
        self.goto       = QDoublePushButton('Go')
        self.update_    = QDoublePushButton('Update')
        self.inUse.setChecked(self.active)
        self.inUse.stateChanged.connect(self.updatePosition)  
        self.Xedit.returnPressed.connect(self.updatePosition)
        self.Yedit.returnPressed.connect(self.updatePosition)
        self.Zedit.returnPressed.connect(self.updatePosition)
        self.del_.doubleClicked.connect(self.delete)
        self.goto.doubleClicked.connect(self.move_stage)
        self.update_.doubleClicked.connect(self.updateButtonClick)
    # validate input    
        self.Xedit.setValidator(QtGui.QDoubleValidator(self.parent().stage.imaging_limits[0][1],self.parent().stage.imaging_limits[0][0],1))
        self.Yedit.setValidator(QtGui.QDoubleValidator(self.parent().stage.imaging_limits[1][1],self.parent().stage.imaging_limits[1][0],1))
        self.Zedit.setValidator(QtGui.QDoubleValidator(self.parent().stage.imaging_limits[2][1],self.parent().stage.imaging_limits[2][0],1))

    def move_stage(self):
        self.parent().stage.move_to(X=self.Xum, Y=self.Yum, Z=self.Zum)
        

    
    
    def updatePosition(self): # handles changes to the text fields and checkbox
        # get and store new values
        self.active = self.inUse.isChecked()
        self.Xum = int(self.Xedit.text())
        self.Yum = int(self.Yedit.text())
        self.Zum = int(self.Zedit.text())
        self.Xpx = self.um2px(self.Xum)
        self.Ypx = self.um2px(self.Yum)
        # edit mark
        self.markGroup.setPos(self.Xpx,self.Ypx)
        
    def updateButtonClick(self): #handles changes after update button clicked
        # get current positon
        self.Xum, self.Yum, self.Zum = self.parent().stage.getPosition()
        #set text boxes
        self.Xedit.setText(self.Xum)
        self.Yedit.setText(self.Yum)
        self.Zedit.setText(self.Zum)
        #call regular update position function
        self.updatePosition()
        
    def updateIndex(self, i):
        self.index = i
        self.markNumber.setHtml('<p style="color:red; font: 90px;">%s</p>' %int(self.index+1))
        
    def addLocation(self,x,y,z,r, um=False, checked=True):
        
    # get unique ID
        
        print('unique ID:', self.ID)
    
    # get position
        if self.parent().stage.flag_CONNECTED and um:
            position = self.parent().stage.get_position()
            if x==None: x=self.parent().stage.get_position()[0]
            if y==None: y=self.parent().stage.get_position()[1]
            if z==None: z=self.parent().stage.get_position()[2]

    # interchange units
        if um:                  #if position supplied in um, convert to pixels
            self.Xpx = self.um2px(x)
            self.Ypx = self.um2px(y)
            self.Xum = x
            self.Yum = y
        else:                   #if position supplied in pixels, convert to um
            self.Xum = self.px2um(x)
            self.Yum = self.px2um(y)
            self.Xpx = x
            self.Ypx = y
            
        print('add location', x,y,z,r,'in um:', um, 'active:', checked)    
    # get index
        if r == None: self.index = self.parent().PositionListWidget.rowCount() 
        else: self.index = r
        
    # set fields
        if checked: 
            self.pen.setColor(QtGui.QColor('#FF0000'))
            self.active = True
        else:       
            self.pen.setColor(QtGui.QColor('#888888'))
            self.active = False
        self.Xedit.setText('%s' %self.Xum)
        self.Yedit.setText('%s' %self.Yum)
        self.Zedit.setText('%s' %self.Zum)

    # build mark
        for l in [[-100,-100],[+100,-100],[-100,+100],[+100,+100]]: 
            a = self.scene.addLine(l[0],l[1],l[0]/2,l[1]/2,self.pen)
            a.setFlag(QtGui.QGraphicsItem.ItemIsSelectable)
            self.markGroup.addToGroup(a)
        ti = QtGui.QGraphicsTextItem()
        ti.setHtml('<p style="color:red; font: 90px;">%s</p>' %int(self.index+1))
        ti.setPos(120,120)
        ti.setFlag(QtGui.QGraphicsItem.ItemIsSelectable)
        self.markGroup.addToGroup(ti)
        self.markGroup.setPos(self.Xpx,self.Ypx)

    # add widgets to table
        self.parent().PositionListWidget.insertRow(self.index)
        self.parent().PositionListWidget.setRowHeight(self.index, 15)
        self.parent().PositionListWidget.setCellWidget(self.index,  0, self.inUse)
        self.parent().PositionListWidget.setCellWidget(self.index,  1, self.Xedit)
        self.parent().PositionListWidget.setCellWidget(self.index,  2, self.Yedit)
        self.parent().PositionListWidget.setCellWidget(self.index,  3, self.Zedit)
        self.parent().PositionListWidget.setCellWidget(self.index,  4, self.del_)
        self.parent().PositionListWidget.setCellWidget(self.index,  5, self.goto)
        self.parent().PositionListWidget.setCellWidget(self.index,  6, self.update_)
        
        
        
    def delete(self):
        print('delete function...')

    def removeMark(self, g):
        print('remove mark', g)
        for item in g.childItems():
            self.stageScene.removeItem(item)
        self.stageScene.destroyItemGroup(g) 
        
