# ===============================================
# Combined Abaqus ODB Processing + Post-Processing
# ===============================================

from post_io import (
    select_odb_folder,
    ensure_output_workspace,
    find_odb_files,
    write_summary,
    write_combined_curve,
)
from post_metrics import process_odb
from post_images import export_image

APP_VERSION = "2.0.0-wip"

# =========================
# USER SETTINGS
# =========================
folder_path = r"C:\Users\borism\Desktop\Claude Inp file"
step_name = "Load-to-Failure"
target_load = 350000.0   # N
peeq_threshold = 1e-6
output_summary = "SUMMARY_RESULTS.csv"
output_root_folder = "output"
output_curves_folder = "CURVES"
output_images_folder = "IMAGES"
output_combined_curve = "COMBINED_LOAD_DISPLACEMENT.csv"
target_LPFs_for_image = [0.5, 1.0, 1.2]
image_modes = ["S_MISES"]
MIDSPAN_SET = "N-MIDSPAN-BOT"
ELSETS = {
    "BF": "E-BF-MIDSPAN",
    "TF": "E-TF-MIDSPAN",
    "WEB": "E-WEB-LOADPT"
}


def get_settings():
    return {
        "step_name": step_name,
        "target_load": target_load,
        "peeq_threshold": peeq_threshold,
        "output_curves_folder": output_curves_folder,
        "midspan_set": MIDSPAN_SET,
        "elsets": ELSETS,
    }


def run_post_processing():
    selected_folder = select_odb_folder(folder_path)
    ensure_output_workspace(selected_folder, output_root_folder)

    odb_files = find_odb_files()
    print("[INFO] Found {} ODB files in: {}".format(len(odb_files), selected_folder))

    results = []
    settings = get_settings()
    for odb_file in odb_files:
        try:
            results.append(process_odb(odb_file, settings))
        except Exception as e:
            print("[ERROR] {}: {}".format(odb_file, e))

    if results:
        write_summary(results, output_summary)
        write_combined_curve(results, output_curves_folder, output_combined_curve)

    for odb_file in odb_files:
        for mode in image_modes:
            for lpf in target_LPFs_for_image:
                try:
                    export_image(odb_file, lpf, mode, step_name, output_images_folder)
                except Exception as e:
                    print("[ERROR IMAGE] {} [{} @ LPF={}]: {}".format(odb_file, mode, lpf, e))

    print("\n[OK] Images exported")


run_post_processing()
