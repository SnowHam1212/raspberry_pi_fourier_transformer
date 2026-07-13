import spidev
import numpy as np
import pygame
import RPi.GPIO as GPIO
import threading
import time
from collections import deque

LED_PIN = 17
SW_PIN = 23
SPEAKER_PIN = 18
SPEAKER_DUTY = 50  # % duty cycle for the tone square wave
DOUBLE_PRESS_WINDOW = 0.4  # max seconds between two presses of a multi-press
MAX_PRESS_COUNT = 4        # presses beyond this are treated as a 4-press (top-4 loop)
PEAK_TONE_SEC = 1.0        # how long the double-press peak tone plays
TOPN_TONE_SEC = 0.3        # how long each top-N tone plays before moving to the next
TOPN_SUPPRESS_HZ = 100     # min spacing between the top-N peaks so they aren't the same spectral bump
DISPLAY_PEAK_COUNT = 4     # number of ranked peak frequencies shown on screen

N = 2048
LOW_CUT_FREQ = 80
HIGH_CUT_FREQ = 2000  # above typical voice fundamentals; cuts out electrical/ADC noise peaks
STRENGTH_THRESHOLD = 0
LONG_PRESS_SEC = 0.5
MAX_DRAW_HZ = 2500
N_AXIS_TICKS = 6

NUM_AVERAGES = 4         # spectra averaged per block to cancel out random noise
NOISE_FLOOR_RATIO = 0.3  # bins below this fraction of the block's max are zeroed
SMOOTH_KERNEL = 3        # moving-average width for smoothing the spectrum shape
PEAK_HISTORY = 5         # peak values kept for median smoothing over time
CALIBRATION_BLOCKS = 3   # blocks captured at startup to build the noise profile

WINDOW = np.hanning(N)

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
        self.peak_history = deque(maxlen=PEAK_HISTORY)
        self.noise_profile = None

shared = Shared()

# ----- hardware setup -----
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.setup(SW_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SPEAKER_PIN, GPIO.OUT)
speaker_pwm = GPIO.PWM(SPEAKER_PIN, 440)

def read_adc(ch):
    r = spi.xfer2([1, (8 + ch) << 4, 0])
    return ((r[1] & 3) << 8) + r[2]

def band_blink_hz(peak):
    for lo, hi, hz in FREQ_BANDS:
        if lo <= peak < hi:
            return hz
    return 0.0

# ------ noise-reduction helpers ------
def read_block(n=N):
    """Read n ADC samples back-to-back and derive the effective sample rate."""
    buf = np.empty(n, dtype=np.float32)
    t0 = time.time()
    for i in range(n):
        buf[i] = read_adc(0)
    rate = n / (time.time() - t0)
    return buf, rate

def compute_spectrum(buf, window=WINDOW):
    """DC removal + window + FFT magnitude for a single block."""
    b = buf - np.mean(buf)
    b = b * window
    return np.abs(np.fft.rfft(b))

def average_spectra(num=NUM_AVERAGES):
    """Capture several blocks and average their spectra; random noise cancels out."""
    spectra = []
    rate = None
    for _ in range(num):
        buf, rate = read_block(N)
        spectra.append(compute_spectrum(buf))
    return np.mean(spectra, axis=0), rate

def subtract_noise_profile(mag, profile):
    """Remove a previously measured steady-state noise spectrum."""
    if profile is None:
        return mag
    out = mag - profile
    out[out < 0] = 0
    return out

def apply_band_limit(mag, freqs, low=LOW_CUT_FREQ, high=HIGH_CUT_FREQ):
    """Zero out everything outside the voice band."""
    mag = mag.copy()
    mag[freqs < low] = 0
    mag[freqs > high] = 0
    return mag

def apply_noise_floor(mag, ratio=NOISE_FLOOR_RATIO):
    """Zero out bins weaker than a fraction of the block's own peak."""
    peak_val = np.max(mag)
    if peak_val <= 0:
        return mag
    mag = mag.copy()
    mag[mag < peak_val * ratio] = 0
    return mag

def smooth_spectrum(mag, kernel_size=SMOOTH_KERNEL):
    """Moving-average smoothing across neighboring frequency bins."""
    if kernel_size <= 1:
        return mag
    kernel = np.ones(kernel_size) / kernel_size
    return np.convolve(mag, kernel, mode="same")

def calibrate_noise_profile(blocks=CALIBRATION_BLOCKS):
    """Measure the ambient/electrical noise spectrum while nothing is being said."""
    print(f"calibrating noise profile ({blocks} blocks, stay quiet)...")
    spectra = []
    for _ in range(blocks):
        buf, _ = read_block(N)
        spectra.append(compute_spectrum(buf))
    profile = np.mean(spectra, axis=0)
    print("noise profile captured")
    return profile

# ------ audio thread ------
def audio_worker():
    while shared.running:
        if not shared.capturing:
            time.sleep(0.01)
            continue

        mag, rate = average_spectra()
        freqs = np.fft.rfftfreq(N, d=1.0 / rate)

        with shared.lock:
            noise_profile = shared.noise_profile

        mag = subtract_noise_profile(mag, noise_profile)
        mag = apply_band_limit(mag, freqs)
        mag = apply_noise_floor(mag)
        mag = smooth_spectrum(mag)

        peak = float(freqs[np.argmax(mag)])
        strength = float(np.max(mag))

        if strength < STRENGTH_THRESHOLD:
            peak = 0.0

        with shared.lock:
            shared.peak_history.append(peak)
            smoothed_peak = float(np.median(shared.peak_history)) if peak > 0 else 0.0
            shared.spectrum = mag
            shared.freqs = freqs
            shared.peak = smoothed_peak
            shared.strength = strength
            shared.blink_hz = band_blink_hz(smoothed_peak) if smoothed_peak > 0 else 0.0

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

# ----- speaker helpers -----
def play_peak_tone(duration=PEAK_TONE_SEC):
    """Play the last detected peak frequency as a tone on GPIO18."""
    with shared.lock:
        hz = shared.peak
    if hz <= 0:
        return
    speaker_pwm.start(SPEAKER_DUTY)
    speaker_pwm.ChangeFrequency(hz)
    time.sleep(duration)
    speaker_pwm.stop()

def top_n_peaks(mag, freqs, n, suppress_hz=TOPN_SUPPRESS_HZ):
    """Return up to n distinct peak frequencies, strongest first, at least
    suppress_hz apart so they aren't just neighboring bins of the same bump."""
    mag = mag.copy()
    freq_res = freqs[1] - freqs[0] if len(freqs) > 1 else 1.0
    suppress_bins = max(1, int(suppress_hz / freq_res))
    peaks = []
    for _ in range(n):
        if np.max(mag) <= 0:
            break
        idx = int(np.argmax(mag))
        peaks.append(float(freqs[idx]))
        lo = max(0, idx - suppress_bins)
        hi = min(len(mag), idx + suppress_bins + 1)
        mag[lo:hi] = 0
    return peaks

def play_topn_loop(n):
    """Loop the top n peak frequencies (TOPN_TONE_SEC each) until the switch
    is pressed again."""
    with shared.lock:
        mag = shared.spectrum.copy()
        freqs = shared.freqs.copy()
    peaks = top_n_peaks(mag, freqs, n)
    if not peaks:
        return
    while shared.running:
        for hz in peaks:
            speaker_pwm.start(SPEAKER_DUTY)
            speaker_pwm.ChangeFrequency(hz)
            stopped = sleep_or_stop(TOPN_TONE_SEC)
            speaker_pwm.stop()
            if stopped:
                wait_for_release()
                return

# ----- switch thread ------
def wait_for_release():
    while GPIO.input(SW_PIN) == GPIO.LOW and shared.running:
        time.sleep(0.01)

def wait_for_press(timeout):
    """Wait up to `timeout` seconds for the switch to go LOW; return whether it did."""
    t0 = time.time()
    while shared.running and time.time() - t0 < timeout:
        if GPIO.input(SW_PIN) == GPIO.LOW:
            return True
        time.sleep(0.01)
    return False

def sleep_or_stop(duration):
    """Sleep in small steps, returning True early if the switch is pressed."""
    t0 = time.time()
    while shared.running and time.time() - t0 < duration:
        if GPIO.input(SW_PIN) == GPIO.LOW:
            return True
        time.sleep(0.01)
    return False

def count_presses(max_count=MAX_PRESS_COUNT, window=DOUBLE_PRESS_WINDOW):
    """Count quick repeated presses (the first press+release already consumed),
    capped at max_count."""
    count = 1
    while count < max_count and wait_for_press(window):
        wait_for_release()
        count += 1
    return count

def switch_worker_continuous():
    """1 press toggles FFT capture on/off (or stops an active top-N loop);
    2 presses play the last peak once; 3+ presses loop the top-N peaks
    (0.3s each, N = press count) until a single press stops it."""
    while shared.running:
        if GPIO.input(SW_PIN) == GPIO.LOW:
            wait_for_release()
            count = count_presses()
            if count == 1:
                shared.capturing = not shared.capturing
            elif count == 2:
                play_peak_tone()
            else:
                play_topn_loop(count)

        time.sleep(0.01)

# ----- pygame display (main thread) ------
def run_display():
    pygame.init()
    W, H = 1280, 720
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Sound FFT")
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
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                shared.running = False

        screen.fill((15, 15, 20))

        with shared.lock:
            mag = shared.spectrum.copy()
            freqs = shared.freqs.copy()
            peak = shared.peak
            strength = shared.strength
            capturing = shared.capturing

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
        state = "CAPTURING" if capturing else "idle (press switch)"
        screen.blit(font.render(state, True, (255, 220, 120)), (20, 76))

        ranked_peaks = top_n_peaks(mag, freqs, DISPLAY_PEAK_COUNT)
        for i in range(DISPLAY_PEAK_COUNT):
            hz_txt = f"{ranked_peaks[i]:6.1f} Hz" if i < len(ranked_peaks) else "   --- Hz"
            line = font.render(f"#{i + 1} peak: {hz_txt}", True, (180, 220, 200))
            screen.blit(line, (20, 104 + i * 26))

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

# ------ main ------
def main():
    shared.noise_profile = calibrate_noise_profile()

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
        GPIO.output(LED_PIN, GPIO.LOW)
        speaker_pwm.stop()
        GPIO.cleanup()
        spi.close()
        print("clean shutdown")

if __name__ == "__main__":
    main()
