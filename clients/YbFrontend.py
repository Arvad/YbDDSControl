from PyQt4 import QtGui
from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal,QThread, QObject, QEventLoop, QWaitCondition, QTimer, Qt, QSettings, QString
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.internet import threads
from twisted.internet.task import LoopingCall
import threading
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvasQTAgg
import matplotlib.pyplot as plt
from DDS_CONTROL import DDS_CONTROL
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
        self.cycletimevalue = 1000
        self.updatedelayvalue = 200
        self.offsetvalue = 350
        self.parsingerror = False
        self.setStyleSheet(buttonstyle('deepskyblue'))
        self.high = False
        self.threadcounter = 0


    # This is a seperate function because it needs to 
    # be able to yield, and __init__ cannot do that
    @inlineCallbacks
    def initialize(self):
        yield self.connect_labrad()
        yield self.create_layout()
        self.messageout('Layout done')
        self.setup_parser()
        self.restoreGui()
        self.messageout('Initialization done')
        
        

    @inlineCallbacks
    def connect_labrad(self):
        from connection import connection
        cxn = connection()
        yield cxn.connect()
        self.connection = cxn
        self.context = cxn.context()
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
        
        sequencetext = self.writingwidget.toPlainText()
        settings.setValue('Sequencetext',sequencetext)
        
        settings.setValue('windowposition',self.pos())
        settings.setValue('windowsize',self.size())
        
        for asplitter in self.findChildren(QtGui.QSplitter):
            name = asplitter.objectName()
            value = asplitter.sizes()
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
        if settings.contains('Sequencetext'):
            self.writingwidget.setPlainText(settings.value('Sequencetext').toString())
        if settings.contains('windowposition'):
            self.move(settings.value("windowposition").toPoint());
        if settings.contains('windowsize'):
            self.resize(settings.value("windowsize").toSize());
        
        for asplitter in self.findChildren(QtGui.QSplitter):
            name = asplitter.objectName()
            values = settings.value(name).toList()
            asplitter.setSizes([x.toInt()[0] for x in values])
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
        splitterwidget.setObjectName('writegraphsplitter')
        self.graphingwidget = graphingwidget(self.reactor,self.hwconfigpath)
        self.writingwidget = QtGui.QTextEdit('Writingbox')
        self.writingwidget.textChanged.connect(self.startbuttonloop)
        font = QtGui.QFont()
        font.setFamily( "Courier" )
        font.setFixedPitch( True )
        font.setPointSize( 10 )
        self.writingwidget.setFont(font)
        highlighter = MyHighlighter( self.writingwidget, 'Classic')

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
        LineTrigbutton.setStyleSheet(buttonstyle('yellowgreen'))
        LineTrigbutton.pressed.connect(self.toggle_linetrig)
        self.ScriptUpdatebutton = QtGui.QPushButton('UPDATE')
        self.updatebuttonloop = LoopingCall(self.flash_update)
        self.ScriptUpdatebutton.setEnabled(False)
        self.ScriptUpdatebutton.pressed.connect(self.update_script)
        
        updatedelay = QtGui.QSpinBox()
        updatedelaylabel = QtGui.QLabel('Update delay')
        cycletime = QtGui.QSpinBox()
        cycletimelabel = QtGui.QLabel('Cycle time')
        endtime = QtGui.QSpinBox()
        endtimelabel = QtGui.QLabel('End time')
        timeoffset = QtGui.QSpinBox()
        timeoffsetlabel = QtGui.QLabel('Offset')

        filetoolbar = QtGui.QToolBar()
        filetoolbar.addAction(QtGui.QIcon('icons/document-open.svg'),'open',self.openbuttonclick)
        filetoolbar.addAction(QtGui.QIcon('icons/document-save.svg'),'save',self.savebuttonclick)
        filetoolbar.addAction(QtGui.QIcon('icons/document-new.svg'),'new',self.newbuttonclick)

        cycletime.valueChanged.connect(self.cycletime_value_changed)
        endtime.valueChanged.connect(self.endtime_value_changed)
        updatedelay.valueChanged.connect(lambda val: setattr(self,"updatedelayvalue",val/1000.))
        timeoffset.valueChanged.connect(self.offset_value_changed)
        cycletime.setObjectName('cycletime')
        updatedelay.setObjectName('updatedelay')
        endtime.setObjectName('endtime')
        timeoffset.setObjectName('timeoffset')

        cycletime.setRange(0,3000)
        cycletime.setValue(1000)
        updatedelay.setRange(0,3000)
        updatedelay.setValue(1)
        endtime.setValue(1000)
        endtime.setRange(1,3000)
        cycletime.setSuffix(' ms')
        updatedelay.setSuffix(' ms')
        timeoffset.setSuffix(' ms')
        endtime.setSuffix(' ms')
        timeoffset.setRange(0,3000)
        timeoffset.setValue(350)
        
        toplabel = QtGui.QLabel('Parameter Vault')
        paramlabelnow = QtGui.QLabel('Now')
        paramlabelnext = QtGui.QLabel('Next')
        font = paramlabelnow.font()
        font.setBold(True)
        paramlabelnow.setFont(font)
        paramlabelnext.setFont(font)
        toplabel.setFont(font)
        self.seqlabelnow = QtGui.QLabel('seq: ')
        self.Alabelnow = QtGui.QLabel('   A: -')
        self.Blabelnow = QtGui.QLabel('   B: -')
        self.Clabelnow = QtGui.QLabel('   C: -')
        self.seqlabelnext = QtGui.QLabel('seq: -')
        self.Alabelnext = QtGui.QLabel('   A: -')
        self.Blabelnext = QtGui.QLabel('   B: -')
        self.Clabelnext = QtGui.QLabel('   C: -')
        

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
        Stopbutton.clicked.connect(lambda bool: Startbutton.setChecked(False))
        Startbutton.clicked.connect(lambda bool: Stopbutton.setChecked(False))

        Startbutton.clicked.connect(self.on_Start)
        Stopbutton.clicked.connect(self.on_Stop)
        
        timingspanel =QtGui.QFrame()
        timingspanel.setFrameStyle(1)
        timingslayout = QtGui.QGridLayout()
        timingslayout.setMargin(0)
        timingslayout.setSpacing(0)
        timingslayout.addWidget(cycletimelabel,0,1,Qt.AlignRight)
        timingslayout.addWidget(cycletime,0,2)
        timingslayout.addWidget(timeoffsetlabel,1,1,Qt.AlignRight)
        timingslayout.addWidget(timeoffset,1,2)
        timingslayout.addWidget(endtimelabel,2,1,Qt.AlignRight)
        timingslayout.addWidget(endtime,2,2)
        timingslayout.addWidget(updatedelaylabel,3,1,Qt.AlignRight)
        timingslayout.addWidget(updatedelay,3,2)
        
        parameterspanel = QtGui.QFrame()
        parameterspanel.setFrameStyle(1)
        parameterslayout = QtGui.QGridLayout()
        parameterslayout.setSpacing(0)
        parameterslayout.addWidget(toplabel,0,0,1,2,Qt.AlignCenter)
        parameterslayout.addWidget(paramlabelnow,1,0)
        parameterslayout.addWidget(self.seqlabelnow,2,0)
        parameterslayout.addWidget(self.Alabelnow,3,0)
        parameterslayout.addWidget(self.Blabelnow,4,0)
        parameterslayout.addWidget(self.Clabelnow,5,0)
        parameterslayout.addWidget(paramlabelnext,1,1)
        parameterslayout.addWidget(self.seqlabelnext,2,1)
        parameterslayout.addWidget(self.Alabelnext,3,1)
        parameterslayout.addWidget(self.Blabelnext,4,1)
        parameterslayout.addWidget(self.Clabelnext,5,1)
        parameterspanel.setLayout(parameterslayout)

        timingspanel.setLayout(timingslayout)
        layout = QtGui.QGridLayout()
        layout.addWidget(Startbutton,0,0)
        layout.addWidget(Stopbutton,1,0)
        layout.addWidget(timingspanel,0,1,3,1)
        layout.addWidget(parameterspanel,3,1,4,1)
        layout.addWidget(LineTrigbutton,2,0)
        layout.addWidget(self.ScriptUpdatebutton,3,0)
        layout.addWidget(filetoolbar,4,0)
        layout.addWidget(self.Messagebox,0,2,7,4)
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
    
    def textChanged(self,val):
        self.script_has_changed = True
        self.ScriptUpdatebutton.setStyleSheet('color : red')
        
    def startbuttonloop(self):
        if not self.updatebuttonloop.running:
            self.updatebuttonloop.start(0.5)
    
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
        try:
            self.graphingwidget.timeoffset = val
            self.parsingworker.timeoffset = val
            self.offsetvalue = val
        except AttributeError:
            pass

    def cycletime_value_changed(self,val):
        try:
            self.cycletimevalue = val
        except AttributeError:
            pass

    def endtime_value_changed(self,val):
        try:
            self.endtimevalue = val
            self.parsingworker.endtime = val
        except AttributeError:
            pass
    
    
    def messagebox_contextmenu(self,event):
        self.menu = QtGui.QMenu(self)
        clearAction = QtGui.QAction('clear',self)
        clearAction.triggered.connect(lambda : self.Messagebox.setText(""))
        self.menu.addAction(clearAction)
        self.menu.popup(QtGui.QCursor.pos())

    def flash_update(self):
        if self.high:
            self.ScriptUpdatebutton.setStyleSheet('background-color : red')
            self.high = False
        else:
            self.ScriptUpdatebutton.setStyleSheet('background-color : grey')
            self.high = True
    
    def update_param_labels(self,message,typ):
        if typ == 'now':
            self.seqlabelnow.setText('seq: {:}'.format(int(message[1])))
            self.Alabelnow.setText('   A: {:}'.format(float(message[5])))
            self.Blabelnow.setText('   B: {:}'.format(float(message[6])))
            self.Clabelnow.setText('   C: {:}'.format(float(message[7])))
        if typ == 'next':
            self.seqlabelnext.setText('seq: {:}'.format(int(message[1])))
            self.Alabelnext.setText('   A: {:}'.format(float(message[5])))
            self.Blabelnext.setText('   B: {:}'.format(float(message[6])))
            self.Clabelnext.setText('   C: {:}'.format(float(message[7])))
        
########################################################################
#########                                                      #########
#########                BUTTON ACTIONS                        #########
#########                                                      #########
########################################################################
    
    

    #################
    #Start and stop buttons
    #################
    def on_Start(self):
        if self.threadcounter == 0:
            self.stopping = False
            self.messageout('Starting')
            self.update_script(start = True)
            self.run()
            self.ScriptUpdatebutton.setEnabled(True)
        if not self.stopping:
            self.sender().setChecked(True)
            

    def on_Stop(self):
        self.sender().setChecked(True)
        self.ScriptUpdatebutton.setEnabled(False)
        self.stopping = True
        
        
    def update_script(self,**kwargs):
        if self.writingwidget.document().isModified() or ('start' in kwargs.keys()):
            self.text = str(self.writingwidget.toPlainText())
            self.writingwidget.document().setModified(False)
            if self.updatebuttonloop.running:
                self.updatebuttonloop.stop()
                self.ScriptUpdatebutton.setStyleSheet('background-color : lightgrey')
        else:
            self.messageout('Nothing to update')

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
        self.writingwidget.document().setModified(False)
            
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
        self.threadcounter += 1
        pv = yield self.connection.get_server('ParameterVault')
        value = yield pv.get_parameter('Raman','announce')
        self.update_param_labels(value,'next')
        d = threads.deferToThread(self.parsingworker.run,self.text,value)
        d.addCallback(self.wait_for_output)
        
        
    def wait_for_output(self,packet):
        if self.parsingerror:
            a = QtGui.QTextCharFormat()
            a.setBackground(QtGui.QBrush(QtGui.QColor('white')))
            cursor = self.writingwidget.textCursor()
            cursor.select(QtGui.QTextCursor.Document)
            cursor.setCharFormat(a)
            self.parsingerror = False
        if len(packet[3]) > 0:
            self.messageout('Parsing error')
            self.stopping = True
            self.threadcounter -= 1
            self.messageout('Stopped')
            a = QtGui.QTextCharFormat()
            a.setBackground(QtGui.QBrush(QtGui.QColor('yellow')))
            for line in packet[3]:
                cursor = self.writingwidget.document().find(line)
                cursor.select(QtGui.QTextCursor.BlockUnderCursor)
                cursor.setCharFormat(a)
            self.parsingerror = True
            return
            
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
            binary,ttl,message, errorlist = packet
            self.update_param_labels(message,'now')
            pulser = yield self.connection.get_server('Pulser')
            yield pulser.new_sequence()
            check = yield pulser.program_dds_and_ttl(binary,ttl)
            yield pulser.start_single()
            started = yield pulser.wait_sequence_started((self.cycletimevalue-self.endtimevalue+self.offsetvalue)/1000.)
            reactor.callLater(self.updatedelayvalue,self.run)
            if started:
                completed = yield pulser.wait_sequence_done((self.endtimevalue-self.offsetvalue)/1000.)
            counts = yield pulser.get_metablock_counts()
            yield pulser.stop_sequence()
            if not started or not completed:
                self.messageout('Pulser: Timed out')
            self.sendIdtoParameterVault(message)
        self.threadcounter -= 1
        if self.threadcounter == 0:
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