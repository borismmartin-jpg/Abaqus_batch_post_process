# ===============================================
# Combined Abaqus ODB Processing + Post-Processing
# ===============================================

from abaqus import *
from abaqusConstants import *
from odbAccess import openOdb
import os, csv
import numpy as np

# =========================
# USER SETTINGS
# =========================
folder_path = r"C:\Users\borism\Desktop\Claude Inp file"
step_name = "Load-to-Failure"
target_load = 350.0      # kN
peeq_threshold = 1e-6
output_summary = "SUMMARY_RESULTS.csv"
output_curves_folder = "CURVES"
output_images_folder = "IMAGES"
output_thickness_folder = "THICKNESS_IMAGES"
target_LPFs_for_image = [0.5, 1.0, 1.2]   # Example: 50%, 100%, 120% load
MIDSPAN_SET = "N-MIDSPAN-BOT"
ELSETS = {
    "BF": "E-BF-MIDSPAN",
    "TF": "E-TF-MIDSPAN",
    "WEB": "E-WEB-LOADPT"
}

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
    region = odb.rootAssembly.nodeSets[MIDSPAN_SET]

    for frame in step.frames:
        lpf = frame.frameValue
        u = frame.fieldOutputs["U"].getSubset(region=region)
        u2 = max([abs(v.data[1]) for v in u.values])
        disp.append(u2)
        load.append(lpf * target_load)  # kN
    return np.array(disp), np.array(load)

# -------------------------
# Stiffness
# -------------------------
def compute_stiffness(disp, load):
    n = max(5, int(0.1 * len(disp)))
    if n < 2: return None
    try:
        coeffs = np.polyfit(disp[:n], load[:n], 1)
        return coeffs[0]  # kN/mm
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
    return np.trapz(load, disp)  # kN.mm

# -------------------------
# Stress image export
# -------------------------
def find_closest_frame(step, target_lpf):
    return min(step.frames, key=lambda f: abs(f.frameValue - target_lpf))
def export_stress_image(odb_path, target_lpf):
    job_name = os.path.basename(odb_path).replace(".odb", "")
    odb = openOdb(path=odb_path)  # <-- use openOdb
    step = odb.steps[step_name]

    vp = session.Viewport(name=f'VP_{job_name}', origin=(0,0), width=200, height=150)
    vp.setValues(displayedObject=odb)

    frame = find_closest_frame(step, target_lpf)
    vp.odbDisplay.setFrame(step=step_name, frame=frame.incrementNumber)
    vp.odbDisplay.setPrimaryVariable(variableLabel='S', outputPosition=INTEGRATION_POINT,
                                     refinement=(INVARIANT, 'Mises'))
    vp.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF,))
    vp.view.fitView()

    if not os.path.exists(output_images_folder):
        os.makedirs(output_images_folder)

    file_path = os.path.join(output_images_folder, f"{job_name}_LPF_{target_lpf:.2f}.png")
    session.printToFile(fileName=file_path, format=PNG, canvasObjects=(vp,))
    odb.close()

# -------------------------
# Thickness image export
# -------------------------
def export_thickness_image(odb_path):
    job_name = os.path.basename(odb_path).replace(".odb", "")
    odb = openOdb(path=odb_path)
    step = safe_get_step(odb)

    vp = session.Viewport(name=f'VP_THK_{job_name}', origin=(0, 0), width=200, height=150)
    vp.setValues(displayedObject=odb)

    # Thickness is generally available as STH for shell elements.
    frame = step.frames[-1]
    vp.odbDisplay.setFrame(step=step.name, frame=frame.incrementNumber)
    if "STH" in frame.fieldOutputs:
        vp.odbDisplay.setPrimaryVariable(variableLabel='STH', outputPosition=INTEGRATION_POINT)
    elif "H" in frame.fieldOutputs:
        vp.odbDisplay.setPrimaryVariable(variableLabel='H', outputPosition=INTEGRATION_POINT)
    else:
        print(f"[WARNING] {job_name}: no shell thickness field output (STH/H) found.")
        odb.close()
        return

    vp.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF,))
    vp.view.fitView()

    if not os.path.exists(output_thickness_folder):
        os.makedirs(output_thickness_folder)

    file_path = os.path.join(output_thickness_folder, f"{job_name}_THICKNESS.png")
    session.printToFile(fileName=file_path, format=PNG, canvasObjects=(vp,))
    odb.close()
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
    peak_load = float(np.max(load))
    yield_lpf = detect_first_yield(step)
    yield_load = yield_lpf * target_load if yield_lpf else None
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
        for d,l in zip(disp,load): writer.writerow([d, l])

    return {
        "Job": job_name,
        "Yield Load (kN)": yield_load,
        "Peak Load (kN)": peak_load,
        "Max Disp (mm)": max_disp,
        "Stiffness (kN/mm)": stiffness,
        "Energy (kN.mm)": energy,
        "Max Stress (MPa)": max_stress,
        "Max PEEQ": max_peeq,
        "Failure Zone": failure_zone
    }

# =========================
# ======== MAIN ===========
# =========================
os.chdir(folder_path)
odb_files = [f for f in os.listdir() if f.endswith(".odb")]

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
    keys = results[0].keys()
    with open(output_summary, "w",newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(results)
    print(f"\n[OK] Summary written to {output_summary}")

# -------------------------
# POST-PROCESSING: Export images
# -------------------------
for odb_file in odb_files:
    for lpf in target_LPFs_for_image:
        try:
            export_stress_image(odb_file, lpf)
        except Exception as e:
            print(f"[ERROR IMAGE] {odb_file}: {e}")

for odb_file in odb_files:
    try:
        export_thickness_image(odb_file)
    except Exception as e:
        print(f"[ERROR THICKNESS IMAGE] {odb_file}: {e}")

print("\n[OK] Images exported")
