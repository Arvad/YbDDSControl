from PyQt4.QtCore import QThread, pyqtSignal, QObject, pyqtSlot, QTimer
from twisted.internet.defer import inlineCallbacks
from connection import connection
import time



class PulserWorker(QObject):

    start = pyqtSignal()
    stopsignal = pyqtSignal()
    loopsignal = pyqtSignal()
    pulsermessages = pyqtSignal(str)
    sequence_done_trigger = pyqtSignal(tuple)

    def __init__(self,reactor,connection,parsingworker):
        
        super(PulserWorker,self).__init__()
        self.reactor = reactor
        self.parsingworker = parsingworker
        self.connection = connection
        self.sequencestorage = []
        self.start.connect(self.run)
        self.stopsignal.connect(self.stop)
        self.loopsignal.connect(self.loop)
        self.running = False
        self.stopping=False
        self.pulser = None
        self.currentannouncement = None
        self.context = None
        self.import_labrad()
        self.setup_server()
   
    def import_labrad(self):
        from labrad.types import Error
        
        self.Error = Error
    
    @inlineCallbacks
    def setup_server(self):
        self.context = yield self.connection.context()
        self.pulser = yield self.connection.get_server('Pulser')
        print self.pulser
        
    def set_shottime(self,time):
        self.shottime = time

    def stop(self):
        self.stopping = True
        self.pulsermessages.emit('Pulser: Stopped')

    def timed_out(self):
        print 'timed out'
        self.pulsermessages.emit('Pulser: Pulser timed out')     
    
    @inlineCallbacks
    def run(self):
        while not self.stopping:
            while True:
                time.sleep(0.2)
                nextsequence, nextttl, nextannouncement = self.parsingworker.get_sequence()
                if nextannouncement is not None: break
            print self.context
            yield self.pulser.new_sequence(context = self.context)
            yield self.pulser.program_dds_and_ttl(nextsequence,nextttl,context = self.context)
            self.pulsermessages.emit('Pulser: Running:' + str(nextannouncement[1]))
            yield self.pulser.start_single(context = self.context)
            completed = yield self.pulser.wait_sequence_done(self.shottime,context = self.context)
            if completed:
                counts = yield self.pulser.get_metablock_counts(context = self.context)
                yield self.pulser.stop_sequence(context = self.context)
                self.sequence_done_trigger.emit(nextannouncement)
                self.pulsermessages.emit('Metablock counts: '+ str(counts[0]))
            else:
                yield self.pulser.stop_sequence(context = self.context)
                self.pulsermessages.emit('Pulser: Timed out')
            
        self.stopping = False

        
    @pyqtSlot()    
    def loop(self):
        import labrad
        cnx = labrad.connect()
        p = cnx.pulser
        self.pulsermessages.emit('Pulser: Looping beginning')
        while not self.stopping:
            p.start_number(1)
            p.wait_sequence_done(timeout=self.shottime)
            p.stop_sequence()
            time.sleep(0.1)
        cnx.disconnect()
        self.stopping = False
        