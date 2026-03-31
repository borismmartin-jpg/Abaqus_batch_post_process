import os
import subprocess

try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    import Tkinter as tk
    import tkFileDialog as filedialog

# =========================
# USER SETTINGS
# =========================
ABAQUS_CMD = r"C:\SIMULIA\Commands\abaqus.bat"

# Optional fallback folder if browser is unavailable/canceled.
# Leave as None to require selection via browser or env var.
DEFAULT_INPUT_FOLDER = None

cpus = 4
memory = "90%"
run_in_background = False  # False = sequential (recommended)


# =========================
# FUNCTIONS
# =========================
def select_input_folder():
    """Select input directory without console input (Abaqus-safe)."""
    env_folder = os.environ.get("ABAQUS_INPUT_FOLDER", "").strip().strip('"')
    if env_folder:
        return env_folder

    folder = ""
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder = filedialog.askdirectory(title="Select folder containing .inp files")
    except Exception:
        folder = ""
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass

    if folder:
        return folder

    if DEFAULT_INPUT_FOLDER:
        return DEFAULT_INPUT_FOLDER

    raise RuntimeError(
        "No input folder selected. Set ABAQUS_INPUT_FOLDER or DEFAULT_INPUT_FOLDER."
    )


def is_job_completed(job_name):
    """Check if job already completed successfully."""
    sta_file = job_name + ".sta"
    if not os.path.exists(sta_file):
        return False

    with open(sta_file, "r") as f:
        content = f.read()
        return "COMPLETED SUCCESSFULLY" in content


def run_job(inp_file):
    job_name = os.path.splitext(inp_file)[0]

    if is_job_completed(job_name):
        print("[SKIP] %s already completed" % job_name)
        return

    cmd = [
        ABAQUS_CMD,
        "job=%s" % job_name,
        "input=%s" % inp_file,
        "cpus=%s" % cpus,
        "memory=%s" % memory,
    ]

    if not run_in_background:
        cmd.append("interactive")

    print("[RUNNING] %s" % job_name)

    try:
        if run_in_background:
            subprocess.Popen(cmd)
        else:
            subprocess.run(cmd, check=True)
            print("[DONE] %s" % job_name)
    except subprocess.CalledProcessError:
        print("[ERROR] %s" % job_name)


# =========================
# MAIN
# =========================
folder_path = select_input_folder()

if not os.path.isdir(folder_path):
    raise FileNotFoundError("Folder does not exist: %s" % folder_path)

os.chdir(folder_path)

inp_files = [f for f in os.listdir(folder_path) if f.endswith(".inp")]

print("Found %d .inp files in: %s\n" % (len(inp_files), folder_path))

for inp in inp_files:
    run_job(inp)

print("\nBatch complete.")
