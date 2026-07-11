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

    // Toast Notification helper
    function showToast(message, isError = false) {
        toast.textContent = message;
        toast.style.borderLeftColor = isError ? "var(--accent-pink)" : "#10b981";
        toast.classList.add("show");
        setTimeout(() => {
            toast.classList.remove("show");
        }, 4000);
    }

    // Trigger File Picker click on dropZone click
    dropZone.addEventListener("click", () => {
        fileInput.click();
    });

    // File Input change event
    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    // Drag-and-drop events
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

    // Handle Upload
    async function handleFileUpload(file) {
        if (file.type !== "application/pdf" && !file.name.endsWith(".pdf")) {
            showToast("Only PDF files are supported.", true);
            return;
        }

        // Reset state
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

            // Success
            documentChunks = data.chunks;
            docStatusChunks.textContent = data.chunk_count || documentChunks.length;
            docStatusState.textContent = "Ready";
            docStatusState.className = "status-value ready";
            chatStatusDot.className = "status-dot active";
            
            chatInput.disabled = false;
            chatInput.placeholder = "Ask a question about the document...";
            chatInput.focus();
            sendBtn.disabled = false;

            // Clear empty state
            if (emptyState) {
                emptyState.remove();
            }

            // Append System Message
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

    // Append Chat Message
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
                // truncate long source text
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

    // Append System Message
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

    // Add typing indicator
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

    // Chat Submission
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const question = chatInput.value.trim();
        if (!question || documentChunks.length === 0) return;

        // Append user question
        appendMessage("user", question);
        chatInput.value = "";
        chatInput.focus();

        // Show typing indicator
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

    // Extremely simple markdown formatter
    function formatMarkdown(text) {
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }
});
