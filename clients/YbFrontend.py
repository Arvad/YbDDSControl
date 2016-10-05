from PyQt4 import QtGui
from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal,QThread, QObject, QEventLoop, QWaitCondition, QTimer, Qt, QSettings
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.internet import threads
import threading
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvasQTAgg
import matplotlib.pyplot as plt
from DDS_CONTROL import DDS_CONTROL
from LEDindicator import LEDindicator
from parsingworker import ParsingWorker
from pulserworker import PulserWorker
import time


def buttonstyle(color, **kwargs):
    if 'textcolor' in kwargs:
        txtcolor = kwargs['textcolor']
    else:
        txtcolor = 'black'
    backgroundcolor = QtGui.QColor(color)    
    string =  "QPushButton {\n"
    string +="color: {:};\n".format(txtcolor)
    string +="border: 2px ;\n"
    string +="border-radius: 5px;\n"
    string +="padding: 5px;\n"
    string +="background: qradialgradient(cx: 0.3, cy: -0.4,\n"
    string +="fx: 0.3, fy: -0.4,\n"
    string +="radius: 1.35, stop: 0 {:}, stop: 1 {:});\n".format(backgroundcolor.name(),backgroundcolor.darker().name())
    string +="min-width: 80px;\n"
    string +="max-width: 80px;\n"
    string +="}\n"
    string +="\n"
    string +="QPushButton:hover {\n"
    string +="background: qradialgradient(cx: 0.4, cy: 0.5,\n"
    string +="fx: 0.3, fy: -0.4,\n"
    string +="radius: 1.35, stop: 0 {:}, stop: 1 {:});\n".format(backgroundcolor.name(),backgroundcolor.lighter().name())
    string +="}\n"
    string +="\n"
    string +="QPushButton:checked {\n"
    string +="background: {:}\n".format(backgroundcolor.lighter().name())
    string +="}"
    return string

class mainwindow(QtGui.QMainWindow):
    start_signal = pyqtSignal()
    stop_signal = pyqtSignal()
    

    def __init__(self,reactor, parent=None):
        super(mainwindow,self).__init__()
        self.reactor = reactor
        self.initialize()
        self.ParamID = None
        self.text = ""
        self.hardwarelock = False
        self.shottimevalue = 1000
        self.updatedelayvalue = 200
        self.setStyleSheet(buttonstyle('deepskyblue'))
        self.restoreGui()


    # This is a seperate function because it needs to 
    # be able to yield, and __init__ cannot do that
    @inlineCallbacks
    def initialize(self):
        yield self.connect_labrad()
        yield self.create_layout()
        self.messageout('Layout done')
        self.setup_parser()
        self.messageout('Initialization done')
        

    @inlineCallbacks
    def connect_labrad(self):
        from connection import connection
        cxn = connection()
        yield cxn.connect()
        self.connection = cxn
        self.context = cxn.context()
        print self.connection
        p = yield self.connection.get_server('Pulser')
        self.hwconfigpath = yield p.get_hardwareconfiguration_path()
        self.linetriggerstate = yield p.line_trigger_state()
       

########################################################################
#########                                                      #########
#########               Creating the GUI                       #########
#########                                                      #########
########################################################################
    
    #################
    # Central (main window)
    #################
    def create_layout(self):
        controlwidget = self.makeControlWidget()
        sequencewidget = self.makeSequenceWidget()
        spectrumplottingwidget = self.makeSpectrumPlottingWidget()
        centralwidget = QtGui.QWidget()
        tabwidget = QtGui.QTabWidget()

        tabwidget.addTab(sequencewidget,'Sequence')
        tabwidget.addTab(controlwidget,'Controls')
        tabwidget.addTab(spectrumplottingwidget,'Spectra')

        layout = QtGui.QHBoxLayout(self)
        layout.addWidget(tabwidget)
        centralwidget.setLayout(layout)

        self.setWindowTitle('Frontend')
        self.setCentralWidget(centralwidget)

    def closeEvent(self,event):
        settings = QSettings('settings.ini',QSettings.IniFormat)
        for aspinbox in self.findChildren(QtGui.QDoubleSpinBox) + self.findChildren(QtGui.QSpinBox):
            name = aspinbox.objectName()
            value= aspinbox.value()
            settings.setValue(name,value)

        settings.sync()

        self.reactor.stop()

    def restoreGui(self):
        settings = QSettings('settings.ini',QSettings.IniFormat)
        settings.setFallbacksEnabled(False)

        for aspinbox in self.findChildren(QtGui.QDoubleSpinBox) + self.findChildren(QtGui.QSpinBox):
            name = aspinbox.objectName()
            if settings.contains(name):
                value= settings.value(name).toFloat()[0]
                aspinbox.setValue(value)

  
    #################
    # Spectrum plotting tab panel
    #################
    def makeSpectrumPlottingWidget(self):
        from SpectrumPlottingWidget import SpectrumPlottingWidget
        widget = SpectrumPlottingWidget()
        return widget
        

    #################
    # Control tab panel
    #################
    def makeControlWidget(self):
        widget = QtGui.QWidget()
        from DDS_CONTROL import DDS_CONTROL
        layout = QtGui.QVBoxLayout()
        try:
            pass
            layout.addWidget(DDS_CONTROL(self.reactor,self.connection))
        except AttributeError, e:
            print e
        widget.setLayout(layout)
        return widget

    #################
    # Sqeuence tab panel
    #################
    def makeSequenceWidget(self):
        from graphingwidget import graphingwidget
        from SyntaxHighlighter import MyHighlighter
        self.filename = None
        splitterwidget = QtGui.QSplitter()
        self.graphingwidget = graphingwidget(self.reactor,self.hwconfigpath)
        self.writingwidget = QtGui.QTextEdit('Writingbox')

        font = QtGui.QFont()
        font.setFamily( "Courier" )
        font.setFixedPitch( True )
        font.setPointSize( 10 )
        self.writingwidget.setFont(font)
        highlighter = MyHighligher( self.writingwidget, 'Classic')
        self.writingwidget.setObjectName('SequenceWritingField')

        leftwidget=QtGui.QWidget()
        buttonpanel = self.makeButtonPanel()
        leftlayout = QtGui.QGridLayout()
        leftlayout.addWidget(buttonpanel,0,0)
        leftlayout.addWidget(self.writingwidget, 1,0,4,1)
        leftlayout.setSpacing(0)
        leftlayout.setContentsMargins(0,0,0,0)
        leftwidget.setLayout(leftlayout)


        splitterwidget.addWidget(leftwidget)
        splitterwidget.addWidget(self.graphingwidget)
        return splitterwidget
    
    
    def makeButtonPanel(self):
        panel = QtGui.QWidget()
        Startbutton = QtGui.QPushButton('RUN')
        Stopbutton = QtGui.QPushButton('STOP')
        LineTrigbutton = QtGui.QPushButton('linetrig')
        LineTrigbutton.setCheckable(True)
        LineTrigbutton.setChecked(self.linetriggerstate)
        LineTrigbutton.setStyleSheet(buttonstyle('yellow'))
        LineTrigbutton.pressed.connect(self.toggle_linetrig)
        self.ledrunning = LEDindicator('Running')
        self.ledprogramming = LEDindicator('Prog.')
        self.ledlinetrigger = LEDindicator('Ext trig',self.linetriggerstate)
        self.ledtracking = LEDindicator('Listening to Param')
        self.ledparsing = LEDindicator('Parse')
        updatedelay = QtGui.QSpinBox()
        updatedelaylabel = QtGui.QLabel('Update delay')
        shottime = QtGui.QSpinBox()
        shottimelabel = QtGui.QLabel('Shot time')
        timeoffset = QtGui.QSpinBox()
        timeoffsetlabel = QtGui.QLabel('Offset')

        filetoolbar = QtGui.QToolBar()
        filetoolbar.addAction(QtGui.QIcon('icons/document-open.svg'),'open',self.openbuttonclick)
        filetoolbar.addAction(QtGui.QIcon('icons/document-save.svg'),'save',self.savebuttonclick)
        filetoolbar.addAction(QtGui.QIcon('icons/document-new.svg'),'new',self.newbuttonclick)

        shottime.valueChanged.connect(self.shottime_value_changed)
        updatedelay.valueChanged.connect(lambda val: setattr(self,"updatedelayvalue",val/1000.))
        timeoffset.valueChanged.connect(self.offset_value_changed)
        shottime.setObjectName('shottime')
        updatedelay.setObjectName('updatedelay')
        timeoffset.setObjectName('timeoffset')

        shottime.setRange(0,3000)
        shottime.setValue(1000)
        updatedelay.setRange(0,3000)
        updatedelay.setValue(1)
        shottime.setSuffix(' ms')
        updatedelay.setSuffix(' ms')
        timeoffset.setSuffix(' ms')
        timeoffset.setRange(0,3000)
        timeoffset.setValue(350)

        self.Messagebox = QtGui.QTextEdit()
        self.Messagebox.setReadOnly(True)
        font = self.Messagebox.font()
        font.setFamily("courier")
        font.setPointSize(10)
        self.Messagebox.contextMenuEvent = self.messagebox_contextmenu

        Startbutton.setCheckable(True)
        Startbutton.setChecked(False)
        Stopbutton.setCheckable(True)
        Stopbutton.setChecked(True)
        Startbutton.setStyleSheet(buttonstyle('green'))
        Stopbutton.setStyleSheet(buttonstyle('red',textcolor = 'white'))
        Stopbutton.clicked.connect(lambda bool: Startbutton.setChecked(not Startbutton.isChecked()))
        Startbutton.clicked.connect(lambda bool: Stopbutton.setChecked(not Stopbutton.isChecked()))
        Startbutton.clicked.connect(self.on_Start)
        Stopbutton.clicked.connect(self.on_Stop)
        Spacetaker = QtGui.QWidget()
        ledpanel =QtGui.QFrame()
        ledpanel.setFrameStyle(1)
        ledlayout = QtGui.QVBoxLayout()
        ledlayout.setMargin(0)
        ledlayout.setSpacing(0)
        ledlayout.addWidget(self.ledrunning)
        ledlayout.addWidget(self.ledprogramming)
        ledlayout.addWidget(self.ledparsing)
        ledlayout.addWidget(self.ledlinetrigger)
        ledlayout.addWidget(self.ledtracking)
        ledpanel.setLayout(ledlayout)
        layout = QtGui.QGridLayout()
        layout.addWidget(Startbutton,0,0)
        layout.addWidget(Stopbutton,1,0)
        layout.addWidget(ledpanel,0,1,3,1)
        layout.addWidget(LineTrigbutton,2,0)
        layout.addWidget(filetoolbar,3,0)
        layout.addWidget(self.Messagebox,0,2,7,4)
        layout.addWidget(updatedelaylabel,4,0,Qt.AlignRight)
        layout.addWidget(shottimelabel,5,0,Qt.AlignRight)
        layout.addWidget(updatedelay,4,1)
        layout.addWidget(shottime,5,1)
        layout.addWidget(timeoffsetlabel,6,0,Qt.AlignRight)
        layout.addWidget(timeoffset,6,1)
        layout.setSpacing(2)
        layout.setContentsMargins(0,0,0,0)
        panel.setLayout(layout)
        return panel

########################################################################
#########                                                      #########
#########                   Start parsers                      #########
#########                and connect signals                   #########
#########                                                      #########
########################################################################
    
    def setup_parser(self):
        self.parsingworker = ParsingWorker(self.hwconfigpath,str(self.writingwidget.toPlainText()),self.reactor,self.connection,self.context)
        self.parsingworker.parsermessages.connect(self.messageout)
        self.parsingworker.new_sequence_trigger.connect(self.graphingwidget.do_sequence)
        

########################################################################
#########                                                      #########
#########                Signal and Callback                   #########
#########                     handling                         #########
#########                                                      #########
######################################################################## 
    
    #################
    #Deliveres a message to the logbox
    #################   
    def messageout(self,text):
        stamp = time.strftime('%H:%M:%S')
        self.Messagebox.moveCursor(QtGui.QTextCursor.End)
        self.Messagebox.insertPlainText("\n"+stamp+" - "+text)
        self.Messagebox.moveCursor(QtGui.QTextCursor.End)

    
    #################
    #Line triggering
    #################    
    @inlineCallbacks
    def toggle_linetrig(self):
        state = not self.sender().isChecked() #is notted because it sends back the previous state of the checkbutton an not the new state
        server = yield self.connection.get_server('Pulser')
        yield server.line_trigger_state(state)
        self.ledlinetrigger.setState(state)
                        

    #################
    #Parameter change on the parameter server
    #send it on on the parsingthread
    #and update the parameter editor
    #################
        
    @inlineCallbacks
    def sendIdtoParameterVault(self,ID):
        pv = yield self.connection.get_server('ParameterVault')
        yield pv.set_parameter('Raman','confirm',ID)
        #print 'time updated id: ',time.time()
        self.messageout('Completed shot: {:}'.format(ID[1]))
    
    def offset_value_changed(self,val):
        self.graphingwidget.timeoffset = val
        self.parsingworker.timeoffset = val

    def shottime_value_changed(self,val):
        self.shottimevalue = val
        self.parsingworker.sequencetimelength = val


    def messagebox_contextmenu(self,event):
        self.menu = QtGui.QMenu(self)
        clearAction = QtGui.QAction('clear',self)
        clearAction.triggered.connect(lambda : self.Messagebox.setText(""))
        self.menu.addAction(clearAction)
        self.menu.popup(QtGui.QCursor.pos())


########################################################################
#########                                                      #########
#########                BUTTON ACTIONS                        #########
#########                                                      #########
########################################################################
    
    

    #################
    #Start and stop buttons
    #################
    def on_Start(self):
        self.text = str(self.writingwidget.toPlainText())
        self.stopping = False
        self.messageout('Starting')
        self.run()

    def on_Stop(self):
        self.stopping = True
        


    #########################
    #File buttons
    #########################
    def openbuttonclick(self):
        if self.writingwidget.document().isModified():
            reply = QtGui.QMessageBox.question(self, 'Message',
                "Do you want to save the changes?", QtGui.QMessageBox.Yes | QtGui.QMessageBox.No | QtGui.QMessageBox.Cancel,
                QtGui.QMessageBox.Cancel)
            if reply == QtGui.QMessageBox.Cancel:
                return
            else:
                if reply == QtGui.QMessageBox.Yes:
                    self.savebuttonclick()
        fname = QtGui.QFileDialog.getOpenFileName(self, 'Open file','sequencescripts/','*.txt')
        if len(fname) != 0:
            try:
                with open(fname,'r') as f:
                    self.writingwidget.setPlainText(f.read())
            except Exception,e:
                print e
        
    def savebuttonclick(self):
        defname = time.strftime('%y%m%d_%H%M%S')
        sname = QtGui.QFileDialog.getSaveFileName(self,'Save file','sequencescripts/'+defname,'*.txt')
        if len(sname)!=0:
            try:
                with open(sname,'w') as f:
                    f.write(self.writingwidget.toPlainText())
            except Exception,e:
                print e
            
    def newbuttonclick(self):
        if self.writingwidget.document().isModified():
            reply = QtGui.QMessageBox.question(self, 'Message',
                "Do you want to save the changes?", QtGui.QMessageBox.Yes | QtGui.QMessageBox.No | QtGui.QMessageBox.Cancel,
                QtGui.QMessageBox.Cancel)
            if reply == QtGui.QMessageBox.Cancel:
                return
            else:
                if reply == QtGui.QMessageBox.Yes:
                    self.savebuttonclick()
        self.writingwidget.clear()

    @inlineCallbacks
    def run(self,bool = None):
        pv = yield self.connection.get_server('ParameterVault')
        value = yield pv.get_parameter('Raman','announce')
        d = threads.deferToThread(self.parsingworker.run,self.text,value)
        d.addCallback(self.wait_for_output)
        
        
    def wait_for_output(self,packet):
        d = threads.deferToThread(self.waiter_func,2)
        d.addCallback(self.output_sequence,packet)
        
    def waiter_func(self,timeout):
        requestCalls = int(timeout / 0.005 ) #number of request calls
        for i in range(requestCalls):
            if not self.hardwarelock:
                return True
            else:
                time.sleep(0.005)
        return False
    

    @inlineCallbacks
    def output_sequence(self,ignore,packet):
        self.hardwarelock = True
        if not self.stopping:
            binary,ttl,message = packet
            pulser = yield self.connection.get_server('Pulser')
            yield pulser.new_sequence()
            check = yield pulser.program_dds_and_ttl(binary,ttl)
            yield pulser.start_single()
            started = yield pulser.wait_sequence_started(self.shottimevalue/1000.)
            reactor.callLater(self.updatedelayvalue,self.run)
            if started:
                completed = yield pulser.wait_sequence_done(self.shottimevalue/1000.)
            counts = yield pulser.get_metablock_counts()
            yield pulser.stop_sequence()
            if not started or not completed:
                self.messageout('Pulser: Timed out')
            self.sendIdtoParameterVault(message)
            
        if self.stopping:
                self.messageout('Stopped')
        self.hardwarelock = False



if __name__== '__main__':
    app = QtGui.QApplication( [])
    import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor
    widget = mainwindow(reactor)
    #widget.showMaximized()
    widget.show()
    reactor.run()