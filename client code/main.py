# main.py -- Unified remote unit application
# - Buttons on pins 34 (CLU), 22 (CLD), 17 (CT)
# - Encoders (clk, dt) pairs: (32,33), (14,27), (13,12), (25,26)
# - LoRa on SPIConfig.esp32_2, CS=5, INT=4, RST=16, freq=433, tx_power=14

from machine import Pin
from time import sleep_ms, ticks_ms
import network
import espnow


# ---------- Button class ----------
class ButtonInput:
    def __init__(self, pin_no, pull=None, debounce_ms=20, name=None):
        if pull == "UP":
            self.pin = Pin(pin_no, Pin.IN, Pin.PULL_UP)
        elif pull == "DOWN":
            self.pin = Pin(pin_no, Pin.IN, Pin.PULL_DOWN)
        else:
            self.pin = Pin(pin_no, Pin.IN)
        self.debounce_ms = debounce_ms
        self.name = name or str(pin_no)
        self._last_state = self.pin.value()
        self._last_time = ticks_ms()

    def read(self):
        """Read with debounce. Returns (changed: bool, state:int)."""
        now = ticks_ms()
        raw = self.pin.value()
        if raw != self._last_state:
            # start debounce timer
            if now - self._last_time >= self.debounce_ms:
                # consider changed
                self._last_state = raw
                self._last_time = now
                return True, raw
            else:
                # within debounce window, ignore
                return False, self._last_state
        else:
            self._last_time = now
            return False, self._last_state

    def state(self):
        return self._last_state


class ESPNowSender:
    def __init__(self, receiverAddress: str):
        self.receiverAddress = receiverAddress
        self.sta = network.WLAN(network.STA_IF)
        self.sta.active(True)
        self.sta.config(channel=1)
        self.sta.disconnect()

        self.espnowSender = espnow.ESPNow()
        try:
            self.espnowSender.active(True)
        except OSError as err:
            print("Failed to Initialize ESP-NOW", err)
            raise

        try:
            self.espnowSender.add_peer(self.receiverAddress)
        except OSError as err:
            print("Failed to add peer", err)
            raise

    def send(self, msg: str):
        try:
            if self.espnowSender.send(
                self.receiverAddress, msg, False
            ):
                print("ESPNow sent:", msg)
            else:
                print("Failed to send message (send returned false)")
        except OSError as err:
            print(f"Failed to send message (OSError: {err})")


# ---------- Application ----------
class RemoteUnitApp:
    POLL_MS = 4  # main polling period; small and efficient

    def __init__(self):
        # Buttons: specify pull type if your hardware has pull-ups/downs.
        # The original code said external pull-downs; if using external pull-downs,
        # don't set Pin.PULL_UP here. Adjust 'pull' argument accordingly.
        # I'll assume pull-ups are safe for ESP32 internal; change if needed.
        self.buttons = {
            "CLU": ButtonInput(
                34, pull=None, debounce_ms=30, name="CLU"
            ),  # external pull-down originally
            "CLD": ButtonInput(
                22, pull=None, debounce_ms=30, name="CLD"
            ),
            "CT": ButtonInput(
                17, pull=None, debounce_ms=30, name="CT"
            ),
        }

        # ESPNow Sender
        self.espnowSender = ESPNowSender(b"\x30\xae\xa4\xf6\x7d\x4c")

        # track last sent button states to avoid repeated sends
        self._last_button_states = {
            k: btn.state() for k, btn in self.buttons.items()
        }

        # batch/queue options could be added here for advanced throttling

    def run(self):
        print("RemoteUnitApp starting. Press Ctrl-C to stop.")
        try:
            while True:
                self._poll_buttons()
                sleep_ms(self.POLL_MS)
        except KeyboardInterrupt:
            print("Stopped by user.")
        except Exception as e:
            print("Runtime exception:", e)

    def _poll_buttons(self):
        changed_any = False
        parts = []
        for name, btn in self.buttons.items():
            changed, state = btn.read()
            if changed:
                # only send when actual change
                changed_any = True
                self._last_button_states[name] = state
            # Build message part for current state (we'll only send if something changed)
            parts.append(f"{name}={state}")
        if changed_any:
            # Send a short message with all button states
            msg = "BTN:" + ",".join(
                parts
            )  # e.g. "BTN:CLU=1,CLD=0,CT=1"
            # self.lora.send(msg)
            self.espnowSender.send(msg)


# ---------- Run ----------

if __name__ == "__main__":
    app = RemoteUnitApp()
    app.run()
