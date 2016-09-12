from PyQt4.QtCore import QThread, pyqtSignal, QObject, pyqtSlot, QTimer

import time


class PulserWorker(QObject):

    start = pyqtSignal()
    stopsignal = pyqtSignal()
    loopsignal = pyqtSignal()
    pulsermessages = pyqtSignal(str)
    sequence_done_trigger = pyqtSignal(tuple)

    def __init__(self,connection,parsingworker):
        
        super(PulserWorker,self).__init__()
        self.parsingworker = parsingworker
        self.connection = connection
        self.sequencestorage = []
        self.start.connect(self.run)
        self.stopsignal.connect(self.stop)
        self.loopsignal.connect(self.loop)
        self.running = False
        self.stopping=False
        self.cnx = None
        self.currentannouncement = None
        self.pulser = connection().Pulser

    def set_shottime(self,time):
        self.shottime = time

    def stop(self):
        self.stopping = True
        self.pulsermessages.emit('Pulser: Stopped')

    def timed_out(self):
        print 'timed out'
        self.pulsermessages.emit('Pulser: Pulser timed out')     
    
    @pyqtSlot()
    def run(self):
        while not self.stopping:
            while nextannouncement is None:
                time.sleep(0.2)
                nextsequence, nextttl, nextannouncement = self.parsingworker.get_sequence()
            
            self.pulser.new_sequence()
            self.program_dds_and_ttl(nextseqeuence,nextttl)
            self.pulsermessages.emit('Pulser: Running:' + str(nextannouncement[1]))
            self.pulser.start_single()
            try:
                self.pulser.wait_sequence_done(timeout=self.shottime)
                counts = self.pulser.get_metablock_counts()
                self.pulser.stop_sequence() #The stop signal stops the loop *if more than one repetition was set, and resets the OKfpga (the ttltimings)
            except labrad.errors.RequestTimeoutError, e:
                self.pulser.stop_sequence()
                self.pulsermessages.emit('Pulser: Timed out')
            else:

                self.sequence_done_trigger.emit(nextannouncement)
                self.pulsermessages.emit('Metablock counts: '+ str(counts[0]))

        
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
        