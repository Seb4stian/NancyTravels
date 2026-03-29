/**
 * chat.js – NancyTravels frontend chat logic
 *
 * Handles:
 * - Sending/receiving chat messages
 * - Text-to-Speech (TTS) playback of assistant replies
 * - Voice recording + Speech-to-Text (STT) via the Microphone API
 * - Auto-growing textarea
 * - Markdown-to-HTML rendering for assistant messages
 * - Language detection (uses last user message language)
 */

(function () {
  "use strict";

  // ── State ────────────────────────────────────────────────────────────────
  let conversationHistory = []; // [{role, content}, ...]
  let currentLanguage = window.NANCY_DEFAULT_LANGUAGE || "en";
  let isLoading = false;

  // Voice recording state
  let mediaRecorder = null;
  let audioChunks = [];
  let isRecording = false;

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const chatContainer = document.getElementById("chatContainer");
  const userInput = document.getElementById("userInput");
  const sendBtn = document.getElementById("sendBtn");
  const micBtn = document.getElementById("micBtn");
  const recordingStatus = document.getElementById("recordingStatus");
  const ttsAudio = document.getElementById("ttsAudio");

  // ── Initialise ────────────────────────────────────────────────────────────
  userInput.addEventListener("keydown", handleKeyDown);
  userInput.addEventListener("input", autoGrow);
  sendBtn.addEventListener("click", handleSend);
  micBtn.addEventListener("click", handleMic);

  // ── Send helpers ──────────────────────────────────────────────────────────

  /**
   * Handle Enter (send) / Shift+Enter (newline).
   */
  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  /**
   * Auto-grow the textarea up to ~140 px.
   */
  function autoGrow() {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 140) + "px";
  }

  /**
   * Send the current input text as a chat message.
   */
  async function handleSend() {
    const text = userInput.value.trim();
    if (!text || isLoading) return;

    userInput.value = "";
    userInput.style.height = "auto";

    appendMessage("user", text);
    conversationHistory.push({ role: "user", content: text });

    await sendMessage(text);
  }

  /**
   * Core function that POSTs to /api/chat and handles the response.
   */
  async function sendMessage(text) {
    setLoading(true);
    const typingId = showTyping();

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          history: conversationHistory.slice(0, -1), // exclude latest (already added)
          language: currentLanguage,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Server error");
      }

      removeTyping(typingId);

      const reply = data.reply || "I'm sorry, I couldn't generate a response. Please try again.";
      appendMessage("assistant", reply);
      conversationHistory.push({ role: "assistant", content: reply });

      // Update language from server response
      if (data.language) currentLanguage = data.language;

      // Speak the reply aloud
      speakText(reply);
    } catch (err) {
      removeTyping(typingId);
      const errMsg = `⚠️ ${err.message || "Network error. Please check your connection and try again."}`;
      appendMessage("assistant", errMsg);
    } finally {
      setLoading(false);
    }
  }

  // ── Message rendering ─────────────────────────────────────────────────────

  /**
   * Append a message bubble to the chat container.
   */
  function appendMessage(role, content) {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${role === "user" ? "user-message" : "assistant-message"}`;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = role === "user" ? "👤" : "🌍";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.innerHTML = renderMarkdown(content);

    wrapper.appendChild(avatar);
    wrapper.appendChild(bubble);
    chatContainer.appendChild(wrapper);
    scrollToBottom();
  }

  /**
   * Show a typing indicator and return its element ID.
   */
  function showTyping() {
    const id = "typing-" + Date.now();
    const wrapper = document.createElement("div");
    wrapper.className = "message assistant-message typing-message";
    wrapper.id = id;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = "🌍";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.innerHTML = `
      <div class="typing-dots">
        <span></span><span></span><span></span>
      </div>`;

    wrapper.appendChild(avatar);
    wrapper.appendChild(bubble);
    chatContainer.appendChild(wrapper);
    scrollToBottom();
    return id;
  }

  function removeTyping(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  // ── Markdown renderer (lightweight, no library dependency) ─────────────

  /**
   * Convert a subset of Markdown to HTML.
   * Supported: headings, bold, italic, code, links, lists, hr.
   */
  function renderMarkdown(text) {
    if (!text) return "";

    // Escape HTML first (except we'll intentionally add tags below)
    let html = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Fenced code blocks
    html = html.replace(/```[\s\S]*?```/g, (m) => {
      const code = m.slice(3, -3).replace(/^\n/, "");
      return `<pre><code>${code}</code></pre>`;
    });

    // Inline code
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

    // Headings
    html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
    html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
    html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");

    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/__(.+?)__/g, "<strong>$1</strong>");

    // Italic (single * or _ not preceded/followed by another * or _, no newlines inside)
    html = html.replace(/(?<!\*)\*(?!\*)([^\*\n]+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");
    html = html.replace(/(?<!_)_(?!_)([^_\n]+?)(?<!_)_(?!_)/g, "<em>$1</em>");

    // Links  [text](url)
    html = html.replace(
      /\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    );

    // Horizontal rule
    html = html.replace(/^---+$/gm, "<hr />");

    // Unordered lists
    html = html.replace(/^(\s*[-*+] .+)(\n\s*[-*+] .+)*/gm, (block) => {
      const items = block
        .split("\n")
        .filter(Boolean)
        .map((line) => `<li>${line.replace(/^\s*[-*+] /, "")}</li>`)
        .join("");
      return `<ul>${items}</ul>`;
    });

    // Ordered lists
    html = html.replace(/^(\s*\d+\. .+)(\n\s*\d+\. .+)*/gm, (block) => {
      const items = block
        .split("\n")
        .filter(Boolean)
        .map((line) => `<li>${line.replace(/^\s*\d+\. /, "")}</li>`)
        .join("");
      return `<ol>${items}</ol>`;
    });

    // Paragraphs (convert double newlines)
    html = html
      .split(/\n{2,}/)
      .map((para) => {
        para = para.trim();
        if (!para) return "";
        // Don't wrap block-level tags in <p>
        if (/^<(h[1-6]|ul|ol|pre|hr|blockquote)/i.test(para)) return para;
        return `<p>${para.replace(/\n/g, "<br />")}</p>`;
      })
      .join("\n");

    return html;
  }

  // ── TTS ──────────────────────────────────────────────────────────────────

  /**
   * Call /api/tts and play the returned audio.
   * Strips Markdown before sending to TTS.
   */
  async function speakText(text) {
    // Strip markdown for cleaner speech
    const plain = text
      .replace(/[#*_`\[\]]/g, "")
      .replace(/https?:\/\/\S+/g, "")
      .replace(/\n+/g, " ")
      .trim();

    if (!plain) return;

    try {
      const response = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: plain.slice(0, 500) }), // limit for TTS
      });

      if (!response.ok) return; // Silently skip if TTS unavailable

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);

      ttsAudio.src = url;
      ttsAudio.play().catch(() => {}); // Ignore autoplay policy errors
      ttsAudio.onended = () => URL.revokeObjectURL(url);
    } catch (_) {
      // TTS is optional – do not show errors to the user
    }
  }

  // ── STT / Microphone ──────────────────────────────────────────────────────

  /**
   * Toggle voice recording on mic button click.
   */
  async function handleMic() {
    if (isRecording) {
      stopRecording();
    } else {
      await startRecording();
    }
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      audioChunks = [];
      mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        await processAudioRecording();
      };

      mediaRecorder.start();
      isRecording = true;

      micBtn.classList.add("recording");
      recordingStatus.classList.remove("hidden");
    } catch (err) {
      alert(
        "Microphone access denied. Please allow microphone access in your browser to use voice input."
      );
    }
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
    isRecording = false;
    micBtn.classList.remove("recording");
    recordingStatus.classList.add("hidden");
  }

  async function processAudioRecording() {
    if (audioChunks.length === 0) return;

    const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.webm");

    setLoading(true);
    const typingId = showTyping();

    try {
      const response = await fetch("/api/stt", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      removeTyping(typingId);

      if (!response.ok || !data.transcript) {
        appendMessage("assistant", "⚠️ Could not transcribe your voice message. Please try again or type your question.");
        setLoading(false);
        return;
      }

      // Put transcribed text in input and send
      userInput.value = data.transcript;
      autoGrow();
      setLoading(false);
      await handleSend();
    } catch (err) {
      removeTyping(typingId);
      appendMessage("assistant", "⚠️ Voice transcription failed. Please check your connection and try again.");
      setLoading(false);
    }
  }

  // ── UI helpers ────────────────────────────────────────────────────────────

  function setLoading(state) {
    isLoading = state;
    sendBtn.disabled = state;
    userInput.disabled = state;
    micBtn.disabled = state;
  }
})();
