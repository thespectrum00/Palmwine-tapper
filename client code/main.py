# main.py -- Unified remote unit application
# - Buttons on pins 34 (CLU), 22 (CLD), 17 (CT)
# - Encoders (clk, dt) pairs: (32,33), (14,27), (13,12), (25,26)
# - LoRa on SPIConfig.esp32_2, CS=5, INT=4, RST=16, freq=433, tx_power=14

from machine import Pin
from time import sleep_ms, ticks_ms
import time
import ulora    # your provided LoRa module

# ---------- Button class ----------
class ButtonInput:
    def __init__(self, pin_no, pull=None, debounce_ms=20, name=None):
        if pull == 'UP':
            self.pin = Pin(pin_no, Pin.IN, Pin.PULL_UP)
        elif pull == 'DOWN':
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

# ---------- Rotary encoder class (polled, efficient) ----------
class RotaryEncoder:
    def __init__(self, clk_pin, dt_pin, index, min_v=0, max_v=180, start=90):
        # Use internal pull-ups (typical for mechanical encoders)
        self.clk = Pin(clk_pin, Pin.IN, Pin.PULL_UP)
        self.dt = Pin(dt_pin, Pin.IN, Pin.PULL_UP)
        self.index = index
        self.counter = start
        self.min_v = min_v
        self.max_v = max_v
        self._last_clk = self.clk.value()
        self._last_sent = self.counter

    def read(self):
        """
        Poll-based encoder read. Returns (changed: bool, value:int)
        A small, fast poll every few ms is efficient on ESP32.
        """
        changed = False
        current_clk = self.clk.value()
        if current_clk != self._last_clk:
            # only react on rising edge (filter)
            if current_clk == 1:
                # determine direction via dt
                if self.dt.value() == 0:
                    self.counter += 1
                else:
                    self.counter -= 1

                # clamp
                if self.counter < self.min_v:
                    self.counter = self.min_v
                elif self.counter > self.max_v:
                    self.counter = self.max_v

                changed = True
        self._last_clk = current_clk
        return changed, self.counter

    def needs_send(self):
        return self.counter != self._last_sent

    def mark_sent(self):
        self._last_sent = self.counter

# ---------- LoRa client wrapper ----------
class LoRaClient:
    def __init__(self,
                 spi_channel=ulora.SPIConfig.esp32_2,
                 int_pin=4, cs_pin=5, reset_pin=16,
                 freq=433, tx_power=14,
                 client_addr=1, server_addr=2,
                 acks=True):
        self.client_addr = client_addr
        self.server_addr = server_addr

        # Initialize LoRa object from your ulora module
        self.lora = ulora.LoRa(spi_channel, int_pin, self.client_addr, cs_pin,
                               reset_pin=reset_pin, freq=freq, tx_power=tx_power,
                               acks=acks)
        
    
    def send(self, msg: str):
        """Send without caring about ACK."""
        try:
            # Send, ignore whether ACK was received
            self.lora.send(msg, self.server_addr)
            print("LoRa SENT:", msg)
            return True
        except Exception as e:
            print("LoRa send exception:", e)
            return False

    
# ---------- Application ----------
class RemoteUnitApp:
    POLL_MS = 4  # main polling period; small and efficient

    def __init__(self):
        # Buttons: specify pull type if your hardware has pull-ups/downs.
        # The original code said external pull-downs; if using external pull-downs,
        # don't set Pin.PULL_UP here. Adjust 'pull' argument accordingly.
        # I'll assume pull-ups are safe for ESP32 internal; change if needed.
        self.buttons = {
            'CLU': ButtonInput(34, pull=None, debounce_ms=30, name='CLU'),  # external pull-down originally
            'CLD': ButtonInput(22, pull=None, debounce_ms=30, name='CLD'),
            'CT' : ButtonInput(17, pull=None, debounce_ms=30, name='CT'),
        }

        # Encoders: order indexes 0..3. Use the pairs you gave.
        # I'll use logical ordering: 0:(32,33), 1:(14,27), 2:(13,12), 3:(25,26)
        self.encoders = [
            RotaryEncoder(32, 33, index=0),
            RotaryEncoder(14, 27, index=1),
            RotaryEncoder(13, 12, index=2),
            RotaryEncoder(25, 26, index=3),
        ]

        # LoRa client
        self.lora = LoRaClient(client_addr=1, server_addr=2, freq=433, tx_power=14)

        # track last sent button states to avoid repeated sends
        self._last_button_states = {k:btn.state() for k,btn in self.buttons.items()}

        # batch/queue options could be added here for advanced throttling

    def run(self):
        print("RemoteUnitApp starting. Press Ctrl-C to stop.")
        try:
            while True:
                self._poll_buttons()
                self._poll_encoders()
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
            msg = "BTN:" + ",".join(parts)  # e.g. "BTN:CLU=1,CLD=0,CT=1"
            self.lora.send(msg)

    def _poll_encoders(self):
        for enc in self.encoders:
            changed, value = enc.read()
            # Only send when changed AND different from last sent value
            if changed and enc.needs_send():
                # encode message compactly: E<index>:<value>
                msg = f"E{enc.index}:{value}"
                sent = self.lora.send(msg)
                if sent:
                    enc.mark_sent()
                # short gap to avoid tight tx bursts if many changes
                sleep_ms(6)

# ---------- Run ----------

if __name__ == "__main__":
    app = RemoteUnitApp()
    app.run()
