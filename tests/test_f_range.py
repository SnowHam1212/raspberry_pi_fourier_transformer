import spidev
import time

spi = spidev.SpiDev()
spi.open(0,0)
spi.max_speed_hz = 1350000

def read_adc(ch):
    r = spi.xfer2([1, (8 + ch) << 4, 0])
    return ((r[1] & 3) << 8) + r[2]

print("Display the output of CH0")
print("Make noise please")

try:
    while True:
        vals = []
        t0 = time.time()
        while time.time() - t0 < 1.0:
            vals.append(read_adc(0))
        lo, hi = min(vals), max(vals)
        print(f"min:{lo:4d}, max:{hi:4d}, range={hi-lo:4d}, number of sample:{len(vals)}")

except KeyboardInterrupt:
    print("TEST COMPLETE!!")
finally:
    spi.close()
