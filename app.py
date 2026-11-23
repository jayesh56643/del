"""Run with: python -m streamlit run app.py"""
import base64
import logging
from io import BytesIO
from pathlib import Path
from threading import Lock

import streamlit as st
from PIL import Image
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent
WEIGHTS = ROOT / "runs/detect/yolo11_training/weights/best.pt"


@st.cache_resource
def load_detector():
    return YOLO(str(WEIGHTS)), Lock()


def describe(result):
    """Summarize distinct class/position pairs, giving stairs first mention."""
    objects = set()
    for box in result.boxes.cpu():
        center_x = float(box.xywhn[0, 0])
        position = "ahead"
        if center_x < 1 / 3:
            position = "on the left"
        elif center_x > 2 / 3:
            position = "on the right"
        name = result.names[int(box.cls.item())].lower()
        objects.add((name, position))
    ranked = sorted(objects, key=lambda item: (item[0] != "stairs", item[1] != "ahead", item))
    if not ranked:
        return "No objects recognized."
    return " ".join(f"{name.capitalize()} {position}." for name, position in ranked[:3])


def main():
    st.set_page_config(page_title="Spoken object guide")
    st.title("Spoken object guide")
    st.write("Point the camera forward to hear where objects appear. The model can miss obstacles and cannot judge distance or whether a path is safe.")
    if not WEIGHTS.is_file():
        st.error(f"Trained model missing at {WEIGHTS}")
        return
    model, lock = load_detector()
    st.caption("Recognizes " + ", ".join(name.lower() for name in model.names.values()) + ".")

    def process_frame():
        frame = st.session_state.guide.frame
        try:
            if len(frame["jpeg"]) > 1_000_000:
                raise ValueError("Frame too large")
            with Image.open(BytesIO(base64.b64decode(frame["jpeg"], validate=True))) as image:
                if image.format != "JPEG" or max(image.size) > 640:
                    raise ValueError("Unexpected frame format")
                with lock:
                    result = model.predict(image.convert("RGB"), imgsz=512, conf=0.45, verbose=False)[0]
            reply = {"text": describe(result)}
        except Exception:
            logging.exception("Camera frame processing failed")
            reply = {"error": "Object detection stopped. Start the camera to try again."}
        st.session_state.reply = {"id": frame["id"], **reply}

    camera = st.components.v2.component(
        "spoken_object_camera",
        html="""
        <button id="start">Start camera</button>
        <button id="voice" aria-pressed="true">Spoken descriptions</button>
        <p id="status" role="status">Camera off.</p>
        <video hidden muted autoplay playsinline aria-label="Live camera preview"></video>
        """,
        css="""
        button {font: inherit; padding: .7rem 1rem; margin: .2rem; border-radius: .45rem;
                border: 1px solid currentColor; background: transparent; color: inherit; cursor: pointer}
        #start {background: #165344; color: white}
        button:focus-visible {outline: 3px solid #168bc0; outline-offset: 2px}
        video {width: 100%; max-height: 55vh; background: #111; border-radius: .5rem}
        #status {font-size: 1.2rem}
        """,
        js=(ROOT / "camera.js").read_text(),
    )
    camera(key="guide", data=st.session_state.get("reply"), on_frame_change=process_frame)


if __name__ == "__main__":
    main()
