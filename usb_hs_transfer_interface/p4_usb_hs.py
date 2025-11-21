import serial
import numpy as np
import time

ARRAY_SIZE = 1024 * 1024  # 64KB
PORT = 'COM6'
BAUDRATE = 115200

def generate_test_data():
    return np.random.randint(-128, 127, ARRAY_SIZE, dtype=np.int8)

def compute_sum(data):
    return np.sum(data, dtype=np.int32)

def send_and_verify(port_name):
    data = generate_test_data()
    expected_sum = compute_sum(data)
    
    print(f"Generated {ARRAY_SIZE} bytes ({ARRAY_SIZE/1024:.1f} KB)")
    print(f"Expected sum: {expected_sum}")
    
    with serial.Serial(port_name, BAUDRATE, timeout=10) as ser:
        time.sleep(2)
        
        start_time = time.perf_counter()
        ser.write(data.tobytes())
        ser.flush()
        write_time = time.perf_counter() - start_time
        
        speed_mbps = (ARRAY_SIZE / write_time) / (1024 * 1024)
        
        print(f"Transfer time: {write_time*1000:.2f} ms")
        print(f"Transfer speed: {speed_mbps:.2f} MB/s")
        print(f"Efficiency: {(speed_mbps/60)*100:.1f}% of 480 Mbps")
        
        response = ser.readline().decode('utf-8').strip()
        
        if response:
            received_sum = int(response)
            print(f"Received sum: {received_sum}")
            
            if received_sum == expected_sum:
                print("✓ MATCH")
            else:
                print(f"✗ MISMATCH")

if __name__ == "__main__":
    send_and_verify(PORT)