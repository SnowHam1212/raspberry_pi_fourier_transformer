import RPi.GPIO

RPi.GPIO.setmode(RPi.GPIO.BCM)
RPi.GPIO.setup(18, RPi.GPIO.IN)
if RPi.GPIO.input(18) ==
RPi.GPIO.LOW:
    print("LOW")
else:
    print("HIGH")

RPi.GPIO.cleanup