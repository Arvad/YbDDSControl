from PyQt4 import QtGui
from PyQt4.QtCore import pyqtSignal, pyqtSlot, QObject
import numpy as np
from connection import connection
import pyqtgraph as pg
import sys
import time

global harwareConfiguration


class graphingwidget(QtGui.QWidget):

    SIGNALID = 104692
    update_signal = pyqtSignal(list)
    def __init__(self,reactor, cnx):
        super(graphingwidget,self).__init__()
        self.connection = cnx
        self.initialize()


    def initialize(self):
        p = self.connection.pulser
        hwconfigpath = p.get_hardwareconfiguration_path()
        sys.path.append(hwconfigpath)
        global hardwareConfiguration
        from hardwareConfiguration import hardwareConfiguration
        self.ddslist = hardwareConfiguration.ddsDict
        self.do_layout()
        


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
        self.figure.setMouseEnabled(x=False,y=False)
        self.figure.showGrid(x=True,y=True,alpha=0.4)

    @pyqtSlot(list)       
    def do_sequence(self,sequence):
        tic = time.clock()
        xdatalist = []
        ydatalist = []
        for achannelname, adds in self.ddslist.iteritems():
            channelpulses = [i for i in sequence if i[0] == achannelname]
            channelpulses.sort(key= lambda name: name[1]['ms'])
            starttimes = []
            endtimes = []
            frequencies = []
            amplitudes = []
            for apulse in channelpulses:
                starttimes.append(apulse[1]['ms'])
                endtimes.append((apulse[1]+ apulse[2])['ms'])
            
            yhigh = 0.75+adds.channelnumber
            ylow = 0.25+adds.channelnumber

            xdata = [0]
            ydata = [ylow]
            for i in range(len(starttimes)):
                xdata += [starttimes[i]]*2 + [endtimes[i]]*2
                
                if ydata[-1] == ylow:
                    ydata += [ylow,yhigh,yhigh,ylow]
                else:
                    ydata += [yhigh,ylow,ylow,yhigh]
            
            xdatalist.append(xdata)
            ydatalist.append(ydata)
        self.plot(xdatalist,ydatalist)
        toc = time.clock()
        print "plotted ",toc-tic
        
        
    def plot(self,xlist,ylist):
        self.figure.clear()
        for i in range(len(xlist)):
            xdata = xlist[i]
            ydata = ylist[i]
            if len(xdata)>1:
                self.figure.addItem(pg.PlotCurveItem(xdata,ydata,pen='w'))

         