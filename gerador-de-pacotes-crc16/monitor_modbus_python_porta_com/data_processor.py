from collections import deque
from typing import List, Tuple
import threading
import time
from dataclasses import dataclass

@dataclass
class Statistics:
    averages: List[float]
    overall_avg: float

class DataManager:
    def __init__(self, num_channels: int = 10, max_recent_values: int = 100, max_raw_history: int = 50):
        self.num_channels = num_channels
        self.max_recent_values = max_recent_values
        self.max_raw_history = max_raw_history
        
        # Dados acumulados
        self.tension_sums = [0.0] * num_channels
        self.tension_counts = [0] * num_channels
        self.recent_tensions = [deque(maxlen=max_recent_values) for _ in range(num_channels)]
        self.raw_value_history = [deque(maxlen=max_raw_history) for _ in range(num_channels)]
        
        # Dados do gráfico
        self.plot_x_history = deque(maxlen=500)
        self.plot_y_history = {i: deque(maxlen=500) for i in range(num_channels)}
        
        # Contadores
        self.count = 0
        self.start_time = time.time()  # ✅ CORRIGIDO: inicializar com tempo atual
        
        # Sincronização
        self.lock = threading.Lock()

    def add_data_point(self, tensions: List[float], raw_values: List[int] = None):
        with self.lock:
            self.count += 1
            
            for i, tension in enumerate(tensions):
                if i < self.num_channels:
                    self.tension_sums[i] += tension
                    self.tension_counts[i] += 1
                    self.recent_tensions[i].append(tension)
                    
                    if raw_values and i < len(raw_values):
                        self.raw_value_history[i].append(raw_values[i])

            self.plot_x_history.append(self.count)
            for i in range(self.num_channels):
                self.plot_y_history[i].append(tensions[i] if i < len(tensions) else 0.0)

    def calculate_statistics(self) -> Statistics:
        with self.lock:
            averages = []
            overall_sum = 0
            overall_count = 0
            for i in range(self.num_channels):
                if self.tension_counts[i] > 0:
                    avg = self.tension_sums[i] / self.tension_counts[i]
                    averages.append(avg)
                    overall_sum += self.tension_sums[i]
                    overall_count += self.tension_counts[i]
                else:
                    averages.append(0.0)
            overall_avg = overall_sum / overall_count if overall_count > 0 else 0.0
            return Statistics(averages=averages, overall_avg=overall_avg)

    def get_current_data(self) -> Tuple[int, List[float], List[float], float, List[int]]:
        stats = self.calculate_statistics()
        current_tensions = [list(self.recent_tensions[i])[-1] if self.recent_tensions[i] else 0.0 
                           for i in range(self.num_channels)]
        recent_raw_values = [list(self.raw_value_history[i])[-1] if self.raw_value_history[i] else 0 
                             for i in range(3)]
        return self.count, current_tensions, stats.averages, stats.overall_avg, recent_raw_values

    def reset(self):
        with self.lock:
            self.count = 0
            self.tension_sums = [0.0] * self.num_channels
            self.tension_counts = [0] * self.num_channels
            self.recent_tensions = [deque(maxlen=self.max_recent_values) for _ in range(self.num_channels)]
            self.raw_value_history = [deque(maxlen=self.max_raw_history) for _ in range(self.num_channels)]
            
            self.plot_x_history.clear()
            for i in range(self.num_channels):
                self.plot_y_history[i].clear()
                
            self.start_time = time.time()  # ✅ CORRIGIDO: resetar tempo

    def get_plot_data(self) -> Tuple[List[int], dict]:
        with self.lock:
            x_list = list(self.plot_x_history)
            y_dict = {i: list(self.plot_y_history[i]) for i in range(self.num_channels)}
            return x_list, y_dict

    def get_elapsed_time_and_rate(self) -> Tuple[str, float]:
        with self.lock:
            elapsed = time.time() - self.start_time
            rate = self.count / elapsed if elapsed > 0 else 0
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            return time_str, rate