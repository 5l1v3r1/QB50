#!/Beacon.py

import socket

def dumpstring(str):
   for x in range(0,len(str)):
      print str[x],
      print (' {0:X}'.format(ord(str[x])))



def format_call(raw_call):
    raw_call = raw_call.upper()
    while len(raw_call) < 6:
       raw_call = raw_call + chr(0x20)

    result = ''
    for x in range(0,6):
       result = result + chr( ord(raw_call[x]) << 1)
    return result

def buildUIFrame(dest_call, source_call, text):
    path1 = "WIDE1" # Hard coded path.  SSID is part of the flag byte below
    path2 = "WIDE2" # TODO: Pass this in and parse it.
    result = format_call(dest_call)
    result = result + chr(0xe0)                  # SSID = 0
    result = result + format_call(source_call)
    result = result + chr(0xfe) # -15            # SSID = 15.  Should the MSB be set? Seems to work either way
    result = result + format_call(path1)
    result = result + chr(0x62)                  # 0 1 1 0001 0: WIDE1-1  
    result = result + format_call(path2)
    result = result + chr(0x65)                  # 0 1 1 0010 1: WIDE2-2, last address
    result = result + chr(0x03) + chr(0xf0)
    result = result + text

    return result


# Wrap the formatted packet in a KISS wrapper to send to the TNC

KISS_ID = 0x00
FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD;

def KissWrap(packet):
    result = chr(FEND) + chr(KISS_ID)
    for i in range(0,len(packet)):
       if (packet[i] == chr(FEND)):
          result = result + chr(FESC) + chr(TFEND)
       elif (packet[i] == chr(FESC)):
          result = result + chr(FESC) + chr(TFESC)
       else:
          result = result + packet[i]

    result = result + chr(FEND)
    return result



# Mainline of the program:

server = socket.socket(socket.AF_INET,socket.SOCK_STREAM)


#Fill in the name and port number of the server with the KISS TNC.
host = socket.gethostbyname('127.0.0.1')
port = 6700
MYCALL = "mycall"

server.connect((host,port))


frame = buildUIFrame("Python",MYCALL,">test of my Python script.")

frame = KissWrap(frame)
print "the kiss frame is:",len(frame)
dumpstring(frame)

#and send it
server.send(frame)


server.close()

