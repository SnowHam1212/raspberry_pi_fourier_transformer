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
        val = read_adc(0)
        bar = "#" * (val // 20)
        print(f"{val:4d} | {bar}")
        time.sleep(0.1)

except KeyboardInterrupt:
    print("TEST COMPLETE!!")
finally:
    spi.close()
