
#!/usr/bin/env python3
"""demo_raman_gui.py – Mock Raman‑Spectrometer Controller
----------------------------------------------------------
*Displays a simple GUI to enter metadata, simulate a two‑peak Raman spectrum,
 and save both spectrum (CSV) and metadata (JSON) in a per‑measurement folder.*

Revision 2025‑06‑07 (d)
───────────────────────
• Auto‑fill Date & Time on launch and on every acquisition.
• Intensity ratio of two peaks increases from 1:1 to 1:10 over 10 acquisitions.
• Each measurement stored in its own sub‑folder under `spectra/`.
• GUI: left – metadata fields; right – live plot of the last spectrum.
"""

import json
import tkinter as tk
from tkinter import ttk, messagebox
import pathlib, datetime, os, math
import jsonschema
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

SCHEMA_PATH = pathlib.Path(__file__).with_name('jsonschema-raman.json')
FORM_DEFAULTS_PATH = pathlib.Path(__file__).with_name('formdata-raman.json')
OUTPUT_DIR = pathlib.Path('spectra')
OUTPUT_DIR.mkdir(exist_ok=True)

with SCHEMA_PATH.open() as f:
    SCHEMA = json.load(f)

if FORM_DEFAULTS_PATH.exists():
    with FORM_DEFAULTS_PATH.open() as f:
        FORM_DEFAULTS = json.load(f)
else:
    FORM_DEFAULTS = {}

# Keep global count of saved spectra to adjust intensity ratio
class RatioTracker:
    def __init__(self):
        self.count = 0

    def next_ratio(self):
        # linear 1,2,...,10 then clamp
        r = min(1 + self.count, 10)
        self.count += 1
        return r

ratio_tracker = RatioTracker()

NUM_FIELDS = list(SCHEMA.get('properties', {}).keys())

NUMERIC_TYPES = {
    'number': float,
    'integer': int,
}

def is_numeric(prop):
    t = SCHEMA['properties'][prop].get('type')
    return t in NUMERIC_TYPES

class RamanGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Demo Raman Spectrometer')
        # Main frames
        self.form_frame = ttk.Frame(self)
        self.form_frame.grid(row=0, column=0, sticky='nsw')
        self.plot_frame = ttk.Frame(self)
        self.plot_frame.grid(row=0, column=1, sticky='nse')
        # Build form
        self.entries = {}
        row = 0
        font_lbl = ('Arial', 12)
        font_ent = ('Arial', 12)
        for prop in NUM_FIELDS:
            lbl_text = prop
            # Add unit if description contains it (simple heuristic)
            desc = SCHEMA['properties'][prop].get('description', '')
            if '(' in desc:
                lbl_text += ' ' + desc[desc.find('('):].split(')')[0] + ')'
            label = ttk.Label(self.form_frame, text=lbl_text, font=font_lbl)
            label.grid(row=row, column=0, sticky='e', pady=2, padx=4)
            var = tk.StringVar()
            entry = ttk.Entry(self.form_frame, textvariable=var, font=font_ent, width=25)
            entry.grid(row=row, column=1, sticky='w', pady=2, padx=4)
            self.entries[prop] = (var, entry)
            row += 1

        # Action buttons
        self.acquire_btn = ttk.Button(self.form_frame, text='Acquire Spectrum', command=self.acquire)
        self.acquire_btn.grid(row=row, column=0, columnspan=2, pady=6)
        row += 1

        # Figure
        self.figure = Figure(figsize=(5,4), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_xlabel('Raman shift (cm⁻¹)')
        self.ax.set_ylabel('Intensity (a.u.)')
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

        self.populate_defaults()

    def populate_defaults(self):
        for prop, (var, _) in self.entries.items():
            if prop in ('Date', 'Time'):
                # auto-fill later
                continue
            default = FORM_DEFAULTS.get(prop, '')
            var.set(str(default))

    def update_datetime(self):
        now = datetime.datetime.now()
        if 'Date' in self.entries:
            self.entries['Date'][0].set(now.strftime('%Y-%m-%d'))
        if 'Time' in self.entries:
            self.entries['Time'][0].set(now.strftime('%H:%M:%S'))

    def gather_metadata(self):
        self.update_datetime()
        data = {}
        errors = []
        for prop, (var, _) in self.entries.items():
            val = var.get()
            if val == '':
                continue
            # cast numeric
            if is_numeric(prop):
                try:
                    val = NUMERIC_TYPES[SCHEMA['properties'][prop]['type']](val)
                except ValueError:
                    errors.append(f'{prop} must be numeric')
            data[prop] = val
        return data, errors

    def validate_metadata(self, data):
        jsonschema.validate(instance=data, schema=SCHEMA)

    def acquire(self):
        # gather + validate metadata
        data, errors = self.gather_metadata()
        if errors:
            messagebox.showerror('Input Error', '\n'.join(errors))
            return
        try:
            self.validate_metadata(data)
        except jsonschema.ValidationError as e:
            messagebox.showerror('Validation Error', str(e))
            return

        # Simulate spectrum
        ratio = ratio_tracker.next_ratio()
        shift = np.linspace(1000, 2000, 2000)
        peak1_center, peak2_center = 1350, 1580
        width = 15
        peak1 = np.exp(-(shift - peak1_center)**2/(2*width**2))
        peak2 = np.exp(-(shift - peak2_center)**2/(2*width**2)) * ratio
        noise = np.random.normal(0, 0.02, shift.shape)
        intensity = peak1 + peak2 + noise

        # Plot
        self.ax.clear()
        self.ax.plot(shift, intensity)
        self.ax.set_xlabel('Raman shift (cm⁻¹)')
        self.ax.set_ylabel('Intensity (a.u.)')
        self.ax.set_title(f'Ratio peak2/peak1 = {ratio:.0f}:1')
        self.figure.tight_layout()
        self.canvas.draw()

        # Save files
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        identifier = data.get('Identifier', 'UNNAMED')
        folder = OUTPUT_DIR / f'{identifier}_{timestamp}'
        folder.mkdir(parents=True, exist_ok=True)
        # CSV
        csv_path = folder / f'{identifier}_{timestamp}.csv'
        np.savetxt(csv_path, np.column_stack((shift, intensity)), delimiter=',', header='shift,intensity', comments='')
        # JSON metadata
        json_path = folder / f'{identifier}_{timestamp}.json'
        with json_path.open('w') as f:
            json.dump(data, f, indent=2)

        messagebox.showinfo('Saved', f'Spectrum & metadata saved to\n{folder}')

if __name__ == '__main__':
    app = RamanGUI()
    app.mainloop()
