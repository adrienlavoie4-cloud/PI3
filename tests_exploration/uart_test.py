import serial
import time

# Open the serial port
uart = serial.Serial("/dev/serial0", baudrate=115200, timeout=1)
print("Listening for raw UART-RVC data packets...")

try:
    while True:
        # UART-RVC packets always start with header bytes 0xAA 0xAA
        data = uart.read(1)
        if data == b'\xaa':
            next_byte = uart.read(1)
            if next_byte == b'\xaa':
                # Read the rest of the 19-byte packet
                packet = uart.read(17)
                print(f"Received active packet! Length: {len(packet)+2} bytes")
        time.sleep(0.01)
except KeyboardInterrupt:
    print("Stopped.")
