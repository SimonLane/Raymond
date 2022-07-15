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
        self.calibration = calibration
        self.stageDim = [int(w/calibration),int(h/calibration)]
        self.stageCen = [int(self.stageDim[0]/2),int(self.stageDim[1]/2)]
        self._empty = True
        self.stageScene = QtWidgets.QGraphicsScene(self)
        self.stageScene.setSceneRect(QtCore.QRectF(0,0,self.stageDim[0],self.stageDim[1]))
        self.setScene(self.stageScene)
        self.stagePixmap = QtWidgets.QGraphicsPixmapItem(QtGui.QPixmap(self.stageDim[0],self.stageDim[1]))
        self.offset = [0,-640] #offset in pixels to map to the real stage
       
        

        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(30, 30, 30)))
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.fitInView()

    def drawForeground(self, painter, rect):
        pen = QtGui.QPen()
        pen.setWidth(5)
        pen.setColor(QtGui.QColor('red'))
        # add centre lines
        self.stageScene.addLine(self.stageCen[0], 0, self.stageCen[0], self.stageDim[0], pen)
        self.stageScene.addLine(0, self.stageCen[1], self.stageDim[1], self.stageCen[1], pen)
        
        
    def fitInView(self, rect=None, scale=True):
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
            
    def mousePressEvent(self,e):
        if self.stagePixmap.isUnderMouse():
            self.mapClicked.emit(QtCore.QPoint(e.pos()))
        super(StageNavigator, self).mousePressEvent(e)
        xPx, yPx = int(self.mapToScene(e.x(), e.y()).x()), int(self.mapToScene(e.x(), e.y()).y())
        xUm, yUm = self.px2um(xPx), self.px2um(yPx)
        if e.button() == 4: #middle button
            # add position to position List
            self.Raymond.addPos(position = [xUm,yUm,None], inuse=True)
    
    def mouseDoubleClickEvent(self, e):
        xPx, yPx = int(self.mapToScene(e.x(), e.y()).x()), int(self.mapToScene(e.x(), e.y()).y())
        xUm, yUm = self.px2um(xPx), self.px2um(yPx)
        self.Raymond.stage.move_to(X=xUm, Y=yUm)
        
    def um2px(self, um):
        return int((um + 10000) * (1/self.calibration))
    
    def px2um(self, px):
        return int(-10000 + (px * self.calibration))
    
    def addMark(self,x,y,r, um=False, checked=True):
        print('add mark', r)
        pen = QtGui.QPen()
        pen.setWidth(10)
        if checked: pen.setColor(QtGui.QColor('#FF0000'))
        else:       pen.setColor(QtGui.QColor('#888888'))
        
        if um:        #if position supplied in um, convert to pixels
            x = self.um2px(x)
            y = self.um2px(y)

        g = self.stageScene.createItemGroup([])
        
        for l in [[-100,-100],[+100,-100],[-100,+100],[+100,+100]]: 
            a = self.scene().addLine(x+l[0],y+l[1],x+l[0]/2,y+l[1]/2,pen)
            a.setFlag(QtGui.QGraphicsItem.ItemIsSelectable)
            # a.setZValue(10)
            g.addToGroup(a)

        print('added mark',r)
        ti = QtGui.QGraphicsTextItem()
        ti.setHtml('<p style="color:red; font: 100px;">%s</p>' %int(r+1))
        # ti.setZValue(10)
        ti.setPos(x-180,y-220)
        ti.setFlag(QtGui.QGraphicsItem.ItemIsSelectable)
        g.addToGroup(ti)
        return g

    def removeMark(self, g):
        print('remove mark', g)
        for item in g.childItems():
            self.stageScene.removeItem(item)
        self.stageScene.destroyItemGroup(g) # try not deleting the group so positons in memory don't change

    def renumberPosition(self, group, number):
        print('renumbering',number)
        ti = group.childItems()[4]
        ti.setHtml('<p style="color:red; font: 100px;">%s</p>' %int(number))

        
        
    def addPixmap(self, img,x,y): #in um
        self.zoom = 0
        self._empty = False
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        a = self.stageScene.addPixmap(QtGui.QPixmap(img))
        a.setPos(self.um2px(x)+self.offset[0],self.um2px(y)+self.offset[1]) #in px
        a.setZValue(-1)
        #self.fitInView() #turn on to resize the view when doing tile scan
        
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
