from abaqus import session
from abaqusConstants import *
from odbAccess import openOdb
import os

from post_metrics import safe_get_step


def find_closest_frame(step, target_lpf):
    return min(step.frames, key=lambda f: abs(f.frameValue - target_lpf))


def set_primary_variable(vp, frame, mode):
    if mode == "S_MISES":
        vp.odbDisplay.setPrimaryVariable(
            variableLabel='S',
            outputPosition=INTEGRATION_POINT,
            refinement=(INVARIANT, 'Mises')
        )
        return "S_MISES"

    if mode == "STH":
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
        raise RuntimeError("Thickness variable '{}' found but could not be displayed".format(field_label))

    raise ValueError("Unsupported image mode: {}".format(mode))


def export_image(odb_path, target_lpf, mode, step_name, output_images_folder):
    job_name = os.path.basename(odb_path).replace(".odb", "")
    odb = openOdb(path=odb_path)

    try:
        step = safe_get_step(odb, step_name)
        used_step_name = step.name

        vp_name = "VP_{}_{}_{:.2f}".format(job_name, mode, target_lpf).replace(".", "p")
        vp = session.Viewport(name=vp_name, origin=(0, 0), width=200, height=150)
        vp.setValues(displayedObject=odb)

        frame = find_closest_frame(step, target_lpf)
        vp.odbDisplay.setFrame(step=used_step_name, frame=frame.incrementNumber)
        resolved_mode = set_primary_variable(vp, frame, mode)
        vp.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF,))
        vp.view.fitView()

        if not os.path.exists(output_images_folder):
            os.makedirs(output_images_folder)

        file_path = os.path.join(output_images_folder, "{}_{}_LPF_{:.2f}.png".format(job_name, resolved_mode, target_lpf))
        session.printToFile(fileName=file_path, format=PNG, canvasObjects=(vp,))
    finally:
        odb.close()
