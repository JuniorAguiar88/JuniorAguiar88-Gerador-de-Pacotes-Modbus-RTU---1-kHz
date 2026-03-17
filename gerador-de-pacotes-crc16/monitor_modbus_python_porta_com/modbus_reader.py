import serial
import threading
import time
from typing import Callable, Optional, List
from dataclasses import dataclass

@dataclass
class PacketData:
    tensions: List[float]
    raw_values: List[int]

class ModbusReader:
    def __init__(
        self,
        port: str = 'COM7',
        baudrate: int = 921600,  # ← AUMENTADO PARA 921600 (crítico para USB CDC)
        timeout: float = 0.001,  # ← REDUZIDO PARA 1ms (crítico!)
        data_callback: Optional[Callable[[PacketData], None]] = None,
        error_callback: Optional[Callable[[Exception], None]] = None
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.data_callback = data_callback
        self.error_callback = error_callback
        
        self.running = False
        self.paused = False
        self.thread: Optional[threading.Thread] = None
        self.serial_conn: Optional[serial.Serial] = None
        
        # Estatísticas de diagnóstico
        self.stats = {
            'bytes_read': 0,
            'packets_valid': 0,
            'packets_discarded': 0,
            'buffer_overflows': 0,
            'resync_events': 0,
            'start_time': time.perf_counter()
        }
        
        # Buffer circular com limite máximo para evitar memory leak
        self.buffer = bytearray()
        self.buffer_max_size = 10000  # 10KB máximo

    def start(self):
        if self.running:
            return
        self.running = True
        self.paused = False
        self.stats['start_time'] = time.perf_counter()
        self.thread = threading.Thread(target=self._read_loop, daemon=True, name="ModbusReader")
        self.thread.start()
        print(f"✅ Iniciando leitura em {self.port} @ {self.baudrate} bps...")

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def stop(self):
        self.running = False
        self.paused = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.close()
            except:
                pass
        print(f"🔌 Leitura parada. Estatísticas: {self.get_statistics()}")

    def get_statistics(self) -> dict:
        elapsed = time.perf_counter() - self.stats['start_time']
        elapsed = max(elapsed, 0.001)  # evitar divisão por zero
        return {
            'elapsed_sec': round(elapsed, 2),
            'packets_per_sec': round(self.stats['packets_valid'] / elapsed, 1),
            'bytes_per_sec': round(self.stats['bytes_read'] / elapsed, 0),
            'packets_total': self.stats['packets_valid'],
            'packets_discarded': self.stats['packets_discarded'],
            'buffer_overflows': self.stats['buffer_overflows'],
            'resync_events': self.stats['resync_events']
        }

    def _parse_packet_fast(self, packet: bytes) -> Optional[PacketData]:
        """Parser otimizado - big-endian direto conforme especificação do firmware"""
        if len(packet) != 22 or packet[0] != 0x55 or packet[1] != 0x00:
            return None
        
        tensions = []
        raw_values = []
        
        # Extrair 10 canais (2 bytes big-endian cada)
        for ch in range(10):
            idx = 2 + ch * 2
            raw = (packet[idx] << 8) | packet[idx + 1]  # Big-endian
            tension = (raw * 3.3) / 65535.0
            tensions.append(tension)
            raw_values.append(raw)
        
        return PacketData(tensions=tensions, raw_values=raw_values)

    def _read_loop(self):
        try:
            # Configuração otimizada para USB CDC de alta velocidade
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
                write_timeout=0
            )
            print(f"✓ Porta {self.port} aberta com sucesso @ {self.baudrate} bps")
        except Exception as e:
            print(f"❌ Erro ao abrir porta {self.port}: {e}")
            if self.error_callback:
                self.error_callback(e)
            return

        last_stats_time = time.perf_counter()
        
        while self.running:
            if self.paused:
                time.sleep(0.01)
                continue

            # 🔑 Leitura não bloqueante - processa tudo disponível imediatamente
            if self.serial_conn.in_waiting > 0:
                try:
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    self.stats['bytes_read'] += len(data)
                    self.buffer.extend(data)
                    
                    # 🔑 Prevenção de buffer overflow
                    if len(self.buffer) > self.buffer_max_size:
                        # Resync: descartar bytes até encontrar próximo cabeçalho ou limpar buffer
                        header_pos = self.buffer.find(b'\x55')
                        if header_pos != -1 and header_pos + 22 <= len(self.buffer):
                            self.buffer = self.buffer[header_pos:]
                            self.stats['resync_events'] += 1
                        else:
                            self.buffer.clear()
                            self.stats['buffer_overflows'] += 1
                            self.stats['packets_discarded'] += (len(self.buffer) // 22)
                            continue
                    
                    # 🔑 Busca eficiente por pacotes válidos
                    while len(self.buffer) >= 22:
                        # Encontrar próximo cabeçalho 0x55
                        header_pos = self.buffer.find(b'\x55')
                        
                        if header_pos == -1:
                            # Nenhum cabeçalho encontrado - descartar buffer
                            self.buffer.clear()
                            self.stats['packets_discarded'] += 1
                            break
                        
                        if header_pos > 0:
                            # Descartar bytes inválidos antes do cabeçalho
                            self.stats['packets_discarded'] += header_pos // 22
                            self.buffer = self.buffer[header_pos:]
                        
                        if len(self.buffer) < 22:
                            break
                        
                        # Extrair e validar pacote
                        packet = bytes(self.buffer[:22])
                        packet_data = self._parse_packet_fast(packet)
                        
                        if packet_data:
                            if self.data_callback:
                                self.data_callback(packet_data)
                            self.stats['packets_valid'] += 1
                            self.buffer = self.buffer[22:]
                        else:
                            # Pacote inválido - descartar 1 byte e tentar novamente
                            self.buffer = self.buffer[1:]
                            self.stats['packets_discarded'] += 1
                
                except serial.SerialException as e:
                    if self.error_callback:
                        self.error_callback(e)
                    time.sleep(0.001)
            
            # 🔑 Estatísticas periódicas (a cada 5 segundos)
            current_time = time.perf_counter()
            if current_time - last_stats_time >= 5.0:
                stats = self.get_statistics()
                print(f"📊 TX: {stats['bytes_per_sec']/1000:.1f} kB/s | "
                      f"Pkt/s: {stats['packets_per_sec']:.0f} | "
                      f"Válidos: {stats['packets_total']} | "
                      f"Descartados: {stats['packets_discarded']}")
                last_stats_time = current_time

        # Cleanup
        try:
            self.serial_conn.close()
        except:
            pass