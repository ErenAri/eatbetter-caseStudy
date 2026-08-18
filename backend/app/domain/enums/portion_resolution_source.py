from enum import StrEnum


class PortionResolutionSource(StrEnum):
    AUTO_ESTIMATE = "AUTO_ESTIMATE"
    USER = "USER"
    USER_HOUSEHOLD_UNIT = "USER_HOUSEHOLD_UNIT"
