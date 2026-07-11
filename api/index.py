import os
import io
import math
import requests
from flask import Flask, request, jsonify

# ponytail: Helper to load .env variables locally without external package dependencies
def load_env():
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    # Strip surrounding quotes
                    v = v.strip("'\"")
                    os.environ[k] = v

# Load environment variables
load_env()

# Initialize Flask app
app = Flask(__name__)

# Enable CORS manually
@app.after_request
def add_cors_headers(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
    return response

# import pypdf safely
try:
    import pypdf
except ImportError:
    pypdf = None

# ponytail: Simple text splitter based on word count to avoid heavy langchain splitters
def split_text(text, chunk_size=2000, chunk_overlap=100):
    chunks = []
    words = text.split()
    current_chunk = []
    current_len = 0
    for word in words:
        current_chunk.append(word)
        current_len += len(word) + 1
        if current_len >= chunk_size:
            chunks.append(" ".join(current_chunk))
            # keep some overlap (e.g. last 10% of overlap words)
            overlap_words = current_chunk[-max(1, int(chunk_overlap/10)):]
            current_chunk = list(overlap_words)
            current_len = sum(len(w) + 1 for w in current_chunk)
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

# ponytail: Simple cosine similarity calculation to avoid numpy or scipy dependency
def cosine_similarity(v1, v2):
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(b * b for b in v2))
    if not magnitude1 or not magnitude2:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)

def get_api_key():
    return os.environ.get("GOOGLE_API_KEY")

def embed_texts(texts):
    api_key = get_api_key()
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is missing.")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents?key={api_key}"
    payload = {
        "requests": [
            {
                "model": "models/text-embedding-004",
                "content": {
                    "parts": [{"text": t}]
                }
            } for t in texts
        ]
    }
    
    response = requests.post(url, json=payload)
    response.raise_for_status()
    embeddings_data = response.json()
    return [emb["values"] for emb in embeddings_data["embeddings"]]

def embed_query(text):
    api_key = get_api_key()
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is missing.")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={api_key}"
    payload = {
        "model": "models/text-embedding-004",
        "content": {
            "parts": [{"text": text}]
        }
    }
    
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()["embedding"]["values"]

def generate_response(system_instruction, user_prompt):
    api_key = get_api_key()
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is missing.")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}]
            }
        ],
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "generationConfig": {
            "temperature": 0.0
        }
    }
    
    response = requests.post(url, json=payload)
    response.raise_for_status()
    res_json = response.json()
    
    try:
        return res_json["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return f"Error: Could not parse response from Gemini. Details: {res_json}"


# -----------------------------
# COMBINED EMBEDDED FRONTEND HTML/CSS/JS (Bulletproof Vercel single-file routing)
# -----------------------------
INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sleek RAG Chatbot</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: rgba(18, 18, 26, 0.6);
            --glass-bg: rgba(25, 25, 35, 0.45);
            --glass-border: rgba(255, 255, 255, 0.08);
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
            --accent-pink: #ec4899;
            --gradient-glow: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            --gradient-glow-pink: linear-gradient(135deg, var(--accent-purple), var(--accent-pink));
            --card-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            --font-heading: 'Outfit', sans-serif;
            --font-body: 'Plus Jakarta Sans', sans-serif;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            background-color: var(--bg-primary);
            color: var(--text-primary);
            font-family: var(--font-body);
            min-height: 100vh;
            overflow-x: hidden;
            display: flex;
            justify-content: center;
            align-items: center;
            position: relative;
        }

        /* Ambient Background Lights */
        .bg-glow-1 {
            position: absolute;
            width: 600px;
            height: 600px;
            background: radial-gradient(circle, rgba(139, 92, 246, 0.12) 0%, rgba(0, 0, 0, 0) 70%);
            top: -200px;
            left: -200px;
            z-index: -1;
            pointer-events: none;
            animation: float 20s infinite alternate;
        }

        .bg-glow-2 {
            position: absolute;
            width: 600px;
            height: 600px;
            background: radial-gradient(circle, rgba(59, 130, 246, 0.12) 0%, rgba(0, 0, 0, 0) 70%);
            bottom: -200px;
            right: -200px;
            z-index: -1;
            pointer-events: none;
            animation: float 25s infinite alternate-reverse;
        }

        @keyframes float {
            0% { transform: translate(0, 0) scale(1); }
            100% { transform: translate(50px, 50px) scale(1.1); }
        }

        /* Container */
        .app-container {
            width: 90vw;
            max-width: 1200px;
            height: 85vh;
            min-height: 600px;
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
            border-radius: 24px;
            box-shadow: var(--card-shadow);
            display: grid;
            grid-template-columns: 320px 1fr;
            overflow: hidden;
            animation: fadeIn 0.8s ease-out;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(15px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Sidebar */
        .sidebar {
            background: rgba(10, 10, 15, 0.4);
            border-right: 1px solid var(--glass-border);
            padding: 30px;
            display: flex;
            flex-direction: column;
            gap: 30px;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .brand-icon {
            width: 40px;
            height: 40px;
            background: var(--gradient-glow);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 20px;
            box-shadow: 0 0 15px rgba(139, 92, 246, 0.4);
        }

        .brand-title {
            font-family: var(--font-heading);
            font-size: 22px;
            font-weight: 700;
            background: linear-gradient(to right, #ffffff, #9ca3af);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .section-title {
            font-family: var(--font-heading);
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: var(--text-secondary);
            margin-bottom: 12px;
        }

        /* Upload Area */
        .upload-zone {
            border: 2px dashed rgba(255, 255, 255, 0.15);
            border-radius: 16px;
            padding: 30px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            background: rgba(255, 255, 255, 0.02);
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 12px;
        }

        .upload-zone:hover, .upload-zone.dragover {
            border-color: var(--accent-blue);
            background: rgba(59, 130, 246, 0.05);
            box-shadow: 0 0 20px rgba(59, 130, 246, 0.1);
        }

        .upload-icon {
            font-size: 32px;
            color: var(--text-secondary);
            transition: transform 0.3s ease;
        }

        .upload-zone:hover .upload-icon {
            transform: translateY(-4px) scale(1.1);
            color: var(--accent-blue);
        }

        .upload-text {
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.5;
        }

        .upload-text span {
            color: var(--accent-blue);
            font-weight: 600;
        }

        #file-input {
            display: none;
        }

        /* Status Card */
        .status-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 15px;
            transition: all 0.3s ease;
        }

        .status-row {
            display: flex;
            justify-content: space-between;
            font-size: 13px;
        }

        .status-label {
            color: var(--text-secondary);
        }

        .status-value {
            font-weight: 600;
        }

        .status-value.processing {
            color: var(--accent-purple);
            animation: pulse 1.5s infinite;
        }

        .status-value.ready {
            color: #10b981;
        }

        @keyframes pulse {
            0% { opacity: 0.6; }
            50% { opacity: 1; }
            100% { opacity: 0.6; }
        }

        /* Main Chat Area */
        .chat-container {
            display: flex;
            flex-direction: column;
            height: 100%;
        }

        .chat-header {
            padding: 20px 30px;
            border-bottom: 1px solid var(--glass-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .chat-info {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #ef4444;
            transition: background-color 0.3s ease;
        }

        .status-dot.active {
            background: #10b981;
        }

        .chat-title {
            font-family: var(--font-heading);
            font-weight: 600;
            font-size: 16px;
        }

        /* Messages */
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 30px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            scroll-behavior: smooth;
        }

        .chat-messages::-webkit-scrollbar {
            width: 6px;
        }

        .chat-messages::-webkit-scrollbar-track {
            background: transparent;
        }

        .chat-messages::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.08);
            border-radius: 10px;
        }

        .chat-messages::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.15);
        }

        .message {
            display: flex;
            gap: 16px;
            max-width: 80%;
            animation: messageSlideIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        @keyframes messageSlideIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message.user {
            align-self: flex-end;
            flex-direction: row-reverse;
        }

        .message.assistant {
            align-self: flex-start;
        }

        .message-avatar {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            flex-shrink: 0;
        }

        .message.user .message-avatar {
            background: var(--gradient-glow-pink);
            color: white;
        }

        .message.assistant .message-avatar {
            background: var(--gradient-glow);
            color: white;
        }

        .message-content {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--glass-border);
            padding: 16px 20px;
            border-radius: 20px;
            font-size: 14px;
            line-height: 1.6;
            word-break: break-word;
        }

        .message.user .message-content {
            background: rgba(139, 92, 246, 0.15);
            border-color: rgba(139, 92, 246, 0.25);
            border-top-right-radius: 4px;
        }

        .message.assistant .message-content {
            background: rgba(255, 255, 255, 0.04);
            border-top-left-radius: 4px;
        }

        .message-sources {
            margin-top: 10px;
            padding-top: 8px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            display: flex;
            flex-direction: column;
            gap: 5px;
        }

        .source-item {
            font-size: 11px;
            color: var(--text-secondary);
            background: rgba(255, 255, 255, 0.02);
            padding: 6px 10px;
            border-radius: 6px;
            border-left: 2px solid var(--accent-blue);
        }

        /* Empty State */
        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            text-align: center;
            color: var(--text-secondary);
            gap: 15px;
            padding: 40px;
        }

        .empty-state-icon {
            font-size: 56px;
            background: var(--gradient-glow);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: pulse 2s infinite ease-in-out;
        }

        .empty-state-title {
            font-family: var(--font-heading);
            font-size: 20px;
            font-weight: 600;
            color: var(--text-primary);
        }

        .empty-state-desc {
            font-size: 14px;
            max-width: 400px;
            line-height: 1.5;
        }

        /* Input Section */
        .chat-input-container {
            padding: 20px 30px 30px;
        }

        .chat-input-wrapper {
            position: relative;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            padding: 6px;
            display: flex;
            align-items: center;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .chat-input-wrapper:focus-within {
            border-color: rgba(139, 92, 246, 0.4);
            box-shadow: 0 0 20px rgba(139, 92, 246, 0.15);
            background: rgba(255, 255, 255, 0.05);
        }

        .chat-input {
            flex: 1;
            background: transparent;
            border: none;
            outline: none;
            color: var(--text-primary);
            padding: 12px 16px;
            font-family: var(--font-body);
            font-size: 14px;
        }

        .chat-input::placeholder {
            color: var(--text-secondary);
        }

        .send-btn {
            width: 40px;
            height: 40px;
            border-radius: 12px;
            background: var(--gradient-glow);
            border: none;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 4px 10px rgba(139, 92, 246, 0.3);
        }

        .send-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 15px rgba(139, 92, 246, 0.5);
        }

        .send-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        /* Typing Indicator */
        .typing-indicator {
            display: flex;
            gap: 4px;
            padding: 6px 10px;
            align-items: center;
            height: 20px;
        }

        .typing-dot {
            width: 6px;
            height: 6px;
            background-color: var(--text-secondary);
            border-radius: 50%;
            animation: typingBounce 1.4s infinite ease-in-out both;
        }

        .typing-dot:nth-child(1) { animation-delay: -0.32s; }
        .typing-dot:nth-child(2) { animation-delay: -0.16s; }

        @keyframes typingBounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }

        /* Toast */
        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(18, 18, 26, 0.95);
            border: 1px solid var(--glass-border);
            border-left: 4px solid var(--accent-pink);
            border-radius: 8px;
            padding: 16px 24px;
            color: var(--text-primary);
            box-shadow: var(--card-shadow);
            z-index: 1000;
            font-size: 13px;
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .toast.show {
            transform: translateY(0);
            opacity: 1;
        }

        @media (max-width: 768px) {
            .app-container {
                grid-template-columns: 1fr;
                height: 95vh;
            }
            .sidebar {
                border-right: none;
                border-bottom: 1px solid var(--glass-border);
                padding: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="bg-glow-1"></div>
    <div class="bg-glow-2"></div>

    <div class="app-container">
        <!-- Sidebar -->
        <aside class="sidebar">
            <div class="brand">
                <div class="brand-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v1a7 7 0 0 1-14 0v-1"/><line x1="12" x2="12" y1="19" y2="22"/></svg>
                </div>
                <h1 class="brand-title">RAG Chatbot</h1>
            </div>

            <div>
                <h2 class="section-title">Upload Source</h2>
                <div class="upload-zone" id="drop-zone">
                    <div class="upload-icon">
                        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                    </div>
                    <p class="upload-text">
                        Drag & drop your PDF or <br>
                        <span>browse files</span>
                    </p>
                    <input type="file" id="file-input" accept=".pdf">
                </div>
            </div>

            <div>
                <h2 class="section-title">Status</h2>
                <div class="status-card">
                    <div class="status-row">
                        <span class="status-label">Document:</span>
                        <span class="status-value" id="doc-status-name">None</span>
                    </div>
                    <div class="status-row">
                        <span class="status-label">Chunks:</span>
                        <span class="status-value" id="doc-status-chunks">0</span>
                    </div>
                    <div class="status-row">
                        <span class="status-label">Status:</span>
                        <span class="status-value" id="doc-status-state">Not Ready</span>
                    </div>
                </div>
            </div>
        </aside>

        <!-- Main Chat Area -->
        <main class="chat-container">
            <header class="chat-header">
                <div class="chat-info">
                    <div class="status-dot" id="chat-status-dot"></div>
                    <h2 class="chat-title">Assistant Q&A</h2>
                </div>
            </header>

            <!-- Chat Messages -->
            <div class="chat-messages" id="chat-messages">
                <div class="empty-state" id="empty-state">
                    <div class="empty-state-icon">
                        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>
                    </div>
                    <h3 class="empty-state-title">Ready for your Knowledge Base</h3>
                    <p class="empty-state-desc">Upload a PDF document to generate vector embeddings. The chatbot will answer your questions using the document context.</p>
                </div>
            </div>

            <!-- Chat Input -->
            <div class="chat-input-container">
                <form id="chat-form" class="chat-input-wrapper">
                    <input type="text" id="chat-input" class="chat-input" placeholder="Upload a document to start chatting..." disabled>
                    <button type="submit" id="send-btn" class="send-btn" disabled>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                    </button>
                </form>
            </div>
        </main>
    </div>

    <!-- Toast Notification -->
    <div class="toast" id="toast">Notification message here</div>

    <script>
        document.addEventListener("DOMContentLoaded", () => {
            const dropZone = document.getElementById("drop-zone");
            const fileInput = document.getElementById("file-input");
            const docStatusName = document.getElementById("doc-status-name");
            const docStatusChunks = document.getElementById("doc-status-chunks");
            const docStatusState = document.getElementById("doc-status-state");
            const chatStatusDot = document.getElementById("chat-status-dot");
            const chatMessages = document.getElementById("chat-messages");
            const emptyState = document.getElementById("empty-state");
            const chatForm = document.getElementById("chat-form");
            const chatInput = document.getElementById("chat-input");
            const sendBtn = document.getElementById("send-btn");
            const toast = document.getElementById("toast");

            let documentChunks = [];

            function showToast(message, isError = false) {
                toast.textContent = message;
                toast.style.borderLeftColor = isError ? "var(--accent-pink)" : "#10b981";
                toast.classList.add("show");
                setTimeout(() => {
                    toast.classList.remove("show");
                }, 4000);
            }

            dropZone.addEventListener("click", () => {
                fileInput.click();
            });

            fileInput.addEventListener("change", (e) => {
                if (e.target.files.length > 0) {
                    handleFileUpload(e.target.files[0]);
                }
            });

            ["dragenter", "dragover"].forEach(eventName => {
                dropZone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    dropZone.classList.add("dragover");
                }, false);
            });

            ["dragleave", "drop"].forEach(eventName => {
                dropZone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    dropZone.classList.remove("dragover");
                }, false);
            });

            dropZone.addEventListener("drop", (e) => {
                const dt = e.dataTransfer;
                const files = dt.files;
                if (files.length > 0) {
                    fileInput.files = files;
                    handleFileUpload(files[0]);
                }
            });

            async function handleFileUpload(file) {
                if (file.type !== "application/pdf" && !file.name.endsWith(".pdf")) {
                    showToast("Only PDF files are supported.", true);
                    return;
                }

                docStatusName.textContent = file.name;
                docStatusChunks.textContent = "0";
                docStatusState.textContent = "Processing...";
                docStatusState.className = "status-value processing";
                chatStatusDot.className = "status-dot";
                chatInput.disabled = true;
                chatInput.placeholder = "Processing PDF, please wait...";
                sendBtn.disabled = true;

                const formData = new FormData();
                formData.append("file", file);

                try {
                    const response = await fetch("/api/upload", {
                        method: "POST",
                        body: formData
                    });

                    const data = await response.json();
                    if (!response.ok) {
                        throw new Error(data.error || "Failed to process PDF.");
                    }

                    documentChunks = data.chunks;
                    docStatusChunks.textContent = data.chunk_count || documentChunks.length;
                    docStatusState.textContent = "Ready";
                    docStatusState.className = "status-value ready";
                    chatStatusDot.className = "status-dot active";
                    
                    chatInput.disabled = false;
                    chatInput.placeholder = "Ask a question about the document...";
                    chatInput.focus();
                    sendBtn.disabled = false;

                    if (emptyState) {
                        emptyState.remove();
                    }

                    appendSystemMessage(`📄 Loaded **${file.name}** (${data.chunk_count} text segments). Ask me anything about it!`);
                    showToast("Document uploaded and vectorized successfully!");
                } catch (error) {
                    console.error(error);
                    docStatusState.textContent = "Error";
                    docStatusState.className = "status-value";
                    chatInput.placeholder = "Upload failed. Try again.";
                    showToast(error.message || "An error occurred during upload.", true);
                }
            }

            function appendMessage(sender, text, sources = []) {
                const messageDiv = document.createElement("div");
                messageDiv.className = `message ${sender}`;

                const avatar = document.createElement("div");
                avatar.className = "message-avatar";
                avatar.innerHTML = sender === "user" 
                    ? `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`
                    : `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/><path d="M15 3v18"/><path d="M3 9h18"/><path d="M3 15h18"/></svg>`;

                const content = document.createElement("div");
                content.className = "message-content";
                content.innerHTML = formatMarkdown(text);

                if (sources && sources.length > 0) {
                    const sourcesDiv = document.createElement("div");
                    sourcesDiv.className = "message-sources";
                    sourcesDiv.innerHTML = `<span style="font-weight: 600; font-size: 11px;">Context references:</span>`;
                    
                    sources.forEach((src, idx) => {
                        const srcItem = document.createElement("div");
                        srcItem.className = "source-item";
                        const snippet = src.length > 150 ? src.substring(0, 150) + "..." : src;
                        srcItem.textContent = `[Segment ${idx + 1}] ${snippet}`;
                        sourcesDiv.appendChild(srcItem);
                    });
                    content.appendChild(sourcesDiv);
                }

                messageDiv.appendChild(avatar);
                messageDiv.appendChild(content);
                chatMessages.appendChild(messageDiv);
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }

            function appendSystemMessage(text) {
                const msg = document.createElement("div");
                msg.style.alignSelf = "center";
                msg.style.background = "rgba(255, 255, 255, 0.05)";
                msg.style.borderRadius = "30px";
                msg.style.padding = "6px 16px";
                msg.style.fontSize = "12px";
                msg.style.color = "var(--text-secondary)";
                msg.style.border = "1px solid var(--glass-border)";
                msg.style.margin = "10px 0";
                msg.innerHTML = formatMarkdown(text);
                chatMessages.appendChild(msg);
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }

            let typingIndicatorElement = null;
            function showTypingIndicator() {
                if (typingIndicatorElement) return;

                const messageDiv = document.createElement("div");
                messageDiv.className = "message assistant";

                const avatar = document.createElement("div");
                avatar.className = "message-avatar";
                avatar.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/><path d="M15 3v18"/><path d="M3 9h18"/><path d="M3 15h18"/></svg>`;

                const content = document.createElement("div");
                content.className = "message-content";
                content.innerHTML = `
                    <div class="typing-indicator">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                `;

                messageDiv.appendChild(avatar);
                messageDiv.appendChild(content);
                chatMessages.appendChild(messageDiv);
                chatMessages.scrollTop = chatMessages.scrollHeight;
                typingIndicatorElement = messageDiv;
            }

            function removeTypingIndicator() {
                if (typingIndicatorElement) {
                    typingIndicatorElement.remove();
                    typingIndicatorElement = null;
                }
            }

            chatForm.addEventListener("submit", async (e) => {
                e.preventDefault();
                const question = chatInput.value.trim();
                if (!question || documentChunks.length === 0) return;

                appendMessage("user", question);
                chatInput.value = "";
                chatInput.focus();

                showTypingIndicator();

                try {
                    const response = await fetch("/api/query", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            question: question,
                            chunks: documentChunks
                        })
                    });

                    const data = await response.json();
                    removeTypingIndicator();

                    if (!response.ok) {
                        throw new Error(data.error || "Query failed.");
                    }

                    appendMessage("assistant", data.answer, data.sources);
                } catch (error) {
                    console.error(error);
                    removeTypingIndicator();
                    appendMessage("assistant", `⚠️ **Error:** ${error.message || "Something went wrong. Please try again."}`);
                }
            });

            function formatMarkdown(text) {
                return text
                    .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
                    .replace(/\\*(.*?)\\*/g, '<em>$1</em>')
                    .replace(/`([^`]+)`/g, '<code>$1</code>')
                    .replace(/\\n/g, '<br>');
            }
        });
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    return INDEX_HTML

@app.route("/api/upload", methods=["POST", "OPTIONS"])
def upload_pdf():
    if request.method == "OPTIONS":
        return "", 200
        
    if not pypdf:
        return jsonify({"error": "pypdf library not installed on backend."}), 500
        
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request."}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected."}), 400
        
    try:
        # Extract text using pypdf from memory bytes
        file_bytes = file.read()
        pdf_file = io.BytesIO(file_bytes)
        reader = pypdf.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        
        if not text.strip():
            return jsonify({"error": "No readable text found in the PDF."}), 400
            
        chunks = split_text(text)
        if not chunks:
            return jsonify({"error": "No content chunks generated."}), 400
            
        # Batch embed the chunks
        embeddings = []
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i : i + batch_size]
            batch_embeddings = embed_texts(batch_chunks)
            embeddings.extend(batch_embeddings)
            
        chunk_data = []
        for c, emb in zip(chunks, embeddings):
            chunk_data.append({
                "text": c,
                "embedding": emb
            })
            
        return jsonify({
            "message": "PDF parsed and embedded successfully.",
            "chunk_count": len(chunk_data),
            "chunks": chunk_data
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/query", methods=["POST", "OPTIONS"])
def query():
    if request.method == "OPTIONS":
        return "", 200
        
    data = request.get_json() or {}
    question = data.get("question")
    chunks = data.get("chunks")
    
    if not question:
        return jsonify({"error": "Missing question."}), 400
    if not chunks:
        return jsonify({"error": "Missing chunks. Please upload a PDF first."}), 400
        
    try:
        # Embed question
        q_emb = embed_query(question)
        
        # Calculate similarity
        scored_chunks = []
        for c in chunks:
            text = c.get("text", "")
            emb = c.get("embedding")
            if not emb:
                continue
            sim = cosine_similarity(q_emb, emb)
            scored_chunks.append((sim, text))
            
        # Sort and take top 3
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_k = scored_chunks[:3]
        
        context = "\n\n".join(text for _, text in top_k)
        
        system_instruction = (
            "You are a helpful assistant. "
            "Answer ONLY using the provided context. "
            "If the answer is not in the context, say 'I don't know.'"
        )
        user_prompt = f"Context:\n{context}\n\nQuestion:\n{question}"
        
        answer = generate_response(system_instruction, user_prompt)
        
        return jsonify({
            "answer": answer,
            "sources": [text for _, text in top_k]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
