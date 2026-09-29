from enum import Enum


class ModeFlight(Enum):
    None_ = 0x00
    Ready = 0x10
    Start = 0x11
    TakeOff = 0x12
    Flight = 0x13
    Landing = 0x14
    Flip = 0x15
    Reverse = 0x16
    Stop = 0x20
    Accident = 0x30
    Error = 0x31
    Test = 0x40
    EndOfType = 0x41


class ModeMovement(Enum):
    None_ = 0x00
    Ready = 0x01
    Hovering = 0x02
    Moving = 0x03
    ReturnHome = 0x04
    EndOfType = 0x05
