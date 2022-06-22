# -*- coding: utf-8 -*-
"""
Created on Wed Jun 22 18:17:54 2022

@author: Simon
"""
from PyQt5 import QtGui, QtCore, QtWidgets

class StageNavigator(QtWidgets.QGraphicsView):
    mapClicked = QtCore.pyqtSignal(QtCore.QPoint)

    def __init__(self, parent, calibration, w, h):
        super(StageNavigator, self).__init__(parent)
        self.Raymond = parent #need to rename parent class to access it, don't know why this works
        self.zoom = 0
        self.um2px = 1/calibration
        self.px2um = calibration
        self.stageDim = [int(w/calibration),int(h/calibration)]
        self.stageCen = [int(self.stageDim[0]/2),int(self.stageDim[1]/2)]
        self._empty = True
        self.stageScene = QtWidgets.QGraphicsScene(self)
        self.stageScene.setSceneRect(QtCore.QRectF(0,0,self.stageDim[0],self.stageDim[1]))
        self.stagePixmap = QtWidgets.QGraphicsPixmapItem(QtGui.QPixmap(self.stageDim[0],self.stageDim[1]))
        self.stageScene.addItem(self.stagePixmap)
        
        # add mm edge grid
        pen = QtGui.QPen()
        pen.setWidth(5)
        pen.setColor(QtGui.QColor('white'))
        for x in range(0,self.stageDim[0],int(1000*self.um2px)):
            self.stageScene.addLine(x, 0, x, 200, pen)
            self.stageScene.addLine(x, self.stageDim[0]-200, x,self.stageDim[0], pen)
        for y in range(0,self.stageDim[1],int(1000*self.um2px)):
            self.stageScene.addLine(0, y, 200, y, pen)
            self.stageScene.addLine(0, self.stageDim[1]-200, 200, self.stageDim[1], pen)
        
            
        self.setScene(self.stageScene)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(30, 30, 30)))
        self.setFrameShape(QtWidgets.QFrame.NoFrame)

    def drawForeground(self, painter, rect):
        pen = QtGui.QPen()
        pen.setWidth(5)
        pen.setColor(QtGui.QColor('red'))
        # add centre lines
        self.stageScene.addLine(self.stageCen[0], 0, self.stageCen[0], self.stageDim[0], pen)
        self.stageScene.addLine(0, self.stageCen[1], self.stageDim[1], self.stageCen[1], pen)

    def fitInView(self, scale=True):
        rect = QtCore.QRectF(self.stagePixmap.pixmap().rect())
        if not rect.isNull():
            self.setSceneRect(rect)
            if not self._empty:
                unity = self.transform().mapRect(QtCore.QRectF(0, 0, 1, 1))
                self.scale(1 / unity.width(), 1 / unity.height())
                viewrect = self.viewport().rect()
                scenerect = self.transform().mapRect(rect)
                factor = min(viewrect.width() / scenerect.width(),
                             viewrect.height() / scenerect.height())
                self.scale(factor, factor)
            self.zoom = 0

    def mouseDoubleClickEvent(self, e):
        xPx, yPx = int(self.mapToScene(e.x(), e.y()).x()), int(self.mapToScene(e.x(), e.y()).y())
        xUm, yUm = 10000 - xPx*self.px2um,10000 -  yPx*self.px2um
        print('px:', xPx, yPx)
        print('um:', xUm, yUm)
        # add mark to StageMap
        self.addMark(xPx,yPx)
        # add position to position List
        self.Raymond.addPos(position = [xUm,yUm,0], getZ=True)
    
    def addMark(self,x,y):
        pen = QtGui.QPen()
        pen.setWidth(10)
        pen.setColor(QtGui.QColor('red'))
        self.stageScene.addLine(x-100,y-100,x-50,y-50,pen)
        self.stageScene.addLine(x+100,y-100,x+50,y-50,pen)
        self.stageScene.addLine(x-100,y+100,x-50,y+50,pen)
        self.stageScene.addLine(x+100,y+100,x+50,y+50,pen)
        
        
        
    def addPixmap(self, img,x,y):
        self.zoom = 0
        self._empty = False
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.stageScene.addPixmap(QtGui.QPixmap(img))
        item_list = self.stageScene.items()
        item_list[0].setPos(x,y)
        self.fitInView()
        print(self, self.parent,self.parent())
        
    def wheelEvent(self, event):
        if not self._empty:
            if event.angleDelta().y() > 0:
                factor = 1.25
                self.zoom += 1
            else:
                factor = 0.8
                self.zoom -= 1
            if self.zoom > 0:
                self.scale(factor, factor)
            elif self.zoom == 0:
                self.fitInView()
            else:
                self.zoom = 0

    def toggleDragMode(self):
        if self.dragMode() == QtWidgets.QGraphicsView.ScrollHandDrag:
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        elif not self.stagePixmap.pixmap().isNull():
            self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)

    def mousePressEvent(self, event):
        if self.stagePixmap.isUnderMouse():
            self.mapClicked.emit(QtCore.QPoint(event.pos()))
        super(StageNavigator, self).mousePressEvent(event)