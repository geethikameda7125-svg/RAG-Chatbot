# RAG Chatbot (Local Deployment)

This is a local, privacy-focused RAG (Retrieval-Augmented Generation) chatbot application that runs entirely on your machine without external hosting.

## Features
- **Local Execution**: No cloud dependencies (except for the Gemini embedding model if using Google API).
- **Drag & Drop PDF Upload**: Simply drag a PDF onto the interface to upload.
- **Smart Chunking**: PDFs are automatically split into processable chunks for vectorization.
- **Vector Embeddings**: Uses Google's `text-embedding-004` model to convert text into searchable vectors.
- **Retrieval**: Finds the most relevant text chunks to answer your query.
- **AI Generation**: Uses Gemini 1.5 Flash to generate human-like responses based on the retrieved context.
- **Progress Tracking**: Real-time status updates for file processing and chat.

## Prerequisites
- **Node.js** (v16 or higher)
- **npm** (usually comes with Node.js)

## Setup Instructions

### 1. Environment Setup
1.  Open your terminal.
2.  Navigate to the project directory:
    ```bash
    cd d:\Desktop\chatbot\RAG-chatbot
    ```
3.  **Create a `.env` file** in the `api` directory (or root if configured there, but based on `index.py` it looks like `api/.env` or root).
    *   *Self-Correction*: Based on `load_env()` in `index.py`, the script looks for `.env` in the *current working directory* where Flask is run.
    *   So, create `.env` in `d:\Desktop\chatbot\RAG-chatbot`.

4.  Add your Google API Key to the `.env` file:
    ```env
    GOOGLE_API_KEY=[GCP_API_KEY]
    ```
    > **Note**: You need a Google AI Studio API Key for both the embedding model and the chat model.

5.  Install Python dependencies (if you haven't already):
    ```bash
    cd api
    pip install -r requirements.txt
    ```

6.  Install Node.js dependencies:
    ```bash
    cd ..
    npm install
    ```

### 2. Start the Application
1.  **Start the Backend (Python/Flask)**:
    Open a **new** terminal, navigate to the `api` folder, and run:
    ```bash
    cd api
    python index.py
    ```
    *   The server will start on `http://localhost:5000`.

2.  **Start the Frontend (HTML/JS)**:
    Open a **third** terminal (or use the same one if you don't mind stopping the backend), and run:
    ```bash
    cd ..
    npm start
    ```
    *   This will start a live server, usually on `http://localhost:5500`.
    *   **Important**: The front-end (`main.js`) expects the backend to be at `/api`. If your Flask server uses a different port (e.g., if you run `python index.py` in a different terminal), you **must** update `main.js` accordingly.

### 3. Usage
1.  Open your browser and go to the URL provided by `npm start` (e.g., `http://localhost:5500`).
2.  Drag and drop a PDF file into the grey box.
3.  Wait for the status to turn green and say "Ready".
4.  Ask questions about your document in the chat window.

## Troubleshooting
- **"Backend is down"**: Make sure the Flask server is running (`python index.py`) and you are using the same port in `main.js`.
- **"pypdf not installed"**: Run `pip install pypdf` in the `api` directory.
- **"400 No file part"**: Ensure you are sending a POST request with `enctype="multipart/form-data"` (handled by the default `upload.html`).
- ** CORS Errors**: If you get CORS errors, ensure the `add_cors_headers` function in `api/index.py` is uncommented and working, or update the `Access-Control-Allow-Origin` header.
