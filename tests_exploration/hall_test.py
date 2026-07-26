import time
import datetime
import RPi.GPIO as GPIO

sense_pin = 7
GPIO.setmode(GPIO.BOARD)
GPIO.setup(sense_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def detect(channel):
    if GPIO.input(sense_pin) == 1:
        print('Magnet detected (ON)')
    else:
        print('Magnet removed (OFF)')

GPIO.add_event_detect(sense_pin, GPIO.BOTH, callback=detect)

try:
    while True:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print('System Active check', now)
        time.sleep(30)

except KeyboardInterrupt:
    print('Interrupted by user')

finally:
    time.sleep(2)
    GPIO.remove_event_detect(sense_pin)
    GPIO.cleanup()
    print('Done')
