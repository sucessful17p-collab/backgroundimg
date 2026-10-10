# Safe setup notes

- No API key is required.
- No background-removal HTTP API is used.
- Model inference happens on the computer running this app.
- First model use may download model weights. This is not an inference API call.
- Do not expose Streamlit to the internet or an untrusted network.
- Only open image files you trust; the app rejects files over 25 MB and images over 40 megapixels.
- Use a virtual environment and avoid administrator privileges.
