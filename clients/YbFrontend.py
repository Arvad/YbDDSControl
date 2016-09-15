from PyQt4 import QtGui
from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal,QThread, QObject, QEventLoop, QWaitCondition, QTimer, Qt
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.internet import threads
import threading
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvasQTAgg
import matplotlib.pyplot as plt
from SWITCH_CONTROL import switchWidget
from DDS_CONTROL import DDS_CONTROL
from LINETRIGGER_CONTROL import linetriggerWidget
from LEDindicator import LEDindicator
from parsingworker import ParsingWorker
from pulserworker import PulserWorker
import time

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
        self.updatedelayvalue = 400


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
        self.reactor.stop()
  
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
        from SWITCH_CONTROL import switchWidget
        from DDS_CONTROL import DDS_CONTROL
        from LINETRIGGER_CONTROL import linetriggerWidget

        layout = QtGui.QVBoxLayout()
        try:
            pass
            #layout.addWidget(switchWidget(self.reactor,self.connection))
            layout.addWidget(DDS_CONTROL(self.reactor,self.connection))
            layout.addWidget(linetriggerWidget(self.reactor,self.connection))
        except AttributeError, e:
            print e
        widget.setLayout(layout)
        return widget

    #################
    # Sqeuence tab panel
    #################
    def makeSequenceWidget(self):
        from graphingwidget import graphingwidget
        self.filename = None
        splitterwidget = QtGui.QSplitter()
        string = "Channel DDS_4 do 200 MHz with 9 dBm for 100 ms at 0.01 ms in mode Normal\nChannel DDS_2 do 200 MHz with 9 dBm for 100 ms at 0.01 ms in mode Normal"        
        self.graphingwidget = graphingwidget(self.reactor,self.hwconfigpath)
        self.writingwidget = QtGui.QTextEdit('Writingbox')
        self.writingwidget.setPlainText(string)

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
        Startbutton = QtGui.QPushButton(QtGui.QIcon('icons/go-next.svg'),'RUN')
        Stopbutton = QtGui.QPushButton(QtGui.QIcon('icons/emblem-noread.svg'),'STOP')
       
        LineTrigbutton = QtGui.QPushButton('linetrig')
        LineTrigbutton.setCheckable(True)
        state = True
        LineTrigbutton.setChecked(state)
        LineTrigbutton.pressed.connect(self.toggle_linetrig)
        self.ledrunning = LEDindicator('Running')
        self.ledprogramming = LEDindicator('Prog.')
        self.ledlinetrigger = LEDindicator('Ext trig')
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

        shottime.valueChanged.connect(lambda val: setattr(self,"shottimevalue",val/1000.))
        updatedelay.valueChanged.connect(lambda val: setattr(self,"updatedelayvalue",val/1000.))
        timeoffset.valueChanged.connect(self.offset_value_changed)


        shottime.setRange(0,3000)
        shottime.setValue(1000)
        updatedelay.setRange(0,3000)
        updatedelay.setValue(400)
        shottime.setSuffix(' ms')
        updatedelay.setSuffix(' ms')
        timeoffset.setSuffix(' ms')
        timeoffset.setRange(0,3000)
        timeoffset.setValue(200)

        self.Messagebox = QtGui.QTextEdit()
        self.Messagebox.setReadOnly(True)
        font = self.Messagebox.font()
        font.setFamily("courier")
        font.setPointSize(10)

        Startbutton.pressed.connect(self.on_Start)
        Stopbutton.pressed.connect(self.on_Stop)
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
        self.parsingworker.busy_trigger.connect(self.ledparsing.setState)
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
        state = self.sender().isChecked()
        server = yield self.connection.get_server('Pulser')
        yield server.line_trigger_state(state)
        if state:
            self.ledlinetrigger.setOn()
        else:
            self.ledlinetrigger.setOff()

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
        print value[1], ' Parameter Vault'
        d = threads.deferToThread(self.parsingworker.run,self.text,value)
        d.addCallback(self.wait_for_output)
        
        
    def wait_for_output(self,packet):
        d = threads.deferToThread(self.waiter_func,2)
        d.addCallback(self.output_sequence,packet)
        
    def waiter_func(self,timeout):
        #print packet[2][1], 'waiting'
        requestCalls = int(timeout / 0.005 ) #number of request calls
        for i in range(requestCalls):
            if not self.hardwarelock:
                #print packet[2][1], ' lock released'
                return True
            else:
                time.sleep(0.005)
        return False
    

    @inlineCallbacks
    def output_sequence(self,ignore,packet):
        self.hardwarelock = True
        if not self.stopping:
            d = threads.deferToThread(self.waiter_func,0.4)
            d.addCallback(self.run)
            #self.reactor.callLater(0,self.run)
            binary,ttl,message = packet
            print message[1],'started '
            pulser = yield self.connection.get_server('Pulser')
            yield pulser.new_sequence()
            check = yield pulser.program_dds_and_ttl(binary,ttl)
           
            yield pulser.start_single()
            completed = yield pulser.wait_sequence_done(self.shottimevalue)
            if completed:
                counts = yield pulser.get_metablock_counts()
                yield pulser.stop_sequence()
                
            else:
                counts = yield pulser.get_metablock_counts()
                yield pulser.stop_sequence()
                self.messageout('Pulser: Timed out')
            self.sendIdtoParameterVault(message)
            print message[1]," done"
        print "releasing lock"
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