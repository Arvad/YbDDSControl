from PyQt4 import QtGui
from PyQt4.QtCore import pyqtSignal, pyqtSlot, QObject, Qt
from twisted.internet.defer import inlineCallbacks
import numpy as np
from connection import connection
import pyqtgraph as pg
from pyqtgraph.SignalProxy import SignalProxy
import sys
import time

global harwareConfiguration


class graphingwidget(QtGui.QWidget):

    SIGNALID = 104692
    update_signal = pyqtSignal(list)
    def __init__(self,reactor, configpath):
        super(graphingwidget,self).__init__()
        self.reactor = reactor
        self.configpath = configpath
        self.initialize()
        self.timeoffset = 200

        
    def mouseMoved(self,evt):
        pos = evt
        if self.figure.sceneBoundingRect().contains(pos):
            mousePoint = self.figure.plotItem.vb.mapSceneToView(pos)
            index = int(mousePoint.x())
            self.label.setPos(mousePoint)
            self.label.setText("{:d}".format(int(mousePoint.x())))
            
    def initialize(self):
        sys.path.append(self.configpath)
        global hardwareConfiguration
        from hardwareConfiguration import hardwareConfiguration
        self.ddslist = hardwareConfiguration.ddsDict
        self.do_layout()
        self.figure.scene().sigMouseMoved.connect(self.mouseMoved)
        


    def do_layout(self):
        yaxis = pg.AxisItem(orientation='left')
        ticks = []
        sorteddict = sorted(self.ddslist.items(),key =lambda x: x[1].channelnumber)
        for i in range(0,17):
            if i < len(sorteddict):
                string = sorteddict[i][0]
            else:
                string = ""
            ticks.append((i+0.5,string))
        yaxis.setTicks([ticks])
        self.figure = pg.PlotWidget(axisItems ={'left':yaxis})
        self.layoutVertical = QtGui.QVBoxLayout(self)
        self.layoutVertical.addWidget(self.figure)
    
        for adds,config in self.ddslist.iteritems():
            self.figure.addItem(pg.PlotCurveItem(range(10),[1]*10,pen='w'))
        self.figure.setYRange(0,17)
        self.figure.setMouseEnabled(y=False)
        self.figure.showGrid(x=True,y=True,alpha=0.4)
        self.label = pg.TextItem(anchor=(0,1))
        self.figure.plotItem.addItem(self.label)

    @pyqtSlot(list,int,list)       
    def do_sequence(self,sequence,timelength,steadystatenames):
        xdatalist = []
        ydatalist = []
        for achannelname, adds in self.ddslist.iteritems():
            channelpulses = [i for i in sequence if i[0] == achannelname]
            channelpulses.sort(key= lambda name: name[1]['ms'])
            starttimes = []
            endtimes = []
            frequencies = []
            amplitudes = []
            if achannelname in steadystatenames:
                starttimes.append(-50)
                endtimes.append(0)
            for apulse in channelpulses:
                starttimes.append(apulse[1]['ms'])
                endtimes.append((apulse[1]+ apulse[2])['ms'])
            yhigh = 0.75+adds.channelnumber
            ylow = 0.25+adds.channelnumber
            
            if len(starttimes) < 0:
                xdata = [starttimes[0]+self.timeoffset]
                ydata = [yhigh]
            else:
                xdata = [self.timeoffset]
                ydata = [ylow]
            for i in range(len(starttimes)):
                xdata += [starttimes[i]+self.timeoffset]*2 + [endtimes[i]+self.timeoffset]*2
                
                if ydata[-1] == ylow:
                    ydata += [ylow,yhigh,yhigh,ylow]
                else:
                    ydata += [yhigh,ylow,ylow,yhigh]
            xdata.append(timelength)
            ydata.append(ylow)
            xdatalist.append(xdata)
            ydatalist.append(ydata)
        self.plot(xdatalist,ydatalist)
      
        
    def plot(self,xlist,ylist):
        self.figure.clear()
        self.figure.addItem(self.label)
        for i in range(len(xlist)):
            xdata = xlist[i]
            ydata = ylist[i]
            if len(xdata)>1:
                self.figure.addItem(pg.PlotCurveItem(xdata,ydata,pen='w'))
        self.figure.addItem(pg.InfiniteLine(self.timeoffset,pen=pg.mkPen('r',style=Qt.DashLine)))

         