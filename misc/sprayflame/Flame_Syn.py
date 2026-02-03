#!/usr/bin/env python3
"""
Demo‑Reactor‑GUI – Mock controller for a spray‑flame reactor that produces
JSON metadata compliant with *Shemata.json*.

Revision 2025‑06‑08 (c)
──────────────────────
• **NEW**: Date and Time fields now auto‑populate with the current system
  date/time at startup.
• **NEW**: On every “Save Metadata” action, Date and Time are refreshed to
  the current moment before validation and are persisted in the JSON file.
• All improvements from the previous (b) revision are retained: side‑by‑side
  layout, compact window height, dynamic breadth, LEDs, live plot, etc.

Place this script, **Shemata.json** and optional **flame.png** in the same
folder.  Run with:  `python flame_syn.py`
"""
from __future__ import annotations

import json
import re
import random
import datetime as _dt
from pathlib import Path
from collections import deque
from tkinter import (
    Tk,
    Frame,
    Label,
    Entry,
    Button,
    StringVar,
    filedialog,
    messagebox,
    ttk,
    PhotoImage,
    font,
)

import jsonschema

# ─── matplotlib for live plot ────────────────────────────────────────────────
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # type: ignore
import matplotlib.pyplot as plt

# ─── Paths ───────────────────────────────────────────────────────────────────
SCHEMA_PATH = Path(__file__).with_name("nanoparticle_synthesis_conditions.json")
IMAGE_PATH = Path(__file__).with_name("flame.png")  # optional banner image
OUTPUT_DIR = Path(__file__).parent / "runs"
OUTPUT_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Helper / Domain Logic
# ─────────────────────────────────────────────────────────────────────────────

def calc_flame_temp(flow_rate: float) -> float:
    """Linear model: 1 SLM → 1500 °C, 5 SLM → 1300 °C (slope −50 °C/SLM)."""
    return 1550 - 50 * flow_rate


def load_schema() -> dict:
    try:
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        messagebox.showerror("Schema fehlt", f"{SCHEMA_PATH} nicht gefunden!")
        raise SystemExit


def default_values() -> dict:
    """Return start‑up defaults, with Date/Time set to *now*."""
    now = _dt.datetime.now()
    defaults = {
        "FileTypeIdentifier": "This is a EMPI-RF metadata File. Do not change this for crawler identification",
        "Identifier": "Spray-Exp_001",
        "SampleID": "FexOy-0001-BFR",
        "Creator": "Max Mustermann",
        "ORCID": "5558-8885-5589-8569",
        # ↓ Auto‑filled ↓
        "Date": now.date().isoformat(),  # YYYY‑MM‑DD
        "Time": now.time().strftime("%H:%M:%S"),  # HH:MM:SS
        "ReactorType": "Spray Flame Reactor 5",
        "PrecursorSolution": "FeNO3",
        "PrecursorConcentration": 1,
        "SprayFlowRate": 1,
        "CarrierGas": "air",
        "CarrierGasFlowRate": 1,
        "CombustionEquivalenceRatio": 0.8,
        "SchemaID": "nanoparticle_synthesis_conditions",
    }
    defaults["FlameTemperature"] = calc_flame_temp(defaults["CarrierGasFlowRate"])
    return defaults

# ─────────────────────────────────────────────────────────────────────────────
# GUI
# ─────────────────────────────────────────────────────────────────────────────

def build_gui(schema: dict):
    root = Tk()
    root.title("Demo Flame‑Reactor Controller")

    # Bigger fonts for presentation/demo
    default_font = font.nametofont("TkDefaultFont")
    default_font.configure(size=14)
    root.option_add("*Font", default_font)

    # ─── Overall grid: 2 columns (left=form, right=image+plot) ─────────────
    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=1)

    left = Frame(root)
    left.grid(row=0, column=0, sticky="nw", padx=10, pady=10)

    right = Frame(root)
    right.grid(row=0, column=1, sticky="ne", padx=10, pady=10)

    # ─── Optional banner image (created later on Start) ────────────────────
    if IMAGE_PATH.exists():
        try:
            root.flame_img = PhotoImage(file=str(IMAGE_PATH))
        except Exception as exc:
            print("Konnte flame.png nicht laden:", exc)
            root.flame_img = None
    else:
        root.flame_img = None
    root.flame_label = None  # will be created on first reactor start

    form_vars: dict[str, StringVar] = {}
    row_idx = 0
    defaults = default_values()

    # ─── Dynamic form generation from the JSON schema ───────────────────────
    for prop, spec in schema.get("properties", {}).items():
        label_text = prop
        prop_lower = prop.lower()
        if prop_lower.endswith("temperature"):
            label_text += " (°C)"
        elif "flowrate" in prop_lower:
            label_text += " (SLM)"
        elif prop_lower.endswith("concentration"):
            label_text += " (mol/L)"

        Label(left, text=label_text).grid(row=row_idx, column=0, sticky="w", padx=10, pady=4)

        var = StringVar(value=str(defaults.get(prop, spec.get("default", ""))))
        form_vars[prop] = var

        readonly = prop == "FlameTemperature"
        if "enum" in spec and not readonly:
            widget = ttk.Combobox(left, textvariable=var, values=spec["enum"], state="readonly")
        else:
            widget_state = "readonly" if readonly else "normal"
            widget = Entry(left, textvariable=var, width=28, state=widget_state)
        widget.grid(row=row_idx, column=1, padx=10, pady=4)
        row_idx += 1

    # ─── Buttons under the form ─────────────────────────────────────────────
    Button(left, text="Save Metadata", width=20, command=lambda: _save()).grid(row=row_idx, column=0, pady=16)
    Button(left, text="Start Reactor", width=20, command=lambda: _start_reactor()).grid(row=row_idx, column=1, pady=16)
    row_idx += 1
    Button(left, text="Notaus", width=20, command=lambda: _stop_reactor()).grid(row=row_idx, column=0, columnspan=2, pady=4)

    row_idx += 1
    Button(left, text="Beenden", width=20, command=root.destroy).grid(row=row_idx, column=0, columnspan=2, pady=4)

    # ─── Flame‑temperature sensor coupling ──────────────────────────────────
    flow_var = form_vars["CarrierGasFlowRate"]
    temp_var = form_vars["FlameTemperature"]

    def _update_temp_from_flow(*_):
        try:
            fr = float(flow_var.get())
            temp_var.set(f"{calc_flame_temp(fr):.0f}")
        except ValueError:
            temp_var.set("?")

    _update_temp_from_flow()
    flow_var.trace_add("write", _update_temp_from_flow)

    # ─── Live‑Plot setup (in right frame) ───────────────────────────────────
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.set_title("Flame Temperature (live)")
    ax.set_xlabel("t [s]")
    ax.set_ylabel("T [°C]")
    ax.set_ylim(1200, 1600)
    ax.grid(True)
    line, = ax.plot([], [])


    times: deque[int] = deque(maxlen=20)   # statt list[int]
    temps: deque[float] = deque(maxlen=20)

    canvas = FigureCanvasTkAgg(fig, master=right)
    canvas.get_tk_widget().grid(row=1, column=0, pady=5)

    # ─── LED indicators (in right frame) ────────────────────────────────────
    running_led = Label(right, text="Running", width=10, bg="grey", relief="sunken")
    running_led.grid(row=2, column=0, pady=4)

    alarm_led = Label(right, text="Alarm", width=10, bg="grey", relief="sunken")
    alarm_led.grid(row=3, column=0, pady=4)

    # ─── State variables for the inner callbacks ────────────────────────────
    simulation_running: bool = False  # mutable in closure via nonlocal
    blink_state: bool = False
    t_counter: int = 0  # time axis in seconds

    # ────────────────────────────────────────────────────────────────────
    # Callbacks
    # ────────────────────────────────────────────────────────────────────

    def _simulate_step():
        nonlocal blink_state, t_counter
        if not simulation_running:
            return

        # Base temperature from current flow + Gaussian noise ±5 °C
        try:
            fr = float(flow_var.get())
        except ValueError:
            fr = 1.0
        temp_true = calc_flame_temp(fr) + random.gauss(0, 5)
        temp_var.set(f"{temp_true:.0f}")

        # Update live‑plot data
        times.append(t_counter)
        temps.append(temp_true)
        t_counter += 1
        line.set_data(list(times), list(temps))
        if len(times) >= 2:
            ax.set_xlim(times[0], times[-1])        # normale Skalierung
        else:
            ax.set_xlim(times[0] - 0.5, times[0] + 0.5)  # kleiner Puffer für den 1-Punkt-Fall
        canvas.draw_idle()

        # Blink «Running» LED (green/darkgreen)
        blink_state = not blink_state
        running_led.configure(bg="green" if blink_state else "darkgreen")

        # Alarm LED logic – temp outside 1300–1550 °C
        if temp_true < 1300 or temp_true > 1550:
            curr = alarm_led.cget("bg")
            alarm_led.configure(bg="red" if curr != "red" else "darkred")
        else:
            alarm_led.configure(bg="grey")

        root.after(1000, _simulate_step)

    # ------------------------------------------------------------------
    def _save():
        """Validate and write metadata – refreshing Date/Time just in time."""
        # Update Date and Time *right now*
        now = _dt.datetime.now()
        form_vars["Date"].set(now.date().isoformat())
        form_vars["Time"].set(now.time().strftime("%H:%M:%S"))

        _update_temp_from_flow()
        data = {k: _coerce(v.get()) for k, v in form_vars.items()}
        try:
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.ValidationError as err:
            messagebox.showerror("Validierungsfehler", str(err))
            return

        fname = f"{data['Identifier']}_{now.strftime('%Y%m%d_%H%M%S')}.json"
        path = filedialog.asksaveasfilename(
            initialdir=OUTPUT_DIR,
            initialfile=fname,
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        messagebox.showinfo("Gespeichert", f"Metadaten gespeichert unter:\n{path}")

        # Auto-increment trailing number in Identifier
        cur_id = form_vars["Identifier"].get()
        match = re.search(r"(\d+)$", cur_id)
        if match:
            s_num = match.group(1)
            n_next = int(s_num) + 1
            # Preserve zero-padding length
            s_next = f"{n_next:0{len(s_num)}d}"
            new_id = cur_id[:match.start()] + s_next
            form_vars["Identifier"].set(new_id)

    # ------------------------------------------------------------------
    def _start_reactor():
        nonlocal simulation_running, t_counter
        if simulation_running:
            return  # already running
        simulation_running = True
        t_counter = 0
        times.clear()
        temps.clear()
        running_led.configure(bg="green")
        alarm_led.configure(bg="grey")

        if root.flame_img is not None and root.flame_label is None:
            root.flame_label = Label(right, image=root.flame_img)
            root.flame_label.grid(row=0, column=0, pady=(0, 10))
        _simulate_step()

    # ------------------------------------------------------------------
    def _stop_reactor():
        nonlocal simulation_running
        if not simulation_running:
            return
        simulation_running = False
        running_led.configure(bg="grey")
        alarm_led.configure(bg="grey")
        messagebox.showinfo("Reactor", "⛔ Reaktor gestoppt (Demo)")

    # ------------------------------------------------------------------
    root.mainloop()

# ─────────────────────────────────────────────────────────────────────────────
# Type helpers
# ─────────────────────────────────────────────────────────────────────────────

def _coerce(value: str):
    """Convert numeric strings to int/float where applicable."""
    try:
        if any(ch in value for ch in ".eE"):
            return float(value)
        return int(value)
    except ValueError:
        return value

# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    build_gui(load_schema())
