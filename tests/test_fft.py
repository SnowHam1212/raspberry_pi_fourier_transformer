import spidev
import numpy as np
import time

spi = spidev.SpiDev()
spi.open(0,0)
spi.max_speed_hz = 1350000

def read_adc(ch):
    r = spi.xfer2([1, (8+ch)<<4, 0])
    return ((r[1]&3)<<8) + r[2]

#collect a block of samples, then run FFT
N = 2048
MEASURED_RATE = 39271

print("Speak or make sounds. Shows peak frequency. (Ctrl+C to stop)")
try:
    while True:
        buf = np.empty(N, dtype=np.float32)
        t0 = time.time()
        for i in range(N):
            buf[i] = read_adc(0)
        actual_rate = N / (time.time() - t0)
        
        buf -= np.mean(buf)
        buf *= np.hanning(len(buf))
        mag = np.abs(np.fft.rfft(buf))
        freqs = np.fft.rfftfreq(N, d=1.0/actual_rate)
        
        mag[:3] = 0
        peak = freqs[np.argmax(mag)]
        strength = np.max(mag)
        bar = "#"*int(strength / 10)
        
        print(f"peak = {peak:8.0f}  strength:{bar}")
        
except KeyboardInterrupt:
    print("stopped")

finally:
    spi.close()