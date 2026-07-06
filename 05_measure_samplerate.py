import spidev
import time

spi = spidev.SpiDev()
spi.open(0,0)
spi.max_speed_hz = 1350000

def read_adc(ch):
    r = spi.xfer2([1, (8+ch)<<4, 0])
    return ((r[1]&3) << 8) + r[2]

N=5000
t0 = time.time()
for _ in range(N):
    read_adc(0)
elasped = time.time() - t0

rate = N / elasped
print(f"{N} reads took {elasped:.3f} sec")
print(f"sampling-rate ~= {rate:.0f}Hz")
print(f"max detectable freq ~= {rate/2:.0f} Hz (Nyquist)")