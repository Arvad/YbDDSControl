from PyQt4.QtCore import QThread, pyqtSignal, QObject, pyqtSlot, QMutex, QMutexLocker
from twisted.internet.defer import inlineCallbacks, returnValue  
import threading
import re
import time
import numpy as np
import array
from decimal import Decimal
import sys

global harwareConfiguration

class ParsingWorker(QObject):
    trackingparameterserver = pyqtSignal(bool)
    parsermessages = pyqtSignal(str)
    new_sequence_trigger = pyqtSignal(list)


    def __init__(self,hwconfigpath,text,reactor,connection,cntx):
        super(ParsingWorker,self).__init__()
        self.text = text
        self.reactor = reactor
        self.connection = connection
        self.context = cntx
        self.sequence = []
        self.defineRegexPatterns()
        self.tracking = False
        self.trackingparameterserver.emit(self.tracking)
        self.seqID = 0
        self.parameters = {}
        self.steadystatedict = {}
        self.lastannouncement = (0L,0L,0,0L,False,0.0,0.0,0.0)
        self.timeoffset = 0
        sys.path.append(hwconfigpath)
        global hardwareConfiguration
        from hardwareConfiguration import hardwareConfiguration
        
    def update_parameters(self, value):
        self.lastannouncement = value
        self.seqID = value[1]
        self.parameters['A'] = value[5]
        self.parameters['B'] = value[6]
        self.parameters['C'] = value[7]

    def add_text(self,text):
        self.text = text
        
    def parse_text(self):
        self.sequence =  []
        self.ddsDict = hardwareConfiguration.ddsDict
        #tic = time.clock()
        defs,reducedtext =  self.findAndReplace(self.defpattern,self.text,re.DOTALL)
        loops,reducedtext = self.findAndReplace(self.looppattern,reducedtext,re.DOTALL)
        steadys,reducedtext = self.findAndReplace(self.steadypattern,reducedtext,re.DOTALL)
        self.parseDefine(defs,loops)
        self.parseLoop(loops)
        self.parseSteadystate(steadys)
        self.parsePulses(reducedtext)
        #toc = time.clock()
        #print 'Parsing time:                  ',toc-tic
        
        
    def findAndReplace(self,pattern,string,flags=0):
        listofmatches = re.findall(pattern,string,flags)
        newstring = re.sub(pattern,'',string,re.DOTALL)
        return listofmatches,newstring

    def defineRegexPatterns(self):
        self.channelpattern = r'Channel\s+([aA0-zZ9]+)\s'
        self.pulsepattern   = r'([a-z]*)\s+([+-]?[0-9]+|[+-]?[0-9]+\.[0-9]+|var\s+[aA0-zZ9]+)\s+([aA-zZ]+)'
        self.looppattern    = r'(?s)(?<=)#repeat(.+?)\s+(.+?)(?=)#endrepeat'
        self.defpattern     = r'(?s)(?<=)#def(.+?)(?=)#enddef'
        self.modepattern    = r'in\s+mode\s+([aA-zZ]+)'
        self.steadypattern     = r'(?s)(?<=)#steadystate(.+?)(?=)#endsteadystate'

    def parseDefine(self,listofstrings,loops):
        for defblock in listofstrings:
            for line in defblock.strip().split('\n'):
                if '=' in line:
                    if "ParameterVault" in line.split():
                        line = re.sub(r'from|ParameterVault','',line)
                        param = line.split()[2]
                        line =re.sub(param,str(self.parameters[param]),line)
                    exec('self.' + line.strip())
                else:
                    words = line.strip().split()
                    exec('self.'+words[1]+' = 0.0')


    def parseLoop(self,listofstrings):
        for loopparams, lines in listofstrings:
            begin,end,it = loopparams.split(',')
            lines = lines.strip()
            itervar = begin.split('=')[0].strip()
            begin=int(begin.split('=')[1])
            it = int(it.split('+')[1])
            end = int(end.split('<')[1])
            newlines = ''
            for i in np.arange(begin,end,it):
                for aline in lines.split('\n'):
                    for amatch in re.findall(r'(\(.+?\))',aline):
                        newstring = amatch
                        if 'var' in amatch:
                            newstring = amatch.replace('var ','self.')
                        if itervar in amatch:
                             newstring = newstring.replace(itervar,str(i))
                        newstring = str(eval(newstring))
                        aline = aline.replace(amatch,newstring)
                    newlines += aline + '\n'
            self.parsePulses(newlines)

    def parseSteadystate(self,listofstrings):
        from labrad.units import WithUnit
        for block in listofstrings:
            for line in block.strip().split('\n'):
                name,line = self.findAndReplace(self.channelpattern,line)
                mode,line = self.findAndReplace(self.modepattern,line)
                pulseparameters,line = self.findAndReplace(self.pulsepattern,line.strip())
                for desig,value,unit in pulseparameters:
                    if desig == 'do':
                        try:
                            __freq = WithUnit(float(value),unit)
                        except ValueError:
                            __freq = WithUnit(float(value),unit)
                    elif desig == 'with':
                        try:
                            __amp = WithUnit(float(value),unit)
                        except ValueError:
                            __amp = WithUnit(float(value),unit)
                self.steadystatedict[name[0]] = {'freq': __freq['MHz'], 'ampl':__amp['dBm']}

    def parsePulses(self,blockoftext):
        if len(blockoftext.strip())==0:
            return
        for line in blockoftext.strip().split('\n'):
            name,line = self.findAndReplace(self.channelpattern,line)
            mode,line = self.findAndReplace(self.modepattern,line)
            pulseparameters,line = self.findAndReplace(self.pulsepattern,line.strip())
            if mode[0] == 'Normal':
                self.makeNormalPulse(name,0,pulseparameters)
            elif mode[0] == 'Modulation':
                self.makeModulationPulse(name,1,pulseparameters)

    def makeNormalPulse(self,name,mode,parameters):
        from labrad.units import WithUnit
        __freq, __amp, __begin, __dur = [0]*4
        __phase = WithUnit(0,"deg")
        __ramprate = WithUnit(0,'MHz')
        __ampramp = WithUnit(0,'dBm')
            
        for desig,value,unit in parameters:
            if   desig == 'do':
                try:
                    __freq = WithUnit(float(value),unit)
                except ValueError:
                    __freq = WithUnit(eval('self.'+value.split()[1].strip()),unit) 
            elif desig == 'at':
                try:
                    __begin = WithUnit(float(value) - self.timeoffset,unit)
                except ValueError:
                    __begin = WithUnit(eval('self.'+value.split()[1].strip()) - self.timeoffset,unit)
            elif desig == 'for':
                try:
                    __dur = WithUnit(float(value),unit)
                except ValueError:
                    __dur = WithUnit(eval('self.'+value.split()[1].strip()),unit)
            elif desig == 'with':
                try:
                    __amp = WithUnit(float(value),unit)
                except ValueError:
                    __amp = WithUnit(eval('self.'+value.split()[1].strip()),unit)
            elif desig == 'freqramp':
                try:
                    __ramprate = WithUnit(float(value),unit)
                except ValueError:
                    __ramprate = WithUnit(eval('self.'+value.split()[1].strip()),unit)
            elif desig == 'ampramp':
                try:
                    __ampramp = WithUnit(float(value),unit)
                except ValueError:
                    __ampramp = WithUnit(eval('self.'+value.split()[1].strip()),unit)
        self.sequence.append((name[0],__begin,__dur,__freq,__amp,__phase,__ramprate,__ampramp,mode))
    
    def makeModulationPulse(self,name,mode,parameters):
        from labrad.units import WithUnit
        __freq, __amp, __begin, __dur, __excur, __modfreq = [0]*6
        __phase = WithUnit(0,"deg")
        for desig,value,unit in parameters:
            if   desig == 'do':
                try:
                    __freq = WithUnit(float(value),unit)
                except ValueError:
                    __freq = WithUnit(eval('self.'+value.split()[1].strip()),unit) 
            elif desig == 'at':
                try:
                    __begin = WithUnit(float(value) - self.timeoffset,unit)
                except ValueError:
                    __begin = WithUnit(eval('self.'+value.split()[1].strip()) - self.timeoffset,unit)
            elif desig == 'for':
                try:
                    __dur = WithUnit(float(value),unit)
                except ValueError:
                    __dur = WithUnit(eval('self.'+value.split()[1].strip()),unit)
            elif desig == 'with':
                try:
                    __amp = WithUnit(float(value),unit)
                except ValueError:
                    __amp = WithUnit(eval('self.'+value.split()[1].strip()),unit)
            elif desig == 'modfreq':
                try:
                    __modfreq = WithUnit(float(value),unit)
                except ValueError:
                    __modfreq = WithUnit(eval('self.'+value.split()[1].strip()),unit)
            elif desig == 'modexcur':
                try:
                    __excur = WithUnit(float(value),unit)
                except ValueError:
                    __excur = WithUnit(eval('self.'+value.split()[1].strip()),unit)
        self.sequence.append((name[0],__begin,__dur,__freq,__amp,__phase,__excur,__modfreq,mode))
    
    
    
    def get_binary_repres(self):
        self.new_sequence_trigger.emit(self.sequence)
        seqObject = Sequence(self.ddsDict,self.steadystatedict)
        seqObject.addDDSPulses(self.sequence)
        tic = time.clock()
        binary,ttl = seqObject.progRepresentation()
        
        return str(binary),str(ttl)
                

    @pyqtSlot()
    def stop(self):
        self.tracking = False
        self.trackingparameterserver.emit(self.tracking)
        self.reset_sequence_storage
    
        
    @pyqtSlot()
    def run(self,text,value = None):
        self.text = text
        if value is not None:
            self.update_parameters(value)
        self.parse_text()
        binary,ttl = self.get_binary_repres() 
        return (binary,ttl,value)
        
class Sequence():
    """Sequence for programming pulses"""
    def __init__(self,ddsDict,steadystatedict):
        self.channelTotal = hardwareConfiguration.channelTotal
        self.timeResolution = Decimal(hardwareConfiguration.timeResolution)
        self.MAX_SWITCHES = hardwareConfiguration.maxSwitches
        self.resetstepDuration = hardwareConfiguration.resetstepDuration
        self.ddsDict = ddsDict
        self.steadystatedict = steadystatedict

        #dictionary in the form time:which channels to switch
        #time is expressed as timestep with the given resolution
        #which channels to switch is a channelTotal-long array with 1 to switch ON, -1 to switch OFF, 0 to do nothing
        self.switchingTimes = {0:np.zeros(self.channelTotal, dtype = np.int8)} 
        self.switches = 1 #keeps track of how many switches are to be performed (same as the number of keys in the switching Times dictionary"
        #dictionary for storing information about dds switches, in the format:
        #timestep: {channel_name: integer representing the state}
        self.ddsSettingList = []
        self.sequenceTimeRange = hardwareConfiguration.sequenceTimeRange
        self.advanceDDS = hardwareConfiguration.channelDict['AdvanceDDS'].channelnumber
        self.resetDDS = hardwareConfiguration.channelDict['ResetDDS'].channelnumber


########################################################################
#########                                                      #########
#########               Adding dds Pulses                      #########
#########                                                      #########
########################################################################


    def addDDSPulses(self,values):
        from labrad.units import WithUnit
        '''
        input in the form of a list:
        Normal  pulses   : [(name, start, duration, frequency, amplitude, phase, ramp_rate, amp_ramp_rate,mode)]
        Modulation pules : [(name, start, duration, frequency, amplitude, phase, freq_excur, freq_mod,mode)]
        '''
        valuedict = {}
        self.initialdict = self._getCurrentDDS()
        for i in range(len(values)):
            name = values[i][0]
            if name in valuedict:
                valuedict[name].append(values[i][1:])
            else:
                valuedict[name] = [values[i][1:]]

        for aname in self.ddsDict.keys():
            if aname in self.steadystatedict:
                steadystatefreq = steadystatedict[aname]['freq']
                steadystateampl = steadystatedict[aname]['ampl']
            else:
                steadystatefreq = 0
                steadystateampl = -37
            if aname in valuedict:
                valuedict[aname].append((WithUnit(0.001,'ms'),WithUnit(0.001,'ms'),WithUnit(steadystatefreq,'MHz'),WithUnit(steadystateampl,'dBm'),
                           WithUnit(0,'deg'),WithUnit(0,'MHz'),WithUnit(0,'dBm'),0))
                print aname
            else:
                valuedict[aname] = [(WithUnit(0,'ms'),WithUnit(0,'ms'),WithUnit(steadystatefreq,'MHz'),WithUnit(steadystateampl,'dBm'),
                           WithUnit(0,'deg'),WithUnit(0,'MHz'),WithUnit(0,'dBm'),0)]
            

        for aname,alist in valuedict.iteritems():
            values = sorted(alist, key = lambda x: x[0])

            for i in range(len(values)):
                value = values[i]
                if i < len(values)-1:
                    nextvalue = values[i+1]
                else:
                    nextvalue = None
                    
                
                start,dur,freq,ampl,phase,modespecific1,modespecific2,mode = value
                if nextvalue is not None:
                    nextstart,nextdur,nextfreq,nextampl,nextphase,nextmodespecific1,nextmodespecific2,nextmode = nextvalue

                try:
                    channel = self.ddsDict[aname]
                except KeyError:
                    raise Exception("Unknown DDS channel {}".format(aname))
                start = start['s']
                dur = dur['s']
                freq = freq['MHz']
                ampl = ampl['dBm'] 
                phase = phase['deg']
                if mode == 0: #normal mode
                    modespecific1 = modespecific1['MHz'] #ramp_rate        If anything different from 0, it will ramp while being off
                    modespecific2 = modespecific2['dBm'] #amp_ramp_rate    If anything different from 0, it will ramp while being off
                elif mode == 1: #modulation mode
                    modespecific1 = modespecific1['MHz'] #freq_excur
                    modespecific2 = modespecific2['MHz'] #Freq_mod

                if nextvalue is not None:
                    nextfreq = nextfreq['MHz']
                    if nextmode == 0: #normal mode
                        if nextmodespecific1 != 0:
                            nextfreq = freq
                        nextmodespecific1 = 0 #ramp_rate        If anything different from 0, it will ramp while being off
                        nextmodespecific2 = 0 #amp_ramp_rate    If anything different from 0, it will ramp while being off
                    elif nextmode == 1: #modulation mode
                        nextmodespecific1 = nextmodespecific1['MHz'] #freq_excur
                        nextmodespecific2 = nextmodespecific2['MHz'] #Freq_mod
            
                if nextvalue is not None:
                    freq_off = nextfreq
                    ampl_off = channel.off_parameters[1]
                    mode_off = nextmode
                    modespecific1_off = nextmodespecific1
                    modespecific2_off = nextmodespecific2
                else:
                    freq_off, ampl_off = channel.off_parameters
                    mode_off = mode
                    modespecific1_off = 0
                    modespecific2_off = 0   
                if freq == 0:
                    freq, ampl = freq_off,ampl_off
                else:
                    if not channel.allowedfreqrange[0] <= freq <=channel.allowedfreqrange[1]: raise Exception ("channel {0} : Frequeny of {1} is outside the allowed range".format(channel.name, freq))
                    if not channel.allowedamplrange[0] <= ampl <=channel.allowedamplrange[1]: raise Exception ("channel {0} : Amplitude of {1} is outside the allowed range".format(channel.name, freq))


                num = self.settings_to_int(channel, freq, ampl,  mode,phase, modespecific1, modespecific2)
                #note that keeping the frequency the same when switching off to preserve phase coherence
                num_off = self.settings_to_int(channel, freq_off, ampl_off,  mode_off, phase, modespecific1_off, modespecific2_off)   
                #note < sign, because start can not be 0. 
                #this would overwrite the 0 position of the ram, and cause the dds to change before pulse sequence is launched
                if not start <= self.sequenceTimeRange[1]: 
                    raise Exception ("DDS start time out of acceptable input range for channel {0} at time {1}".format(aname, start))
                if not start + dur <= self.sequenceTimeRange[1]: 
                    raise Exception ("DDS start time out of acceptable input range for channel {0} at time {1}".format(aname, start + dur))
                if start == 0:
                    self.initialdict[aname] = num
                elif not dur == 0:#0 length pulses are ignored
                    self.addDDS(aname, start, num, 'start')
                    self.addDDS(aname, start + dur, num_off, 'stop')

    def addDDS(self, name, start, num, typ):
        #Convert startime to integer
        sec = '{0:.9f}'.format(start) #round to nanoseconds
        sec= Decimal(sec) #convert to decimal 
        timeStep = ( sec / self.timeResolution).to_integral_value()
        timeStep = int(timeStep)
        #Add dds with starttime represented as an integer number of timesteps
        self.ddsSettingList.append((name, timeStep, num, typ))


########################################################################
#########                                                      #########
#########               Conversion funtions                    #########
#########                                                      #########
########################################################################
    def settings_to_int(self, channel, freq, ampl, mode, phase = 0, modespecific1 = 0, modespecific2 = 0): ### add ramp for ramping functionality
        '''
        takes the frequency and amplitude values for the specific channel and returns integer representation of the dds setting
        freq is in MHz
        power is in dbm
        '''
       # print mode
        freqrange = channel.boardfreqrange
        amplrange = channel.boardamplrange
        phaserange = channel.boardphaserange
        ## changed the precision from 32 to 64 to handle super fine frequency tuning
        bytearr = ''
        if mode == 0: #0 = Normal operation mode
            ramp_rate = modespecific1
            amp_ramp_rate = modespecific2
            amp_ramp_range = (channel.board_amp_ramp_range[0],channel.board_amp_ramp_range[1])
            ramprange = channel.boardramprange

            if ramp_rate < ramprange[0]:
                ramp_rate = ramprange[0]
            elif ramp_rate > ramprange[1]:
                ramp_rate = ramprange[1]

            if amp_ramp_rate < amp_ramp_range[0]:
                amp_ramp_rate = amp_ramp_range[0]
            elif amp_ramp_rate > amp_ramp_range[1]:
                amp_ramp_rate = amp_ramp_range[1]
            else:
                amp_ramp_rate = 1/amp_ramp_rate



            for val, rng, precision, extrabits in [(phase,              phaserange, 16, False),
                                                    (ampl,               amplrange, 16, True),
                                                    (amp_ramp_rate, amp_ramp_range, 16, False),
                                                    (ramp_rate,          ramprange, 16, False),
                                                    (freq,               freqrange, 64, False)]:
                minim,maxim = rng                                    
                resolution = (maxim - minim) / float(2**precision - 1)
                num = int((val - minim)/resolution) #number representation
                b = bytearray(precision/8)
                for i in range(len(b)):
                    tmp = (num//(2**(i*8)))%256
                    if extrabits:
                        if i == 0:
                            tmp = tmp & 0b11111100 # Masks out the last two bits of the amplitude, indicated mode 0
                    b[i] = tmp
                #import binascii
                #print binascii.hexlify(b)
                bytearr += b
        elif mode == 1: # Frequency modulation mode
            centerfrequency = freq
            frequencyexcursion = modespecific1
            frequencymodulation = modespecific2
            
            high_ramp_limit = centerfrequency + frequencyexcursion
            low_ramp_limit  = centerfrequency - frequencyexcursion
            ramping_interval = (10*24.)/2000  # hardcoded in fpga code, 120 ns between each frequency step
            freq_change_rate  = 4 * frequencyexcursion * frequencymodulation # frequency change per second required
            freq_step_size = freq_change_rate * ramping_interval
            
            for val, rng, precision, extrabits in [(phase,            phaserange, 16, False),
                                                    (ampl,             amplrange, 16, True),
                                                    (freq_step_size,   freqrange, 32, False),
                                                    (high_ramp_limit,  freqrange, 32, False),
                                                    (low_ramp_limit,   freqrange, 32, False)]: 
                minim,maxim = rng                                      
                resolution = (maxim - minim) / float(2**precision - 1)
                num = int((val - minim)/resolution) #number representation
                b = bytearray(precision/8)
                for i in range(len(b)):
                    tmp = (num//(2**(i*8)))%256
                    if extrabits:
                        if i == 0:
                            tmp = tmp & 0b11111100 # Masks out the last two bits of the amplitude, indicated mode 1
                            tmp = tmp | 0b00000001
                    b[i] = tmp
                bytearr += b
                
        return bytearr
    

    def _addNewSwitch(self, timeStep, chan, value):
        if self.switchingTimes.has_key(timeStep):
            if self.switchingTimes[timeStep][chan]: raise Exception ('Double switch at time {} for channel {}'.format(timeStep, chan))
            self.switchingTimes[timeStep][chan] = value
        else:
            if self.switches == self.MAX_SWITCHES: raise Exception("Exceeded maximum number of switches {}".format(self.switches))
            self.switchingTimes[timeStep] = np.zeros(self.channelTotal, dtype = np.int8)
            self.switches += 1
            self.switchingTimes[timeStep][chan] = value
    
    def progRepresentation(self, parse = True):
        if parse:
            self.ddsSettings = self.parseDDS()
            self.ttlProgram = self.parseTTL()
            fullbinary = None
            metablockcounter = 0
            for name, pulsebinary in self.ddsSettings.iteritems():
                addresse = self.ddsDict[name].channelnumber
                blocklist = [pulsebinary[i:i+16] for i in range(0, len(pulsebinary), 16)]
                i = 0
                while i < len(blocklist):
                    repeat = 0
                    currentblock = blocklist[i]
                    j = i+1
                    try:
                        while blocklist[j] == currentblock and repeat < 250:
                            repeat += 1
                            j += 1
                    except IndexError ,e:
                        pass
                    i = j
                    if fullbinary is None:
                        fullbinary = bytearray([addresse,repeat]) + currentblock
                    else:
                        fullbinary += bytearray([addresse,repeat]) + currentblock
                    metablockcounter += 1
                fullbinary[-18] = 128 + addresse
        import binascii
        for abyte in [fullbinary[i:i+18] for i in range(0, len(fullbinary), 18)]:
            print '------------------'
            print binascii.hexlify(abyte),len(abyte)
        fullbinary = bytearray('e000'.decode('hex'))  + fullbinary + bytearray('F000'.decode('hex'))
        print self.switches
        return fullbinary, self.ttlProgram
        
    def userAddedDDS(self):
        return bool(len(self.ddsSettingList))
    
    def _getCurrentDDS(self):
        '''
        Returns a dictionary {name:num} with the reprsentation of the current dds state
        '''
        d = dict([(name,self._channel_to_num(channel)) for (name,channel) in self.ddsDict.iteritems()])
        return d
    

    def _channel_to_num(self, channel):
        '''returns the current state of the channel in the num represenation'''
        if channel.state:
            #if on, use current values. else, use off values
            freq,ampl,mode = (channel.frequency, channel.amplitude,channel.mode)
        else:
            freq,ampl = channel.off_parameters
            mode = 0
        num = self.settings_to_int(channel, freq, ampl,  mode)
        return num
    
    def parseDDS(self):
        if not self.userAddedDDS(): return None
        state = self.initialdict
        pulses_end = {}.fromkeys(state, (0, 'stop')) #time / boolean whether in a middle of a pulse 
        dds_program = {}.fromkeys(state, '')
        lastTime = 0
        entries = sorted(self.ddsSettingList, key = lambda t: t[1] ) #sort by starting time
        possibleError = (0,'')
        print entries
        #print state
        #print entries
        while True:
            try:
                name,start,num,typ = entries.pop(0)
            except IndexError:
                if start  == lastTime:
                    #still have unprogrammed entries
                    self.addToProgram(dds_program, state)
                    self._addNewSwitch(lastTime,self.advanceDDS,1)
                    self._addNewSwitch(lastTime + self.resetstepDuration,self.advanceDDS,-1)
                #add termination
                #at the end of the sequence, reset dds
                lastTTL = max(self.switchingTimes.keys())
                self._addNewSwitch(lastTTL ,self.resetDDS, 1 )
                self._addNewSwitch(lastTTL + self.resetstepDuration ,self.resetDDS,-1)
                return dds_program
            end_time, end_typ =  pulses_end[name]
            if start > lastTime:
                #the time has advanced, so need to program the previous state
                if possibleError[0] == lastTime and len(possibleError[1]): raise Exception(possibleError[1]) #if error exists and belongs to that time
                self.addToProgram(dds_program, state)
                if not lastTime == 0:
                    self._addNewSwitch(lastTime,self.advanceDDS,1)
                    self._addNewSwitch(lastTime + self.resetstepDuration,self.advanceDDS,-1)
                lastTime = start
            if start == end_time:
                #overwite only when extending pulse
                if end_typ == 'stop' and typ == 'start':
                    possibleError = (0,'')
                    state[name] = num
                    pulses_end[name] = (start, typ)
                elif end_typ == 'start' and typ == 'stop':
                    possibleError = (0,'')
            elif end_typ == typ:
                possibleError = (start,'Found Overlap Of Two Pules for channel {}'.format(name))
                state[name] = num
                pulses_end[name] = (start, typ)
            else:
                state[name] = num
                pulses_end[name] = (start, typ)

    def addToProgram(self, prog, state):
        for name,num in state.iteritems():
            #import binascii
            #print '------------------'
            #print binascii.hexlify(num),len(num)
            prog[name] += num
             
        
   
    
        
    def parseTTL(self):
        """Returns the representation of the sequence for programming the FPGA"""
        rep = ''
        lastChannels = np.zeros(self.channelTotal)
        powerArray = 2**np.arange(self.channelTotal, dtype = np.uint64)
        for key,newChannels in sorted(self.switchingTimes.iteritems()):
            channels = lastChannels + newChannels #computes the action of switching on the state
            if (channels < 0).any(): raise Exception ('Trying to switch off channel that is not already on')
            channelInt = np.dot(channels,powerArray)
            rep = rep + self.numToHex(key) + self.numToHex(channelInt) #converts the new state to hex and adds it to the sequence
            lastChannels = channels
        rep = rep + 2*self.numToHex(0) #adding termination
        return rep
        
    def numToHex(self, number):
        number = int(number)
        b = bytearray(4)
        b[2] = number%256
        b[3] = (number//256)%256
        b[0] = (number//65536)%256
        b[1] = (number//16777216)%256
        return b

