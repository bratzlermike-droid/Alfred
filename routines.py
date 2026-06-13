# ── Server (FastAPI backend) ──
fastapi
uvicorn[standard]
groq
faster-whisper
piper-tts
chromadb
python-multipart

# ── Desktop app (Windows) ──
customtkinter
pillow
sounddevice
numpy
scipy
pynput
SpeechRecognition
pyaudio
psutil
pywin32; sys_platform == 'win32'
pycaw; sys_platform == 'win32'
comtypes; sys_platform == 'win32'

# ── Local TTS fallback ──
kokoro
soundfile
torch

# ── Feature modules ──
requests
spotipy
PyPDF2
python-docx
ddgs
schedule
google-api-python-client
google-auth-oauthlib
