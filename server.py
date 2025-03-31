from time import sleep
from machine import Pin
from ulora import LoRa, ModemConfig, SPIConfig

# This is our callback function that runs when a message is received
def on_recv(payload):
    print("From:", payload.header_from)
    print("Received:", payload.message)
    print("RSSI: {}; SNR: {}".format(payload.rssi, payload.snr))

# Lora Parameters
RFM95_RST = 16
RFM95_SPIBUS = SPIConfig.esp32_2
RFM95_CS = 5
RFM95_INT = 4
RF95_FREQ = 433
RF95_POW = 14
CLIENT_ADDRESS = 1
SERVER_ADDRESS = 2

#reset = Pin(RFM95_RST, Pin.OUT)
#reset.value(0)  # Pull low to reset
#time.sleep(0.1)
#reset.value(1)  # Release reset
#time.sleep(0.1)

# initialise radio
lora = LoRa(RFM95_SPIBUS, RFM95_INT, SERVER_ADDRESS, RFM95_CS, reset_pin=RFM95_RST, freq=RF95_FREQ, tx_power=RF95_POW, acks=True)

# set callback
lora.on_recv = on_recv

# set to listen continuously
lora.set_mode_rx()

# loop and wait for data
while True:
    sleep(0.1)
