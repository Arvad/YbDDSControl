from PyQt4 import QtGui
from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal,QThread, QObject, QEventLoop, QWaitCondition, QTimer, Qt, QSettings, QString, QProcess
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.internet import threads
from twisted.internet.task import LoopingCall
from parsingworker import ParsingWorker
import time, sys, os
from GUIelements import *



class mainwindow(QtGui.QMainWindow):
    start_signal = pyqtSignal()
    stop_signal = pyqtSignal()
    

    def __init__(self,reactor, parent=None):
        super(mainwindow,self).__init__()
        self.reactor = reactor
        self.pulserserverpath = "C:\Users\Katori lab\YbDDSControl\servers\Pulser\pulser_ok.py"
        self.initialize()
        self.ParamID = None
        self.textlist = [[],[],[],[]]
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
        self.pulserserver = serverwidget('Pulser',self.pulserserverpath)
        self.pulserserver.start_server()
        time.sleep(5)
        yield self.connect_labrad()
        yield self.create_layout()
        self.messageout('Layout done')
        self.setup_parser()
        self.restoreGui()
        self.messageout('Initialization done')
        sys.stdout = EmittingStream(textWritten=self.normalOutputWritten)
        sys.stderr = EmittingStream(textWritten=self.normalOutputWritten)
        
        

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
        self.makeHelpWidget()
        controlwidget = self.makeControlWidget()
        sequencewidget = self.makeSequenceWidget()
        spectrumplottingwidget = self.makeSpectrumPlottingWidget()
        stdoutwidget = self.makeStdOutputWidget()

        centralwidget = QtGui.QWidget()
        tabwidget = QtGui.QTabWidget()

        tabwidget.addTab(sequencewidget,'Sequence')
        tabwidget.addTab(controlwidget,'Controls')
        tabwidget.addTab(spectrumplottingwidget,'Spectra')
        tabwidget.addTab(stdoutwidget,'StdOut')
        tabwidget.addTab(self.pulserserver,'Pulser server')
        
        
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
        
        for i in range(len(self.writingwidgets)):
            awidget = self.writingwidgets[i]
            sequencetext = awidget.toPlainText()
            settings.setValue('Sequencetext{:}'.format(i),sequencetext)
        
        settings.setValue('windowposition',self.pos())
        settings.setValue('windowsize',self.size())
        
        for asplitter in self.findChildren(QtGui.QSplitter):
            name = asplitter.objectName()
            value = asplitter.sizes()
            settings.setValue(name,value)
        settings.sync()
        self.pulserserver.kill_server()
        self.reactor.stop()

    def restoreGui(self):
        settings = QSettings('settings.ini',QSettings.IniFormat)
        settings.setFallbacksEnabled(False)

        for aspinbox in self.findChildren(QtGui.QDoubleSpinBox) + self.findChildren(QtGui.QSpinBox):
            name = aspinbox.objectName()
            if settings.contains(name):
                value= settings.value(name).toFloat()[0]
                aspinbox.setValue(value)
        
        for i in range(len(self.writingwidgets)):
            awidget = self.writingwidgets[i]
            if settings.contains('Sequencetext{:}'.format(i)):
                awidget.setPlainText(settings.value('Sequencetext{:}'.format(i)).toString())
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
    # Std Output panel
    #################
    def makeStdOutputWidget(self):
        widget = QtGui.QWidget()
        label = QtGui.QLabel('Terminal output of Frontend')
        self.stdouttextfield = QtGui.QTextEdit()
        self.stdouttextfield.setReadOnly(True)
        self.stdouttextfield.contextMenuEvent = self.messagebox_contextmenu
        layout = QtGui.QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.stdouttextfield)
        widget.setLayout(layout)
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
    # Help window
    #################
    def makeHelpWidget(self):
        self.Helpwindow = QtGui.QWidget()
        layout = QtGui.QHBoxLayout()
        editor = QtGui.QTextEdit()
        editor.setReadOnly(True)
        try:
            with open('helpfile.html','r') as f:
                data = f.read() #reads entire file into one string
                editor.setHtml(data)
        except Exception,e:
            print e
            editor.setPlainText('Sorry - "helpfile.txt" could not be found')
        layout.addWidget(editor)
        self.Helpwindow.setLayout(layout)
        self.Helpwindow.show()
        self.Helpwindow.setHidden(True)
    
    
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
        self.writingtab = QtGui.QTabWidget()
        self.writingwidgets = []
        for i in range(4):
            self.writingwidgets.append(QtGui.QTextEdit('Writingbox{:}'.format(i)))
                
        font = QtGui.QFont()
        font.setFamily( "Courier" )
        font.setFixedPitch( True )
        font.setPointSize( 10 )
        self.colorlist = [QtGui.QColor(255,255,255), #Mode 1 - white
                     QtGui.QColor(255,240,240), #Mode 2 - red
                     QtGui.QColor(240,255,240), #Mode 3 - green
                     QtGui.QColor(240,240,255)] #Mode 4 - blue
        for i in range(len(self.writingwidgets)):
            awritingwidget = self.writingwidgets[i]
            pal = awritingwidget.palette()
            pal.setColor(QtGui.QPalette.Base, self.colorlist[i])
            awritingwidget.setPalette(pal)
            awritingwidget.textChanged.connect(self.startbuttonloop)
            awritingwidget.setFont(font)
            highlighter = MyHighlighter( awritingwidget, 'Classic')
            self.writingtab.addTab(awritingwidget,'Mode {:}'.format(i+1))
            p = awritingwidget.palette()
            p.setColor(awritingwidget.backgroundRole(), Qt.red)
            awritingwidget.setPalette(p)
#            self.writingtab.tabBar().setTabTextColor(i,colorlist[i])
        leftwidget=QtGui.QWidget()
        buttonpanel = self.makeButtonPanel()
        leftlayout = QtGui.QGridLayout()
        leftlayout.addWidget(buttonpanel,0,0)
        leftlayout.addWidget(self.writingtab, 1,0,4,1)
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
        helpbutton = QtGui.QPushButton('HELP!')
        
        updatedelay = QtGui.QSpinBox()
        updatedelaylabel = QtGui.QLabel('Update delay')
        cycletime = QtGui.QSpinBox()
        cycletimelabel = QtGui.QLabel('Cycle time')
        endtime = QtGui.QSpinBox()
        endtimelabel = QtGui.QLabel('End time')
        timeoffset = QtGui.QSpinBox()
        timeoffsetlabel = QtGui.QLabel('Offset')

        filetoolbar = QtGui.QToolBar()
        filetoolbar.addAction(QtGui.QIcon(QtGui.QPixmap(icon_open())),'open',self.openbuttonclick)
        filetoolbar.addAction(QtGui.QIcon(QtGui.QPixmap(icon_save())),'save',self.savebuttonclick)
        filetoolbar.addAction(QtGui.QIcon(QtGui.QPixmap(icon_new())),'new',self.newbuttonclick)
        
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
        self.Modelabelnow = QtGui.QLabel('Mode: -')
        self.seqlabelnext = QtGui.QLabel('seq: -')
        self.Alabelnext = QtGui.QLabel('   A: -')
        self.Blabelnext = QtGui.QLabel('   B: -')
        self.Clabelnext = QtGui.QLabel('   C: -')
        self.Modelabelnext = QtGui.QLabel('Mode: -')
        

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
        helpbutton.clicked.connect(lambda bool:self.Helpwindow.setHidden(not self.Helpwindow.isHidden()))
        
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
        parameterslayout.addWidget(self.Modelabelnow,6,0)
        parameterslayout.addWidget(paramlabelnext,1,1)
        parameterslayout.addWidget(self.seqlabelnext,2,1)
        parameterslayout.addWidget(self.Alabelnext,3,1)
        parameterslayout.addWidget(self.Blabelnext,4,1)
        parameterslayout.addWidget(self.Clabelnext,5,1)
        parameterslayout.addWidget(self.Modelabelnext,6,1)
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
        layout.addWidget(helpbutton,5,0)
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
        self.parsingworker = ParsingWorker(self.hwconfigpath,self.reactor,self.connection,self.context)
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
    #writes Stdout and Stderr
    #################   
    def normalOutputWritten(self, text):
        cursor = self.stdouttextfield.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertText(text)
        cursor.movePosition(QtGui.QTextCursor.End)
    
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
        self.messageout('Completed shot: {:} from Mode: {:}'.format(ID[1],ID[2]%16))
    
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
            self.Modelabelnow.setText('Mode: {:}'.format(int(message[2])%16))
        if typ == 'next':
            self.seqlabelnext.setText('seq: {:}'.format(int(message[1])))
            self.Alabelnext.setText('   A: {:}'.format(float(message[5])))
            self.Blabelnext.setText('   B: {:}'.format(float(message[6])))
            self.Clabelnext.setText('   C: {:}'.format(float(message[7])))
            self.Modelabelnext.setText('Mode: {:}'.format(int(message[2])%16))
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
        for i in range(len(self.writingwidgets)):
            awidget = self.writingwidgets[i]
            if awidget.document().isModified() or ('start' in kwargs.keys()):
                self.textlist[i] = str(awidget.toPlainText())
                awidget.document().setModified(False)
                if self.updatebuttonloop.running:
                    self.updatebuttonloop.stop()
                    self.ScriptUpdatebutton.setStyleSheet('background-color : lightgrey')
            else:
                self.messageout('Nothing to update for Mode {:}'.format(i+1))
        
    
    #########################
    #File buttons
    #########################
    def openbuttonclick(self):
        writingwidget = self.writingwidgets[self.writingtab.currentIndex()]
        if writingwidget.document().isModified():
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
                    writingwidget.setPlainText(f.read())
            except Exception,e:
                print e
        
    def savebuttonclick(self):
        writingwidget = self.writingwidgets[self.writingtab.currentIndex()]
        defname = time.strftime('%y%m%d_%H%M%S')
        sname = QtGui.QFileDialog.getSaveFileName(self,'Save file','sequencescripts/'+defname,'*.txt')
        if len(sname)!=0:
            try:
                with open(sname,'w') as f:
                    f.write(writingwidget.toPlainText())
            except Exception,e:
                print e
        writingwidget.document().setModified(False)
            
    def newbuttonclick(self):
        writingwidget = self.writingwidgets[self.writingtab.currentIndex()]
        if writingwidget.document().isModified():
            reply = QtGui.QMessageBox.question(self, 'Message',
                "Do you want to save the changes?", QtGui.QMessageBox.Yes | QtGui.QMessageBox.No | QtGui.QMessageBox.Cancel,
                QtGui.QMessageBox.Cancel)
            if reply == QtGui.QMessageBox.Cancel:
                return
            else:
                if reply == QtGui.QMessageBox.Yes:
                    self.savebuttonclick()
        writingwidget.clear()

    @inlineCallbacks
    def run(self,bool = None):
        self.threadcounter += 1
        pv = yield self.connection.get_server('ParameterVault')
        value = yield pv.get_parameter('Raman','announce')
        self.update_param_labels(value,'next')
        mode = value[2]%16
        if 0 < mode < len(self.writingwidgets):
            d = threads.deferToThread(self.parsingworker.run,self.textlist[mode-1],value)
            d.addCallback(self.wait_for_output)
        else:
            self.messageout('Mode {:} is not a valid mode'.format(mode))
            self.threadcounter -= 1
        
    def wait_for_output(self,packet):
        mode = packet[2][2]%16-1 #because python 0 indexes
        widget = self.writingwidgets[mode]
        if self.parsingerror:
            a = QtGui.QTextCharFormat()
            a.setBackground(QtGui.QBrush(QtGui.QColor(self.colorlist[mode])))
            
            cursor = widget.textCursor()
            cursor.select(QtGui.QTextCursor.Document)
            cursor.setCharFormat(a)
            self.parsingerror = False
        if len(packet[3]) > 0:
            self.messageout('Parsing error in Mode {:}'.format(mode+1))
            self.threadcounter -= 1
            self.messageout('Stopped')
            a = QtGui.QTextCharFormat()
            a.setBackground(QtGui.QBrush(QtGui.QColor('yellow')))
            for line in packet[3]:
                cursor = widget.document().find(line)
                cursor.select(QtGui.QTextCursor.BlockUnderCursor)
                cursor.setCharFormat(a)
                self.messageout('Problems in Mode {:}'.format(mode+1))
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
            binary,ttl,message, errorlist, metablocks = packet
            returnmessage = (message[0],message[1],message[2],message[3],False,0.,0.,0.)#return message (confirm) in the form (TS,seq,mode,TT,good(bool),A,B,C)
            completed = False
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
            if counts[0] == metablocks and completed:
                returnmessage = (message[0],message[1],message[2],message[3],True,0.,0.,0.)  #return message (confirm) in the form (TS,seq,mode,TT,good(bool),A,B,C)
            yield pulser.stop_sequence()
            if not started or not completed:
                returnmessage = (message[0],message[1],message[2],message[3],False,0.,0.,0.)  #return message (confirm) in the form (TS,seq,mode,TT,good(bool),A,B,C)
                if not started:
                    self.messageout('Pulser: Timed out. Did not receive starting trigger')
                elif not completed:
                    self.messageout('Pulser: Timed out. Did not finish sequence in time')
            self.sendIdtoParameterVault(returnmessage)
        self.threadcounter -= 1
        if self.threadcounter == 0:
            self.messageout('Stopped')
        self.hardwarelock = False

class EmittingStream(QObject):

    textWritten = pyqtSignal(str)

    def write(self, text):
        self.textWritten.emit(str(text))
        
class serverwidget(QtGui.QFrame):

    def __init__(self,aname,apath):
        super(serverwidget, self).__init__()
        self.process = None
        self.path = apath
        self.name = aname
        self.setFrameStyle(QtGui.QFrame.Panel | QtGui.QFrame.Sunken)
        title = QtGui.QLabel(self.name)
        startbutton = QtGui.QPushButton('START')
        killbutton = QtGui.QPushButton('TERMINATE')
        pingbutton = QtGui.QPushButton('PING')
        self.textfield = QtGui.QTextEdit()
        self.textfield.setReadOnly(True)
        startbutton.pressed.connect(self.start_server)
        killbutton.pressed.connect(self.kill_server)
        pingbutton.pressed.connect(self.ping_server)
        
        sublayout = QtGui.QVBoxLayout()
        sublayout.addWidget(title)
        sublayout.addWidget(startbutton)
        sublayout.addWidget(killbutton)
        sublayout.addWidget(pingbutton)
        sublayout.addWidget(self.textfield)
        self.setLayout(sublayout)
        
    def start_server(self):
        if self.process is None:
            self.process = QProcess()
            self.process.readyReadStandardOutput.connect(self.read_output)
            self.process.started.connect(lambda : self.write_message('Server started')) 
            self.process.finished.connect(lambda : self.write_message('Server stopped'))
            self.process.setProcessChannelMode(QProcess.MergedChannels)
            self.process.setWorkingDirectory(os.path.dirname(self.path))
            self.process.start('python',[self.path])
        else:
            self.textfield.append('Cannot start "{:}", as it is already running'.format(self.name))

    def kill_server(self):
        if self.process is not None:
            self.process.terminate()
            self.process = None
        else:
            self.textfield.append('Cannot terminate "{:}", as it is not running'.format(self.name))
    
    def ping_server(self):
        if self.process is not None:
            state = self.process.state()
            msg = "PING: "
            if state == 0:
                msg +='Process died'
            elif state == 1:
                msg +='Process is starting up'
            elif state == 2:
                msg += 'Process is alive'
            self.textfield.append(msg)
        else:
            self.textfield.append('Cannot ping a server that is not started')

    def read_output(self):
        data = self.process.readAllStandardOutput()
        self.textfield.append(str(data))        

    def write_message(self,message):
        self.textfield.append(message)
        
        
if __name__== '__main__':
    app = QtGui.QApplication( [])
    app.setWindowIcon(QtGui.QIcon(QtGui.QPixmap(logo())))
    import ctypes
    myappid = u'mycompany.myproduct.subproduct.version' # arbitrary string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
    splash_pix = QtGui.QPixmap(splash())
    splash = QtGui.QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
    splash.setMask(splash_pix.mask())
    splash.show()
    
    import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor
    widget = mainwindow(reactor)
    #widget.showMaximized()
    widget.show()
    splash.close()
    reactor.run()