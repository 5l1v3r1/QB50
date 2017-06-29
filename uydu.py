#!/usr/bin/env python
#
#Baris DINC - TA7W - June 2017
#
#TODO : Add frequency change over HamLib or directly for Kenwood TS2000
#TODO : Add PTT keying for QRO operation
#

#imports section
import serial
import threading
import time


mycall="TA7W  " #...... for BeEagleSAT and ...... for HavelSAT (SSIDs is 0)
stcall="ON02TR" #ON01TR for BeEagleSAT and ON02TR for HavelSAT (SSIDs is 1)

#Do you have a modem connected : Ture/False 
hasModem=True   
modem_port ="/tmp/ttyV1"
modem_speed=38400
modem_kiss ="1B 40 4B" #ESC@K

#Do you have a radio connected : True/False
hasRadio=False
radio_port="/dev/ttyUSB1"
radio_speed=9600
radio_command="" #insert command for Frequency change

###SETTINGS for SCS Modem
modemSettings=[]
modemSettings.append("Z0")       #Z0   # Set flow-control (Hardware flow-control, no XON/XOFF)
modemSettings.append("E0")       #E0   # Disable echoing of commands
modemSettings.append("X1")       #X1   # Enable the PTT line
modemSettings.append("W0")       #W0   # Minimize the slottime
modemSettings.append("T100")     #T100 # Set the TX-Delay to x*10ms
modemSettings.append("@D0")      #@D0  # Set full duplex transmission
modemSettings.append("@F1")      #@F1  # Send flags during pauses
modemSettings.append("%B9600")   #%B9600  # Configuration of the Packet-Radio Mode
modemSettings.append("%T0")      #%T0     # Disable TX frequency tracking (should not apply at 1200bps anyway)
modemSettings.append("%XA2400")  #%XA2400 # AFSK amplitude %XA[30-30000] mV
modemSettings.append("%X9000")   #%X9000  # All modulations amplitude %X[30-30000] mV
modemSettings.append("@K")       #@K      # Switch to KISS Mode




#C0 00 9E 9C 60 64 A8= A4 60 A8 82 64 9E 94 82 61 03 F0 DB DC 18 0A CA 26 00 05 19 08 01 60 B8 33 C0 
#testing with socat : socat -d -d pty,raw,echo=0,link=/tmp/ttyV0 pty,raw,echo=0,link=/tmp/ttyV1

lookUpTable=[] #Array for CCIT CRC16 syndrome
dataToSend=[]  #Data to be send out to modem
if hasModem: modemPort=serial.Serial()
if hasRadio: radioPort=serial.Serial()
currSequence=0xA25 #for packet sequencing (initialize)


def CRC_Init():
#prepares the CCIT lookUpTable[]
    for i in range(256):
	tmp=0
	if (i & 1)   !=0: tmp = tmp ^ 0x1021
	if (i & 2)   !=0: tmp = tmp ^ 0x2042
	if (i & 4)   !=0: tmp = tmp ^ 0x4084
	if (i & 8)   !=0: tmp = tmp ^ 0x8108
	if (i & 16)  !=0: tmp = tmp ^ 0x1231
	if (i & 32)  !=0: tmp = tmp ^ 0x2462
	if (i & 64)  !=0: tmp = tmp ^ 0x48C4
	if (i & 128) !=0: tmp = tmp ^ 0x9188
	lookUpTable.append(tmp)
    return
def calc_CSUM(data,dStart,dLength):
    #Do CheckSum calculations
    chksum=0xFFFF
    for dByte in data[dStart:dStart+dLength]:
      chksum=((chksum<<8)&0xFF00)^(lookUpTable[((chksum>>8)^dByte) & 0x00FF]) 
    return chksum

def About():
    print "QB50 uplink tester..... by TA7W"
    return

def doChecks():
    retVal = []
    print "preparing system and configuration checks..."
    if len(mycall) !=6: retVal.append("source Callsign (mycall) must be 6 characters long... If not please fill with spaces.")
    if len(stcall) !=6: retVal.append("Destionation Callsign (stcall) must be 6 characters long... If not please fill with spaces.")
    #Check modem port availability 
    global modemPort
    if hasModem:
      print "Chechking modem....."
      try:
	modemPort = serial.Serial(modem_port)
 	#modemPort.close()
      except serial.serialutil.SerialException:
        retVal.append("Cannot open Modem port...: %s " % modem_port)
	pass
    #Check radio port availability 
    global radioPort
    if hasRadio:
      print "Chechking radio....."
      try:
	radioPort = serial.Serial(modem_port)
 	#radioPort.close()
      except serial.serialutil.SerialException:
        retVal.append("Cannot open Radio port...: %s " % radio_port)
	pass

    return retVal
	
def prepareHeader():
    #Prepare the header of the AX25 message
    dataToSend.append(0xC0) #first char FEND for KISS data start
    dataToSend.append(0x00) #kiss ode data identifier
    for data in stcall: dataToSend.append(2*ord(data))
    dataToSend.append(96) #append -0 as SSID
    for data in mycall: dataToSend.append(2*ord(data))
    dataToSend.append(97) #append -1 as SSID
    dataToSend.append(3)  #append 3 as FLAG
    dataToSend.append(240)#append F0 as protocol identifier
    dataToSend.append(219)#append DB : this is the ESCAPE character .. we want to send C0 as data start... DB DC replaces C0
    dataToSend.append(220)#append DC : look remarks of previous byte
    dataToSend.append(24) #append 18 : don't know the meaning yet  
    dataToSend.append(10) #append 0A : don't know the meaning yet

    return

def prepareSEQ(Sequence):
    #Prepare the sequence and insert 2 bytes... we need a new sequence for every transmission
    SequenceFlags=0xC000 #11...... first two buts of sequence is flags, and it is 0b11000000
    Sequence=(SequenceFlags|(Sequence+1) ) & 0x00FFFF #keep it 2 bytes
    dataToSend.append(Sequence>>8)      #append first sequence byte
    dataToSend.append(((Sequence<<8)&0xFF00)>>8) #append second sequence byte

    return Sequence

def preparePayload():
    #Prepare the payload of the AX25 message
    #TODO: This is only for GET MODE... extend it for other commands
    dataToSend.append(0x00)  # 0x00 0x05 0x019 0x08 0x01 0x60 
    dataToSend.append(0x05)  #TODO: this is length of GetMode 
    dataToSend.append(0x0A)  #TODO: describe this byte
    dataToSend.append(0x08)  #Type 8  - HouseKeeping
    dataToSend.append(0x01)  #SubType - always 1
    dataToSend.append(0x60)  #Getmode command 
    return

def prepareCSUM(csData):
    #Prepare the CSUM for the payload
    csum=calc_CSUM(csData,20,10)
    dataToSend.append((csum>>8)&0x00FF)      #fisrt byte of checksum
    dataToSend.append(((csum<<8)&0xFF00)>>8) #second byte of checksum
    return

def prepareFooter():
    #Prepare the footer of the AX25 message
    dataToSend.append(192) #append C0 : last character for KISS data end
    return

def prepareModem():
    #send modem parameters to modem and put it into KISS mode
    #TODO 
    print "preparing modem...."
    global modemPort
    for modemsetting in modemSettings:
      try:
        modemPort.write("%s\n\r" % modemsetting)
      except:
        print "ERROR : Problem ocured while trying to configure modem..."
    return


def timeTicks():
    global hasModem
    tmr = threading.Timer(1.0, timeTicks) #timer function to send periodic messages
    tmr.start()         #start the timer
    del dataToSend[:]   #Data to be send cleared out (deleted) before next turn
    prepareHeader()     #prepare the first part of AX25 message
    global currSequence #We shuld update the global current Sequence variable
    currSequence=prepareSEQ(currSequence)      #prepare the packet sequence number for payload
    preparePayload()    #prepare the payload part
    prepareCSUM(dataToSend)
    prepareFooter()
    #we're done with preparations, send the data out to the modem
    print "Seq [%04X]" % currSequence, 
    for dataout in dataToSend:
	if hasModem: modemPort.write(chr(dataout))
	print "0x%02X" % dataout,
    print ""
    print "Seq [%04X] sent out..." % currSequence

    return

def main():
    About()    #print header ads
    CRC_Init() #prepare the lookup table
    retVal=doChecks() #do definition checks
    if len(retVal)!=0:
	for Message in retVal: print "ERROR: ",Message
	return 0
    if hasModem: prepareModem()    #prepare the modem for KISS mode with appropriate settings


    timeTicks() #Start timer events
    while True:
     time.sleep(5)


if __name__ == '__main__':
    main()





