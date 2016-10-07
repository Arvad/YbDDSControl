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
            filelist = [i for i in listdir(self.directorydisplay.text()) if i.endswith(".csv")]
            Ncolumn = int(len(filelist)**0.5)+1
            i = 0
            j = 0
            for filename in filelist:
                if 'sideband' in filename.lower():
                    data = self.getData(self.directorydisplay.text()+'\\'+filename,'Spectrum')
                    x = data['freq']
                    y1 = data['P_c']
                    y2 = data['N_tc']
                elif 'param' in filename.lower():
                    data = self.getData(self.directorydisplay.text()+'\\'+filename,'Parameterscan')
                    x = data['param']
                    y1 = data['P_c']
                    y2 = data['N_tc']
                else:
                    return
                p1 = self.mainwindow.addPlot(row = i*2, col = j)
                p2 = self.mainwindow.addPlot(row = i*2+1, col = j)
                p1.plot(x,y1)
                p1.setToolTip(filename)
                p1.setTitle(filename[9:13])
                self.dataitemdict[p1] = (x,y1,filename)
                p2.plot(x,y2)
                p2.setToolTip(filename)
                p2.setTitle(filename[9:13])
                p2.setXLink(p1)
                self.dataitemdict[p2] = (x,y2,filename)

                j += 1
                if j ==Ncolumn:
                    j = 0
                    i += 1

    def mouse(self,event):
        plots =  ([x for x in self.mainwindow.scene().items(event.scenePos()) if isinstance(x, pg.PlotItem)])
        x,y,fname = self.dataitemdict[plots[0]]
        temp = pg.plot(x,y,labels = {'top':fname})
        
    def getData(self,fname,scantype):
        with open(fname,'r') as f:
            if scantype == 'Parameterscan':
                data = {'freq':[],'param':[],'P_c':[],'N_tc':[]}
            elif scantype == 'Spectrum':
                data = {'freq':[],'P_c':[],'N_tc':[]}
            else:
                print 'Invalid scan type: ',scantype
                return None
            for line in f:
                columns = line.split(',')
                if columns[0] == ' shot':
                    continue
                else:
                    if scantype == 'Parameterscan':
                        try:
                            data['freq'].append(float(columns[2]))
                            data['param'].append(float(columns[3]))
                            data['P_c'].append(float(columns[4]))
                            data['N_tc'].append(float(columns[5]))
                        except Exception,e:
                            print e
                    elif scantype == 'Spectrum':
                        try:
                            data['freq'].append(float(columns[1]))
                            data['P_c'].append(float(columns[2]))
                            data['N_tc'].append(float(columns[3]))
                        except Exception,e:
                            print e
            return data
        
       
if __name__=="__main__":
    a = QtGui.QApplication( [] )
    pl = SpectrumPlottingWidget()
    sys.exit(a.exec_())