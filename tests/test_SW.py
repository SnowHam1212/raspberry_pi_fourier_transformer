import RPi.GPIO as GPIO
import time

SW = 23

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(SW, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("push the switch")
print("If you push it, 'PUSHED' is displayed.")
try:
    prev = 1
    while True:
        now = GPIO.input(SW)
        if now == 0 and prev == 1:
            print("PUSHED!!")
        prev = now
        time.sleep(0.02)
except KyboardInterrupt:
    print("TEST COMPLETED!")
finally:
    GPIO.cleanup() 
