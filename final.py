import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import psutil
import time
import os
from collections import defaultdict
import subprocess
import glob
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

class CPUMonitor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CPU Core Monitor")
        self.geometry("1600x1000")
        self.max = -1
        self.count = 0

        # Create main container
        self.main_container = ttk.Frame(self)
        self.main_container.pack(expand=True, fill="both", padx=10, pady=10)

        # Get number of CPU cores
        self.num_cores = psutil.cpu_count(logical=True)

        # Initialize data storage
        self.time_points = []
        self.core_data = {
            'usage': defaultdict(list),
            'temp': defaultdict(list),
            'freq': defaultdict(list),
            'power': defaultdict(list)  # New metric for power consumption
        }

        # Create frames for each metric type
        self.create_metric_frames()

        # Start monitoring
        self.after(100, self.update_metrics)

    def create_metric_frames(self):
        metrics = [
            ("CPU Usage (%)", 'usage'),
            ("Temperature (\u00b0C)", 'temp'),
            ("Frequency (MHz)", 'freq'),
            ("Power Consumption (Watts)", 'power'),  # New frame for power consumption
            ("System Info", 'info')
        ]

        self.figures = {}
        self.axes = {}
        self.canvases = {}

        for i, (title, metric) in enumerate(metrics):
            frame = ttk.LabelFrame(self.main_container, text=title, padding=(10, 5))
            frame.grid(row=i // 2, column=i % 2, padx=5, pady=5, sticky="nsew")

            if metric != 'info':
                fig, ax = plt.subplots(figsize=(6, 4))
                canvas = FigureCanvasTkAgg(fig, master=frame)
                canvas.draw()
                canvas.get_tk_widget().pack(expand=True, fill="both")

                self.figures[metric] = fig
                self.axes[metric] = ax
                self.canvases[metric] = canvas
            else:
                # Add label to display names only
                info_label = tk.Label(frame, text=self.get_names(), font=("Helvetica", 18), justify="left", fg="blue",
                                      bg="lightgray")
                info_label.pack(anchor="nw")

            self.main_container.grid_columnconfigure(i % 2, weight=1)
            self.main_container.grid_rowconfigure(i // 2, weight=1)

    def get_names(self):
        """Return the specified names for the system info section."""
        return "BY:\nPreksha - 2023300193\nShivsharan - 2023300194"

    def read_temperatures(self):
        temperatures = {}
        try:
            # Run sensors command and parse output
            result = subprocess.run(['sensors'], capture_output=True, text=True)
            output = result.stdout

            count = 0
            # Parse the output to get core temperatures
            for line in output.split('\n'):
                if 'Core' in line:
                    # Extract core number and temperature
                    parts = line.split(':')
                    if len(parts) >= 2:
                        #core_num = int(''.join(filter(str.isdigit, parts[0])))
                        temp = float(parts[1].split()[0].strip('+\u00b0C'))
                        temperatures[f'Core {count}'] = temp
                    count +=1

        except Exception as e:
            print(f"Error reading temperatures: {e}")

        return temperatures

    def read_power_consumption(self):
        power_data = {}
        password = "1853"  # Replace with your sudo password
        num_cores = psutil.cpu_count(logical=True)

        def run_perf(core):
            """Run perf command for a specific core."""
            try:
                result = subprocess.run(
                    ['sudo', '-S', 'perf', 'stat', '-C', f"{core}", '-e', 'power/energy-cores/', 'sleep', '1'],
                    input=f"{password}\n",
                    capture_output=True,
                    text=True
                )
                if result.stderr:
                    for line in result.stderr.split("\n"):
                        if "Joules" in line:
                            parts = line.split()
                            joules = float(parts[0])  # Extract the energy in Joules
                            return (f"Core {core}", joules / 1.0)  # Convert to Watts (Joules/Seconds)
            except Exception as e:
                print(f"Error for Core {core}: {e}")
            return (f"Core {core}", None)

        # Use ThreadPoolExecutor for parallel execution
        with ThreadPoolExecutor(max_workers=num_cores) as executor:
            results = list(executor.map(run_perf, range(num_cores)))

        # Populate power_data with results
        for core, power in results:
            if power is not None:
                power_data[core] = power

        return power_data

    def update_plot(self, metric_type, data):
        ax = self.axes[metric_type]
        ax.clear()
        colors = plt.cm.rainbow(np.linspace(0, 1, self.num_cores))
        for (core, values), color in zip(self.core_data[metric_type].items(), colors):
            if values:  # Only plot if we have data
                ax.plot(self.time_points, values, label=core, color=color, linewidth=2)
        ax.set_title(f'Per-Core {metric_type.title()}')
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.legend(loc='center left', bbox_to_anchor=(1, 0.5), fontsize='small')
        if metric_type == 'usage':
            ax.set_ylim(0, 100)
        elif metric_type == 'temp':
            ax.set_ylim(30, 100)
        elif metric_type == 'freq':
            ax.set_ylim(0, 5000)
        elif metric_type == 'power':
            ax.set_ylim(0, 5)  # Adjust based on expected power range
        self.figures[metric_type].tight_layout()
        self.canvases[metric_type].draw()

    def get_core_metrics(self):
        metrics = {
            'usage': {},
            'temp': {},
            'freq': {},
            'power': {}  # New metric for power consumption
        }
        cpu_usage = psutil.cpu_percent(interval=None, percpu=True)
        for i in range(self.num_cores):
            metrics['usage'][f'Core {i}'] = cpu_usage[i]
        cpu_freq = psutil.cpu_freq(percpu=True)
        if cpu_freq:
            for i in range(self.num_cores):
                metrics['freq'][f'Core {i}'] = cpu_freq[i].current
        temperatures = self.read_temperatures()
        metrics['temp'] = temperatures

        # Add power consumption data
        metrics['power'] = self.read_power_consumption()

        return metrics

    def update_metrics(self):
        self.time_points.append(len(self.time_points))
        metrics = self.get_core_metrics()

        for metric_type, core_values in metrics.items():
            for core, value in core_values.items():
                self.core_data[metric_type][core].append(value)

        for metric_type in self.core_data:
            self.update_plot(metric_type, self.core_data[metric_type])

        write = not os.path.exists("data.csv")
        df = pd.DataFrame(metrics).T
        df.to_csv("data.csv",mode="a",header=write)
        #self.count+=1
        self.after(1000, self.update_metrics)


if __name__ == "__main__":
    app = CPUMonitor()
    app.mainloop()
