from machine import Pin
from time import sleep

class CustomMotorDriver:
    def __init__(self, clk_pin: int, anti_clk_pin: int) -> None:
        self.clk = Pin(clk_pin, Pin.OUT)
        self.anti_clk = Pin(anti_clk_pin, Pin.OUT)


    def rotate_clockwise(self):
        self.clk.value(0)
        self.anti_clk.value(1)
        sleep(5)
    
    def rotate_anti_clockwise(self):
        self.clk.value(1)
        self.anti_clk.value(0)
        sleep(5)

    def stop(self):
        self.clk.value(0)
        self.anti_clk.value(0)