import RPi.GPIO as GPIO
import time

SPEAKER_PIN = 18
DUTY = 50  # %

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(SPEAKER_PIN, GPIO.OUT)

pwm = GPIO.PWM(SPEAKER_PIN, 440)

print("Sweeping 200Hz-2000Hz on the GPIO18 speaker. (Ctrl+C to stop)")
try:
    pwm.start(DUTY)
    for hz in range(200, 2001, 100):
        print(f"{hz} Hz")
        pwm.ChangeFrequency(hz)
        time.sleep(0.3)
except KeyboardInterrupt:
    print("stopped")
finally:
    pwm.stop()
    GPIO.cleanup()
