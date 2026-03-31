# ===============================================
# Combined Abaqus ODB Processing + Post-Processing
# ===============================================

from abaqus import *
from abaqusConstants import *
from odbAccess import openOdb
import os, csv
import tkinter as tk
from tkinter import filedialog
import numpy as np

APP_VERSION = "2.0.0-wip"

# =========================
# USER SETTINGS
# =========================
folder_path = r"C:\Users\borism\Desktop\Claude Inp file"
step_name = "Load-to-Failure"
target_load = 350000.0   # N
peeq_threshold = 1e-6
output_summary = "SUMMARY_RESULTS.csv"
output_curves_folder = "CURVES"
output_combined_curve = "COMBINED_LOAD_DISPLACEMENT.csv"
output_images_folder = "IMAGES"
output_thickness_images_folder = "THICKNESS_IMAGES"
image_modes = ["S_MISES"]
MIDSPAN_SET = "N-MIDSPAN-BOT"
SUPPORT_SET = "N-SUPPORT"
NUM_SUPPORTS = 2  # If SUPPORT_SET contains one support line, scale RF2 to total test load
ELSETS = {
    "BF": "E-BF-MIDSPAN",
    "TF": "E-TF-MIDSPAN",
    "WEB": "E-WEB-LOADPT"
}


def select_odb_folder(default_folder):
    """
    Select ODB folder with a GUI picker when possible.
    Falls back to default/current directory in non-GUI sessions.
    """
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder = filedialog.askdirectory(title="Select folder containing .odb files")
        root.destroy()
        if folder:
            return folder
    except Exception as e:
        print("[WARN] Folder picker unavailable in this Abaqus session: {}".format(e))

    cwd = os.getcwd()
    default_has_odb = os.path.isdir(default_folder) and any(f.endswith(".odb") for f in os.listdir(default_folder))
    cwd_has_odb = os.path.isdir(cwd) and any(f.endswith(".odb") for f in os.listdir(cwd))

    if default_has_odb:
        print("[INFO] Using default folder_path: {}".format(default_folder))
        return default_folder
    if cwd_has_odb:
        print("[INFO] Default folder has no ODB files; using current directory: {}".format(cwd))
        return cwd

    print("[INFO] Using default folder_path: {}".format(default_folder))
    return default_folder

# =========================
# ======== FUNCTIONS ======
# =========================

def safe_get_step(odb):
    if step_name in odb.steps.keys():
        return odb.steps[step_name]
    else:
        first_step_name = list(odb.steps.keys())[0]
        return odb.steps[first_step_name]
# -------------------------
# Curve extraction
# -------------------------
def extract_curve_data(step, odb):
    disp, load = [], []
    disp_region = odb.rootAssembly.nodeSets[MIDSPAN_SET]
    node_sets = odb.rootAssembly.nodeSets

    if SUPPORT_SET in node_sets.keys():
        rf_regions = [node_sets[SUPPORT_SET]]
        rf_scale = NUM_SUPPORTS
    else:
        support_like = sorted([k for k in node_sets.keys() if "SUPPORT" in k.upper()])
        rp_like = sorted([k for k in node_sets.keys() if "RP" in k.upper()])
        fallback_names = support_like if support_like else rp_like
        if not fallback_names:
            raise KeyError(
                "Support node set '{}' not found. Available node sets: {}".format(
                    SUPPORT_SET, ", ".join(sorted(node_sets.keys()))
                )
            )
        print("[WARN] '{}' not found. Using support-like sets: {} (no extra scaling).".format(
            SUPPORT_SET, ", ".join(fallback_names)
        ))
        rf_regions = [node_sets[name] for name in fallback_names]
        rf_scale = 1.0

    for frame in step.frames:
        u = frame.fieldOutputs["U"].getSubset(region=disp_region)
        rf2 = 0.0
        for rf_region in rf_regions:
            rf = frame.fieldOutputs["RF"].getSubset(region=rf_region)
            rf2 += sum([v.data[1] for v in rf.values])

        u2 = max([abs(v.data[1]) for v in u.values])

        disp.append(u2)
        load.append(abs(rf2) * rf_scale)
    return np.array(disp), np.array(load)

# -------------------------
# Stiffness
# -------------------------
def compute_stiffness(disp, load):
    n = max(5, int(0.1 * len(disp)))
    if n < 2: return None
    try:
        coeffs = np.polyfit(disp[:n], load[:n], 1)
        return coeffs[0] / 1000.0  # kN/mm
    except:
        return None

# -------------------------
# First yield detection
# -------------------------
def detect_first_yield(step):
    for frame in step.frames:
        if "PEEQ" not in frame.fieldOutputs:
            continue
        peeq = frame.fieldOutputs["PEEQ"]
        if any(v.data > peeq_threshold for v in peeq.values):
            return frame.frameValue
    return None

# -------------------------
# Local metrics
# -------------------------
# -------------------------
# Local metrics extraction (robust)
# -------------------------
def extract_local_metrics(step, odb):
    max_stress = 0.0
    max_peeq = 0.0
    failure_zone = "UNKNOWN"

    # Check each ELSET, fallback to ALL ELEMENTS if missing
    for zone, elset_name in ELSETS.items():
        try:
            # Instance prefix required
            region = odb.rootAssembly.elementSets[f"IBEAM-1.{elset_name}"]
        except KeyError:
            # fallback to all elements
            region = odb.rootAssembly.elementSets[' ALL ELEMENTS']

        for frame in step.frames:
            # --- Stress (S) ---
            if "S" in frame.fieldOutputs:
                s = frame.fieldOutputs["S"].getSubset(region=region)
                for v in s.values:
                    mises = v.mises
                    if mises > max_stress:
                        max_stress = mises
                        failure_zone = zone  # mark which zone reached max

            # --- Plastic strain (PEEQ) ---
            if "PEEQ" in frame.fieldOutputs:
                peeq = frame.fieldOutputs["PEEQ"].getSubset(region=region)
                for v in peeq.values:
                    # v.data might be a float or tuple, handle both
                    val = v.data if isinstance(v.data, float) else v.data[0]
                    if val > max_peeq:
                        max_peeq = val

    return max_stress, max_peeq, failure_zone
# -------------------------
# Energy absorption
# -------------------------
def compute_energy(disp, load):
    return np.trapz(load, disp)/1000.0  # kN.mm

# -------------------------
# Stress image export
# -------------------------
def find_closest_frame(step, target_lpf):
    return min(step.frames, key=lambda f: abs(f.frameValue - target_lpf))

def set_primary_variable(vp, frame, mode):
    """
    Configure viewport primary variable for a requested image mode.
    """
    if mode == "S_MISES":
        vp.odbDisplay.setPrimaryVariable(
            variableLabel='S',
            outputPosition=INTEGRATION_POINT,
            refinement=(INVARIANT, 'Mises')
        )
        return "S_MISES"

    if mode == "STH":
        # Abaqus shell thickness field output labels can vary by setup/version.
        # Try common labels in order and use the first one that exists.
        available = frame.fieldOutputs.keys()
        candidates = ["STH", "H", "THICKNESS"]
        found = [c for c in candidates if c in available]
        if not found:
            raise KeyError("No shell thickness field found (tried: STH, H, THICKNESS)")

        field_label = found[0]
        for pos in (INTEGRATION_POINT, ELEMENT_NODAL, CENTROID):
            try:
                vp.odbDisplay.setPrimaryVariable(variableLabel=field_label, outputPosition=pos)
                return field_label
            except Exception:
                continue
        raise RuntimeError(f"Thickness variable '{field_label}' found but could not be displayed")

    raise ValueError(f"Unsupported image mode: {mode}")


def export_image(odb_path, target_lpf, mode):
    job_name = os.path.basename(odb_path).replace(".odb", "")
    odb = openOdb(path=odb_path)  # <-- use openOdb

    try:
        step = safe_get_step(odb)
        used_step_name = step.name

        vp_name = f"VP_{job_name}_{mode}_{target_lpf:.2f}".replace(".", "p")
        vp = session.Viewport(name=vp_name, origin=(0,0), width=200, height=150)
        vp.setValues(displayedObject=odb)

        frame = find_closest_frame(step, target_lpf)
        vp.odbDisplay.setFrame(step=used_step_name, frame=frame.incrementNumber)
        resolved_mode = set_primary_variable(vp, frame, mode)
        vp.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF,))
        vp.view.fitView()

        if not os.path.exists(output_images_folder):
            os.makedirs(output_images_folder)

        file_path = os.path.join(output_images_folder, f"{job_name}_{resolved_mode}_LPF_{target_lpf:.2f}.png")
        session.printToFile(fileName=file_path, format=PNG, canvasObjects=(vp,))
    finally:
        odb.close()


def export_initial_thickness_image(odb_path):
    job_name = os.path.basename(odb_path).replace(".odb", "")
    odb = openOdb(path=odb_path)

    try:
        step = safe_get_step(odb)
        used_step_name = step.name
        initial_frame = step.frames[0]

        vp_name = f"VP_{job_name}_THICKNESS_INITIAL".replace(".", "p")
        vp = session.Viewport(name=vp_name, origin=(0,0), width=200, height=150)
        vp.setValues(displayedObject=odb)
        vp.odbDisplay.setFrame(step=used_step_name, frame=initial_frame.incrementNumber)

        try:
            resolved_mode = set_primary_variable(vp, initial_frame, "STH")
            vp.odbDisplay.display.setValues(plotState=(CONTOURS_ON_UNDEF,))
        except Exception:
            resolved_mode = "THICKNESS_INITIAL_GEOMETRY"
            vp.odbDisplay.display.setValues(plotState=(UNDEFORMED,))
            print(f"[WARN THICKNESS] {job_name}: shell thickness field missing, exported initial geometry only.")

        vp.view.fitView()

        if not os.path.exists(output_thickness_images_folder):
            os.makedirs(output_thickness_images_folder)
        file_path = os.path.join(output_thickness_images_folder, f"{job_name}_{resolved_mode}.png")
        session.printToFile(fileName=file_path, format=PNG, canvasObjects=(vp,))
    finally:
        odb.close()


def export_combined_curve_plot(results, output_plot="COMBINED_LOAD_DISPLACEMENT"):
    xyplot_name = "XYPlot_COMBINED_LD"
    vp_name = "VP_COMBINED_LD"
    if xyplot_name in session.xyPlots:
        del session.xyPlots[xyplot_name]
    if vp_name in session.viewports:
        del session.viewports[vp_name]

    xyplot = session.XYPlot(name=xyplot_name)
    chart_key = xyplot.charts.keys()[0]
    chart = xyplot.charts[chart_key]

    curves = []
    for row in results:
        disp = row.get("Curve Disp (mm)", [])
        load = row.get("Curve Load (kN)", [])
        if not disp or not load:
            continue
        xy_name = "LD_" + row["Job"]
        if xy_name in session.xyDataObjects:
            del session.xyDataObjects[xy_name]
        pairs = tuple((float(d), float(l)) for d, l in zip(disp, load))
        xy_data = session.XYData(data=pairs, name=xy_name)
        curves.append(session.Curve(xyData=xy_data))

    if not curves:
        print("[WARN] No curve data available for combined plot.")
        return

    chart.setValues(curvesToPlot=tuple(curves))
    vp = session.Viewport(name=vp_name, origin=(0, 0), width=200, height=150)
    vp.setValues(displayedObject=xyplot)
    vp.view.fitView()
    session.printToFile(fileName=output_plot, format=PNG, canvasObjects=(vp,))
    print(f"[OK] Combined load-displacement plot written to {output_plot}.png")
# -------------------------
# Single ODB processing
# -------------------------
def process_odb(odb_file):
    job_name = odb_file.replace(".odb","")
    print(f"[PROCESSING] {job_name}")
    odb = openOdb(odb_file)
    step = safe_get_step(odb)

    # Curve
    disp, load = extract_curve_data(step, odb)
    max_disp = float(np.max(disp))
    peak_load = float(np.max(load)/1000.0)
    peak_lpf = float(step.frames[int(np.argmax(load))].frameValue)
    yield_lpf = detect_first_yield(step)
    yield_load = None
    if yield_lpf is not None:
        closest_idx = int(np.argmin(np.abs(np.array([f.frameValue for f in step.frames]) - yield_lpf)))
        yield_load = float(load[closest_idx] / 1000.0)
    stiffness = compute_stiffness(disp, load)
    energy = compute_energy(disp, load)
    max_stress, max_peeq, failure_zone = extract_local_metrics(step, odb)
    odb.close()

    # Save curve
    if not os.path.exists(output_curves_folder): os.makedirs(output_curves_folder)
    curve_file = os.path.join(output_curves_folder, f"{job_name}_curve.csv")
    with open(curve_file,"w",newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Disp (mm)", "Load (kN)"])
        for d,l in zip(disp,load): writer.writerow([d, l/1000.0])

    return {
        "Job": job_name,
        "Yield Load (kN)": yield_load,
        "Yield LPF": yield_lpf,
        "Peak Load (kN)": peak_load,
        "Peak Load LPF": peak_lpf,
        "Max Disp (mm)": max_disp,
        "Stiffness (kN/mm)": stiffness,
        "Energy (kN.mm)": energy,
        "Max Stress (MPa)": max_stress,
        "Max PEEQ": max_peeq,
        "Failure Zone": failure_zone,
        "Curve Disp (mm)": disp.tolist(),
        "Curve Load (kN)": (load / 1000.0).tolist()
    }


def export_combined_curve(results):
    with open(output_combined_curve, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Job", "Disp (mm)", "Load (kN)"])
        for row in results:
            disp = row.get("Curve Disp (mm)", [])
            load = row.get("Curve Load (kN)", [])
            for d, l in zip(disp, load):
                writer.writerow([row["Job"], d, l])
    print(f"[OK] Combined load-displacement data written to {output_combined_curve}")

# =========================
# ======== MAIN ===========
# =========================
folder_path = select_odb_folder(folder_path)
if not os.path.isdir(folder_path):
    raise FileNotFoundError(f"Folder does not exist: {folder_path}")

os.chdir(folder_path)
odb_files = [f for f in os.listdir() if f.endswith(".odb")]
print(f"[INFO] Found {len(odb_files)} ODB files in: {folder_path}")

# -------------------------
# PROCESSING
# -------------------------
results = []
for odb_file in odb_files:
    try:
        results.append(process_odb(odb_file))
    except Exception as e:
        print(f"[ERROR] {odb_file}: {e}")

# -------------------------
# POST-PROCESSING: Save CSV
# -------------------------
if results:
    export_combined_curve(results)
    export_combined_curve_plot(results)
    cleaned_results = []
    for row in results:
        reduced = dict(row)
        reduced.pop("Curve Disp (mm)", None)
        reduced.pop("Curve Load (kN)", None)
        cleaned_results.append(reduced)
    keys = cleaned_results[0].keys()
    with open(output_summary, "w",newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(cleaned_results)
    print(f"\n[OK] Summary written to {output_summary}")

# -------------------------
# POST-PROCESSING: Export images
# -------------------------
for odb_file in odb_files:
    odb_result = next((r for r in results if r["Job"] == odb_file.replace(".odb", "")), None)
    if not odb_result:
        continue
    stress_targets = [odb_result["Peak Load LPF"]]
    if odb_result["Yield LPF"] is not None:
        stress_targets = [odb_result["Yield LPF"], odb_result["Peak Load LPF"]]
    for mode in image_modes:
        for lpf in stress_targets:
            try:
                export_image(odb_file, lpf, mode)
            except Exception as e:
                print(f"[ERROR IMAGE] {odb_file} [{mode} @ LPF={lpf}]: {e}")

# Thickness images in a dedicated folder
for odb_file in odb_files:
    try:
        export_initial_thickness_image(odb_file)
    except Exception as e:
        print(f"[ERROR THICKNESS IMAGE] {odb_file}: {e}")

print("\n[OK] Images exported")
