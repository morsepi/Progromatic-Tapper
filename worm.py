import serial
import time
import tkinter as tk
from tkinter import messagebox, ttk
import threading
from serial.tools import list_ports

# LCUS-1 Settings
BAUD_RATE = 9600
RELAY_ON = bytes([0xA0, 0x01, 0x01, 0xA2])  # ON command
RELAY_OFF = bytes([0xA0, 0x01, 0x00, 0xA1]) # OFF command

class TapperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("WormLab Tapper GUI")
        
        # Discover available USB serial ports
        available_ports = [port.device for port in list_ports.comports()]
        if not available_ports:
            available_ports = ['No devices found']
        
        # Variables with defaults matching requirements (interval 10s, taps 30)
        self.serial_port = tk.StringVar(value=available_ports[0])  # Default to first port
        self.interval_sec = tk.DoubleVar(value=10.0)  # Default interval (every 10s)
        self.tap_count = tk.IntVar(value=30)          # Default number of taps
        self.tap_duration = tk.DoubleVar(value=0.1)   # Default force (duration)
        self.session_time = tk.StringVar(value="00:00:00")  # Display elapsed time
        self.taps_done = tk.IntVar(value=0)           # Display taps completed
        self.is_running = False
        self.is_paused = False
        self.elapsed_time = 0
        self.start_time = None
        self.tap_thread = None
        self.timer_thread = None
        self.ser = None  # Serial connection, opened dynamically
        
        # GUI Elements
        tk.Label(root, text="USB Serial Port:").grid(row=0, column=0, padx=10, pady=5)
        self.port_dropdown = ttk.Combobox(root, textvariable=self.serial_port, values=available_ports)
        self.port_dropdown.grid(row=0, column=1)
        
        tk.Label(root, text="Interval (s):").grid(row=1, column=0, padx=10, pady=5)
        tk.Entry(root, textvariable=self.interval_sec).grid(row=1, column=1)
        
        tk.Label(root, text="Tap Count (0 for unlimited):").grid(row=2, column=0, padx=10, pady=5)
        tk.Entry(root, textvariable=self.tap_count).grid(row=2, column=1)
        
        tk.Label(root, text="Force (tap duration s):").grid(row=3, column=0, padx=10, pady=5)
        tk.Entry(root, textvariable=self.tap_duration).grid(row=3, column=1)
        
        tk.Label(root, text="Session Timer:").grid(row=4, column=0, padx=10, pady=5)
        tk.Label(root, textvariable=self.session_time).grid(row=4, column=1)
        
        tk.Label(root, text="Taps Completed:").grid(row=5, column=0, padx=10, pady=5)
        tk.Label(root, textvariable=self.taps_done).grid(row=5, column=1)
        
        self.start_button = tk.Button(root, text="Start", command=self.start_tapping)
        self.start_button.grid(row=6, column=0, pady=10)
        
        self.stop_button = tk.Button(root, text="Stop", command=self.stop_tapping, state=tk.DISABLED)
        self.stop_button.grid(row=6, column=1, pady=10)
        
        # Bind space bar to pause/resume
        root.bind('<space>', self.toggle_pause)
    
    def tap_solenoid(self):
        self.ser.write(RELAY_ON)
        time.sleep(self.tap_duration.get())
        self.ser.write(RELAY_OFF)
    
    def tapping_loop(self):
        taps_done = 0
        max_taps = self.tap_count.get()
        while self.is_running and (max_taps == 0 or taps_done < max_taps):
            if not self.is_paused:
                self.tap_solenoid()
                taps_done += 1
                self.taps_done.set(taps_done)
                time.sleep(self.interval_sec.get() - self.tap_duration.get())
            else:
                time.sleep(0.1)  # Wait while paused
        self.stop_tapping()
    
    def update_timer(self):
        while self.is_running:
            if not self.is_paused and self.start_time:
                self.elapsed_time = time.time() - self.start_time
                hours, rem = divmod(self.elapsed_time, 3600)
                mins, secs = divmod(rem, 60)
                self.session_time.set(f"{int(hours):02d}:{int(mins):02d}:{int(secs):02d}")
            time.sleep(1)
    
    def start_tapping(self):
        if not self.is_running:
            try:
                # Open serial connection
                port = self.serial_port.get()
                if port == 'No devices found':
                    raise serial.SerialException("No USB devices available")
                self.ser = serial.Serial(port, BAUD_RATE, timeout=1)
                
                interval = self.interval_sec.get()
                duration = self.tap_duration.get()
                if interval <= duration:
                    raise ValueError("Interval must be greater than tap duration")
                
                self.is_running = True
                self.is_paused = False
                self.start_time = time.time()
                self.elapsed_time = 0
                self.taps_done.set(0)  # Reset taps done
                self.tap_thread = threading.Thread(target=self.tapping_loop)
                self.tap_thread.start()
                self.timer_thread = threading.Thread(target=self.update_timer)
                self.timer_thread.start()
                
                self.start_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.NORMAL)
            except ValueError as ve:
                messagebox.showerror("Input Error", str(ve))
                self.close_serial()
            except serial.SerialException as se:
                messagebox.showerror("Serial Error", f"Failed to open serial port: {se}")
                self.close_serial()
    
    def stop_tapping(self):
        self.is_running = False
        self.is_paused = False
        self.start_time = None
        self.session_time.set("00:00:00")
        self.taps_done.set(0)  # Reset taps done
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        if self.tap_thread:
            self.tap_thread.join()
        if self.timer_thread:
            self.timer_thread.join()
        self.close_serial()
    
    def toggle_pause(self, event=None):
        if self.is_running:
            self.is_paused = not self.is_paused
            status = "paused" if self.is_paused else "resumed"
            messagebox.showinfo("Pause", f"Tapping {status}. Press space to toggle.")
    
    def close_serial(self):
        if self.ser:
            self.ser.close()
            self.ser = None

if __name__ == "__main__":
    root = tk.Tk()
    app = TapperApp(root)
    root.mainloop()
