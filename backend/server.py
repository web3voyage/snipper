import os
import sys
import time
import ctypes
import threading
import logging
import pyaudio
import wave
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Initialize structured logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("StealthBackend")

app = FastAPI(title="StealthOverlay Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WDA_EXCLUDEFROMCAPTURE = 0x00000011  # Win10 2004+ capture exclusion flag

state = {
    "api_key": "sk-G7Wnlk03b9SPCVvzoofPjv93niPYmRhBd5a1FA29HkCEt1yC",
    "api_url": "https://api.agentrouter.com/v1/chat/completions",
    "model_name": "gpt-5.5",
    "is_recording": False,
}

class AppConfig(BaseModel):
    api_key: str
    api_url: str
    model_name: str

class QueryPayload(BaseModel):
    prompt: str

# Win32 controller to apply the capture exclusion flag
def apply_stealth_to_window(window_title: str) -> bool:
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, window_title)
    if hwnd:
        # Excludes window from screenshots, OBS, Discord, and Teams capture
        success = user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        if success:
            logger.info(f"Stealth capture exclusion applied to HWND: {hwnd}")
            return True
    return False

def run_window_stealth_monitor():
    logger.info("Starting stealth window monitor thread...")
    while True:
        # Polls for the React Native window handle by its exact class/title
        if apply_stealth_to_window("StealthOverlay"):
            logger.info("Stealth configuration complete. Monitor thread closing.")
            break
        time.sleep(1.5)

@app.post("/configure")
def configure(config: AppConfig):
    state["api_key"] = config.api_key
    state["api_url"] = config.api_url
    state["model_name"] = config.model_name
    logger.info("Configuration updated successfully.")
    return {"status": "configured"}

@app.post("/chat")
def chat(payload: QueryPayload):
    if not state["api_key"]:
        raise HTTPException(status_code=400, detail="API Key not configured.")
    
    headers = {
        "Authorization": f"Bearer {state['api_key']}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": state["model_name"],
        "messages": [{"role": "user", "content": payload.prompt}],
        "temperature": 0.5
    }
    
    try:
        response = requests.post(state["api_url"], json=data, headers=headers, timeout=12)
        response.raise_for_status()
        res = response.json()
        return {"answer": res['choices'][0]['message']['content']}
    except Exception as e:
        logger.error(f"Upstream API failure: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# System Sound & Audio capture loops
class WinAudioEngine:
    def __init__(self):
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.frames = []
        self._pa = pyaudio.PyAudio()
        self.stream = None

    def start_recording(self):
        self.frames = []
        self.stream = self._pa.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk
        )
        state["is_recording"] = True
        threading.Thread(target=self._record_loop, daemon=True).start()

    def _record_loop(self):
        while state["is_recording"]:
            try:
                data = self.stream.read(self.chunk)
                self.frames.append(data)
            except Exception as e:
                logger.error(f"Recording buffer read error: {e}")
                break

    def stop_recording(self, path="query.wav"):
        state["is_recording"] = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        wf = wave.open(path, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(self._pa.get_sample_size(self.format))
        wf.setframerate(self.rate)
        wf.writeframes(b''.join(self.frames))
        wf.close()

audio_engine = WinAudioEngine()

@app.post("/voice/start")
def voice_start():
    audio_engine.start_recording()
    return {"status": "started"}

@app.post("/voice/stop")
def voice_stop():
    audio_engine.stop_recording()
    # Mock speech-to-text response
    return {"transcription": "What is the recommended design structure for a desktop app?"}

if __name__ == "__main__":
    import uvicorn
    threading.Thread(target=run_window_stealth_monitor, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000)