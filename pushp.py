from machine import Pin
import time

button_pins = { 
    "btn1": 23,
    "btn2": 22,
    "btn3": 19
}

# Create button objects with pull-down resistors
buttons = {name: Pin(pin, Pin.IN) for name, pin in button_pins.items()}  # Use PULL_DOWN instead of PULL_UP

def read_buttons():
    """Read button states and return as a dictionary"""
    return {name: button.value() for name, button in buttons.items()} 

while True:
    button_states = read_buttons()
    print(button_states)  # Dictionary to transmit via LoRa
    time.sleep(0.2)

# 
# from machine import Pin
# import time
# 
# btn1 = Pin(23, Pin.IN)  # Change pin if needed
# 
# while True:
#     print(f"BTN1: {btn1.value()}")
#     time.sleep(0.2)