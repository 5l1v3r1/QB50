
#!/usr/bin/env python
#
#Baris DINC - TA7W - June 2017
#

import os
import SocketServer

class RadioRequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        global radio_frequency
        while 1:
            self.data = self.request.recv(1024)
            if not self.data:
                break
            self.data = self.data.strip()
            if self.data[0]=="F":
	       response="RPRT 0"
	       radio_frequency=int(self.data.split(" ")[2])
               print "radio_frequency setted... %011d " % radio_frequency
            if self.data[0]=="f":
	       response=str(radio_frequency)
            #self.request.send(self.data.upper())
            self.request.send(response)

class RadioServer(SocketServer.ForkingMixIn, SocketServer.TCPServer):
    pass


if __name__ == '__main__':
    print ""
    print "Uydu Project Library file for radio Server  Baris DINC (TA7W) (c)"
    print "--------------------------------------------------------------------------------------------"
    print "ERROR: This program cannot be called directly.. It is part of UYDU Project.. Please run uydu"
    print ""

