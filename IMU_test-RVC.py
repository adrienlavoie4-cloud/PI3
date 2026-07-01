import time
import serial
from adafruit_bno08x_rvc import BNO08x_RVC

uart = serial.Serial("/dev/serial0", 115200)
rvc = BNO08x_RVC(uart)

while True:
    print("Reading rvc")
    roll, pitch, yaw, x_accel, y_accel, z_accel = rvc.heading
    print("Roll: %2.2f Pitch: %2.2f Yaw: %2.2f Degrees" % (roll, pitch, yaw))
    print("Acceleration X: %2.2f Y: %2.2f Z: %2.2f m/s^2" % (x_accel, y_accel, z_accel))
    print("")
    time.sleep(0.1)
