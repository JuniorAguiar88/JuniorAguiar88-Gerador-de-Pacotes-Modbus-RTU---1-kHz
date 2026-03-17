# config.py
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class SerialConfig:
    port: str = 'COM7'
    baudrate: int = 921600  # ← ALTERADO DE 115200 PARA 921600
    timeout: float = 0.001  # ← ALTERADO DE 0.1 PARA 0.001

@dataclass
class PlotConfig:
    max_points: int = 500
    refresh_rate: float = 0.1
    window_size: tuple = (600, 600)

@dataclass
class AppSettings:
    title: str = "Monitoramento Modbus"
    window_size: tuple = (920, 660)
    voltage_range: tuple = (0.0, 3.3)
    num_channels: int = 10