import os
import subprocess

APP_VERSION = "2.0.0-wip"

# =========================
# USER SETTINGS
# =========================
ABAQUS_CMD = r"C:\SIMULIA\Commands\abaqus.bat"
default_input_folder = r"C:\Users\borism\Desktop\Claude Inp file"

cpus = 4
memory = "90%"
run_in_background = False  # False = sequential (recommended)


# =========================
# FUNCTIONS
# =========================
def select_input_folder(default_folder):
    """
    Prompt for input directory path; press Enter to use configured default.
    """
    try:
        folder = input("Enter full folder path with .inp files (press Enter to use default): ").strip().strip('"')
    except Exception as e:
        print("[WARN] input() unavailable in this Abaqus session: {}".format(e))
        print("[INFO] Using default input folder: {}".format(default_folder))
        return default_folder
    if folder:
        return folder
    return default_folder


def is_job_completed(job_name):
    """Check if job already completed successfully"""
    sta_file = job_name + ".sta"
    if not os.path.exists(sta_file):
        return False

    with open(sta_file, "r") as f:
        content = f.read()
        return "COMPLETED SUCCESSFULLY" in content


def run_job(inp_file):
    job_name = os.path.splitext(inp_file)[0]

    if is_job_completed(job_name):
        print(f"[SKIP] {job_name} already completed")
        return

    cmd = [
        ABAQUS_CMD,
        f"job={job_name}",
        f"input={inp_file}",
        f"cpus={cpus}",
        f"memory={memory}",
    ]

    if not run_in_background:
        cmd.append("interactive")

    print(f"[RUNNING] {job_name}")

    try:
        if run_in_background:
            subprocess.Popen(cmd)
        else:
            subprocess.run(cmd, check=True)
            print(f"[DONE] {job_name}")
    except subprocess.CalledProcessError:
        print(f"[ERROR] {job_name}")


# =========================
# MAIN
# =========================
folder_path = select_input_folder(default_input_folder)

if not os.path.isdir(folder_path):
    raise FileNotFoundError(f"Folder does not exist: {folder_path}")

os.chdir(folder_path)

inp_files = [f for f in os.listdir(folder_path) if f.endswith(".inp")]

print(f"Found {len(inp_files)} .inp files in: {folder_path}\n")

for inp in inp_files:
    run_job(inp)

print("\nBatch complete.")
