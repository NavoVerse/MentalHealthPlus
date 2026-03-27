from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from langdetect import detect
from datetime import datetime, timedelta
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from deep_translator import GoogleTranslator
import torch
import librosa
import numpy as np
from transformers import pipeline
import os

# --- Database Setup ---
DATABASE_URL = "sqlite:///./mental_health.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)

from datetime import timezone

class MoodLog(Base):
    __tablename__ = "mood_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    score = Column(Float)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    mode = Column(String) # text, audio, video
    text = Column(String) # For historical context

class VoiceNote(Base):
    __tablename__ = "voice_notes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String)
    text = Column(String) # Transcription
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)

# --- ML Models ---
analyzer = SentimentIntensityAnalyzer()
translator = GoogleTranslator(source='auto', target='en')
# Using a speech emotion classifier (wav2vec2)
audio_classifier = pipeline("audio-classification", model="ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition")

# For translating the reply back if needed
bn_translator = GoogleTranslator(source='en', target='bn')

app = FastAPI()

# Ensure voice notes directory exists
if not os.path.exists("backend/voice_notes"):
    os.makedirs("backend/voice_notes")

app.mount("/voice_notes", StaticFiles(directory="backend/voice_notes"), name="voice_notes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Routes ---

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username, User.password == password).first()
    if not user:
        # For simplicity in this demo, create if not exists or return 401
        new_user = User(username=username, password=password)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return {"id": new_user.id, "username": new_user.username}
    return {"id": user.id, "username": user.username}

from functools import lru_cache

@lru_cache(maxsize=1000)
def translate_if_needed(text: str) -> str:
    try:
        return translator.translate(text)
    except:
        pass
    return text

def serialize_timestamp(dt: datetime) -> str:
    # SQLite returns naive datetimes here; these app timestamps are stored as UTC.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

def check_persistent_sadness(user_id: int, db: Session) -> bool:
    # Get last 5 logs for this user
    last_logs = db.query(MoodLog).filter(MoodLog.user_id == user_id).order_by(MoodLog.timestamp.desc()).limit(5).all()
    if len(last_logs) < 5:
        return False
    # Check if ALL of them are negative (score <= -2.0)
    return all(log.score <= -2.0 for log in last_logs)

@app.post("/analyze/text")
def analyze_text(user_id: int = Form(...), text: str = Form(...), db: Session = Depends(get_db)):
    import random
    
    # Mood Detection (Text)
    # Use cached translation
    processed_text = translate_if_needed(text)

    scores = analyzer.polarity_scores(processed_text)
    compound = scores['compound']
    scaled_score = compound * 10 # Scale -10 to 10
    
    mood_emoji = "😊" if scaled_score > 2 else "😔" if scaled_score < -2 else "😐"
    feeling = "positive" if scaled_score > 0 else "negative" if scaled_score < 0 else "neutral"
    
    reply = f"I sense you're feeling {feeling} (Score: {scaled_score:.1f}). {mood_emoji}"
    
    if scaled_score <= -2.0:
        suggestions = [
            "Why not take a 10-minute walk outside? Fresh air helps!",
            "Listening to your favorite upbeat song might lift your spirits 🎵",
            "Maybe try drawing or writing down your feelings in a journal?",
            "Have a glass of water and take 5 deep breaths.",
            "Talk to a friend or someone you trust about how you feel.",
            "Watch a funny video or a stand-up comedy clip!"
        ]
        
        # Check if persistent sadness (last 4 + this one = 5)
        # We check the database first. This logic happens BEFORE the current one is saved to DB.
        # But wait, we save to DB later in this function.
        # So check_persistent_sadness will check the PREVIOUS 5.
        # If we want 5 CONSTANTLY (including this one), we should check the last 4.
        
        last_4_sad = db.query(MoodLog).filter(MoodLog.user_id == user_id).order_by(MoodLog.timestamp.desc()).limit(4).all()
        is_persistent = len(last_4_sad) == 4 and all(l.score <= -2.0 for l in last_4_sad)
        
        reply += f"\n\nSuggestion: {random.choice(suggestions)}"
        
        if is_persistent:
            reply += "\n\nAlert: You've been feeling low for a while. It might help to talk to a professional: 📞 +1-800-MENTAL-CARE"
    
    # Translate back to Bengali if input was Bengali
    if text and text.strip():
        try:
            if detect(text.strip()) == 'bn':
                reply = bn_translator.translate(reply)
        except:
            pass

    # Save log
    log = MoodLog(user_id=user_id, score=scaled_score, mode="text", text=text)
    db.add(log)
    db.commit()
    
    return {"score": scaled_score, "sentiment": scores, "reply": reply}

@app.post("/analyze/audio")
def analyze_audio(user_id: int = Form(...), text: str = Form(None), face_emotion: str = Form(None), file: UploadFile = File(...), db: Session = Depends(get_db)):
    import random
    
    # Save temp file
    temp_filename = f"temp_{file.filename}"
    with open(temp_filename, "wb") as f:
        f.write(file.file.read())
    
    # Audio Analysis
    results = audio_classifier(temp_filename)
    # Map results to a score
    emotion_map = {
        "happy": 8, "calm": 5, "neutral": 2, "surprise": 1,
        "sad": -7, "angry": -9, "fear": -8, "disgust": -6
    }
    
    # --- Deep Feature Analysis ---
    results = audio_classifier(temp_filename)
    top_emotion = results[0]['label']
    confidence = results[0]['score']
    
    # --- Physical Signal Analysis (Pitch & Throw) ---
    y, sr = librosa.load(temp_filename)
    # Pitch (Fundamental Frequency Estimation)
    pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
    pitch_vals = pitches[magnitudes > np.median(magnitudes)]
    mean_pitch = np.mean(pitch_vals) if len(pitch_vals) > 0 else 0
    
    # Energy (Throw/Intensity)
    rms = librosa.feature.rms(y=y)
    mean_rms = np.mean(rms)
    
    # Base categorical score
    categorical_score = emotion_map.get(top_emotion, 0)
    
    # Heuristic Refinement based on Signal Physics (Pitch and Energy)
    signal_adjustment = 0
    if mean_rms < 0.01: # Very soft / whispering
        signal_adjustment -= 2.0
    elif mean_rms > 0.1: # Loud / shouting
        if top_emotion in ["happy", "surprise"]: signal_adjustment += 1.0
        else: signal_adjustment -= 2.0 # Angry/Stressed
        
    if mean_pitch < 100: # Very low pitch (often sad/monotone)
        signal_adjustment -= 1.0
    elif mean_pitch > 300: # High pitch
        if top_emotion == "happy": signal_adjustment += 1.0
        
    # Scale categorical score by confidence and add signal adjustment
    audio_score = (categorical_score * confidence) + signal_adjustment
    audio_score = max(-10, min(10, audio_score)) # Clamp to -10 to 10
    
    # Text Analysis (if transcription is provided)
    text_score = 0
    if text and text.strip():
        msg = text.strip().lower()
        processed_text = translate_if_needed(msg)
        scores = analyzer.polarity_scores(processed_text)
        text_score = (scores.get('compound', 0)) * 10
        
        # Keyword "Veto" logic - if words are strong, they should override ambiguous tone
        negative_keywords = ["sad", "depressed", "unhappy", "lonely", "anxious", "pain", "bad", "terrible", "hate", "kill"]
        positive_keywords = ["happy", "great", "wonderful", "joy", "excellent", "good", "love", "excited"]
        
        # Force-shift if keywords are found to ensure keywords carry weight
        if any(word in msg for word in negative_keywords) and text_score > -2.0:
            text_score = -6.0
        elif any(word in msg for word in positive_keywords) and text_score < 2.0:
            text_score = 6.0
    else:
        text_score = 0
    
    # Combine (weighted: 30% physical audio, 70% content) - prioritizing verbal expression
    final_score = (audio_score * 0.3 + text_score * 0.7) if text else audio_score
    
    # Face Emotion Analysis Integration
    face_score = 0
    used_face = False
    if face_emotion and face_emotion not in ["Detecting...", "No Face Found"]:
        face_map = {
            "Happy": 8, "Neutral": 0, "Sad": -7, "Angry": -9, "Fearful": -8, "Disgusted": -6, "Surprised": 1
        }
        face_score = face_map.get(face_emotion, 0)
        used_face = True
        
        # Re-weight for 3 modalities: 25% Audio, 50% Text, 25% Face
        if text:
            final_score = (audio_score * 0.25) + (text_score * 0.50) + (face_score * 0.25)
        else:
            final_score = (audio_score * 0.5) + (face_score * 0.5)
            
    # Final emotional "anchor": If user explicitly says "I am sad", don't let a high pitch/energy make it positive
    if text and "sad" in text.lower() and final_score > 0:
        final_score = -2.0 # Minimum sadness if explicitly stated
    
    analysis_details = f"Tone: {top_emotion} (conf: {confidence*100:.0f}%), Pitch: {('High' if mean_pitch > 200 else 'Low' if mean_pitch < 120 else 'Med')}, Energy: {('High' if mean_rms > 0.05 else 'Low')}"
    if used_face:
        analysis_details += f", Face: {face_emotion}"
    
    if text:
        text_sentiment = "positive" if text_score > 2 else "negative" if text_score < -2 else "neutral"
        reply = f"I've combined spectral analysis with physical pitch/energy checks. Your {analysis_details} suggests a {text_sentiment} sentiment in your words."
    else:
        reply = f"Signal Analysis complete. {analysis_details}."

    reply += f" Mood Score: {final_score:.1f}/10."

    if final_score <= -2.0:
        suggestions = [
            "Why not take a 10-minute walk outside? Fresh air helps!",
            "Listening to your favorite upbeat song might lift your spirits 🎵",
            "Maybe try drawing or writing down your feelings in a journal?",
            "Have a glass of water and take 5 deep breaths.",
            "Talk to a friend or someone you trust about how you feel.",
            "Watch a funny video or a stand-up comedy clip!"
        ]
        
        # Check if persistent sadness (last 4 + this one = 5)
        last_4_sad = db.query(MoodLog).filter(MoodLog.user_id == user_id).order_by(MoodLog.timestamp.desc()).limit(4).all()
        is_persistent = len(last_4_sad) == 4 and all(l.score <= -2.0 for l in last_4_sad)
        
        reply += f"\n\nSuggestion: {random.choice(suggestions)}"
        
        if is_persistent:
            reply += "\n\nAlert: You've been feeling low for a while. It might help to talk to a professional: 📞 +1-800-MENTAL-CARE"

    # Translate back to Bengali if input was detected as Bengali
    if text and text.strip():
        try:
            if detect(text.strip()) == 'bn':
                reply = bn_translator.translate(reply)
        except:
            pass
    
    # Save log
    log = MoodLog(user_id=user_id, score=final_score, mode="audio", text=text)
    db.add(log)
    
    # Permanently save as voice note
    note_filename = f"note_{user_id}_{int(datetime.now().timestamp())}.wav"
    note_path = os.path.join("backend", "voice_notes", note_filename)
    import shutil
    shutil.copy(temp_filename, note_path)
    
    voice_note = VoiceNote(user_id=user_id, filename=note_filename, text=text)
    db.add(voice_note)
    
    db.commit()
    
    os.remove(temp_filename)
    return {"score": final_score, "emotion": top_emotion, "details": results, "reply": reply, "voice_note": note_filename}

@app.get("/voice_history/{user_id}")
def get_voice_history(user_id: int, db: Session = Depends(get_db)):
    notes = db.query(VoiceNote).filter(VoiceNote.user_id == user_id).order_by(VoiceNote.timestamp.desc()).all()
    return [{"id": n.id, "filename": n.filename, "timestamp": serialize_timestamp(n.timestamp), "text": n.text, "url": f"/voice_notes/{n.filename}"} for n in notes]

@app.get("/mood/history/{user_id}")
def get_mood_history(user_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import func
    from datetime import timezone
    
    logs = db.query(MoodLog).filter(MoodLog.user_id == user_id).order_by(MoodLog.timestamp.desc()).limit(30).all()
    
    # Alert logic - Check last 7 days average using DB aggregation
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    
    avg_score = db.query(func.avg(MoodLog.score)).filter(MoodLog.user_id == user_id, MoodLog.timestamp >= seven_days_ago).scalar()
    count = db.query(func.count(MoodLog.id)).filter(MoodLog.user_id == user_id, MoodLog.timestamp >= seven_days_ago).scalar()
    
    average_mood = float(avg_score) if avg_score is not None else 0.0
    
    alert = False
    if count >= 7 and average_mood < -5:
        alert = True

    suggestions = []
    if alert:
        suggestions = [
            "Take a 15-minute nature walk.",
            "Try a guided 10-minute meditation.",
            "Call a close friend or family member just to talk.",
            "Write down 3 things you are grateful for right now.",
            "Contact a mental health professional for a consultation."
        ]

    return {
        "history": [{"score": l.score, "timestamp": serialize_timestamp(l.timestamp), "mode": l.mode} for l in reversed(logs)],
        "alert": alert,
        "average_mood": average_mood,
        "suggestions": suggestions
    }

# --- Static Files & Frontend ---
@app.get("/")
async def read_index():
    return FileResponse('frontend/index.html')

app.mount("/", StaticFiles(directory="frontend"), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
