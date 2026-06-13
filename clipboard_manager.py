"""
Alfred AI Server - Groq Edition with Ollama Fallback
FastAPI with chat, voice, tools, memory, Groq LLM, and web UI.
"""
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import wave
import struct
import tempfile
from groq import Groq
from faster_whisper import WhisperModel
from piper import PiperVoice
from datetime import datetime
from tools import TOOLS, detect_tool
from memory import ChiefMemory, detect_memory_intent
from server_features import detect_server_feature
import json as json_lib

app = FastAPI(title="Alfred AI Server")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
security = HTTPBearer()

# ── Configuration ──────────────────────────────────────────────
GROQ_MODEL   = "llama-3.3-70b-versatile"
AUTH_TOKEN    = os.environ.get("ALFRED_AUTH_TOKEN", "change-me-in-env")
VOICE_PATH   = "voices/en_US-ryan-high.onnx"
WHISPER_SIZE  = "tiny"

SYSTEM_PROMPT = """You are Alfred Pennyworth. British butler. Dry wit. Loyal. You call the user Sir.
Reply in 1-2 sentences MAXIMUM. Be extremely brief. Never write more than 2 sentences unless asked to elaborate."""

# ── Initialize ─────────────────────────────────────────────────
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

print("Loading Whisper...")
WHISPER = WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8")
print("Loading Piper voice...")
TTS_VOICE = PiperVoice.load(VOICE_PATH)
print("Loading memory...")
MEMORY = ChiefMemory()
stats = MEMORY.get_stats()
print("Memory: " + str(stats["total_facts"]) + " facts, "
      + str(stats["total_conversations"]) + " conversations")
print("Using Groq model: " + GROQ_MODEL)
print("Alfred is ready.")

# ── Auth ───────────────────────────────────────────────────────
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials

# ── Models ─────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    history: list = []

class ChatResponse(BaseModel):
    reply: str
    timestamp: str

# ── LLM Helpers ────────────────────────────────────────────────
def call_ollama(messages, max_tokens=150):
    """Fallback to local Ollama when Groq is rate-limited."""
    import requests as req
    try:
        ollama_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
        r = req.post("http://localhost:11434/api/chat", json={
            "model": "qwen2.5:7b",
            "messages": ollama_messages,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.7}
        }, timeout=60)
        if r.status_code == 200:
            return r.json()["message"]["content"]
    except Exception as e:
        print("Ollama error:", e)
    return "I'm temporarily unable to respond, Sir. Both services are unavailable."

def call_groq(messages, max_tokens=100):
    """Call Groq API with automatic Ollama fallback on rate limit."""
    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "rate_limit" in error_str:
            print("Groq rate limited — falling back to Ollama")
            return call_ollama(messages, max_tokens)
        raise e

# ── Main Chat Logic ────────────────────────────────────────────
def ask_chief(message, history=[]):
    """Handle a message with features, memory, tools, and LLM."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[-6:]:
        messages.append(msg)

    # 0. Check server features (briefing, weather, reminders, finance)
    feat_action, feat_args, feat_response = detect_server_feature(message)
    if feat_action == "direct":
        return feat_response
    elif feat_action == "briefing":
        messages.append({"role": "user", "content": feat_response})
        return call_groq(messages, max_tokens=150)

    # 1. Check memory intent
    mem_action, mem_content = detect_memory_intent(message)

    if mem_action == "store":
        MEMORY.remember_fact(message)
        messages.append({"role": "user", "content": message +
            "\n\n[You stored this fact in memory. Confirm briefly.]"})
        return call_groq(messages, max_tokens=100)

    if mem_action == "store_schedule":
        MEMORY.remember_schedule(message)
        messages.append({"role": "user", "content": message +
            "\n\n[You stored this schedule item in memory. Confirm briefly.]"})
        return call_groq(messages, max_tokens=100)

    if mem_action in ("recall", "list"):
        if mem_action == "list":
            facts = MEMORY.get_all_facts()
            schedule = MEMORY.get_all_schedule()
            context = ""
            if facts:
                context += "[Facts]:\n"
                for f in facts:
                    context += "- " + f["content"] + "\n"
            if schedule:
                context += "[Schedule]:\n"
                for s in schedule:
                    context += "- " + s["event_date"] + ": " + s["content"] + "\n"
            if not context:
                context = "[No memories stored yet.]"
        else:
            context = MEMORY.recall(message)
            if not context:
                context = "[No relevant memories found.]"
        messages.append({"role": "user", "content": message + "\n\n" + context})
        return call_groq(messages, max_tokens=150)

    if mem_action == "forget":
        MEMORY.forget_all()
        return "Done. All memories cleared."

    # 2. Check tool intent
    tool_name, tool_args = detect_tool(message)
    if tool_name and tool_name in TOOLS:
        try:
            func = TOOLS[tool_name]
            if tool_args is not None:
                tool_result = func(tool_args)
            else:
                tool_result = func()
            messages.append({"role": "user", "content": message +
                "\n\n[Tool: " + tool_name + "]\n" + str(tool_result)})
            return call_groq(messages, max_tokens=150)
        except Exception:
            pass

    # 3. Regular message with memory context
    memory_context = MEMORY.recall(message, n_results=3)
    if not memory_context:
        memory_context = ""

    # Check for long response mode
    if "[LONG RESPONSE OK]" in message:
        tok = 800
    else:
        tok = 100

    full_message = message + memory_context[:200]
    messages.append({"role": "user", "content": full_message})
    reply = call_groq(messages, max_tokens=tok)

    # Auto-save interesting conversations
    skip = ["hello", "hi", "hey", "thanks", "bye", "ok", "okay", "yes", "no"]
    if len(message.split()) > 3 and message.lower().strip() not in skip:
        try:
            summary = "User asked: " + message[:200] + " | Alfred said: " + reply[:200]
            MEMORY.remember_conversation(summary, message, reply)
        except Exception:
            pass

    return reply

# ── Audio Helpers ──────────────────────────────────────────────
def text_to_speech(text):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    with wave.open(tmp_path, 'wb') as wav_file:
        TTS_VOICE.synthesize_wav(text, wav_file)
    with open(tmp_path, 'rb') as f:
        audio_bytes = f.read()
    os.unlink(tmp_path)
    return audio_bytes

def transcribe_audio(audio_bytes, suffix=".wav"):
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
        tmp.write(audio_bytes)
    segments, _ = WHISPER.transcribe(
        tmp_path, language="en", beam_size=1, vad_filter=True
    )
    text = " ".join([s.text for s in segments]).strip()
    os.unlink(tmp_path)
    return text

# ── Routes ─────────────────────────────────────────────────────
@app.get("/status")
def status():
    stats = MEMORY.get_stats()
    return {
        "status": "online",
        "model": GROQ_MODEL,
        "name": "Alfred",
        "engine": "Groq",
        "memories": stats["total_facts"] + stats.get("total_schedule", 0),
        "conversations": stats["total_conversations"]
    }

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, token: str = Depends(verify_token)):
    try:
        reply = ask_chief(request.message, request.history)
        return ChatResponse(reply=reply, timestamp=datetime.now().isoformat())
    except Exception as e:
        raise HTTPException(status_code=500, detail="Alfred error: " + str(e))

@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    token: str = Depends(verify_token)
):
    try:
        audio_bytes = await audio.read()
        filename = audio.filename or "audio.wav"
        if ".webm" in filename:
            suffix = ".webm"
        elif ".ogg" in filename:
            suffix = ".ogg"
        elif ".mp3" in filename:
            suffix = ".mp3"
        else:
            suffix = ".wav"
        text = transcribe_audio(audio_bytes, suffix=suffix)
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/voice/chat")
async def voice_chat(
    audio: UploadFile = File(...),
    token: str = Depends(verify_token)
):
    try:
        audio_bytes = await audio.read()
        transcript = transcribe_audio(audio_bytes)
        if not transcript:
            raise HTTPException(status_code=400, detail="Could not transcribe audio")
        reply = ask_chief(transcript)
        speech_bytes = text_to_speech(reply)
        return Response(
            content=speech_bytes,
            media_type="audio/wav",
            headers={"X-Transcript": transcript, "X-Reply": reply[:200]}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tts")
async def tts(request: ChatRequest, token: str = Depends(verify_token)):
    try:
        speech_bytes = text_to_speech(request.message)
        return Response(content=speech_bytes, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Sync Endpoints ─────────────────────────────────────────────

SYNC_DATA_DIR = os.path.expanduser("~/chief/data")
os.makedirs(SYNC_DATA_DIR, exist_ok=True)

@app.get("/sync/finance")
def sync_get_finance(token: str = Depends(verify_token)):
    path = os.path.join(SYNC_DATA_DIR, "finance.json")
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json_lib.load(f)
    return {"expenses": [], "budgets": {}, "watchlist": []}

@app.post("/sync/finance")
def sync_post_finance(data: dict, token: str = Depends(verify_token)):
    path = os.path.join(SYNC_DATA_DIR, "finance.json")
    with open(path, 'w') as f:
        json_lib.dump(data, f, indent=2)
    return {"status": "ok"}

@app.get("/sync/reminders")
def sync_get_reminders(token: str = Depends(verify_token)):
    path = os.path.join(SYNC_DATA_DIR, "reminders.json")
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json_lib.load(f)
    return []

@app.post("/sync/reminders")
def sync_post_reminders(data: list, token: str = Depends(verify_token)):
    path = os.path.join(SYNC_DATA_DIR, "reminders.json")
    with open(path, 'w') as f:
        json_lib.dump(data, f, indent=2)
    return {"status": "ok"}

@app.get("/")
async def web_ui():
    ui_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(ui_path):
        return FileResponse(ui_path, media_type="text/html")
    return {"error": "Web UI not found."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
