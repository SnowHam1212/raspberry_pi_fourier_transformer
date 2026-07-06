"""
Laptop-only stand-in for main_sound_fft.py.

Fakes the mic (spidev ADC) and the LED/switch (RPi.GPIO) so the FFT logic
and pygame display can be exercised without a Raspberry Pi. Not used on
the Pi itself -- run main_sound_fft.py there.

Controls: SPACE = press the (fake) switch, UP/DOWN = change the fake tone's pitch.
"""
import math
import threading
import time

import numpy as np
import pygame

LED_PIN = 17
SW_PIN = 23

N = 2048
LOW_CUT_FREQ = 80
STRENGTH_THRESHOLD = 0
LONG_PRESS_SEC = 0.5
MAX_DRAW_HZ = 2500
N_AXIS_TICKS = 6
FAKE_SAMPLE_RATE = 8000.0  # virtual mic sample rate used for the fake tone

# FREQ_BANDS: (min, max, blink_freq)
FREQ_BANDS = [
    (0, 300, 2.0),
    (300, 1000, 5.0),
    (1000, 1000000, 10.0)
]

# -------- shared state --------
class Shared:
    def __init__(self):
        self.lock = threading.Lock()
        self.spectrum = np.zeros(N // 2 + 1)
        self.freqs = np.zeros(N // 2 + 1)
        self.peak = 0.0
        self.strength = 0.0
        self.blink_hz = 0.0
        self.running = True
        self.capturing = False
        self.led_on = False
        self.fake_freq = 440.0
        self.fake_switch = False

shared = Shared()

# ----- fake hardware -----
class DummyGPIO:
    BCM = OUT = IN = PUD_UP = 0
    LOW = 0
    HIGH = 1

    def setmode(self, *a): pass
    def setwarnings(self, *a): pass
    def setup(self, *a, **k): pass

    def output(self, pin, value):
        if pin == LED_PIN:
            with shared.lock:
                shared.led_on = (value == self.HIGH)

    def input(self, pin):
        if pin == SW_PIN:
            with shared.lock:
                pressed = shared.fake_switch
            return self.LOW if pressed else self.HIGH
        return self.HIGH

    def cleanup(self): pass

class DummySpiDev:
    def __init__(self):
        self._n = 0

    def open(self, *a, **k): pass

    def xfer2(self, data):
        # Uses a virtual sample counter (not the wall clock) so the fake tone's
        # frequency stays exact no matter how fast/slow this loop actually runs.
        with shared.lock:
            freq = shared.fake_freq
        t = self._n / FAKE_SAMPLE_RATE
        self._n += 1
        val = math.sin(2 * math.pi * freq * t)
        val += 0.02 * (np.random.rand() - 0.5)  # a little noise
        raw = int((val * 0.5 + 0.5) * 1023)
        raw = max(0, min(1023, raw))
        return [0, (raw >> 8) & 0x3, raw & 0xFF]

    def close(self): pass

GPIO = DummyGPIO()
spi = DummySpiDev()

def read_adc(ch):
    r = spi.xfer2([1, (8 + ch) << 4, 0])
    return ((r[1] & 3) << 8) + r[2]

def band_blink_hz(peak):
    for lo, hi, hz in FREQ_BANDS:
        if lo <= peak < hi:
            return hz
    return 0.0

# ------ audio thread ------
def audio_worker():
    window = np.hanning(N)
    buf = np.empty(N, dtype=np.float32)
    while shared.running:
        if not shared.capturing:
            time.sleep(0.01)
            continue

        for i in range(N):
            buf[i] = read_adc(0)
        rate = FAKE_SAMPLE_RATE  # the fake tone runs on a fixed virtual clock

        b = buf - np.mean(buf)  # remove DC offset
        b = b * window  # window function
        mag = np.abs(np.fft.rfft(b))
        freqs = np.fft.rfftfreq(N, d=1.0 / rate)
        mag[freqs < LOW_CUT_FREQ] = 0

        peak = float(freqs[np.argmax(mag)])
        strength = float(np.max(mag))

        if strength < STRENGTH_THRESHOLD:
            peak = 0.0
            blink = 0.0
        else:
            blink = band_blink_hz(peak)

        with shared.lock:
            shared.spectrum = mag
            shared.freqs = freqs
            shared.peak = peak
            shared.strength = strength
            shared.blink_hz = blink

# ----- LED thread ------
def led_worker():
    while shared.running:
        with shared.lock:
            hz = shared.blink_hz
        if hz <= 0:
            GPIO.output(LED_PIN, GPIO.LOW)
            time.sleep(0.05)
            continue
        half = 0.5 / hz
        GPIO.output(LED_PIN, GPIO.HIGH)
        time.sleep(half)
        GPIO.output(LED_PIN, GPIO.LOW)
        time.sleep(half)

# ----- switch thread ------
def switch_worker_continuous():
    while shared.running:
        pressed = GPIO.input(SW_PIN) == GPIO.LOW
        if pressed:
            shared.capturing = True
            while GPIO.input(SW_PIN) == GPIO.LOW and shared.running:
                time.sleep(0.01)
            shared.capturing = False

        time.sleep(0.01)

# ----- pygame display (main thread) ------
def run_display():
    pygame.init()
    W, H = 800, 400
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Sound FFT [laptop test mode]")
    font = pygame.font.SysFont("monospace", 20)
    clock = pygame.time.Clock()

    while shared.running:
        try:
            events = pygame.event.get()
        except pygame.error:
            break

        for event in events:
            if event.type == pygame.QUIT:
                shared.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    shared.running = False
                elif event.key == pygame.K_SPACE:
                    with shared.lock:
                        shared.fake_switch = True
                elif event.key == pygame.K_UP:
                    with shared.lock:
                        shared.fake_freq = min(shared.fake_freq + 50, MAX_DRAW_HZ)
                elif event.key == pygame.K_DOWN:
                    with shared.lock:
                        shared.fake_freq = max(shared.fake_freq - 50, LOW_CUT_FREQ)
            elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
                with shared.lock:
                    shared.fake_switch = False

        screen.fill((15, 15, 20))

        with shared.lock:
            mag = shared.spectrum.copy()
            freqs = shared.freqs.copy()
            peak = shared.peak
            strength = shared.strength
            capturing = shared.capturing
            led_on = shared.led_on
            fake_freq = shared.fake_freq

        if len(freqs) > 1 and np.max(mag) > 0:
            mask = freqs <= MAX_DRAW_HZ
            msel = mag[mask]
            if len(msel) > 0:
                norm = msel / (np.max(msel) + 1e-9)
                bar_w = W / len(msel)
                for i, v in enumerate(norm):
                    h = int(v * (H - 120))
                    x = int(i * bar_w)
                    pygame.draw.rect(screen, (80, 100, 255),
                                     (x, H - 60 - h, max(1, int(bar_w)), h))

        # x-axis (Hz) ticks, evenly spaced from 0 to MAX_DRAW_HZ
        axis_y = H - 60
        for k in range(N_AXIS_TICKS + 1):
            tick_hz = MAX_DRAW_HZ * k / N_AXIS_TICKS
            tx = int(tick_hz / MAX_DRAW_HZ * W)
            pygame.draw.line(screen, (90, 90, 100), (tx, axis_y), (tx, axis_y + 5))
            label = font.render(f"{int(tick_hz)}Hz", True, (150, 150, 160))
            lx = min(max(tx - label.get_width() // 2, 0), W - label.get_width())
            screen.blit(label, (lx, axis_y + 8))

        peak_txt = f"peak: {peak:6.1f} Hz" if peak > 0 else "peak:    --- Hz"
        screen.blit(font.render(peak_txt, True, (255, 255, 255)), (20, 20))
        screen.blit(font.render(f"strength: {strength:9.0f}", True, (200, 200, 200)), (20, 48))
        state = "CAPTURING" if capturing else "idle (press SPACE)"
        screen.blit(font.render(state, True, (255, 220, 120)), (20, 76))

        led_color = (255, 60, 60) if led_on else (60, 20, 20)
        pygame.draw.circle(screen, led_color, (W - 40, 30), 12)

        hint = f"fake tone: {fake_freq:.0f} Hz  (UP/DOWN = change pitch, SPACE = switch)"
        screen.blit(font.render(hint, True, (120, 200, 120)), (20, H - 30))

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

# ------ main ------
def main():
    threads = [
        threading.Thread(target=audio_worker, daemon=True),
        threading.Thread(target=led_worker, daemon=True),
        threading.Thread(target=switch_worker_continuous, daemon=True)
    ]

    for t in threads:
        t.start()

    try:
        run_display()
    finally:
        shared.running = False
        time.sleep(0.2)
        print("clean shutdown")

if __name__ == "__main__":
    main()
