"""Domain enumerations and constants for AMS binary wire format."""

from enum import IntEnum

LOG_BLOCK_SIZE_B: int = 4096
LOG_HEADER_SIZE_B: int = 8


class LogSourceId(IntEnum):
    """Source IDs mirroring Core/Inc/Algorithms/AMS_log_format.h."""
    PAD = 0x00
    FILE_HEADER = 0x01
    CAN_INVERTER = 0x10
    SENSORS_ADC = 0x20
    GPS_RMC = 0x30
    BMS_SPI = 0x40
    LOGGER_STATS = 0xF0

    @classmethod
    def is_known(cls, value: int) -> bool:
        return value in cls._value2member_map_

    @classmethod
    def get_name(cls, value: int) -> str:
        try:
            return cls(value).name
        except ValueError:
            return f"UNKNOWN_0x{value:02X}"
