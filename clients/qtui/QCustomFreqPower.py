import sys
from PyQt4 import QtGui, QtCore
import numpy as np

class customStepBox(QtGui.QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super(customStepBox, self).__init__(*args, **kwargs)
          
    def textFromValue(self, value):
        ## implement value into MHZ with leading zeros ##
        str_show = "%8.6f" % (10**(value-6.0))
#         str_show = "%8.6f" % value
        return str_show
    
    def valueFromText(self, text):
        value = np.log10(float(text))+6.0
        return value
        


class TextChangingButton(QtGui.QPushButton):
    """Button that changes its text to ON or OFF and colors when it's pressed""" 
    def __init__(self, parent = None):
        super(TextChangingButton, self).__init__(parent)
        self.setCheckable(True)
        self.setFont(QtGui.QFont('MS Shell Dlg 2',pointSize=10))
        self.setSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Minimum)
        #connect signal for appearance changing
        self.toggled.connect(self.setAppearance)
        self.defaultstyle = self.styleSheet()
        self.setAppearance(self.isDown())
        self.setAutoFillBackground(True)
        self.setStyleSheet("QPushButton {\n"
"color: black;\n"
"border: 2px solid #555;\n"
"border-radius: 11px;\n"
"padding: 5px;\n"
"background: qradialgradient(cx: 0.3, cy: -0.4,\n"
"fx: 0.3, fy: -0.4,\n"
"radius: 1.35, stop: 0 lightgray, stop: 1 gray);\n"
"min-width: 80px;\n"
"max-width: 80px;\n"
"}\n"
"\n"
"QPushButton:hover {\n"
"background: qradialgradient(cx: 0.4, cy: 0.5,\n"
"fx: 0.3, fy: -0.4,\n"
"radius: 1.35, stop: 0 red, stop: 1 lightred);\n"
"}\n"
"\n"
"QPushButton:checked {\n"
"background: qradialgradient(cx: 0.4, cy: -0.1,\n"
"fx: 0.4, fy: -0.1,\n"
"radius: 1.35, stop: 0 red, stop: 1 darkred);\n"
"}")
        
    def setAppearance(self, down):
        if down:
            self.setText('I')
            #self.setStyleSheet("background-color: red; border-color:darkred")
        else:
            self.setText('O')
            #self.setStyleSheet(self.defaultstyle)
    
    def sizeHint(self):
        return QtCore.QSize(37, 26)

class QCustomFreqPower(QtGui.QFrame):
    def __init__(self, title, switchable = True, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.setFrameStyle(0x0001 | 0x0030)
        self.makeLayout(title, switchable)
    
    def makeLayout(self, title, switchable):
        layout = QtGui.QGridLayout()
        #labels
        title = QtGui.QLabel(title)
        title.setFont(QtGui.QFont('MS Shell Dlg 2',pointSize=16))
        title.setAlignment(QtCore.Qt.AlignCenter)
        freqlabel = QtGui.QLabel('Frequency (MHz)')
        powerlabel = QtGui.QLabel('Power (dBm)')
        steplabel = QtGui.QLabel('Step (MHz)')

        layout.addWidget(title,0, 0,1,4)
        layout.addWidget(freqlabel,1, 1)
        layout.addWidget(steplabel,1,2)
        layout.addWidget(powerlabel,1, 3)        
        
        
        #editable fields
        self.spinFreq = QtGui.QDoubleSpinBox()
        #self.spinFreq = customSpinBox()
        self.spinFreq.setSizePolicy(QtGui.QSizePolicy.Fixed,QtGui.QSizePolicy.Fixed)
        self.spinFreq.setFont(QtGui.QFont('MS Shell Dlg 2',pointSize=16))
        self.spinFreq.setDecimals(9)
        self.spinFreq.setSingleStep(0.00001) ## set single step here
        self.spinFreq.setRange(1.0,400.0)
        self.spinFreq.setKeyboardTracking(False)
        
        #self.stepBox = QtGui.QDoubleSpinBox()
        self.stepBox = customStepBox()
        self.stepBox.setSizePolicy(QtGui.QSizePolicy.Fixed,QtGui.QSizePolicy.Fixed)
        self.stepBox.setFont(QtGui.QFont('MS Shell Dlg 2',pointSize=13))
        self.stepBox.setDecimals(6)
        self.stepBox.setRange(0.0,6.0)
        self.stepBox.setValue(1.0)
        self.stepBox.setKeyboardTracking(False)
        
        self.stepBox.valueChanged.connect(self.stepChanged)
        
        self.spinPower = QtGui.QDoubleSpinBox()
        self.spinPower.setFont(QtGui.QFont('MS Shell Dlg 2',pointSize=16))
        self.spinPower.setSizePolicy(QtGui.QSizePolicy.Fixed,QtGui.QSizePolicy.Fixed)
        self.spinPower.setDecimals(2)
        self.spinPower.setSingleStep(0.1)
        self.spinPower.setRange(-145.0, 30.0)
        self.spinPower.setKeyboardTracking(False)
        layout.addWidget(self.spinFreq,     2, 1)
        layout.addWidget(self.stepBox,      2, 2)
        layout.addWidget(self.spinPower,    2, 3)
        if switchable:
            self.buttonSwitch = TextChangingButton()
            layout.addWidget(self.buttonSwitch, 2, 4)
        self.setLayout(layout)
        
    def stepChanged(self, value):
        self.spinFreq.setSingleStep((10**(value-6.0)))
        #print value
    
    def setPowerRange(self, powerrange):
        self.spinPower.setRange(*powerrange)
    
    def setFreqRange(self, freqrange):
        self.spinFreq.setRange(*freqrange)
        
    def setPowerNoSignal(self, power):
        self.spinPower.blockSignals(True)
        power = power['dBm']
        self.spinPower.setValue(power)
        self.spinPower.blockSignals(False)
        
    def setFreqNoSignal(self, freq): 
        self.spinFreq.blockSignals(True)
        freq = freq['MHz']
        self.spinFreq.setValue(freq)
        self.spinFreq.blockSignals(False)
    
    def setStateNoSignal(self, state):
        self.buttonSwitch.blockSignals(True)
        self.buttonSwitch.setChecked(state)
        self.buttonSwitch.setAppearance(state)
        self.buttonSwitch.blockSignals(False)

if __name__=="__main__":
    app = QtGui.QApplication(sys.argv)
    icon = QCustomFreqPower('Control')
    icon.show()
    app.exec_()