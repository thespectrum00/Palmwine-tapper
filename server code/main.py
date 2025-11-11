from driver_bts7960 import Bts7960
import network
import asyncio
import aioespnow

# =====================
# Motor Controllers
# =====================


class ClimbingMotor:
    """Controls the climbing motor via BTS7960 driver"""

    def __init__(self, rpwm, lpwm, ren, len_):
        self.motor = Bts7960(rpwm, lpwm, ren, len_)
        self.stop()  # ensure safe state at init

    def clockwise(self, speed=50):
        print("[Climbing] Clockwise", speed)
        self.motor.start(abs(int(speed)))

    def anticlockwise(self, speed=50):
        print("[Climbing] Anticlockwise", speed)
        self.motor.start(-abs(int(speed)))

    def stop(self):
        print("[Climbing] Stop")
        try:
            self.motor.stop()
        except Exception as e:
            print("[Climbing] stop() exception:", e)


class ESPNowReceiver:
    def __init__(self, climbing_motor):
        self.sta = network.WLAN(network.STA_IF)
        self.sta.active(True)
        self.sta.config(channel=1)
        self.sta.disconnect()

        self.espnowReceiver = aioespnow.ESPNow()
        try:
            self.espnowReceiver.active(True)
        except OSError as err:
            print("Failed to Initialize ESP-NOW", err)
            raise

        self.climbing_motor = climbing_motor

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

        except Exception as e:
            print("Button Parse Error:", e)

    async def receiveMessages(self):
        while True:
            try:
                async for mac, msg in self.espnowReceiver:
                    msg = msg.decode()
                    print(f"Received form {mac.hex()}: {msg}")
                    # BUTTON messages: "BTN:CLU=1,CLD=0,CT=1"
                    if msg.upper().startswith("BTN:"):
                        # Use the helper to parse and act
                        self.handle_button_message(msg[4:])

                    else:
                        print("[LoRa] Unknown message format:", msg)
            except OSError as err:
                print("Error: ", err)
                await asyncio.sleep(5)


# =====================
# Main
# =====================


async def main():
    climbing_motor = ClimbingMotor(13, 4, 33, 12)  # BTS7960 pins

    # Force safe state at startup (extra guarantee)
    try:
        climbing_motor.stop()
    except Exception:
        pass

    espnowReceiver = ESPNowReceiver(climbing_motor)
    await asyncio.gather(espnowReceiver.receiveMessages())

    print("[System] Server started, waiting for ESPNow messages...")
    await asyncio.sleep(0.2)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopping Receiver")
