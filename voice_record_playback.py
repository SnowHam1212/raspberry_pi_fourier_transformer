import subprocess

import time

import numpy as np
import pygame
import spidev
import RPi.GPIO as GPIO

LED_PIN = 17
SW_PIN = 23

MAX_RECORD_SEC = 5     # safety cap so a stuck switch can't record forever
PLAYBACK_RATE = 44100  # pygame mixer output rate

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.setup(SW_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def read_adc(ch=0):
    r = spi.xfer2([1, (8 + ch) << 4, 0])
    return ((r[1] & 3) << 8) + r[2]

def record_while_pressed():
    samples = []
    t0 = time.time()
    GPIO.output(LED_PIN, GPIO.HIGH)
    print("recording... (release the switch to stop)")
    while GPIO.input(SW_PIN) == GPIO.LOW and (time.time() - t0) < MAX_RECORD_SEC:
        samples.append(read_adc(0))
    GPIO.output(LED_PIN, GPIO.LOW)
    elapsed = time.time() - t0
    rate = len(samples) / elapsed if elapsed > 0 else 1.0
    print(f"recorded {len(samples)} samples in {elapsed:.2f}s (~{rate:.0f} Hz)")
    return np.array(samples, dtype=np.float32), rate

def to_stereo_wave(raw, rate):
    """Center/normalize the raw 10-bit ADC samples and resample them to PLAYBACK_RATE."""
    centered = raw - np.mean(raw)
    peak = np.max(np.abs(centered))
    normalized = centered / peak if peak > 0 else centered

    n_out = max(2, int(len(normalized) * PLAYBACK_RATE / rate))
    x_old = np.linspace(0, 1, len(normalized))
    x_new = np.linspace(0, 1, n_out)
    resampled = np.interp(x_new, x_old, normalized)

    mono = (resampled * 32767 * 0.9).astype(np.int16)
    return np.column_stack([mono, mono])  # pygame mixer default is stereo

def main():
    pygame.mixer.init(frequency=PLAYBACK_RATE, size=-16, channels=2)
    print("Hold the switch and speak to record. Release it to play back. Ctrl+C to quit.")

    try:
        while True:
            if GPIO.input(SW_PIN) == GPIO.LOW:
                raw, rate = record_while_pressed()
                if len(raw) < 10:
                    print("too short, skipped")
                    continue

                wave = to_stereo_wave(raw, rate)
                sound = pygame.sndarray.make_sound(np.ascontiguousarray(wave))
                print("playing back...")
                sound.play()
                while pygame.mixer.get_busy():
                    time.sleep(0.05)

            time.sleep(0.01)
    except KeyboardInterrupt:
        print("stopped")
    finally:
        GPIO.output(LED_PIN, GPIO.LOW)
        GPIO.cleanup()
        spi.close()
        pygame.mixer.quit()

if __name__ == "__main__":
    main()
