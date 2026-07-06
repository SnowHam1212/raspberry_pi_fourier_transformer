import RPi.GPIO as GPIO
import time

LED = 17

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(LED, GPIO.OUT)

print("LED wo 5 kai tennmetu")
try:
    for i in range(5):
        GPIO.output(LED, GPIO.HIGH)
        print(f"{i+1}times: flashed")
        time.sleep(0.5)
        GPIO.output(LED, GPIO.LOW)
        time.sleep(0.5)
    print("TEST COMPLETE")
finally:
    GPIO.cleanup()