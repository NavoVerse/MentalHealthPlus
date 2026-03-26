from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
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

Base.metadata.create_all(bind=engine)

# --- ML Models ---
analyzer = SentimentIntensityAnalyzer()
translator = GoogleTranslator(source='auto', target='en')
# Using a speech emotion classifier (wav2vec2)
audio_classifier = pipeline("audio-classification", model="ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition")

app = FastAPI()

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
        reply += f"\n\nSuggestion: {random.choice(suggestions)}"
    
    # Save log
    log = MoodLog(user_id=user_id, score=scaled_score, mode="text")
    db.add(log)
    db.commit()
    
    return {"score": scaled_score, "sentiment": scores, "reply": reply}

@app.post("/analyze/audio")
def analyze_audio(user_id: int = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
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
    
    # Get top emotion
    top_emotion = results[0]['label']
    score = emotion_map.get(top_emotion, 0)
    
    reply = f"Voice analysis: You sound {top_emotion}. (Score: {score})"
    
    if score <= -2.0:
        suggestions = [
            "Why not take a 10-minute walk outside? Fresh air helps!",
            "Listening to your favorite upbeat song might lift your spirits 🎵",
            "Maybe try drawing or writing down your feelings in a journal?",
            "Have a glass of water and take 5 deep breaths.",
            "Talk to a friend or someone you trust about how you feel.",
            "Watch a funny video or a stand-up comedy clip!"
        ]
        reply += f"\n\nSuggestion: {random.choice(suggestions)}"
    
    # Save log
    log = MoodLog(user_id=user_id, score=score, mode="audio")
    db.add(log)
    db.commit()
    
    import os
    os.remove(temp_filename)
    return {"score": score, "emotion": top_emotion, "details": results, "reply": reply}

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
        "history": [{"score": l.score, "timestamp": l.timestamp, "mode": l.mode} for l in reversed(logs)],
        "alert": alert,
        "average_mood": average_mood,
        "suggestions": suggestions
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
