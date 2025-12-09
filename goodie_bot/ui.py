from __future__ import annotations

from pathlib import Path
from typing import List

import streamlit as st

# Allow running both as module (`python -m streamlit run goodie_bot/ui.py`) and as package
try:  # when invoked as a package
    from .cli import ensure_output_dir, load_jobs, load_template_config, process_job
except ImportError:  # when invoked as a script (no package context)
    from cli import ensure_output_dir, load_jobs, load_template_config, process_job  # type: ignore


def run_ui() -> None:
    st.set_page_config(page_title="Goodie Bag Bot", layout="wide")
    st.title("Goodie Bag Bot")
    st.caption("Clean, minimal dashboard. Upload photos, edit text, export cards.")

    st.write("Backgrounds are preserved. If you want cutouts, upload transparent PNGs.")

    col_left, col_right = st.columns([1.1, 1])

    # Quick create
    with col_left:
        st.subheader("Quick Create")
        with st.form("quick_form"):
            uploaded_files = st.file_uploader("Upload photo(s)", accept_multiple_files=True, type=["png", "jpg", "jpeg"])
            recipient_name = st.text_input("Recipient name", "")
            project_name = st.text_input("Project / Team", "")
            message = st.text_input("Message line", "Receiving goodie bag from")
            giver_name = st.text_input("Giver name(s)", "")
            uploaded_output = st.text_input("Output filename (no extension)", "card")
            template_path_quick = Path(st.text_input("Template YAML", "configs/template.yml"))
            output_dir_quick = Path(st.text_input("Output folder", "output"))
            font_override_quick = st.text_input("Override font (optional)", "")
            skip_autocolor_quick = st.checkbox("Skip color correction", value=True)
            font_scale_quick = st.slider("Font scale", min_value=0.5, max_value=2.2, value=1.3, step=0.05)
            remove_bg_jpg_quick = st.checkbox("Remove background for JPG/JPEG (uses rembg)", value=False)
            photo_scale_quick = st.slider("Photo scale", min_value=0.5, max_value=2.5, value=1.0, step=0.05)
            submitted_quick = st.form_submit_button("Generate")

        if submitted_quick:
            if not uploaded_files:
                st.error("Please upload at least one photo.")
            else:
                try:
                    template_cfg = load_template_config(
                        template_path_quick,
                        font_override=Path(font_override_quick) if font_override_quick else None,
                    )
                except Exception as exc:
                    st.error(f"Template load failed: {exc}")
                else:
                    ensure_output_dir(output_dir_quick)
                    upload_dir = Path("uploaded_photos")
                    upload_dir.mkdir(exist_ok=True)
                    photo_paths = []
                    for uf in uploaded_files:
                        dest = upload_dir / uf.name
                        with dest.open("wb") as fp:
                            fp.write(uf.read())
                        photo_paths.append(dest.as_posix())

                    job = {
                        "recipient_name": recipient_name,
                        "giver_name": giver_name,
                        "message": message,
                        "project_name": project_name,
                        "photos": photo_paths,
                        "output_name": uploaded_output,
                    }
                    dest = process_job(
                        job,
                        template_cfg=template_cfg,
                        output_dir=output_dir_quick,
                        auto_color=not skip_autocolor_quick,
                        dry_run=False,
                        font_scale=font_scale_quick,
                        remove_bg_jpg=remove_bg_jpg_quick,
                        photo_scale=photo_scale_quick,
                    )
                    st.success(f"Generated -> {dest}")

    # Batch
    with col_right:
        st.subheader("Batch (jobs file)")
        with st.form("batch_form"):
            template_path = Path(st.text_input("Template YAML (batch)", "configs/template.yml"))
            jobs_path = Path(st.text_input("Jobs YAML/CSV", "jobs/sample_jobs.yml"))
            output_dir = Path(st.text_input("Output folder", "output"))
            font_override = st.text_input("Override font (batch, optional)", "")
            skip_autocolor = st.checkbox("Skip color correction (batch)", value=True)
            font_scale_batch = st.slider("Font scale (batch)", min_value=0.5, max_value=2.2, value=1.3, step=0.05)
            remove_bg_jpg_batch = st.checkbox("Remove background for JPG/JPEG (batch)", value=False)
            photo_scale_batch = st.slider("Photo scale (batch)", min_value=0.5, max_value=2.5, value=1.0, step=0.05)
            run_all = st.form_submit_button("Generate All")

        if run_all:
            try:
                template_cfg = load_template_config(
                    template_path, font_override=Path(font_override) if font_override else None
                )
                jobs = load_jobs(jobs_path)
            except Exception as exc:
                st.error(f"Load failed: {exc}")
            else:
                ensure_output_dir(output_dir)
                results = []
                for job in jobs:
                    dest = process_job(
                        job,
                        template_cfg=template_cfg,
                        output_dir=output_dir,
                        auto_color=not skip_autocolor,
                        dry_run=False,
                        font_scale=font_scale_batch,
                        remove_bg_jpg=remove_bg_jpg_batch,
                        photo_scale=photo_scale_batch,
                    )
                    results.append(str(dest))
                st.success("Batch complete.")
                for dest in results:
                    st.write(dest)

    st.markdown("---")
    st.subheader("CLI helper")
    st.code("python -m goodie_bot --template configs/template.yml --jobs jobs/sample_jobs.yml --output output")


def main() -> None:
    # Allow `goodie-bag-ui` console script
    run_ui()


if __name__ == "__main__":
    main()
