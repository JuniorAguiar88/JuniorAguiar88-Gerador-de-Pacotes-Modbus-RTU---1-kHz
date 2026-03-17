import dearpygui.dearpygui as dpg
from dataclasses import dataclass
from typing import Callable, Optional

@dataclass
class DisplayData:
    count: int = 0
    rate: float = 0.0  # Agora representa kbps (kilobits por segundo)
    tensions: list[float] = None
    averages: list[float] = None
    overall_avg: float = 0.0
    raw_values: list[int] = None
    debug_info: list[str] = None

    def __post_init__(self):
        if self.tensions is None:
            self.tensions = [0.0] * 10
        if self.averages is None:
            self.averages = [0.0] * 10
        if self.raw_values is None:
            self.raw_values = []
        if self.debug_info is None:
            self.debug_info = []

class GUIManager:
    def __init__(
        self,
        num_channels: int = 10,
        voltage_range: tuple = (0.0, 3.3),
        window_size: tuple = (920, 760),
        title: str = "Monitoramento Modbus"
    ):
        self.num_channels = num_channels
        self.voltage_range = voltage_range
        self.window_size = window_size
        self.title = title

        # Callbacks para controle externo
        self.start_callback: Optional[Callable] = None
        self.pause_callback: Optional[Callable] = None
        self.stop_callback: Optional[Callable] = None
        self.reset_callback: Optional[Callable] = None
        self.toggle_debug_callback: Optional[Callable] = None

        # Referências para elementos da GUI
        self.plot_series_ids = {}
        self.plot_window_open = False

    def setup_gui(self):
        dpg.create_context()

        # Tema global
        with dpg.theme() as global_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3, category=dpg.mvThemeCat_Core)
        dpg.bind_theme(global_theme)

        # Janela principal
        with dpg.window(tag="PrimaryWindow", width=800, height=560, no_collapse=True):
            dpg.add_text("CONTADOR DE PACOTES MODBUS", color=[255, 255, 255])
            dpg.add_separator()

            # Contador PKT + Taxa de transferência lado a lado
            with dpg.group(horizontal=True):
                dpg.add_text("PKT:", color=[255, 255, 255])
                dpg.add_text("0", tag="count_display", color=[0, 255, 255])
                dpg.add_spacer(width=20)
                dpg.add_text("TX:", color=[255, 255, 255])  # TX = Transferência
                dpg.add_text("0.0", tag="rate_display", color=[100, 200, 255])
                dpg.add_text("kbps", color=[255, 255, 255])  # Unidade em kbps

            dpg.add_spacer(height=20)

            # Botões de controle
            with dpg.group(horizontal=True):
                dpg.add_button(label=" Iniciar", callback=self.start_callback, tag="start_btn")
                dpg.add_button(label=" Pausar", callback=self.pause_callback, tag="pause_btn", enabled=False)
                dpg.add_button(label=" Parar", callback=self.stop_callback, tag="stop_btn", enabled=False)
                dpg.add_button(label=" Zerar", callback=self.reset_callback, tag="reset_btn")
                dpg.add_button(label=" Debug DESATIVADO", callback=self.toggle_debug_callback, tag="debug_btn")
                dpg.add_button(label=" Gráfico", callback=self.create_plot_window)
                dpg.add_button(label=" Gráficos Individuais", callback=self.create_individual_graphs_window)

            dpg.add_spacer(height=15)
            dpg.add_text("Status: Pronto", tag="status_text", color=[255, 255, 0])
            dpg.add_text("Último pacote:", tag="last_packet_text", color=[128, 128, 128])

        dpg.create_viewport(title=self.title, width=self.window_size[0], height=self.window_size[1])
        dpg.setup_dearpygui()

    def show(self):
        dpg.show_viewport()

    def render_frame(self):
        dpg.render_dearpygui_frame()

    def is_running(self):
        return dpg.is_dearpygui_running()

    def destroy_context(self):
        dpg.destroy_context()

    def update_display(self, data):
        # Atualiza contador e taxa de transferência (kbps)
        dpg.set_value("count_display", str(data.count))
        
        # Formatação inteligente: 2 casas decimais para valores < 10, 1 casa para >= 10
        if data.rate < 10.0:
            rate_str = f"{data.rate:.2f}"
        else:
            rate_str = f"{data.rate:.1f}"
        dpg.set_value("rate_display", rate_str)

        if data.debug_info:
            last_line = data.debug_info[-1] if data.debug_info else ''
            dpg.set_value("last_packet_text", f"Debug: {last_line}")
        elif data.raw_values:
            raw_str = ' '.join(str(v) for v in data.raw_values[:3])
            dpg.set_value("last_packet_text", f"Valores brutos: {raw_str}...")

    def update_status(self, message: str, color: tuple):
        dpg.set_value("status_text", message)
        dpg.configure_item("status_text", color=color)

    def enable_start_button(self):
        dpg.enable_item("start_btn")
        dpg.disable_item("pause_btn")
        dpg.disable_item("stop_btn")

    def enable_running_controls(self):
        dpg.enable_item("pause_btn")
        dpg.enable_item("stop_btn")
        dpg.disable_item("start_btn")

    def disable_running_controls(self):
        dpg.disable_item("pause_btn")
        dpg.disable_item("stop_btn")
        dpg.enable_item("start_btn")

    def set_button_label(self, button_tag: str, label: str):
        dpg.set_item_label(button_tag, label)

    def create_plot_window(self):
        if dpg.does_item_exist("plot_window"):
            dpg.focus_item("plot_window")
            self.plot_window_open = True
            return

        self.plot_window_open = True
        with dpg.window(
            label="Gráfico em Tempo Real",
            tag="plot_window",
            width=1000,
            height=600,
            on_close=self.close_plot_window
        ):
            with dpg.plot(label="Tensões em Tempo Real", height=-1, width=-1):
                dpg.add_plot_legend()
                x_axis = dpg.add_plot_axis(dpg.mvXAxis, label="Pacote", tag="plot_x_axis")
                y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Tensão (V)", tag="plot_y_axis")

                for ch in range(self.num_channels):
                    series_id = dpg.add_line_series([], [], label=f"CH{ch}", parent=y_axis)
                    self.plot_series_ids[ch] = series_id

    def close_plot_window(self, sender, app_data):
        self.plot_window_open = False
        if dpg.does_item_exist("plot_window"):
            dpg.delete_item("plot_window")

    def create_individual_graphs_window(self):
        if dpg.does_item_exist("individual_graphs_window"):
            dpg.focus_item("individual_graphs_window")
            return

        cols = 5
        rows = (self.num_channels + cols - 1) // cols

        with dpg.window(
            label="Gráficos Individuais por Canal",
            tag="individual_graphs_window",
            width=1200,
            height=700,
            on_close=self.close_individual_graphs_window
        ):
            with dpg.table(
                tag="graphs_table",
                header_row=False,
                resizable=True,
                policy=dpg.mvTable_SizingStretchProp,
                row_background=True,
                borders_innerH=True,
                borders_outerH=True,
                borders_innerV=True,
                borders_outerV=True,
            ):
                for _ in range(cols):
                    dpg.add_table_column()

                for row in range(rows):
                    with dpg.table_row():
                        for col in range(cols):
                            ch = row * cols + col
                            if ch >= self.num_channels:
                                with dpg.table_cell():
                                    dpg.add_spacer(height=10)
                            else:
                                with dpg.table_cell():
                                    with dpg.collapsing_header(label=f"CH{ch}", default_open=True):
                                        with dpg.plot(label=f"", height=200, width=-1, tag=f"plot_ch_{ch}"):
                                            x_axis = dpg.add_plot_axis(dpg.mvXAxis, label="Tempo", tag=f"x_axis_ch_{ch}")
                                            y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="V", tag=f"y_axis_ch_{ch}")
                                            series_id = dpg.add_line_series([], [], parent=y_axis, label=f"CH{ch}")
                                            self.plot_series_ids[f"ch_{ch}"] = series_id

    def close_individual_graphs_window(self, sender, app_data):
        if dpg.does_item_exist("individual_graphs_window"):
            dpg.delete_item("individual_graphs_window")

    def update_plots(self, x_data, y_data):
        if not x_data:
            return

        # Atualizar gráfico principal
        if dpg.does_item_exist("plot_window") and self.plot_series_ids:
            for ch in range(self.num_channels):
                series_key = ch
                if series_key in self.plot_series_ids:
                    y_list = y_data.get(ch, [])
                    min_len = min(len(x_data), len(y_list))
                    if min_len > 0:
                        dpg.set_value(
                            self.plot_series_ids[series_key],
                            [x_data[-min_len:], y_list[-min_len:]]
                        )
            dpg.fit_axis_data("plot_y_axis")
            dpg.fit_axis_data("plot_x_axis")

        # Atualizar gráficos individuais
        if dpg.does_item_exist("individual_graphs_window"):
            for ch in range(self.num_channels):
                key = f"ch_{ch}"
                if key in self.plot_series_ids:
                    y_list = y_data.get(ch, [])
                    min_len = min(len(x_data), len(y_list))
                    if min_len > 0:
                        dpg.set_value(
                            self.plot_series_ids[key],
                            [x_data[-min_len:], y_list[-min_len:]]
                        )
                    dpg.fit_axis_data(f"y_axis_ch_{ch}")
                    dpg.fit_axis_data(f"x_axis_ch_{ch}")