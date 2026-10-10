from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Iterable

import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError, ImageDraw
from rembg import new_session, remove
from streamlit_drawable_canvas import st_canvas

st.set_page_config(page_title="Local Background Remover", page_icon="✂️", layout="wide")

MAX_FILE_MB = 25
SUPPORTED_TYPES = ["png", "jpg", "jpeg", "webp"]


@st.cache_resource(show_spinner=False)
def get_session(model_name: str):
    # Model inference runs locally. rembg may download weights on first use.
    return new_session(model_name)


def load_image(uploaded_file) -> Image.Image:
    raw = uploaded_file.getvalue()
    if len(raw) > MAX_FILE_MB * 1024 * 1024:
        raise ValueError(f"File is larger than {MAX_FILE_MB} MB.")
    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image.load()
        if image.width * image.height > 40_000_000:
            raise ValueError("Image is larger than 40 megapixels. Please resize it first.")
        return image.convert("RGBA")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("This file could not be read as a valid image.") from exc


def remove_background(image: Image.Image, session) -> Image.Image:
    output = remove(image, session=session)
    if isinstance(output, bytes):
        output = Image.open(io.BytesIO(output))
    return output.convert("RGBA")


def apply_polygon_selection(foreground: Image.Image, objects, canvas_width: int, canvas_height: int) -> Image.Image:
    """Keep only pixels inside the user-drawn polygon, preserving AI alpha."""
    if objects is None or not isinstance(objects, dict):
        raise ValueError("Draw a closed polygon around the object first.")
    polygons = []
    for obj in objects.get("objects", []):
        if obj.get("type") == "path":
            # Canvas polygon paths are represented as move/line commands.
            pts = []
            for cmd in obj.get("path", []):
                if len(cmd) >= 3 and cmd[0] in ("M", "L"):
                    pts.append((float(cmd[1]), float(cmd[2])))
            if len(pts) >= 3:
                polygons.append(pts)
    if not polygons:
        raise ValueError("I couldn't detect a polygon. Try drawing around the object again.")
    sx = foreground.width / max(1, canvas_width)
    sy = foreground.height / max(1, canvas_height)
    selection = Image.new("L", foreground.size, 0)
    draw = ImageDraw.Draw(selection)
    for points in polygons:
        scaled = [(round(x * sx), round(y * sy)) for x, y in points]
        draw.polygon(scaled, fill=255)
    out = foreground.convert("RGBA")
    alpha = out.getchannel("A")
    # Preserve the model's alpha only inside the hand-drawn selection.
    import PIL.ImageChops
    out.putalpha(PIL.ImageChops.multiply(alpha, selection))
    return out

def replace_background(foreground: Image.Image, color: str) -> Image.Image:
    background = Image.new("RGBA", foreground.size, color)
    background.alpha_composite(foreground)
    return background.convert("RGB")


def png_bytes(image: Image.Image) -> bytes:
    stream = io.BytesIO()
    image.save(stream, format="PNG", optimize=True)
    return stream.getvalue()


def safe_stem(filename: str) -> str:
    stem = Path(filename).stem
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem)
    return cleaned[:80] or "image"


def build_zip(items: Iterable[tuple[str, bytes]]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in items:
            archive.writestr(name, data)
    return stream.getvalue()


st.title("✂️ Local Background Remover")
st.caption("AI background removal on your computer — no background-removal API and no image uploads to a service.")
with st.sidebar:
    st.header("Settings")
    model_name = st.selectbox(
        "AI model",
        options=["u2net", "u2netp", "isnet-general-use", "birefnet-general"],
        index=0,
        help="u2net is a general-purpose default. u2netp is smaller and faster but may be less accurate.",
    )
    mode = st.radio(
        "Output background",
        ["Transparent PNG", "Solid color"],
        help="Transparent PNG is best for logos, product photos, and further editing.",
    )
    bg_color = "#FFFFFF"
    if mode == "Solid color":
        bg_color = st.color_picker("Background color", "#FFFFFF")
    st.divider()
    st.caption("Privacy: image inference is local. The selected model may be downloaded on first use.")

tab_single, tab_batch = st.tabs(["Single image", "Batch images"])

with tab_single:
    uploaded = st.file_uploader("Choose an image", type=SUPPORTED_TYPES, key="single_upload")
    if uploaded:
        try:
            source = load_image(uploaded)
            st.subheader("1. Encircle the object you want to keep")
            st.caption("Draw a closed polygon around the main object. The AI removes the background, then your outline trims away anything outside it.")
            preview = source.copy()
            preview.thumbnail((850, 650))
            canvas_width, canvas_height = preview.size
            canvas_result = st_canvas(
                fill_color="rgba(0, 180, 255, 0.12)",
                stroke_width=3, stroke_color="#00AEEF",
                background_image=preview, update_streamlit=True,
                height=canvas_height, width=canvas_width,
                drawing_mode="polygon",
                key=f"selection_canvas_{uploaded.name}_{len(uploaded.getvalue())}",
            )
            use_selection = st.checkbox("Apply my outline (recommended)", value=True, key="use_outline")
            left, right = st.columns(2)
            with left:
                st.subheader("Original")
                st.image(source, use_container_width=True)
            if st.button("Remove background", type="primary", key="remove_single"):
                with st.spinner("Loading local model and removing background… first run can take longer."):
                    session = get_session(model_name)
                    result = remove_background(source, session)
                    if use_selection:
                        if canvas_result is None or canvas_result.json_data is None:
                            raise ValueError("Please encircle the object on the image before processing, or untick 'Apply my outline'.")
                        result = apply_polygon_selection(result, canvas_result.json_data, canvas_width, canvas_height)
                    if mode == "Solid color":
                        display_result = replace_background(result, bg_color)
                    else:
                        display_result = result
                    st.session_state["single_result"] = png_bytes(display_result if display_result.mode == "RGBA" else display_result.convert("RGBA"))
                    st.session_state["single_result_name"] = safe_stem(uploaded.name) + "-background-removed.png"
            result_bytes = st.session_state.get("single_result")
            if result_bytes:
                result_image = Image.open(io.BytesIO(result_bytes)).convert("RGBA")
                with right:
                    st.subheader("Result")
                    if mode == "Transparent PNG":
                        st.image(result_image, use_container_width=True)
                        st.caption("Checkerboard transparency is represented by the viewer.")
                    else:
                        st.image(result_image.convert("RGB"), use_container_width=True)
                st.download_button(
                    "Download result (PNG)",
                    data=result_bytes,
                    file_name=st.session_state.get("single_result_name", "background-removed.png"),
                    mime="image/png",
                    type="primary",
                )
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error("Background removal failed. Check your internet connection on first run, model selection, and installed dependencies.")
            st.caption(f"Technical detail: {type(exc).__name__}: {exc}")

with tab_batch:
    batch_files = st.file_uploader(
        "Choose multiple images",
        type=SUPPORTED_TYPES,
        accept_multiple_files=True,
        key="batch_upload",
    )
    if batch_files:
        st.info(f"{len(batch_files)} file(s) selected. Processing happens locally and may use substantial memory.")
        if st.button("Process batch", type="primary"):
            outputs = []
            progress = st.progress(0)
            status = st.empty()
            try:
                session = get_session(model_name)
                for index, file in enumerate(batch_files):
                    status.write(f"Processing {file.name} ({index + 1}/{len(batch_files)})…")
                    try:
                        source = load_image(file)
                        result = remove_background(source, session)
                        if mode == "Solid color":
                            result = replace_background(result, bg_color).convert("RGBA")
                        outputs.append((safe_stem(file.name) + "-background-removed.png", png_bytes(result)))
                    except Exception as exc:
                        st.warning(f"Skipped {file.name}: {type(exc).__name__}: {exc}")
                    progress.progress((index + 1) / len(batch_files))
                st.session_state["batch_outputs"] = outputs
                status.write(f"Finished: {len(outputs)} image(s) processed.")
            except Exception as exc:
                st.error(f"Could not start the local model: {type(exc).__name__}: {exc}")
        outputs = st.session_state.get("batch_outputs", [])
        if outputs:
            st.download_button(
                "Download all results (ZIP)",
                data=build_zip(outputs),
                file_name="background-removed-images.zip",
                mime="application/zip",
                type="primary",
            )
            with st.expander("Preview processed files"):
                for name, data in outputs:
                    st.image(data, caption=name, use_container_width=True)

st.divider()
st.caption("Runs locally in your browser via a local Streamlit server. No API key is required.")
