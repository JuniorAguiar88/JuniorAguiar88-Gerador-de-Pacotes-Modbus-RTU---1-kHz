"""
CONTADOR SIMPLES DE PACOTES MODBUS COM LEITURA CORRIGIDA DE TENSÕES
Versão com gráfico em tempo real que funciona mesmo se aberto após o início da leitura
"""

import serial
import threading
import time
from collections import deque
import struct
from dearpygui import dearpygui as dpg

# Estado global
running = False
paused = False
start_time = 0
debug_mode = False
count = 0
tension_sums = [0.0] * 10
tension_counts = [0] * 10
recent_tensions = [deque(maxlen=100) for _ in range(10)]
raw_value_history = [[] for _ in range(10)]

# Lock para atualizações seguras
data_lock = threading.Lock()
latest_update = None
error_message = None

# === Dados para o gráfico (armazenamento contínuo) ===
plot_window_open = False
plot_series_ids = {}
max_plot_points = 500
plot_x_history = deque(maxlen=max_plot_points)
plot_y_history = {i: deque(maxlen=max_plot_points) for i in range(10)}

# === Funções de parsing ===

def parse_tension_packet_corrected(packet):
    if len(packet) != 22 or packet[0] != 0x55:
        return None
    tensions = []
    raw_values = []
    for ch in range(10):
        idx = 2 + (ch * 2)
        if idx + 1 < len(packet):
            value_be = (packet[idx] << 8) | packet[idx + 1]
            value_le = (packet[idx + 1] << 8) | packet[idx]
            if 0 <= value_be <= 65535 and 0 <= value_le <= 65535:
                value = value_be
            else:
                value = value_be if 0 <= value_be <= 65535 else value_le
            raw_values.append(value)
            tension = (value * 3.3) / 65535.0
            tensions.append(tension)
        else:
            tensions.append(0.0)
            raw_values.append(0)
    return tensions, raw_values

def parse_tension_alternative(packet):
    tensions = []
    raw_values = []
    for ch in range(10):
        idx = 2 + (ch * 2)
        if idx + 1 < len(packet):
            interpretations = [
                ('BE', (packet[idx] << 8) | packet[idx + 1]),
                ('LE', (packet[idx + 1] << 8) | packet[idx]),
            ]
            best_val = 0
            for name, val in interpretations:
                if 0 <= val <= 65535:
                    if 1000 <= val <= 64535:
                        best_val = val
                        break
                    best_val = val
            if best_val == 0 and interpretations:
                best_val = interpretations[0][1]
            raw_values.append(best_val)
            tension = (best_val * 3.3) / 65535.0
            tensions.append(tension)
        else:
            tensions.append(0.0)
            raw_values.append(0)
    return tensions, raw_values

def calculate_statistics():
    averages = []
    overall_sum = 0
    overall_count = 0
    for i in range(10):
        if tension_counts[i] > 0:
            avg = tension_sums[i] / tension_counts[i]
            averages.append(avg)
            overall_sum += tension_sums[i]
            overall_count += tension_counts[i]
        else:
            averages.append(0.0)
    overall_avg = overall_sum / overall_count if overall_count > 0 else 0.0
    return {'averages': averages, 'overall_avg': overall_avg}

def update_tension_data(tensions, raw_values=None):
    global tension_sums, tension_counts, recent_tensions, raw_value_history
    global plot_x_history, plot_y_history, count

    for i, tension in enumerate(tensions):
        if i < 10:
            tension_sums[i] += tension
            tension_counts[i] += 1
            recent_tensions[i].append(tension)
            if raw_values and i < len(raw_values):
                raw_value_history[i].append(raw_values[i])
                if len(raw_value_history[i]) > 50:
                    raw_value_history[i].pop(0)

    plot_x_history.append(count)
    for i in range(10):
        plot_y_history[i].append(tensions[i] if i < len(tensions) else 0.0)

def reset_data():
    global count, tension_sums, tension_counts, recent_tensions, raw_value_history
    global plot_x_history, plot_y_history
    count = 0
    tension_sums = [0.0] * 10
    tension_counts = [0] * 10
    recent_tensions = [deque(maxlen=100) for _ in range(10)]
    raw_value_history = [[] for _ in range(10)]
    plot_x_history.clear()
    for i in range(10):
        plot_y_history[i].clear()

def debug_packet(packet, tensions, raw_values):
    debug_info = []
    debug_info.append(f"Pacote completo: {' '.join(f'{b:02X}' for b in packet[:12])}...")
    for i in range(min(3, len(tensions))):
        idx = 2 + (i * 2)
        if idx + 1 < len(packet):
            byte1 = packet[idx]
            byte2 = packet[idx + 1]
            debug_info.append(f"CH{i}: bytes {byte1:02X} {byte2:02X} = raw:{raw_values[i]} = {tensions[i]:.3f}V")
    return debug_info

# === Thread de leitura serial ===

def read_serial():
    global running, paused, count, start_time, debug_mode, latest_update, error_message
    try:
        print(" Tentando abrir porta COM7...")
        ser = serial.Serial('COM7', 115200, timeout=0.1)
        print(" Porta COM7 aberta com sucesso!")
    except Exception as e:
        print(f" Erro ao abrir porta COM7: {e}")
        with data_lock:
            error_message = f"Porta COM7 indisponível: {e}"
        return

    buffer = bytearray()

    while running:
        if paused:
            time.sleep(0.1)
            continue

        if ser.in_waiting:
            data = ser.read(ser.in_waiting)
            buffer.extend(data)

            i = 0
            while i < len(buffer):
                if buffer[i] == 0x55 and i + 22 <= len(buffer):
                    with data_lock:
                        count += 1
                    packet = buffer[i:i+22]

                    tensions, raw_values = parse_tension_packet_corrected(packet)
                    if tensions is None:
                        tensions, raw_values = parse_tension_alternative(packet)

                    if tensions:
                        update_tension_data(tensions, raw_values)
                        stats = calculate_statistics()

                        update_data = {
                            'count': count,
                            'tensions': tensions,
                            'averages': stats['averages'],
                            'overall_avg': stats['overall_avg'],
                            'raw_values': raw_values[:5] if raw_values else []
                        }

                        if debug_mode and count % 100 == 0:
                            debug_info = debug_packet(packet, tensions, raw_values)
                            update_data['debug_info'] = debug_info

                        with data_lock:
                            latest_update = update_data

                    buffer = buffer[i+22:]
                    i = 0
                else:
                    i += 1

        time.sleep(0.001)

    ser.close()
    print("🔌 Porta COM7 fechada.")

# === Callbacks da GUI ===

def start_reading():
    global running, paused, start_time
    if not running:
        running = True
        paused = False
        start_time = time.time()
        print("▶️ Iniciando thread de leitura serial...")
        threading.Thread(target=read_serial, daemon=True).start()
        dpg.enable_item("pause_btn")
        dpg.enable_item("stop_btn")
        dpg.disable_item("start_btn")
        dpg.set_value("status_text", "Contando pacotes...")
        dpg.configure_item("status_text", color=[0, 255, 0])

def toggle_pause():
    global paused
    paused = not paused
    if paused:
        dpg.set_item_label("pause_btn", "▶ Retomar")
        dpg.set_value("status_text", "PAUSADO")
        dpg.configure_item("status_text", color=[255, 165, 0])
    else:
        dpg.set_item_label("pause_btn", "⏸ Pausar")
        dpg.set_value("status_text", "Contando pacotes...")
        dpg.configure_item("status_text", color=[0, 255, 0])

def stop_reading():
    global running, paused
    running = False
    paused = False
    dpg.disable_item("pause_btn")
    dpg.disable_item("stop_btn")
    dpg.enable_item("start_btn")
    dpg.set_item_label("pause_btn", "⏸ Pausar")
    dpg.set_value("status_text", "Parado")
    dpg.configure_item("status_text", color=[255, 255, 0])

def reset_counters():
    global start_time
    reset_data()
    if running:
        start_time = time.time()
    dpg.set_value("count_display", "0")
    dpg.set_value("total_packets", "0")
    dpg.set_value("overall_avg_display", "0.000")
    dpg.set_value("rate_display", "0.0")
    dpg.set_value("time_display", "00:00:00")
    dpg.set_value("last_packet_text", "")
    for i in range(10):
        dpg.set_value(f"tension_{i}", "0.000")
        dpg.set_value(f"avg_tension_{i}", "0.000")
        dpg.set_value(f"progress_{i}", 0.0)
    dpg.set_value("status_text", "Contadores zerados")
    dpg.configure_item("status_text", color=[0, 255, 255])

def toggle_debug():
    global debug_mode
    debug_mode = not debug_mode
    status = "ATIVADO" if debug_mode else "DESATIVADO"
    dpg.set_item_label("debug_btn", f" Debug {status}")
    dpg.set_value("status_text", f"Modo debug {status.lower()}")
    dpg.configure_item("status_text", color=[128, 0, 128] if debug_mode else [255, 255, 0])

def close_plot_window(sender, app_data):
    global plot_window_open
    plot_window_open = False

def create_plot_window():
    global plot_window_open, plot_series_ids, plot_x_history, plot_y_history
    if dpg.does_item_exist("plot_window"):
        dpg.focus_item("plot_window")
        return

    plot_window_open = True
    with dpg.window(
        label="Gráfico em Tempo Real",
        tag="plot_window",
        width=1000,
        height=600,
        on_close=close_plot_window
    ):
        with dpg.plot(label="Tensões em Tempo Real", height=-1, width=-1):
            dpg.add_plot_legend()
            x_axis = dpg.add_plot_axis(dpg.mvXAxis, label="Pacote")
            y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Tensão (V)", tag="plot_y_axis")

            for ch in range(10):
                series_id = dpg.add_line_series([], [], label=f"CH{ch}", parent=y_axis)
                plot_series_ids[ch] = series_id

    update_plots()

# === Atualização da GUI e Gráficos ===

def update_gui():
    global latest_update, error_message, start_time, count

    with data_lock:
        err = error_message
        if err:
            error_message = None
    if err:
        dpg.set_value("status_text", f"ERRO: {err}")
        dpg.configure_item("status_text", color=[255, 0, 0])
        global running
        running = False
        return

    with data_lock:
        data = latest_update
        latest_update = None

    if data is not None:
        dpg.set_value("count_display", str(data['count']))
        dpg.set_value("total_packets", str(data['count']))

        for i in range(10):
            tension = data['tensions'][i]
            dpg.set_value(f"tension_{i}", f"{tension:.3f}")
            dpg.set_value(f"progress_{i}", min(1.0, tension / 3.3))

        for i in range(10):
            avg = data['averages'][i]
            dpg.set_value(f"avg_tension_{i}", f"{avg:.3f}")

        dpg.set_value("overall_avg_display", f"{data['overall_avg']:.3f}")

        if 'debug_info' in data:
            last_line = data['debug_info'][-1] if data['debug_info'] else ''
            dpg.set_value("last_packet_text", f"Debug: {last_line}")
        elif 'raw_values' in data and data['raw_values']:
            raw_str = ' '.join(str(v) for v in data['raw_values'][:3])
            dpg.set_value("last_packet_text", f"Valores brutos: {raw_str}...")

        if start_time > 0:
            elapsed = time.time() - start_time
            rate = data['count'] / elapsed if elapsed > 0 else 0
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            dpg.set_value("rate_display", f"{rate:.1f}")
            dpg.set_value("time_display", time_str)

def update_plots():
    global plot_x_history, plot_y_history, plot_series_ids, plot_window_open
    if not dpg.does_item_exist("plot_window"):
        return

    if len(plot_x_history) == 0:
        return

    x_list = list(plot_x_history)
    for ch in range(10):
        if ch in plot_series_ids:
            y_list = list(plot_y_history[ch])
            min_len = min(len(x_list), len(y_list))
            dpg.set_value(plot_series_ids[ch], [x_list[-min_len:], y_list[-min_len:]])
    
    dpg.fit_axis_data("plot_y_axis")
    plot_item = dpg.get_item_children("plot_window")[1][0]
    axes = dpg.get_item_children(plot_item)[1]
    if len(axes) >= 1:
        dpg.fit_axis_data(axes[0])

# === Configuração da janela principal ===

def simple_counter_with_tensions():
    print(" Iniciando contexto do dearpygui...")
    dpg.create_context()

    with dpg.theme() as global_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3, category=dpg.mvThemeCat_Core)
    dpg.bind_theme(global_theme)

    print(" Criando janela principal...")
    with dpg.window(tag="PrimaryWindow", width=900, height=560, no_collapse=True):
        dpg.add_text("CONTADOR DE PACOTES MODBUS", color=[255, 255, 255])
        dpg.add_separator()

        with dpg.group(horizontal=True):
            dpg.add_text("PKT:", color=[255, 255, 255])
            dpg.add_text("0", tag="count_display", color=[0, 255, 255])

        dpg.add_spacer(height=10)

        with dpg.collapsing_header(label="TENSÕES ATUAIS (0-3.3V)", default_open=True):
            with dpg.group(horizontal=True):
                with dpg.child_window(width=430, height=120, border=False):
                    for i in range(5):
                        with dpg.group(horizontal=True):
                            dpg.add_text(f"CH{i}:", color=[255, 255, 255])
                            dpg.add_text("0.000", tag=f"tension_{i}", color=[50, 255, 50])
                            dpg.add_text("V", color=[255, 255, 255])
                            dpg.add_progress_bar(tag=f"progress_{i}", width=120, height=15)
                dpg.add_spacer(width=10)
                with dpg.child_window(width=430, height=120, border=False):
                    for i in range(5, 10):
                        with dpg.group(horizontal=True):
                            dpg.add_text(f"CH{i}:", color=[255, 255, 255])
                            dpg.add_text("0.000", tag=f"tension_{i}", color=[50, 255, 50])
                            dpg.add_text("V", color=[255, 255, 255])
                            dpg.add_progress_bar(tag=f"progress_{i}", width=120, height=15)

        with dpg.collapsing_header(label="MÉDIAS ACUMULADAS", default_open=True):
            with dpg.group(horizontal=True):
                with dpg.child_window(width=430, height=120, border=False):
                    for i in range(5):
                        with dpg.group(horizontal=True):
                            dpg.add_text(f"CH{i}:", color=[255, 255, 255])
                            dpg.add_text("0.000", tag=f"avg_tension_{i}", color=[255, 255, 0])
                dpg.add_spacer(width=10)
                with dpg.child_window(width=430, height=120, border=False):
                    for i in range(5, 10):
                        with dpg.group(horizontal=True):
                            dpg.add_text(f"CH{i}:", color=[255, 255, 255])
                            dpg.add_text("0.000", tag=f"avg_tension_{i}", color=[255, 255, 0])

        with dpg.collapsing_header(label="ESTATÍSTICAS", default_open=True):
            with dpg.group(horizontal=True):
                dpg.add_text("Taxa:", color=[255, 255, 255])
                dpg.add_text("0.0", tag="rate_display", color=[255, 255, 255])
                dpg.add_text("pkt/s", color=[255, 255, 255])
                dpg.add_text("Tempo:", color=[255, 255, 255])
                dpg.add_text("00:00:00", tag="time_display", color=[255, 255, 255])
            with dpg.group(horizontal=True):
                dpg.add_text("Pacotes:", color=[255, 255, 255])
                dpg.add_text("0", tag="total_packets", color=[255, 255, 255])
                dpg.add_text("Média geral:", color=[255, 255, 255])
                dpg.add_text("0.000", tag="overall_avg_display", color=[255, 255, 255])
                dpg.add_text("V", color=[255, 255, 255])

        dpg.add_spacer(height=10)

        with dpg.group(horizontal=True):
            dpg.add_button(label=" Iniciar", callback=start_reading, tag="start_btn")
            dpg.add_button(label=" Pausar", callback=toggle_pause, tag="pause_btn", enabled=False)
            dpg.add_button(label=" Parar", callback=stop_reading, tag="stop_btn", enabled=False)
            dpg.add_button(label=" Zerar", callback=reset_counters, tag="reset_btn")
            dpg.add_button(label=" Debug DESATIVADO", callback=toggle_debug, tag="debug_btn")
            dpg.add_button(label=" Gráfico", callback=create_plot_window)

        dpg.add_spacer(height=5)
        dpg.add_text("Status: Pronto", tag="status_text", color=[255, 255, 0])
        dpg.add_text("Último pacote:", tag="last_packet_text", color=[128, 128, 128])

    print(" Criando viewport...")
    dpg.create_viewport(title='Contador Modbus - Leitura Corrigida', width=920, height=760)
    dpg.setup_dearpygui()

    print(" Mostrando viewport...")
    dpg.show_viewport()

    print(" Iniciando loop da GUI...")
    while dpg.is_dearpygui_running():
        update_gui()
        update_plots()
        dpg.render_dearpygui_frame()
        time.sleep(0.01)

    print(" GUI encerrada.")
    dpg.destroy_context()

# ============================================================================

if __name__ == "__main__":
    simple_counter_with_tensions()