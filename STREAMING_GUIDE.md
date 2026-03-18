# 🎬 Streaming Responses - Gemini-Like AI Experience

Your speech guidance assistant now supports **real-time streaming responses** like Google Gemini! See AI responses appear token-by-token in real-time.

## ✨ What's New

### Streaming Features
- ⚡ **Real-time Token Streaming** — Text appears as it's generated
- 💬 **Gemini-like Web UI** — Beautiful, modern chat interface
- 🖥️ **Terminal Streaming** — Smooth streaming in the console
- 🔄 **Multi-Provider Support** — Works with OpenAI, Groq, and Ollama
- 📱 **Responsive Design** — Works on desktop and mobile
- 🎯 **Interactive Suggestions** — Click suggested responses

## 🚀 Getting Started

### Option 1: Web Dashboard (Recommended)
Perfect for a Gemini-like experience with beautiful UI:

```bash
python demo_web.py
# Then open: http://localhost:5000/streaming
```

**Features:**
- Chat-like interface with streaming responses
- Real-time status indicators
- Text-to-speech toggle
- Educational mode toggle
- Suggestion buttons for quick replies
- Responsive design

### Option 2: Terminal (Main App)
For a terminal-based experience:

```bash
python main.py
```

Responses will stream in real-time in your terminal with live text appearance!

## 🏗️ Architecture

### New Modules

#### `streaming_response.py`
Handles streaming from all LLM providers:
- `StreamingResponseHandler` class
- Supports OpenAI, Groq, and Ollama
- Token-by-token callback mechanism
- Async streaming support

#### Updated `display.py`
Added streaming display methods:
- `stream_response_start()` — Initialize streaming section
- `stream_token()` — Display individual token
- `stream_response_end()` — End streaming section

#### `streaming_assistant.html` (New)
Gemini-like web interface with:
- Modern chat UI inspired by Google Gemini
- Real-time streaming display
- Socket.IO for live updates
- Responsive design
- Interactive controls

## 💻 Usage Examples

### Web Dashboard Usage
1. Open http://localhost:5000/streaming
2. Click the microphone button to start recording
3. Speak your question or text
4. Watch the AI response stream in real-time
5. Click suggestions to continue the conversation

### Terminal Usage
1. Run `python main.py`
2. Speak when prompted
3. See the response stream line-by-line:
```
┌─ AI RESPONSE ─────────────────────────────────────┐
│  The best way to improve your presentation skills is... 
│  practicing regular... with constructive feedback...
└─────────────────────────────────────────────────────┘
```

## 🔧 Configuration

### Streaming Settings
Add to your `config.yaml`:

```yaml
# --- Streaming Settings ---
streaming:
  enable_streaming: true
  stream_timeout: 60  # seconds
  buffer_tokens: false  # false = true streaming; true = buffer then display
  
# --- Display Streaming Settings ---
display:
  streaming_animation: true  # Show cursor blink while streaming
  stream_chunk_delay: 0.02   # Delay between token display (seconds)
```

### Provider-Specific Settings

**OpenAI:**
```yaml
ai:
  provider: "openai"
  openai_api_key: "sk-..."
  openai_model: "gpt-4o-mini"
  max_tokens: 500
  temperature: 0.7
```

**Groq (fast cloud):**
```yaml
ai:
  provider: "groq"
  groq_api_key: "gsk_..."
  groq_model: "llama-3.3-70b-versatile"
```

**Ollama (local):**
```yaml
ai:
  provider: "ollama"
  ollama_model: "llama3.2:3b"
  ollama_url: "http://localhost:11434"
```

## 📡 How Streaming Works

### Web Streaming Flow
```
User speaks
    ↓
Speech-to-Text
    ↓
Build messages for LLM
    ↓
StreamingResponseHandler.stream_response()
    ├─ For each token from LLM:
    │   ├─ on_token() callback
    │   └─ display.stream_token() → SocketIO → Web UI
    └─ on_complete() callback
```

### Terminal Streaming Flow
```
User speaks
    ↓
Speech-to-Text
    ↓
Build messages for LLM
    ↓
Display.stream_response_start()
    ↓
StreamingResponseHandler.stream_response()
    ├─ For each token from LLM:
    │   ├─ on_token() callback
    │   └─ display.stream_token() → print to terminal
    └─ display.stream_response_end()
```

## 🎨 Web UI Features

### Status Indicators
- 🟢 Green dot = Connected
- 🎤 Listening state = Ready for input
- ⏳ Processing = Analyzing speech
- ✨ Response streaming in progress

### Controls
| Control | Function |
|---------|----------|
| 🎙️ Microphone | Start/Stop recording |
| 🔊 Speaker | Toggle text-to-speech |
| 📚 Book | Toggle educational mode |

### Response Display
- Streaming text appears in real-time
- Suggested next responses show as clickable buttons
- Full transcript visible in input area
- Message history in chat

## 🔌 API Events (SocketIO)

### Emitted from Backend
```python
# Start streaming
socket.emit('stream_start', {'section': 'AI Response'})

# Stream each token
socket.emit('stream_token', {'token': 'The'})
socket.emit('stream_token', {'token': ' best'})
socket.emit('stream_token', {'token': ' way'})

# End streaming
socket.emit('stream_end', {})
```

### Received by Backend
```python
@socket.on('mic_toggle')
def handle_mic_toggle(data):
    # data['recording'] = True/False

@socket.on('toggle_tts')
def handle_toggle_tts(data):
    # data['enabled'] = True/False

@socket.on('toggle_educational')
def handle_toggle_educational(data):
    # data['enabled'] = True/False
```

## ⚙️ Advanced Features

### Custom Streaming Callback
```python
from modules.streaming_response import StreamingResponseHandler

handler = StreamingResponseHandler(config)

full_response = ""
tokens_received = 0

def on_token(token):
    global full_response, tokens_received
    full_response += token
    tokens_received += 1
    print(f"Token {tokens_received}: {token}")

def on_complete(response):
    print(f"Complete response received: {response}")
    print(f"Total tokens: {tokens_received}")

handler.stream_response(
    messages,
    on_token=on_token,
    on_complete=on_complete,
    on_error=lambda e: print(f"Error: {e}")
)
```

### Async Streaming
```python
# Stream in background thread
thread = handler.stream_response_async(
    messages,
    on_token=on_token,
    on_complete=on_complete
)

# Do other work while streaming happens
print("Streaming in background...")
thread.join()  # Wait for completion
```

### Custom Display Formatting
For terminal, modify `display.stream_token()` method:

```python
def stream_token(self, token: str):
    """Custom streaming display with special formatting."""
    # Add custom colors or formatting
    if token in ['.', '!', '?']:
        print(f"{self.BOLD}{token}{self.RESET}", end="", flush=True)
    elif token == '\n':
        print(f"\n{self.CYAN}│  {self.RESET}", end="", flush=True)
    else:
        print(f"{self.WHITE}{token}{self.RESET}", end="", flush=True)
```

## 🐛 Troubleshooting

**Q: Streaming appears frozen/slow**
A: Check your internet connection (for cloud LLMs). For local Ollama, ensure it's running:
```bash
ollama serve
```

**Q: Tokens not appearing in web UI**
A: Ensure Socket.IO is connected:
- Check browser console for connection errors
- Verify Flask-SocketIO is installed: `pip install python-socketio python-engineio`

**Q: Terminal streaming doesn't show**
A: Make sure stdout is not buffered:
```python
# In your code, use flush=True
print(token, end="", flush=True)
```

**Q: Different response quality between providers**
A: OpenAI and Groq are cloud-based (higher quality). Ollama runs locally and may be lower quality depending on model size.

## 📊 Performance Tips

1. **Use smaller models locally** — `llama3.2:1b` vs `3b` depends on your hardware
2. **Increase max_tokens gradually** — Start with 256, go up to 500
3. **Adjust temperature** — 0.5-0.8 for balanced quality/creativity
4. **Close other apps** — Free up resources for LLM inference
5. **Test with web first** — Debug in web UI before terminal

## 🎓 Educational Enhancements

The streaming responses work seamlessly with the learning features:

```python
# Initialize with user profile for personalized streaming
profile = UserProfile("student_001")
ai = AIResponseEngine(config, user_profile=profile)
streaming = StreamingResponseHandler(config)

# Stream personalized response based on learning level
messages = ai._build_messages(transcript)  # Uses learner context
handler.stream_response(messages, on_token=display.stream_token)
```

## 📚 Next Steps

1. ✅ Try the web dashboard: `python demo_web.py`
2. ✅ Open http://localhost:5000/streaming in browser
3. ✅ Click the microphone and start speaking
4. ✅ Watch responses stream in real-time!
5. ✅ Try different LLM providers in config
6. ✅ Integrate with your main app: `python main.py`

---

**Enjoy your Gemini-like AI experience! 🚀**
