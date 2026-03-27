// --- Configuration ---
const API_URL = 'http://localhost:8000';
let currentUser = null;
let chart = null;

// --- DOM Elements ---
const loginScreen = document.getElementById('login-screen');
const appContainer = document.getElementById('app-container');
const loginBtn = document.getElementById('login-btn');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');
const navBtns = document.querySelectorAll('.nav-btn');
const tabContents = document.querySelectorAll('.tab-content');
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendChatBtn = document.getElementById('send-chat-btn');
const recordVoiceBtn = document.getElementById('record-voice-btn');
const alertBanner = document.getElementById('alert-banner');
const webcam = document.getElementById('webcam');
const faceMood = document.getElementById('face-mood');
const recordAudioLarge = document.getElementById('record-audio-large');
const voiceNotesList = document.getElementById('voice-notes-list');
let currentLang = 'en-US';

// --- Language Toggle ---
document.getElementById('lang-en').onclick = () => setLang('en-US');
document.getElementById('lang-bn').onclick = () => setLang('bn-BD');

function setLang(lang) {
    currentLang = lang;
    document.getElementById('lang-en').classList.remove('bg-purple-500', 'font-bold');
    document.getElementById('lang-bn').classList.remove('bg-purple-500', 'font-bold');
    document.getElementById('lang-en').classList.add('opacity-40');
    document.getElementById('lang-bn').classList.add('opacity-40');

    if (lang === 'en-US') {
        document.getElementById('lang-en').classList.add('bg-purple-500', 'font-bold');
        document.getElementById('lang-en').classList.remove('opacity-40');
    } else {
        document.getElementById('lang-bn').classList.add('bg-purple-500', 'font-bold');
        document.getElementById('lang-bn').classList.remove('opacity-40');
    }
}

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initChart();
});

// --- Auth ---
loginBtn.onclick = async () => {
    const user = usernameInput.value;
    const pass = passwordInput.value;
    if (!user || !pass) return;

    const fd = new FormData();
    fd.append('username', user);
    fd.append('password', pass);

    try {
        const resp = await fetch(`${API_URL}/login`, { method: 'POST', body: fd });
        currentUser = await resp.json();
        loginScreen.classList.add('hidden');
        appContainer.classList.remove('hidden');
        loadHistory();
        loadVoiceNotes();
    } catch (err) {
        alert('Login failed. Ensure backend is running.');
    }
};

// --- Tabs ---
function initTabs() {
    navBtns.forEach(btn => {
        if (btn.classList.contains('logout')) {
            btn.onclick = () => {
                currentUser = null;
                appContainer.classList.add('hidden');
                loginScreen.classList.remove('hidden');
                stopCamera();
                if (chart) {
                    chart.data.labels = [];
                    chart.data.datasets[0].data = [];
                    chart.update();
                }
            };
            return;
        }

        btn.onclick = () => {
            const tabId = btn.dataset.tab;
            if (!tabId) return;
            
            navBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            tabContents.forEach(tc => {
                tc.id === `${tabId}-tab` ? tc.classList.remove('hidden') : tc.classList.add('hidden');
            });

            if (tabId === 'media') {
                startCamera();
                loadVoiceNotes();
            } else {
                stopCamera();
            }
            if (tabId === 'stats') loadHistory();
        };
    });
}

// --- Chat & Text Analysis ---
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendChatBtn.click();
    }
});

sendChatBtn.onclick = async () => {
    const text = chatInput.value;
    if (!text) return;
    
    addMessage('user', text);
    chatInput.value = '';

    const fd = new FormData();
    fd.append('user_id', currentUser.id);
    fd.append('text', text);

    const resp = await fetch(`${API_URL}/analyze/text`, { method: 'POST', body: fd });
    const data = await resp.json();
    
    // Use the backend's smartly constructed reply (which includes suggestions)
    addMessage('bot', data.reply);
};

function addMessage(who, text, audioUrl = null) {
    const div = document.createElement('div');
    // Enhanced styles for messages to support audio and better layout
    div.className = `message ${who} px-5 py-3 rounded-2xl border ${who==='bot'?'bg-white/5 border-white/10 self-start':'bg-purple-500/20 border-purple-500/30 self-end ml-auto'} max-w-[80%] flex flex-col gap-2`;
    
    if (text) {
        const p = document.createElement('p');
        p.innerText = text;
        div.appendChild(p);
    }

    if (audioUrl) {
        const audio = document.createElement('audio');
        audio.controls = true;
        audio.src = audioUrl;
        audio.className = 'w-full h-8 mt-1 opacity-70 hover:opacity-100 transition-opacity';
        div.appendChild(audio);
    }
    
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// --- Video/Face Detection ---
let faceInterval;
let modelsLoaded = false;

async function startCamera() {
    try {
        if (!modelsLoaded) {
            faceMood.innerText = "Loading Visual AI...";
            await faceapi.nets.tinyFaceDetector.loadFromUri('/models');
            await faceapi.nets.faceExpressionNet.loadFromUri('/models');
            modelsLoaded = true;
            faceMood.innerText = "Detecting...";
        }

        if (!webcam.srcObject) {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            webcam.srcObject = stream;
        }
        
        // Genuine face detection logic
        clearInterval(faceInterval);
        faceInterval = setInterval(async () => {
            if (currentUser && webcam.readyState === 4) {
                const detections = await faceapi.detectSingleFace(webcam, new faceapi.TinyFaceDetectorOptions()).withFaceExpressions();
                if (detections) {
                    const expressions = detections.expressions;
                    
                    // Boost 'sad' confidence to make subtle frowns much easier to detect
                    if (expressions.sad !== undefined) {
                        expressions.sad *= 2.0; 
                    }

                    // Find emotion with highest probability
                    const topEmotion = Object.keys(expressions).reduce((a, b) => expressions[a] > expressions[b] ? a : b);

                    // Map generic face-api text to clean format
                    const emotionMap = {
                        neutral: 'Neutral', sad: 'Sad', happy: 'Happy', 
                        angry: 'Angry', fearful: 'Fearful', disgusted: 'Disgusted', surprised: 'Surprised'
                    };
                    faceMood.innerText = emotionMap[topEmotion] || topEmotion;
                } else {
                    faceMood.innerText = "No Face Found";
                }
            }
        }, 800); // 800ms to save CPU power
    } catch (err) {
        console.error("Camera error:", err);
    }
}

function stopCamera() {
    clearInterval(faceInterval);
    if (webcam.srcObject) {
        webcam.srcObject.getTracks().forEach(track => track.stop());
        webcam.srcObject = null;
    }
}

// --- Voice Recording & Transcribe ---
let mediaRecorder;
let audioChunks = [];
let recordTimerInterval;
let recordSeconds = 0;
const recordTimer = document.getElementById('record-timer');
const unifiedScore = document.getElementById('unified-score');

recordAudioLarge.onclick = startRecording;
recordVoiceBtn.onclick = startRecording;

let recognition;
let currentTranscript = '';
const liveTranscript = document.getElementById('live-transcript');

function updateTimer() {
    recordSeconds++;
    const mins = String(Math.floor(recordSeconds / 60)).padStart(2, '0');
    const secs = String(recordSeconds % 60).padStart(2, '0');
    recordTimer.innerText = `${mins}:${secs}`;
}

async function startRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        recordAudioLarge.innerText = '🔴';
        recordVoiceBtn.innerText = '🎤';
        recordVoiceBtn.classList.remove('bg-red-500/20', 'text-red-400');
        clearInterval(recordTimerInterval);
        return;
    }

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];
    recordSeconds = 0;
    recordTimer.innerText = '00:00';
    recordTimerInterval = setInterval(updateTimer, 1000);

    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
    mediaRecorder.onstop = async () => {
        // Stop recognition first but wait a moment for final chunks
        if (recognition) recognition.stop();
        await new Promise(r => setTimeout(r, 1000)); 

        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        const audioUrl = URL.createObjectURL(audioBlob);
        const transcript = currentTranscript.trim();
        
        // Add user's voice note to the chat immediately
        addMessage('user', transcript || "Voice message", audioUrl);
        chatInput.value = ''; // Clear for next input
        if (liveTranscript) {
            liveTranscript.classList.add('hidden');
            liveTranscript.innerText = "Listening...";
        }

        const thinkingDiv = document.createElement('div');
        const vocalStatus = document.getElementById('vocal-status');
        if (vocalStatus) vocalStatus.classList.remove('hidden');

        thinkingDiv.className = 'message bot px-5 py-3 rounded-2xl bg-white/5 border border-white/10 self-start max-w-[80%] animate-pulse italic text-gray-400';
        thinkingDiv.innerText = 'Analyzing voice and tone...';
        chatMessages.appendChild(thinkingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        const fd = new FormData();
        fd.append('user_id', currentUser.id);
        fd.append('file', audioBlob, 'record.wav');
        if (transcript) fd.append('text', transcript);

        try {
            const resp = await fetch(`${API_URL}/analyze/audio`, { method: 'POST', body: fd });
            const data = await resp.json();
            
            // Output the smartly formatted reply (with any suggestions)
            addMessage('bot', data.reply);
            
            // Update unified score
            unifiedScore.innerText = `${data.score > 0 ? '+' : ''}${data.score.toFixed(1)}`;
            unifiedScore.classList.remove('text-red-400', 'text-green-400', 'text-gray-400');
            if (data.score > 0) unifiedScore.classList.add('text-green-400');
            else if (data.score < 0) unifiedScore.classList.add('text-red-400');
            else unifiedScore.classList.add('text-gray-400');
            
            loadHistory(); // refresh the chart with new data
            loadVoiceNotes(); // refresh the voice notes list
        } catch (err) {
            console.error("Audio upload failed", err);
            addMessage('bot', "Sorry, I couldn't analyze your voice right now. Please check your connection.");
        } finally {
            thinkingDiv.remove();
            if (vocalStatus) vocalStatus.classList.add('hidden');
            currentTranscript = '';
        }
    };

    mediaRecorder.start();
    recordAudioLarge.innerText = '⏹️';
    recordVoiceBtn.innerText = '⏹️';
    recordVoiceBtn.classList.add('bg-red-500/20', 'text-red-400');
    
    currentTranscript = '';
    if (liveTranscript) {
        liveTranscript.innerText = "Listening...";
        liveTranscript.classList.remove('hidden');
    }

    // Web Speech API for transcribing
    recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = currentLang; 
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event) => {
        let finalTranscript = '';
        let interimTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                finalTranscript += event.results[i][0].transcript;
            } else {
                interimTranscript += event.results[i][0].transcript;
            }
        }
        if (finalTranscript) {
            currentTranscript += ' ' + finalTranscript;
            chatInput.value = currentTranscript.trim();
        }
        if (liveTranscript) {
            liveTranscript.innerText = (currentTranscript + ' ' + interimTranscript).trim() || 'Listening...';
        }
    };
    recognition.start();
}

// --- Charts ---
function initChart() {
    const ctx = document.getElementById('moodChart').getContext('2d');
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Mood Score (-10 to 10)',
                data: [],
                borderColor: '#9b51e0',
                backgroundColor: 'rgba(155, 81, 224, 0.1)',
                borderWidth: 3,
                tension: 0.4,
                fill: true,
                pointBackgroundColor: '#9b51e0',
                pointRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { min: -10, max: 10, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#888' } },
                x: { grid: { display: false }, ticks: { color: '#888' } }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

async function loadHistory() {
    const resp = await fetch(`${API_URL}/mood/history/${currentUser.id}`);
    const data = await resp.json();
    
    // Update Chart
    chart.data.labels = data.history.map(h => new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    chart.data.datasets[0].data = data.history.map(h => h.score);
    chart.update();

    // Alert
    if (data.alert) {
        alertBanner.classList.remove('hidden');
    } else {
        alertBanner.classList.add('hidden');
    }
}

async function loadVoiceNotes() {
    if (!currentUser || !voiceNotesList) return;
    try {
        const resp = await fetch(`${API_URL}/voice_history/${currentUser.id}`);
        const notes = await resp.json();
        
        voiceNotesList.innerHTML = notes.length ? '' : '<p class="text-gray-500">Record to save notes...</p>';
        
        notes.slice(0, 10).forEach(note => { // Show last 10
            const div = document.createElement('div');
            div.className = 'p-3 bg-white/5 rounded-xl border border-white/5 flex flex-col space-y-2';
            const date = new Date(note.timestamp).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            div.innerHTML = `
                <div class="flex justify-between items-center text-[10px] text-gray-400">
                    <span>${date}</span>
                    <span class="text-purple-400 font-bold">Voice Note</span>
                </div>
                <audio controls src="${API_URL}${note.url}" class="w-full h-8 opacity-70 hover:opacity-100 transition-opacity"></audio>
                <p class="text-[10px] text-gray-300 italic opacity-80 mt-1">${note.text || 'No transcription available'}</p>
            `;
            voiceNotesList.appendChild(div);
        });
    } catch (err) {
        console.error("Failed to load voice notes", err);
    }
}
