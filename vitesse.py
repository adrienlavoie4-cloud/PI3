import time
import RPi.GPIO as GPIO

# --- Configuration ---
WheelDiameter = 700  # mm
WheelCircumference = WheelDiameter * 3.141592654  # mm

dynamicMovingAverageMaxCount = 8  # number of pulses in the moving average window
WheelSensorGPIO = 4

# --- State variables ---
dynamicMovingAverage = [0] * (dynamicMovingAverageMaxCount + 1)
dynamicMovingAverageCount = 0
sensorTimer = 0

speedValue = 0.0
odometerValue = 0.0  # km


def gotPulse(channel):
    global dynamicMovingAverageCount, sensorTimer, speedValue, odometerValue

    sensorTimer = 20  # reset "still moving" watchdog (~2 seconds at 100ms ticks)

    ctime = time.time()
    dynamicMovingAverage[dynamicMovingAverageMaxCount] = ctime

    # time elapsed since the pulse 'dynamicMovingAverageCount' ago
    deltaTime = ctime - dynamicMovingAverage[dynamicMovingAverageMaxCount - dynamicMovingAverageCount]

    # shift the array left (drop oldest timestamp)
    for i in range(dynamicMovingAverageMaxCount):
        dynamicMovingAverage[i] = dynamicMovingAverage[i + 1]

    if deltaTime == 0.0:
        speed = 0.0
    else:
        speed = dynamicMovingAverageCount * WheelCircumference / deltaTime  # mm/s

    dynamicMovingAverageCount += 1
    if dynamicMovingAverageCount > dynamicMovingAverageMaxCount:
        dynamicMovingAverageCount = dynamicMovingAverageMaxCount

    # convert mm/s -> km/h
    speedValue = speed * 3600.0 / 1000000.0

    # one pulse = one wheel revolution
    odometerValue += WheelCircumference / 1000000.0  # km

    print("Speed: {:.2f} km/h | Odometer: {:.3f} km".format(speedValue, odometerValue))


def watchdog():
    """Call this periodically (e.g. every 100ms) to zero the speed if no pulses arrive."""
    global sensorTimer, speedValue
    if sensorTimer > 0:
        sensorTimer -= 1
    else:
        if speedValue != 0.0:
            speedValue = 0.0
            print("Stopped. Speed: 0.0 km/h")


# --- GPIO setup ---
GPIO.setmode(GPIO.BCM)
GPIO.setup(WheelSensorGPIO, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(WheelSensorGPIO, GPIO.FALLING, callback=gotPulse, bouncetime=100)

# --- Main loop ---
try:
    while True:
        watchdog()
        time.sleep(0.1)  # 100ms tick, matches original update_clock() rate
except KeyboardInterrupt:
    GPIO.cleanup()

