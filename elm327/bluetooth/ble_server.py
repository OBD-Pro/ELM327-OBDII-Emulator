import dbus

from elm327.bluetooth.constants import ADVERT_PATH, BLUEZ, GATT_APP_PATH
from elm327.bluetooth.gatt import Advertisement, GattApplication
from elm327.bluetooth.logging_helpers import log


class BleServer:
    def __init__(self, bus, adapter_path, name, link):
        self._name = name
        self._application = GattApplication(bus, link)
        self._advertisement = Advertisement(bus, name)
        adapter = bus.get_object(BLUEZ, adapter_path)
        self._gatt_manager = dbus.Interface(adapter, "org.bluez.GattManager1")
        self._advert_manager = dbus.Interface(
            adapter, "org.bluez.LEAdvertisingManager1"
        )
        self._gatt_registered = False
        self._advert_registered = False

    def register(self):
        self._gatt_manager.RegisterApplication(
            GATT_APP_PATH,
            {},
            reply_handler=self._on_gatt_registered,
            error_handler=self._failure_logger("GATT server"),
        )

    def _on_gatt_registered(self):
        self._gatt_registered = True
        self._advert_manager.RegisterAdvertisement(
            ADVERT_PATH,
            {},
            reply_handler=self._on_advert_registered,
            error_handler=self._failure_logger("advertising"),
        )

    def _on_advert_registered(self):
        self._advert_registered = True
        log(
            f"BLE ready, advertising '{self._name}' "
            "(iPhone: connect from the OBD app, not from Settings)"
        )

    def _failure_logger(self, step):
        def log_failure(error):
            message = error.get_dbus_message()
            log(f"BLE {step} failed ({message}); Classic SPP still works")

        return log_failure

    def unregister_steps(self):
        steps = []
        if self._advert_registered:
            manager = self._advert_manager
            steps.append(lambda: manager.UnregisterAdvertisement(ADVERT_PATH))
        if self._gatt_registered:
            manager_gatt = self._gatt_manager
            steps.append(lambda: manager_gatt.UnregisterApplication(GATT_APP_PATH))
        return steps
