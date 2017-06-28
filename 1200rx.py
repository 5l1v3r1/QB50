#!/usr/bin/env python
from gnuradio import gr,usrp,packetradio,blks
import gnuradio.gr.gr_threading as _threading
from optparse import OptionParser
from gnuradio.eng_option import eng_option
from math import pi
import time
from ax25 import *
 
#
#   64e6 (250) 256000 (3/5) 153600 (128) 1200
#

    
class queue_watcher_thread(_threading.Thread):
    def __init__(self, rcvd_pktq, callback):
        _threading.Thread.__init__(self)
        self.setDaemon(1)
        self.rcvd_pktq = rcvd_pktq
        self.callback = callback
        self.keep_running = True
        self.start()

    def stop(self):
        self.keep_running = False
        
    def run(self):
        while self.keep_running:
            msg = self.rcvd_pktq.delete_head()
            if self.callback:
                self.callback(msg.to_string())

def main():
    parser=OptionParser(option_class=eng_option)
    parser.add_option("-R", "--rx-subdev-spec", type="subdev", default=None,help="select USRP Rx side A or B (default=A)")
    parser.add_option("-f", "--freq", type="eng_float", default=144.800e6,help="set frequency to FREQ", metavar="FREQ")
    parser.add_option("-g", "--gain", type="eng_float", default=None,help="set gain in dB (default is midpoint)")
    parser.add_option("-d", "--do-logging", action="store_true", default=False, help="enable logging on datafiles")
    parser.add_option("-s", "--use-datafile", action="store_true", default=False, help="use usrp.dat (256kbps) as input")
    (options, args) = parser.parse_args()
    if len(args) !=0:
        parser.print_help()
        sys.exit(1)

    markfreq=2200
    spacefreq=1200
    bitrate=1200
    usrp_decim=250
    if_rate=64e6/usrp_decim                     #256e3
    sf=(if_rate*3)/5                            #153600
    bit_oversampling=8
    sw_decim=int(sf/bitrate/bit_oversampling)   #8
    bf=sf/sw_decim

    symdev=abs(markfreq-spacefreq)/2
    symcf=min(markfreq,spacefreq)+symdev
    nbfmdev=3e3
    nbfmk=if_rate/(2*pi*nbfmdev)
    symk=bf/(2*pi*symdev)
    
    fg = gr.flow_graph ()  
    
    if options.do_logging:
        logger1 = gr.file_sink(gr.sizeof_gr_complex, "usrpout.dat")       
        logger2 = gr.file_sink(gr.sizeof_float, "demod.dat")
        logger3 = gr.file_sink(gr.sizeof_float, "clkrec.dat")
        logger4 = gr.file_sink(gr.sizeof_char, "slicer.dat")  
        
    if options.use_datafile:
        src = gr.file_source(gr.sizeof_gr_complex,"usrp.dat")
    else:
        u=usrp.source_c()
        u.set_decim_rate(usrp_decim)
        if options.rx_subdev_spec is None:
            subdev_spec=usrp.pick_rx_subdevice(u)
        else:
            subdev_spec=options.rx_subdev_spec
        subdev=usrp.selected_subdev(u, subdev_spec)
        print "Using RX d'board %s" % (subdev.side_and_name(),)
        u.set_mux(usrp.determine_rx_mux_value(u, subdev_spec))
        print "MUX:%x" % (usrp.determine_rx_mux_value(u, subdev_spec))
        if options.gain is None:
            g=subdev.gain_range()
            gain=float(g[0]+g[1])/2
        else:
            gain=options.gain
        subdev.set_gain(gain)
        print "Gain set to",str(gain)
        r=usrp.tune(u, 0, subdev, options.freq)
        if r:
            print "Frequency set to",options.freq
        else:
            print "Frequency set to",options.freq,"failed"
        src=u        

    chan_taps =  gr.firdes.low_pass(1,if_rate,13e3,4e3,gr.firdes.WIN_HANN)
    chan = gr.fir_filter_ccf(1,chan_taps)                           #256e3

    dee = blks.fm_deemph(fg, if_rate, 75e-6)

    fmdem = gr.quadrature_demod_cf(nbfmk)
    
    res_taps = blks.design_filter(3,5,0.4)
    res = blks.rational_resampler_fff(fg,3,5,res_taps)              #153600
    
    lo = gr.sig_source_c(sf,gr.GR_SIN_WAVE,-symcf,1)
    mix = gr.multiply_cc()
    r2c = gr.float_to_complex()
    lp_taps = gr.firdes.low_pass(sw_decim,sf,600,2e3,gr.firdes.WIN_HANN)
    lp = gr.fir_filter_ccf(sw_decim,lp_taps) 
    
    dem = gr.quadrature_demod_cf(symk)
        
    alpha = 0.0001
    freqoff = gr.single_pole_iir_filter_ff(alpha)
    sub = gr.sub_ff()
    
    _def_gain_mu = 0.05
    _def_mu = 0.5
    _def_freq_error = 0.00
    _def_omega_relative_limit = 0.005
    
    _omega = bit_oversampling*(1+_def_freq_error)
    _gain_omega = .25 * _def_gain_mu * _def_gain_mu      

    clkrec = gr.clock_recovery_mm_ff(_omega, _gain_omega, _def_mu, _def_gain_mu, _def_omega_relative_limit)
    
    slicer = gr.binary_slicer_fb()
    
    pktq = gr.msg_queue()
    sink = packetradio.hdlc_framer(pktq,0)
    watcher=queue_watcher_thread(pktq,rx_callback)

    fg.connect(src,chan,fmdem,dee,res,r2c,(mix,0))
    fg.connect(lo,(mix,1))
    fg.connect(mix,lp,dem)
    fg.connect(dem,(sub,0))
    fg.connect(dem,freqoff,(sub,1))
    fg.connect(sub,clkrec,slicer)
    fg.connect(slicer,sink)
    
    if options.do_logging:
        fg.connect(src,logger1)
        fg.connect(sub,logger2)
        fg.connect(clkrec,logger3)
        fg.connect(slicer,logger4)
        
    fg.start()   
    fg.wait()

def rx_callback(payload):
    string=printpacket(payload)
    print "\n=====",time.asctime(time.localtime()),"\n",string,"=====\n"
   
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass


