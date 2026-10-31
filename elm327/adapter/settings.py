from dataclasses import dataclass
from typing import Optional

BROADCAST_REQUEST_ID = "7DF"
ENGINE_RESPONSE_ID = "7E8"
STANDARD_ID_MASK = 0x7FF


@dataclass
class AdapterSettings:
    initialized: bool = False
    preinit_no_data: bool = False
    echo: bool = True
    linefeeds: bool = False
    spaces: bool = True
    headers: bool = False
    show_dlc: bool = False
    protocol: int = 0
    timeout: int = 32
    adaptive_timing: int = 1
    request_id: str = BROADCAST_REQUEST_ID
    response_id: Optional[str] = ENGINE_RESPONSE_ID
    can_filter: Optional[int] = None
    can_mask: Optional[int] = None
    flow_control: Optional[str] = None
    monitoring: bool = False
    monitor_address: Optional[int] = None

    def reset(self):
        defaults = AdapterSettings()
        for name in self.__dataclass_fields__:
            if name not in ("initialized", "preinit_no_data"):
                setattr(self, name, getattr(defaults, name))

    def start_monitoring(self, address=None):
        self.monitoring = True
        self.monitor_address = address

    def accepts(self, can_id):
        if self._blocked_by_monitor_address(can_id):
            return False
        if self.can_filter is None and self.can_mask is None:
            return True
        can_filter = self.can_filter or 0
        mask = STANDARD_ID_MASK if self.can_mask is None else self.can_mask
        return (can_id & mask) == (can_filter & mask)

    def _blocked_by_monitor_address(self, can_id):
        if not self.monitoring or self.monitor_address is None:
            return False
        return (can_id & 0xFF) != self.monitor_address
