import math
import time
import serial
from adafruit_bno08x.uart import BNO08X_UART
from adafruit_bno08x import (
    BNO_REPORT_ACCELEROMETER,
    BNO_REPORT_GYROSCOPE,
    BNO_REPORT_MAGNETOMETER,
    BNO_REPORT_ROTATION_VECTOR,
    BNO_REPORT_LINEAR_ACCELERATION,
    BNO_REPORT_GRAVITY,
    BNO_REPORT_GAME_ROTATION_VECTOR,
    BNO_REPORT_GEOMAGNETIC_ROTATION_VECTOR,
    BNO_REPORT_STEP_COUNTER,
)

UART_PORT = "/dev/serial0"  # use "/dev/ttyAMA0" if Bluetooth holds serial0
BAUD = 3000000
SAMPLE_INTERVAL_S = 0.5


def quat_to_euler_deg(i, j, k, real):
    """Convert BNO085 quaternion (I, J, K, Real) to yaw, pitch, roll in degrees."""
    sinr_cosp = 2 * (real * i + j * k)
    cosr_cosp = 1 - 2 * (i * i + j * j)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2 * (real * j - k * i)
    pitch = math.copysign(math.pi / 2, sinp) if abs(sinp) >= 1 else math.asin(sinp)

    siny_cosp = 2 * (real * k + i * j)
    cosy_cosp = 1 - 2 * (j * j + k * k)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return math.degrees(yaw), math.degrees(pitch), math.degrees(roll)


def print_xyz(label, x, y, z, unit):
    print(f"  {label:<10}  X:{x:8.2f}  Y:{y:8.2f}  Z:{z:8.2f}  {unit}")


def print_heading(label, yaw, pitch, roll):
    print(f"  {label:<10}  Yaw:{yaw:7.1f}°  Pitch:{pitch:7.1f}°  Roll:{roll:7.1f}°")


uart = serial.Serial(UART_PORT, baudrate=BAUD, timeout=1)

print("Attempting to connect to BNO085 over UART...")
try:
    bno = BNO08X_UART(uart)
    print("Success! Connected to BNO085.\n")

    features = [
        BNO_REPORT_ACCELEROMETER,
        BNO_REPORT_GYROSCOPE,
        BNO_REPORT_MAGNETOMETER,
        BNO_REPORT_ROTATION_VECTOR,
        BNO_REPORT_LINEAR_ACCELERATION,
        BNO_REPORT_GRAVITY,
        BNO_REPORT_GAME_ROTATION_VECTOR,
        BNO_REPORT_GEOMAGNETIC_ROTATION_VECTOR,
        BNO_REPORT_STEP_COUNTER,
    ]
    for feature in features:
        bno.enable_feature(feature)
    time.sleep(0.2)

    while True:
        time.sleep(SAMPLE_INTERVAL_S)

        accel = bno.acceleration
        gyro = bno.gyro
        mag = bno.magnetic
        quat = bno.quaternion
        game_quat = bno.game_quaternion
        linear = bno.linear_acceleration
        gravity = bno.gravity
        steps = bno.steps

        yaw, pitch, roll = quat_to_euler_deg(*quat)
        game_yaw, game_pitch, game_roll = quat_to_euler_deg(*game_quat)

        print("=" * 52)
        print(f"  BNO085  |  {time.strftime('%H:%M:%S')}")
        print("-" * 52)
        print("  Orientation")
        print_heading("Fused", yaw, pitch, roll)
        print_heading("Game", game_yaw, game_pitch, game_roll)
        print("-" * 52)
        print("  Motion")
        print_xyz("Accel", *accel, "m/s²")
        print_xyz("Gyro", *gyro, "rad/s")
        print_xyz("Magnetic", *mag, "µT")
        print("-" * 52)
        print("  Derived")
        print_xyz("Linear", *linear, "m/s²")
        print_xyz("Gravity", *gravity, "m/s²")
        print(f"  Steps: {steps}")
        print()

except KeyboardInterrupt:
    print("\nStopped.")
except Exception as e:
    print(f"\nConnection failed: {e}")
    print("Check your PS1 pin jumper (must be tied to VIN) and your TX/RX wiring.")
finally:
    uart.close()
