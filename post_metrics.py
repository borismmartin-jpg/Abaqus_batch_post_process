import os
import csv
import numpy as np
from odbAccess import openOdb


def safe_get_step(odb, step_name):
    if step_name in odb.steps.keys():
        return odb.steps[step_name]
    first_step_name = list(odb.steps.keys())[0]
    return odb.steps[first_step_name]


def extract_curve_data(step, odb, midspan_set, target_load):
    disp, load = [], []
    region = odb.rootAssembly.nodeSets[midspan_set]

    for frame in step.frames:
        lpf = frame.frameValue
        u = frame.fieldOutputs["U"].getSubset(region=region)
        u2 = max([abs(v.data[1]) for v in u.values])
        disp.append(u2)
        load.append(lpf * target_load)
    return np.array(disp), np.array(load)


def compute_stiffness(disp, load):
    n = max(5, int(0.1 * len(disp)))
    if n < 2:
        return None
    try:
        coeffs = np.polyfit(disp[:n], load[:n], 1)
        return coeffs[0] / 1000.0
    except Exception:
        return None


def detect_first_yield(step, peeq_threshold):
    for frame in step.frames:
        if "PEEQ" not in frame.fieldOutputs:
            continue
        peeq = frame.fieldOutputs["PEEQ"]
        if any(v.data > peeq_threshold for v in peeq.values):
            return frame.frameValue
    return None


def extract_local_metrics(step, odb, elsets):
    max_stress = 0.0
    max_peeq = 0.0
    failure_zone = "UNKNOWN"

    for zone, elset_name in elsets.items():
        try:
            region = odb.rootAssembly.elementSets["IBEAM-1.{}".format(elset_name)]
        except KeyError:
            region = odb.rootAssembly.elementSets[' ALL ELEMENTS']

        for frame in step.frames:
            if "S" in frame.fieldOutputs:
                s = frame.fieldOutputs["S"].getSubset(region=region)
                for v in s.values:
                    mises = v.mises
                    if mises > max_stress:
                        max_stress = mises
                        failure_zone = zone

            if "PEEQ" in frame.fieldOutputs:
                peeq = frame.fieldOutputs["PEEQ"].getSubset(region=region)
                for v in peeq.values:
                    val = v.data if isinstance(v.data, float) else v.data[0]
                    if val > max_peeq:
                        max_peeq = val

    return max_stress, max_peeq, failure_zone


def compute_energy(disp, load):
    return np.trapz(load, disp) / 1000.0


def save_curve(job_name, disp, load, output_curves_folder):
    if not os.path.exists(output_curves_folder):
        os.makedirs(output_curves_folder)
    curve_file = os.path.join(output_curves_folder, "{}_curve.csv".format(job_name))
    with open(curve_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Disp (mm)", "Load (kN)"])
        for d, l in zip(disp, load):
            writer.writerow([d, l / 1000.0])


def process_odb(odb_file, settings):
    job_name = os.path.basename(odb_file).replace(".odb", "")
    print("[PROCESSING] {}".format(job_name))
    odb = openOdb(odb_file)
    step = safe_get_step(odb, settings["step_name"])

    disp, load = extract_curve_data(step, odb, settings["midspan_set"], settings["target_load"])
    max_disp = float(np.max(disp))
    peak_load = float(np.max(load) / 1000.0)
    yield_lpf = detect_first_yield(step, settings["peeq_threshold"])
    yield_load = yield_lpf * settings["target_load"] / 1000.0 if yield_lpf else None
    stiffness = compute_stiffness(disp, load)
    energy = compute_energy(disp, load)
    max_stress, max_peeq, failure_zone = extract_local_metrics(step, odb, settings["elsets"])
    odb.close()

    save_curve(job_name, disp, load, settings["output_curves_folder"])

    return {
        "Job": job_name,
        "Yield Load (kN)": yield_load,
        "Peak Load (kN)": peak_load,
        "Max Disp (mm)": max_disp,
        "Stiffness (kN/mm)": stiffness,
        "Energy (kN.mm)": energy,
        "Max Stress (MPa)": max_stress,
        "Max PEEQ": max_peeq,
        "Failure Zone": failure_zone,
    }
