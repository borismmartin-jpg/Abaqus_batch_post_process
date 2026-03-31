import os
import csv
import tkinter as tk
from tkinter import filedialog


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


def ensure_output_workspace(folder_path, output_root_folder):
    os.chdir(folder_path)
    if not os.path.exists(output_root_folder):
        os.makedirs(output_root_folder)
    os.chdir(output_root_folder)


def find_odb_files():
    odb_files = [f for f in os.listdir() if f.endswith(".odb")]
    if not odb_files:
        odb_files = [f for f in os.listdir("..") if f.endswith(".odb")]
        odb_files = [os.path.join("..", f) for f in odb_files]
    return odb_files


def write_summary(results, output_summary):
    keys = results[0].keys()
    with open(output_summary, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(results)
    print("\n[OK] Summary written to {}".format(output_summary))


def write_combined_curve(results, output_curves_folder, output_combined_curve):
    with open(output_combined_curve, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Job", "Disp (mm)", "Load (kN)"])
        for row in results:
            curve_file = os.path.join(output_curves_folder, "{}_curve.csv".format(row["Job"]))
            if not os.path.isfile(curve_file):
                continue
            with open(curve_file, "r") as curve_in:
                reader = csv.reader(curve_in)
                next(reader, None)
                for d, l in reader:
                    writer.writerow([row["Job"], d, l])

    print("[OK] Combined curve written to {}".format(output_combined_curve))
