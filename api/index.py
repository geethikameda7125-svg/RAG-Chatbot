import os
import io
import math
import requests
from flask import Flask, request, jsonify, render_template

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

# Initialize Flask app using default templates and static settings
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

@app.route("/")
def home():
    return render_template("index.html")

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
