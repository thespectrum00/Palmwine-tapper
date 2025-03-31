from time import sleep
from ulora import LoRa, ModemConfig, SPIConfig

# Lora Parameters
RFM95_RST = 16 #32 for pushed lora
RFM95_SPIBUS = SPIConfig.esp32_2
RFM95_CS = 5
RFM95_INT = 4 #14 for pushed lora
RF95_FREQ = 433
RF95_POW = 20
CLIENT_ADDRESS = 1
SERVER_ADDRESS = 2

# initialise radio
lora = LoRa(RFM95_SPIBUS, RFM95_INT, CLIENT_ADDRESS, RFM95_CS, reset_pin=RFM95_RST, freq=RF95_FREQ, tx_power=RF95_POW, acks=True)


# loop and send data
while True:
    lora.send_to_wait("This is a test message", SERVER_ADDRESS)
    print("sent")
    sleep(10)
