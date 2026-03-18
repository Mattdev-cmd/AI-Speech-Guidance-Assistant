# API Keys Setup Guide

## ⚠️ IMPORTANT SECURITY WARNING

Your API keys are currently committed to this repository in `config.yaml`. This means:
- Anyone with access to this repo can see your API keys
- Your API keys could be exposed if the repo is made public
- Malicious actors could use your keys and charge you money

**⚠️ BEST PRACTICE:** If you push this to GitHub, consider these keys COMPROMISED and regenerate them immediately.

---

## Quick Setup on a New PC

### Option 1: Copy config.yaml Manually (Not Recommended for Public Repos)
1. Copy `config.yaml` from your current PC to the new PC
2. Place it in the project root directory
3. Run the assistant normally

### Option 2: Use Environment Variables (Recommended)

Instead of putting keys in `config.yaml`, use environment variables:

#### Windows PowerShell:
```powershell
$env:OPENAI_API_KEY="sk-proj-your-key-here"
$env:GROQ_API_KEY="gsk_your-key-here"
```

#### macOS/Linux:
```bash
export OPENAI_API_KEY="sk-proj-your-key-here"
export GROQ_API_KEY="gsk_your-key-here"
```

### Option 3: Create a Local `.env.local` File (Recommended for Private Repos)

1. Create `.env.local` in the project root:
```
OPENAI_API_KEY=sk-proj-your-key-here
GROQ_API_KEY=gsk_your-key-here
```

2. Add to `.gitignore` (already done):
```
.env.local
```

3. Update `main.py` or `config.yaml` to read from environment variables

---

## Where Are the API Keys?

Currently located in:
- **File:** `config.yaml`
- **OpenAI Key:** `ai.openai_api_key`
- **Groq Key:** `ai.groq_api_key`

---

## How to Get New API Keys

### OpenAI
1. Go to https://platform.openai.com/api/keys
2. Log in or create an account
3. Create a new API key
4. Copy and paste into `config.yaml` or environment variable

### Groq
1. Go to https://console.groq.com/keys
2. Log in or create an account
3. Create a new API key
4. Copy and paste into `config.yaml` or environment variable

---

## Steps to Set Up on Another PC

### Initial Setup (First Time)
```bash
# 1. Clone the repo
git clone https://github.com/yourusername/speech-guidance-assistant.git
cd speech-guidance-assistant

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Option A: Copy config.yaml from your original PC
#    (requires secure transfer - DO NOT email!)
#    Option B: Set environment variables with your API keys
#    Option C: Edit config.yaml and paste your API keys

# 6. For Ollama users: Download Ollama
#    https://ollama.ai

# 7. Run the assistant
python main.py
```

---

## Recommendation: Migrate to Environment Variables

To make your setup more secure and portable, I recommend:

1. **Keep API keys in `.env.local`** (not committed to git)
2. **Update code to read from environment** (we can do this for you)
3. **Document the vars needed** (this file)

Would you like me to modify your code to use environment variables instead? It's more secure and won't require copying files between PCs.
