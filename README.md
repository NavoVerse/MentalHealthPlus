# Glow - Mental Health Plus 🌟

Glow is a premium, multi-modal mental health tracking and care application. It leverages AI to monitor your emotional well-being through text, voice, and facial expressions, providing actionable insights and suggestions to improve your mood.

## 🚀 Features

-   **Multi-Modal Emotion Detection**:
    -   **Text**: Real-time sentiment analysis for English and Bengali.
    -   **Voice**: Audio tone analysis using Wav2Vec2.
    -   **Video**: Real-time facial expression recognition via face-api.js.
-   **Intelligent AI Conversation**: A chat interface that understands your feelings and offers personalized suggestions to make you feel better.
-   **Daily Mood Tracking**: Visualize your mental health journey with dynamic VADER-based graphs.
-   **Smart Alerting System**: Automatically detects prolonged periods of low mood (7+ days below -5) and suggests professional help and clinic contacts.
-   **Voice-to-Text Integration**: Automatically transcribes your voice recordings into the chat for a seamless experience.
-   **Premium Glassmorphism UI**: A beautiful, responsive dark-mode interface designed for comfort and ease of use.

## 🛠️ Technology Stack

-   **Frontend**: Vanilla HTML5, CSS3 (Custom Glassmorphism), JavaScript (ES6+).
-   **Backend**: FastAPI (Python), SQLAlchemy (SQLite).
-   **AI/ML**:
    -   `vaderSentiment`: Lexicon and rule-based sentiment analysis.
    -   `transformers`: Wav2Vec2 for speech emotion classification.
    -   `face-api.js`: Browser-based neural networks for face detection and expressions.
    -   `deep-translator`: Modern translation for Bengali support.
-   **Charts**: Chart.js for data visualization.

## 📦 Setup & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/NavoVerse/MentalHealthPlus.git
cd MentalHealthPlus
```

### 2. Backend Setup
-   Ensure you have Python 3.10+ installed.
-   Install dependencies:
    ```bash
    pip install -r backend/requirements.txt
    pip install deep-translator
    ```
-   Run the backend server:
    ```bash
    python backend/main.py
    ```

### 3. Frontend Setup
-   Serve the frontend using any local server (e.g., Live Server in VS Code or Python's http.server):
    ```bash
    cd frontend
    python -m http.server 8001
    ```
-   Open your browser and navigate to `http://localhost:8001`.

## 📌 Usage

1.  **Login**: Use any username/password to get started (auto-creates an account).
2.  **Chat**: Type in English or Bengali to talk to the AI.
3.  **Media**: Go to the Media tab to enable your camera for facial analysis or record your voice for tone detection.
4.  **Stats**: Check the Stats tab to see your mood history and progress.

## 📝 License

This project is part of the NavoVerse initiative.