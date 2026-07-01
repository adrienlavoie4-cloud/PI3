import time
import serial
import board
import busio
from adafruit_bno08x.uart import BNO08X_UART
from adafruit_bno08x import BNO_REPORT_ACCELEROMETER, BNO_REPORT_GYROSCOPE

# 1. Initialize the serial port. 
# Change to '/dev/ttyAMA0' if you disabled Bluetooth.
uart = serial.Serial("/dev/serial0", baudrate=460800, timeout=1)


print("Attempting to connect to BNO085 over UART...")
try:
    # 2. Initialize the BNO085 sensor object over UART
    bno = BNO08X_UART(uart)
    print("Success! Connected to BNO085.")
    
    # 3. Enable the data streams you want to read
    bno.enable_feature(BNO_REPORT_ACCELEROMETER)
    bno.enable_feature(BNO_REPORT_GYROSCOPE)

    # 4. Loop and print data
    while True:
        time.sleep(0.5)
        print("--- Sensor Data ---")
        accel_x, accel_y, accel_z = bno.acceleration
        print(f"Acceleration: X: {accel_x:.2f}, Y: {accel_y:.2f}, Z: {accel_z:.2f} m/s^2")
        gyro_x, gyro_y, gyro_z = bno.gyro
        print(f"Gyroscope:    X: {gyro_x:.2f}, Y: {gyro_y:.2f}, Z: {gyro_z:.2f} rad/s")

except Exception as e:
    print(f"\nConnection failed: {e}")
    print("Check your PS1 pin jumper (must be tied to VIN) and your TX/RX wiring.")
