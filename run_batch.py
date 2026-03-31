import os
import subprocess
import tkinter as tk
from tkinter import filedialog

# =========================
# USER SETTINGS
# =========================
ABAQUS_CMD = r"C:\SIMULIA\Commands\abaqus.bat"

# Optional fallback folder if the file browser is unavailable/canceled.
# Leave as None to require folder selection through file browser or env var.
DEFAULT_INPUT_FOLDER = None

cpus = 4
memory = "90%"
run_in_background = False  # False = sequential (recommended)


# =========================
# FUNCTIONS
# =========================
def select_input_folder():
    """Select input directory without using console input (Abaqus-safe)."""
    env_folder = os.environ.get("ABAQUS_INPUT_FOLDER", "").strip().strip('"')
    if env_folder:
        return env_folder

    try:
    """Prompt user and open a folder browser to pick the input directory."""
    user_choice = input("Select input folder using file browser? (Y/n): ").strip().lower()

    if user_choice in ("", "y", "yes"):
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder = filedialog.askdirectory(title="Select folder containing .inp files")
        root.destroy()
        if folder:
            return folder
    except tk.TclError:
        # GUI not available (e.g., headless session)
        pass

    if DEFAULT_INPUT_FOLDER:
        return DEFAULT_INPUT_FOLDER

    raise RuntimeError(
        "No input folder selected. Set ABAQUS_INPUT_FOLDER or DEFAULT_INPUT_FOLDER."
    )

        if folder:
            return folder

        print("No folder selected in browser.")

    folder = input("Enter full folder path with .inp files: ").strip().strip('"')
    if not folder:
        raise ValueError("No folder path provided.")

    return folder


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
folder_path = select_input_folder()

if not os.path.isdir(folder_path):
    raise FileNotFoundError(f"Folder does not exist: {folder_path}")

os.chdir(folder_path)

inp_files = [f for f in os.listdir(folder_path) if f.endswith(".inp")]

print(f"Found {len(inp_files)} .inp files in: {folder_path}\n")

for inp in inp_files:
    run_job(inp)

print("\nBatch complete.")
