from abc import ABC, abstractmethod


class Vehicle(ABC):
    mode = None

    def __init__(self, trouble_codes):
        self.trouble_codes = trouble_codes

    @abstractmethod
    def read_mode01(self, command):
        raise NotImplementedError

    @abstractmethod
    def battery_voltage(self):
        raise NotImplementedError

    @abstractmethod
    def open_can_source(self, now):
        raise NotImplementedError
