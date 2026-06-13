"""
Alfred's Meeting Recorder
Records system audio, transcribes, and summarizes meetings.
"""
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import os
import datetime
import threading
import tempfile
import requests
import time
from groq import Groq

SERVER_URL = os.environ.get("ALFRED_SERVER_URL", "http://localhost:8000")
AUTH_TOKEN = "Bearer " + os.environ.get("ALFRED_AUTH_TOKEN", "change-me-in-env")
RECORDINGS_DIR = os.path.expanduser("~/alfred_recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

_recording = False
_audio_chunks = []
_record_thread = None
_record_start = None


def _get_groq():
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        config = os.path.expanduser("~/chief_config.txt")
        if os.path.exists(config):
            with open(config) as f:
                for line in f:
                    if line.startswith("GROQ_API_KEY="):
                        key = line.strip().split("=", 1)[1]
    return Groq(api_key=key)


def start_recording(source="mic"):
    """Start recording audio. Source: 'mic' for microphone."""
    global _recording, _audio_chunks, _record_thread, _record_start

    if _recording:
        return "Already recording, Sir."

    _recording = True
    _audio_chunks = []
    _record_start = datetime.datetime.now()

    def record():
        sample_rate = 16000
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16') as stream:
            while _recording:
                chunk, _ = stream.read(1024)
                _audio_chunks.append(chunk)

    _record_thread = threading.Thread(target=record, daemon=True)
    _record_thread.start()

    return "Recording started. Say 'stop recording' when finished."


def stop_recording():
    """Stop recording and save the file."""
    global _recording

    if not _recording:
        return "No active recording, Sir."

    _recording = False
    time.sleep(0.5)  # Let the thread finish

    if not _audio_chunks:
        return "No audio captured."

    # Save to file
    audio_data = np.concatenate(_audio_chunks, axis=0)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(RECORDINGS_DIR, "meeting_" + timestamp + ".wav")
    wav.write(filepath, 16000, audio_data)

    duration = len(audio_data) / 16000
    minutes = int(duration // 60)
    seconds = int(duration % 60)

    return ("Recording saved: " + str(minutes) + "m " + str(seconds) + "s. "
            + "Say 'transcribe last recording' to process it.")


def transcribe_recording(filepath=None):
    """Transcribe a recording using the server's Whisper."""
    if filepath is None:
        # Find the most recent recording
        files = sorted(os.listdir(RECORDINGS_DIR))
        if not files:
            return "No recordings found."
        filepath = os.path.join(RECORDINGS_DIR, files[-1])

    if not os.path.exists(filepath):
        return "Recording not found: " + filepath

    try:
        with open(filepath, 'rb') as f:
            r = requests.post(
                SERVER_URL + "/transcribe",
                headers={"Authorization": AUTH_TOKEN},
                files={"audio": ("recording.wav", f, "audio/wav")},
                timeout=120
            )
        if r.status_code == 200:
            text = r.json().get("text", "")
            if text:
                # Save transcript
                transcript_path = filepath.replace(".wav", "_transcript.txt")
                with open(transcript_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                return text
            return "Could not transcribe the recording."
        return "Transcription error: " + str(r.status_code)
    except Exception as e:
        return "Error: " + str(e)


def summarize_recording(filepath=None):
    """Transcribe and summarize a recording."""
    transcript = transcribe_recording(filepath)
    if transcript.startswith("No recordings") or transcript.startswith("Error") or transcript.startswith("Could not"):
        return transcript

    if len(transcript) < 50:
        return "Recording too short to summarize."

    client = _get_groq()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are Alfred. Summarize this meeting transcript concisely. Extract key discussion points and action items."},
            {"role": "user", "content": "Meeting transcript:\n\n" + transcript[:6000]}
        ],
        max_tokens=500,
        temperature=0.3
    )
    summary = response.choices[0].message.content

    # Save summary
    files = sorted(os.listdir(RECORDINGS_DIR))
    if files:
        summary_path = os.path.join(RECORDINGS_DIR, files[-1].replace(".wav", "_summary.txt"))
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary)

    return "Meeting summary:\n\n" + summary


def list_recordings():
    """List all saved recordings."""
    files = [f for f in os.listdir(RECORDINGS_DIR) if f.endswith('.wav')]
    if not files:
        return "No recordings saved, Sir."

    lines = "Recordings:\n"
    for f in sorted(files, reverse=True)[:10]:
        size_mb = os.path.getsize(os.path.join(RECORDINGS_DIR, f)) / (1024 * 1024)
        has_transcript = os.path.exists(os.path.join(RECORDINGS_DIR, f.replace(".wav", "_transcript.txt")))
        lines += "  " + f + " (" + str(round(size_mb, 1)) + " MB)"
        if has_transcript:
            lines += " [transcribed]"
        lines += "\n"
    return lines.strip()


# ── Intent Detection ──────────────────────────────────────────
def detect_recording_command(message):
    msg = message.lower().strip()

    if any(w in msg for w in ["start recording", "record meeting", "record this",
                               "begin recording", "start the recording"]):
        return ("start", None)

    if any(w in msg for w in ["stop recording", "end recording", "finish recording",
                               "stop the recording"]):
        return ("stop", None)

    if any(w in msg for w in ["transcribe", "transcribe recording",
                               "transcribe last recording"]):
        return ("transcribe", None)

    if any(w in msg for w in ["summarize recording", "summarize meeting",
                               "meeting summary", "summarize last recording"]):
        return ("summarize", None)

    if any(w in msg for w in ["my recordings", "list recordings", "show recordings"]):
        return ("list", None)

    if "am i recording" in msg or "recording status" in msg:
        return ("status", None)

    return (None, None)


def execute_recording_command(action, args):
    global _recording
    if action == "start":
        return start_recording()
    elif action == "stop":
        return stop_recording()
    elif action == "transcribe":
        return transcribe_recording()
    elif action == "summarize":
        return summarize_recording()
    elif action == "list":
        return list_recordings()
    elif action == "status":
        if _recording:
            elapsed = (datetime.datetime.now() - _record_start).seconds
            return "Recording in progress: " + str(elapsed // 60) + "m " + str(elapsed % 60) + "s"
        return "Not currently recording, Sir."
    return "Unknown recording command"
