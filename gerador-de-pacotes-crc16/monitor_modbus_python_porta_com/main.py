import threading
import time
import signal
import sys

# Importar os módulos locais
from modbus_reader import ModbusReader, PacketData
from data_processor import DataManager
from gui_manager import GUIManager, DisplayData
from config import AppSettings, SerialConfig
import dearpygui.dearpygui as dpg


class ModbusMonitorApp:
    def __init__(self):
        self.settings = AppSettings()
        self.serial_config = SerialConfig()
        self.data_manager = DataManager(num_channels=self.settings.num_channels)
        self.modbus_reader = ModbusReader(
            port=self.serial_config.port,
            baudrate=self.serial_config.baudrate,
            timeout=self.serial_config.timeout,
            data_callback=self.on_data_received,
            error_callback=self.on_error
        )
        self.gui = GUIManager(
            num_channels=self.settings.num_channels,
            voltage_range=self.settings.voltage_range,
            window_size=self.settings.window_size,
            title=self.settings.title
        )
        
        # Configurar callbacks da GUI
        self.gui.start_callback = self.start_monitoring
        self.gui.pause_callback = self.toggle_pause
        self.gui.stop_callback = self.stop_monitoring
        self.gui.reset_callback = self.reset_counters
        self.gui.toggle_debug_callback = self.toggle_debug
        
        self.is_paused = False
        self.debug_mode = False
        self.running = True
        
        # 🔑 CORRIGIDO: Tamanho REAL do pacote de dados (22 bytes)
        # Estrutura: 1 byte header (0x55) + 1 byte empty (0x00) + 20 bytes tensões (10 canais × 2 bytes)
        self.bytes_per_packet = 22
        self.last_count = 0
        self.last_time = time.time()
        self.smoothed_kbps = 0.0  # Média móvel exponencial em kbps
        self.alpha = 0.15  # Fator de suavização (0.15 = bom equilíbrio suavidade/responsividade)

    def on_data_received(self, packet_data: PacketData):
        self.data_manager.add_data_point(packet_data.tensions, packet_data.raw_values)

    def on_error(self, error: Exception):
        print(f"❌ Erro na comunicação serial: {error}")
        self.gui.update_status(f"Erro: {error}", (255, 0, 0))

    def start_monitoring(self, sender, app_data):
        self.modbus_reader.start()
        self.gui.enable_running_controls()
        self.gui.update_status("Monitorando...", (0, 255, 0))

    def toggle_pause(self, sender, app_data):
        if self.is_paused:
            self.modbus_reader.resume()
            self.gui.set_button_label("pause_btn", "⏸ Pausar")
            self.gui.update_status("Monitorando...", (0, 255, 0))
        else:
            self.modbus_reader.pause()
            self.gui.set_button_label("pause_btn", "▶ Retomar")
            self.gui.update_status("PAUSADO", (255, 165, 0))
        self.is_paused = not self.is_paused

    def stop_monitoring(self, sender, app_data):
        self.modbus_reader.stop()
        self.gui.disable_running_controls()
        self.gui.update_status("Parado", (255, 255, 0))

    def reset_counters(self, sender, app_data):
        self.data_manager.reset()
        self.last_count = 0
        self.last_time = time.time()
        self.smoothed_kbps = 0.0
        self.gui.update_status("Contadores zerados", (0, 255, 255))

    def toggle_debug(self, sender, app_data):
        self.debug_mode = not self.debug_mode
        status = "ATIVADO" if self.debug_mode else "DESATIVADO"
        self.gui.set_button_label("debug_btn", f" Debug {status}")
        self.gui.update_status(f"Modo debug {status.lower()}", (128, 0, 128) if self.debug_mode else (255, 255, 0))

    def run(self):
        # Configurar GUI
        self.gui.setup_gui()
        self.gui.show()

        # Loop principal
        while self.gui.is_running() and self.running:
            # Atualizar dados na GUI
            count, tensions, averages, overall_avg, raw_values = self.data_manager.get_current_data()
            
            # 🔑 Cálculo CORRIGIDO da taxa de transferência em kbps
            current_time = time.time()
            time_delta = current_time - self.last_time
            
            # Atualizar a cada 50ms para melhor precisão em alta velocidade
            if time_delta > 0.05:
                # Taxa instantânea em pacotes por segundo
                instant_rate = (count - self.last_count) / time_delta
                
                # 🔑 Converter para kbps usando tamanho REAL do pacote (22 bytes)
                # Fórmula: pacotes/s × bytes/pacote × 8 bits/byte ÷ 1000
                instant_kbps = instant_rate * self.bytes_per_packet * 8 / 1000.0
                
                # Suavização com média móvel exponencial (EMA)
                self.smoothed_kbps = (
                    self.alpha * instant_kbps + 
                    (1 - self.alpha) * self.smoothed_kbps
                )
                
                self.last_count = count
                self.last_time = current_time
            
            # Atualizar display com contador e taxa suavizada
            display_data = DisplayData(
                count=count,
                rate=self.smoothed_kbps,  # Taxa em kbps (suavizada)
                tensions=tensions,
                averages=averages,
                overall_avg=overall_avg,
                raw_values=raw_values
            )
            self.gui.update_display(display_data)
            
            # Atualizar gráficos
            x_data, y_data = self.data_manager.get_plot_data()
            self.gui.update_plots(x_data, y_data)
            
            # Renderizar frame da GUI
            self.gui.render_frame()
            time.sleep(0.01)  # 10ms → atualização suave sem sobrecarregar CPU

        # Cleanup
        self.modbus_reader.stop()
        self.gui.destroy_context()

    def shutdown(self):
        self.running = False
        self.modbus_reader.stop()


def signal_handler(sig, frame):
    print("\n🛑 Encerrando aplicação...")
    if 'app' in globals():
        app.shutdown()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    print("🚀 Iniciando Monitoramento Modbus...")
    print("   Pressione Ctrl+C para encerrar\n")
    app = ModbusMonitorApp()
    app.run()