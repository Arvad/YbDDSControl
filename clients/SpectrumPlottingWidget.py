from PyQt4 import QtGui
import pyqtgraph as pg
import sys
from os import listdir
import re

class SpectrumPlottingWidget(QtGui.QWidget):
    def __init__(self):
        super(SpectrumPlottingWidget,self).__init__()
        self.initialize()
        self.default_path = None            

    def initialize(self):
        buttonspanel = QtGui.QWidget()
        Directory = QtGui.QPushButton('Dir...')
        Directory.pressed.connect(self.dir_pressed)
        self.directorydisplay = QtGui.QLineEdit()
        plotbutton = QtGui.QPushButton('Plot')
        plotbutton.pressed.connect(self.plot_pressed)
        panellayout = QtGui.QHBoxLayout()
        panellayout.addWidget(Directory)
        panellayout.addWidget(self.directorydisplay)
        panellayout.addWidget(plotbutton)
        buttonspanel.setLayout(panellayout)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(buttonspanel)
        self.mainwindow = pg.GraphicsWindow()
        self.mainwindow.scene().sigMouseClicked.connect(self.mouse)
        layout.addWidget(self.mainwindow)
        self.setLayout(layout)
        self.show()

    def dir_pressed(self):
        if self.default_path is None:                
            directory = QtGui.QFileDialog.getExistingDirectory()
            self.default_path = directory
        else:
            directory = QtGui.QFileDialog.getExistingDirectory(self,'Pick a directory',self.default_path)
            self.default_path = directory
        self.directorydisplay.setText(directory)

    def plot_pressed(self):
        self.dataitemdict={}
        self.mainwindow.clear()
        if len(self.directorydisplay.text()) > 0:
            filelist = [i for i in listdir(self.directorydisplay.text()) if i.endswith(".csv") and re.search('spectrum',i) is not None]
            Ncolumn = int(len(filelist)**0.5)+1
            i = 0
            j = 0
            for filename in filelist:
                x,y = self.readdata(self.directorydisplay.text()+'\\'+filename)
                p = self.mainwindow.addPlot(row = i, col = j)
                d = p.plot(x,y)
                p.setToolTip(filename)
                p.setTitle(filename[9:13])
                self.dataitemdict[p] = (x,y,filename)
                j += 1
                if j ==Ncolumn:
                    j = 0
                    i += 1

    def mouse(self,event):
        plots =  ([x for x in self.mainwindow.scene().items(event.scenePos()) if isinstance(x, pg.PlotItem)])
        x,y,fname = self.dataitemdict[plots[0]]
        temp = pg.plot(x,y,labels = {'top':fname},symbol='o', pen={'color': 0.8, 'width': 2})

    def readdata(self,filename):
        with open(filename,'r') as f:
            x = []
            y = []
            for line in f:
                columns = line.split(',')
                try:
                    x.append(float(columns[1]))
                    y.append(float(columns[2]))
                except Exception,e:
                    pass
            return x,y




if __name__=="__main__":
    a = QtGui.QApplication( [] )
    pl = Plottingwidget()
    sys.exit(a.exec_())