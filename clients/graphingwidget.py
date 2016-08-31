from PyQt4 import QtGui
from PyQt4.QtCore import QThread, pyqtSignal, pyqtSlot, QObject
from twisted.internet.defer import inlineCallbacks
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator, MultipleLocator
import numpy as np
from connection import connection
import pyqtgraph as pg
import sys

global harwareConfiguration


class graphingwidget(QtGui.QWidget):

    SIGNALID = 104692
    update_signal = pyqtSignal(list)
    def __init__(self,reactor, cnx):
        super(graphingwidget,self).__init__()
        self.reactor = reactor
        self.connection = cnx
        self.initialize()


    @inlineCallbacks
    def initialize(self):
        p = yield self.connection.get_server('Pulser')
        hwconfigpath = yield p.get_hardwareconfiguration_path()
        sys.path.append(hwconfigpath)
        global hardwareConfiguration
        from hardwareConfiguration import hardwareConfiguration
        self.ddslist = hardwareConfiguration.ddsDict
        self.plottingthread = QThread()
        self.plottingworker = PlottingWorker()
        self.plottingworker.plotted_trigger.connect(self.update)
        self.plottingworker.moveToThread(self.plottingthread)
        self.plottingthread.start()
        self.do_layout(self.ddslist)
        


    def do_layout(self,ddslist):
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
 
        self.plottingworker.setup_figure(ddslist,self.figure)
        

    def update(self):
        pass

    def update_tooltip(self,event):
        if event.inaxes:
            x = event.xdata
            self.canvas.setToolTip(str(int(x)))

class PlottingWorker(QObject):
    plotted_trigger= pyqtSignal()
    start = pyqtSignal(list)
    def __init__(self):
        super(PlottingWorker,self).__init__()
        self.start.connect(self.run)

    def setup_figure(self,ddslist,figure):
        self.thread_figure = figure
        self.plotlist = {}
        for adds,config in ddslist.iteritems():
            self.plotlist[adds] = (config.channelnumber,pg.PlotCurveItem(range(10),[1]*10,pen='w'))
            self.thread_figure.addItem(self.plotlist[adds][1])
        self.thread_figure.setYRange(0,17)
        self.thread_figure.setMouseEnabled(x=False,y=False)
        self.thread_figure.showGrid(x=True,y=True,alpha=0.4)

            
    def do_sequence(self,sequence):
        lastend = 0
        counter = 1.5
        self.thread_figure.clear()
        for achannelname, aplot in self.plotlist.iteritems():
            channelpulses = [i for i in sequence if i[0] == achannelname]
            channelpulses.sort(key= lambda name: name[1]['ms'])
            starttimes = []
            endtimes = []
            frequencies = []
            amplitudes = []
            for apulse in channelpulses:
                starttimes.append(apulse[1]['ms'])
                endtimes.append((apulse[1]+ apulse[2])['ms'])
                frequencies.append(apulse[3]['MHz'])
                amplitudes.append(apulse[4]['dBm'])

            xdata = [0]
            ydata = [0]
            for i in range(len(starttimes)):
                xdata += [starttimes[i]]*2 + [endtimes[i]]*2
                               
                if ydata[-1] == 0:
                    ydata += [0.25,0.75,0.75,0.25]
                else:
                    ydata += [0.75,0.25,0.25,0.75]

            lastend = int(xdata[-1]) if lastend<xdata[-1] else lastend
            self.plotlist[achannelname] = (aplot[0],pg.PlotCurveItem(xdata,[i+ aplot[0] for i in ydata],pen='w'))
            counter += 1
        for aplotname, aplotitem in self.plotlist.iteritems():
            self.thread_figure.addItem(aplotitem[1])

        
    
    @pyqtSlot(list)
    def run(self,sequence):
        self.do_sequence(sequence)
        self.plotted_trigger.emit()
 