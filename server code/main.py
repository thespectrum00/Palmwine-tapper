from machine import Pin, PWM, SoftI2C
from time import sleep
from ulora import LoRa, SPIConfig
from driver_bts7960 import Bts7960
from new_motor import CustomMotorDriver
from servo import Servos
from dcmotor import DCMotor
import time

# =====================
# Motor Controllers
# =====================

class ClimbingMotor:
    """Controls the climbing motor via BTS7960 driver"""
    def __init__(self, clk_pin, anti_clk_pin):
        # self.motor = Bts7960(rpwm, lpwm, ren, len_)
        self.motor = CustomMotorDriver(clk_pin, anti_clk_pin)
        self.stop()   # ensure safe state at init

    def clockwise(self, speed=50):
        print("[Climbing] Clockwise")
        # self.motor.start(abs(int(speed)))
        self.motor.rotate_clockwise()

    def anticlockwise(self, speed=50):
        print("[Climbing] Anticlockwise")
        # self.motor.start(-abs(int(speed)))
        self.motor.rotate_anti_clockwise()

    def stop(self):
        print("[Climbing] Stop")
        try:
            self.motor.stop()
        except Exception as e:
            print("[Climbing] stop() exception:", e)


class CuttingMotor:
    """Controls the cutting motor via L298N driver"""
    def __init__(self, in1, in2, en_pin, freq=15000):
        self.pwm = PWM(Pin(en_pin), freq)
        # Ensure PWM starts at 0 duty
        try:
            # MicroPython PWM API differs across ports; attempt common methods
            self.pwm.duty(0)
        except Exception:
            try:
                self.pwm.duty_u16(0)
            except Exception:
                pass

        # Provide min/max duty inside DCMotor constructor (as you used)
        self.motor = DCMotor(Pin(in1, Pin.OUT), Pin(in2, Pin.OUT), self.pwm, 350, 1023)
        self.stop()  # ensure motor stopped at init

    def start(self, speed=100):
        print("[Cutting] Start", speed)
        # You previously found backwards() was needed due to wiring polarity
        self.motor.backwards(int(speed))

    def stop(self):
        print("[Cutting] Stop")
        try:
            self.motor.stop()
            # also explicitly set PWM duty to zero
            try:
                self.pwm.duty(0)
            except Exception:
                try:
                    self.pwm.duty_u16(0)
                except Exception:
                    pass
        except Exception as e:
            print("[Cutting] stop() exception:", e)


# =====================
# Servo Controller
# =====================

class ServoController:
    """Controls multiple servos via PCA9685"""
    def __init__(self, scl_pin=22, sda_pin=21, indices=[0, 1, 2, 3]):
        i2c = SoftI2C(scl=Pin(scl_pin), sda=Pin(sda_pin))
        self.servos = Servos(i2c, min_us=1280, max_us=2180)
        self.indices = indices
        self.previous_angles = {index: 90 for index in indices}

        # Start all servos at neutral (stop)
        for index in indices:
            try:
                self.servos.position(index=index, degrees=90)
            except Exception as e:
                print("[Servo] init position exception:", e)

    def rotate(self, index, new_value):
        """Rotate servo based on encoder change"""
        if index not in self.previous_angles:
            print(f"[Servo] Invalid index: {index}")
            return

        old_value = self.previous_angles[index]
        print(f"[Servo {index}] {old_value} -> {new_value}")

        if new_value > old_value:
            print("Clockwise")
            self.servos.position(index=index, degrees=120)
        elif new_value < old_value:
            print("Anticlockwise")
            self.servos.position(index=index, degrees=60)
        else:
            print("Stop")
            self.servos.position(index=index, degrees=90)
            return

        # Brief movement, then stop
        time.sleep(0.15)
        self.servos.position(index=index, degrees=90)

        # Update state
        self.previous_angles[index] = new_value

    def neutral_all(self):
        for i in self.indices:
            try:
                self.servos.position(index=i, degrees=90)
            except Exception as e:
                print("[Servo] neutral exception:", e)


# =====================
# LoRa Receiver
# =====================

class LoRaServer:
    """Receives LoRa messages and dispatches motor/servo actions"""
    def __init__(self, climbing_motor, cutting_motor):
        self.climbing_motor = climbing_motor
        self.cutting_motor = cutting_motor
        
        RFM95_RST = 32
        RFM95_SPIBUS = SPIConfig.esp32_2
        RFM95_CS = 5
        RFM95_INT = 14
        RF95_FREQ = 433
        RF95_POW = 14
        SERVER_ADDRESS = 2

        self.lora = LoRa(
            RFM95_SPIBUS, RFM95_INT, SERVER_ADDRESS, RFM95_CS,
            reset_pin=RFM95_RST, freq=RF95_FREQ, tx_power=RF95_POW, acks=False
        )

        # set the callback and start listening
        self.lora.on_recv = self.on_message
        self.lora.set_mode_rx()

    def on_message(self, payload):
        try:
            msg = payload.message.decode().strip()
            print(f"[LoRa] Received: {msg}")

            # BUTTON messages: "BTN:CLU=1,CLD=0,CT=1"
            if msg.upper().startswith("BTN:"):
                # Use the helper to parse and act
                self.handle_button_message(msg[4:])

            # Encoder messages: "E<index>:<value>" (like "E2:85")
            elif msg.startswith("E"):
                try:
                    epart, value_str = msg.split(":", 1)
                    # strip the 'E' and allow whitespace
                    index = int(epart[1:].strip())
                    value = int(value_str.strip())
                    #self.servo_controller.rotate(index, value)
                except Exception as e:
                    print("[LoRa] Bad encoder message:", msg, "err:", e)

            else:
                print("[LoRa] Unknown message format:", msg)

            # Re-arm RX to be safe (prevents radio getting stuck)
            try:
                self.lora.set_mode_rx()
            except Exception:
                pass

        except Exception as e:
            print("LoRa Receive Error:", e)

    def handle_button_message(self, msg):
        """Parse BTN messages and control motors"""
        try:
            parts = msg.split(",")
            data = {}
            for part in parts:
                if "=" in part:
                    key, value = part.split("=", 1)
                    key = key.strip().upper()
                    # guard against non-numeric garbage
                    try:
                        data[key] = int(value.strip())
                    except Exception:
                        data[key] = 0

            print("[BTN parsed] ", data)

            # Climbing motor logic
            clu = data.get("CLU", 0)
            cld = data.get("CLD", 0)

            if clu == 1 and cld != 1:
                self.climbing_motor.clockwise()
            elif cld == 1 and clu != 1:
                self.climbing_motor.anticlockwise()
            else:
                # either both 0 or both 1 -> stop to be safe
                self.climbing_motor.stop()

            # Cutting motor
            ct = data.get("CT", 0)
            if ct == 1:
                self.cutting_motor.start()
            else:
                self.cutting_motor.stop()

        except Exception as e:
            print("Button Parse Error:", e)


# =====================
# Main
# =====================

def main():
    climbing_motor = ClimbingMotor(25, 26)   # BTS7960 pins
    cutting_motor = CuttingMotor(26, 25, 27)        # L298N pins
    #servo_controller = ServoController()            # PCA9685 servos

    # Force safe state at startup (extra guarantee)
    try:
        climbing_motor.stop()
    except Exception:
        pass
    try:
        cutting_motor.stop()
    except Exception:
        pass
    
    server = LoRaServer(climbing_motor, cutting_motor)

    print("[System] Server started, waiting for LoRa messages...")

    # Keep alive loop: re-arm RX periodically to avoid SX127x losing RX mode
    while True:
        try:
            server.lora.set_mode_rx()
        except Exception:
            pass
        sleep(0.2)


if __name__ == "__main__":
    main()
