from dataclasses import dataclass


@dataclass
class Demand:
    src: str
    dst: str
    volume: int
