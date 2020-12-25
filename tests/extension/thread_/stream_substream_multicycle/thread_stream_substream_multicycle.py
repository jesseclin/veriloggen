from __future__ import absolute_import
from __future__ import print_function
import sys
import os

# the next line can be removed after installation
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from veriloggen import *
import veriloggen.thread as vthread
import veriloggen.types.axi as axi


def mkLed():
    m = Module('blinkled')
    clk = m.Input('CLK')
    rst = m.Input('RST')

    datawidth = 32
    addrwidth = 10
    myaxi = vthread.AXIM(m, 'myaxi', clk, rst, datawidth)
    ram_a = vthread.RAM(m, 'ram_a', clk, rst, datawidth, addrwidth)
    ram_b = vthread.RAM(m, 'ram_b', clk, rst, datawidth, addrwidth)
    ram_c = vthread.RAM(m, 'ram_c', clk, rst, datawidth, addrwidth)

    mulstrm = vthread.Stream(m, 'mul_stream', clk, rst)
    mulx = mulstrm.source('x')
    muly = mulstrm.source('y')
    mulz = mulx * muly
    mulz = mulz + mulx + muly - mulx - muly
    mulstrm.sink(mulz, 'z')

    wrapstrm = vthread.Stream(m, 'wrap_stream', clk, rst)
    a = wrapstrm.source('a')
    b = wrapstrm.source('b')
    a = a + 1
    b = b + 1
    sub = wrapstrm.substream_multicycle(mulstrm)
    sub.to_source('x', a)
    sub.to_source('y', b)
    c = sub.from_sink('z')
    c = c + 100
    wrapstrm.sink(c, 'c')

    all_ok = m.TmpReg(initval=0)

    def comp_stream_mul(size, offset):
        mulstrm.set_source('x', ram_a, offset, size)
        mulstrm.set_source('y', ram_b, offset, size)
        mulstrm.set_sink('z', ram_c, offset, size)
        mulstrm.run()
        mulstrm.join()

    def comp_stream_wrap(size, offset):
        wrapstrm.set_source('a', ram_a, offset, size)
        wrapstrm.set_source('b', ram_b, offset, size)
        wrapstrm.set_sink('c', ram_c, offset, size)
        wrapstrm.run()
        wrapstrm.join()

    def comp_sequential_mul(size, offset):
        sum = 0
        for i in range(size):
            a = ram_a.read(i + offset)
            b = ram_b.read(i + offset)
            sum = a * b
            ram_c.write(i + offset, sum)

    def comp_sequential_wrap(size, offset):
        sum = 0
        for i in range(size):
            a = ram_a.read(i + offset) + 1
            b = ram_b.read(i + offset) + 1
            sum = a * b
            sum += 100
            ram_c.write(i + offset, sum)

    def check(size, offset_stream, offset_seq):
        for i in range(size):
            st = ram_c.read(i + offset_stream)
            sq = ram_c.read(i + offset_seq)
            if vthread.verilog.NotEql(st, sq):
                all_ok.value = False
        if all_ok:
            print('# verify: PASSED')
        else:
            print('# verify: FAILED')

    def comp(size):
        all_ok.value = True

        # mul
        # stream
        offset = 0
        myaxi.dma_read(ram_a, offset, 0, size)
        myaxi.dma_read(ram_b, offset, 512, size)
        comp_stream_mul(size, offset)
        myaxi.dma_write(ram_c, offset, 1024, size)

        # sequential
        offset = size
        myaxi.dma_read(ram_a, offset, 0, size)
        myaxi.dma_read(ram_b, offset, 512, size)
        comp_sequential_mul(size, offset)
        myaxi.dma_write(ram_c, offset, 1024 * 2, size)

        # verification
        print('# MUL')
        myaxi.dma_read(ram_c, 0, 1024, size)
        myaxi.dma_read(ram_c, offset, 1024 * 2, size)
        check(size, 0, offset)

        # wrap
        # stream
        offset = 0
        myaxi.dma_read(ram_a, offset, 0, size)
        myaxi.dma_read(ram_b, offset, 512, size)
        comp_stream_wrap(size, offset)
        myaxi.dma_write(ram_c, offset, 1024, size)

        # sequential
        offset = size
        myaxi.dma_read(ram_a, offset, 0, size)
        myaxi.dma_read(ram_b, offset, 512, size)
        comp_sequential_wrap(size, offset)
        myaxi.dma_write(ram_c, offset, 1024 * 2, size)

        # verification
        print('# WRAP')
        myaxi.dma_read(ram_c, 0, 1024, size)
        myaxi.dma_read(ram_c, offset, 1024 * 2, size)
        check(size, 0, offset)

        vthread.finish()

    th = vthread.Thread(m, 'th_comp', clk, rst, comp)
    # fsm = th.start(32)
    fsm = th.start(8)

    return m


def mkTest(memimg_name=None):
    m = Module('test')

    # target instance
    led = mkLed()

    # copy paras and ports
    params = m.copy_params(led)
    ports = m.copy_sim_ports(led)

    clk = ports['CLK']
    rst = ports['RST']

    memory = axi.AxiMemoryModel(m, 'memory', clk, rst, memimg_name=memimg_name)
    memory.connect(ports, 'myaxi')

    uut = m.Instance(led, 'uut',
                     params=m.connect_params(led),
                     ports=m.connect_ports(led))

    # simulation.setup_waveform(m, uut)
    simulation.setup_clock(m, clk, hperiod=5)
    init = simulation.setup_reset(m, rst, m.make_reset(), period=100)

    init.add(
        Delay(1000000),
        Systask('finish'),
    )

    return m


def run(filename='tmp.v', simtype='iverilog', outputfile=None):

    if outputfile is None:
        outputfile = os.path.splitext(os.path.basename(__file__))[0] + '.out'

    memimg_name = 'memimg_' + outputfile

    test = mkTest(memimg_name=memimg_name)

    if filename is not None:
        test.to_verilog(filename)

    sim = simulation.Simulator(test, sim=simtype)
    rslt = sim.run(outputfile=outputfile)
    lines = rslt.splitlines()
    if simtype == 'verilator' and lines[-1].startswith('-'):
        rslt = '\n'.join(lines[:-1])
    return rslt


if __name__ == '__main__':
    rslt = run(filename='tmp.v')
    print(rslt)
