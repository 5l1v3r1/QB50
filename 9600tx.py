#!/usr/bin/env python

from gnuradio import gr,usrp,blks
from gnuradio.eng_option import eng_option
from optparse import OptionParser
from math import pi
from ax25 import *
import Numeric

#
# 9600 (16) 153600 (5/3) 256000 (500) 128e6
#

def main():
    parser=OptionParser(option_class=eng_option)
    parser.add_option("-f", "--freq", type="eng_float", default=144.800e6,help="set frequency to FREQ", metavar="FREQ")
    parser.add_option("-m", "--message", type="string", default=":ALL      :this is a test",help="message to send", metavar="MESSAGE")
    parser.add_option("-c", "--mycall", type="string", default="MYCALL", help="source callsign", metavar="CALL")
    parser.add_option("-t", "--tocall", type="string", default="CQ", help="recipient callsign", metavar="CALL")
    parser.add_option("-v", "--via", type="string", default="RELAY", help="digipeater callsign", metavar="CALL")
    parser.add_option("-d", "--do-logging", action="store_true", default=False, help="enable logging on datafiles")
    parser.add_option("-s", "--use-datafile", action="store_true", default=False, help="use usrp.dat (256kbps) as output")
    (options, args) = parser.parse_args()
    if len(args) !=0:
        parser.print_help()
        sys.exit(1)    
    
    bitrate=9600
    dac_rate=128e6
    usrp_interp=500
    cordic_freq=options.freq-dac_rate
    sf=153600
    syminterp=sf/bitrate                                                #16
    nbfmdev=3e3    
    fmsens=2*pi*nbfmdev/(sf*5/3)
    bit_oversampling=8
    sw_interp=int(sf/bitrate/bit_oversampling)                          #2

    fg = gr.flow_graph()

    p=buildpacket(options.mycall,0,options.tocall,0,options.via,0,0x03,0xf0,options.message)
    if options.do_logging:
        dumppackettofile(p,"packet.dat")
    v=bits2syms(nrziencode(scrambler(hdlcpacket(p,100,1000))))        
    src = gr.vector_source_f(v)
    gaussian_taps = gr.firdes.gaussian(
            1,                        # gain
            bit_oversampling,         # symbol_rate
            0.3,                      # bandwidth * symbol time
            4*bit_oversampling     	  # number of taps
    )
    sqwave = (1,) * syminterp         #rectangular window
    taps = Numeric.convolve(Numeric.array(gaussian_taps),Numeric.array(sqwave))
    gaussian = gr.interp_fir_filter_fff(syminterp, taps)		    #9600*16=153600
    
    res_taps = blks.design_filter(5,3,0.4)
    res = blks.rational_resampler_fff(fg,5,3,res_taps)        	    #153600*5/3=256000
    fmmod = gr.frequency_modulator_fc(fmsens)
    amp = gr.multiply_const_cc(32000)

    if options.use_datafile:
        dst=gr.file_sink(gr.sizeof_gr_complex,"usrp.dat")
    else:
        u = usrp.sink_c(0,usrp_interp)                              #256000*500=128000000
        tx_subdev_spec = usrp.pick_tx_subdevice(u)
        m = usrp.determine_tx_mux_value(u, tx_subdev_spec)
        print "mux = %#04x" % (m,)
        u.set_mux(m)
        subdev = usrp.selected_subdev(u, tx_subdev_spec)
        print "Using TX d'board %s" % (subdev.side_and_name(),)
        u.set_tx_freq (0, cordic_freq)
        u.set_pga(0,0)
        print "Actual frequency: ",u.tx_freq(0)
        dst=u

    fg.connect(src,gaussian,res,fmmod,amp,dst)

    fg.start()   
    fg.wait()
    
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass        



