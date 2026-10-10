# Local Background Remover — U2NET edition

This version defaults to the `u2net` model and needs no API key. Image inference is performed locally. The first model run may download model weights; this is not an inference API request.

## Windows quick start
1. Extract the entire ZIP. Do not run commands from the ZIP preview.
2. Open the extracted `local-background-remover-u2net` folder.
3. Double-click `START_WINDOWS.bat`.
4. Wait for package installation and the browser to open.

The launcher automatically changes to its own folder, so it can find `requirements.txt` even if you start it from another directory.

Requirements: 64-bit Python 3.12 installed, with the Python launcher (`py`).

Manual alternative, in PowerShell opened inside this folder:
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The default model is `u2net`. Other model choices remain available in the sidebar. The app does not use a background-removal API or require an API key. First-time model weights may be downloaded from the model host.
