# Render.com Deployment Guide for AudioAnalyzerAutomate

This guide explains how to deploy `AudioAnalyzerAutomate` to **Render.com** (Free Web Service Tier).

---

## 📁 Files Created for Render Deployment

1. [`Dockerfile`](file:///c:/Prince%20projects/YoutubeAutomate/AudioAnalyzer/AudioAnalyzerAutomate/Dockerfile): Container configuration using lightweight Python 3.10 with CPU-optimized PyTorch.
2. [`requirements.txt`](file:///c:/Prince%20projects/YoutubeAutomate/AudioAnalyzer/AudioAnalyzerAutomate/requirements.txt): Application dependencies.
3. [`render.yaml`](file:///c:/Prince%20projects/YoutubeAutomate/AudioAnalyzer/AudioAnalyzerAutomate/render.yaml): Render infrastructure-as-code Blueprint.

---

## 🚀 4-Step Deployment Steps

### Step 1: Push Code to GitHub / GitLab
Ensure your project repository contains the newly created files (`Dockerfile`, `requirements.txt`, `render.yaml`, `fast_studio_app.py`, `dynamo_logger.py`).

```bash
git add .
git commit -m "Add Render deployment configuration and DynamoDB logger"
git push origin main
```

---

### Step 2: Connect Repository to Render.com
1. Log in to [Render.com](https://dashboard.render.com).
2. Click **New +** in the top right corner and select **Web Service** (or **Blueprint**).
3. Connect your GitHub/GitLab account and select your repository (`AudioAnalyzer`).
4. If using **Web Service**:
   - **Name**: `audio-analyzer-service`
   - **Environment**: `Docker`
   - **Dockerfile Path**: `./AudioAnalyzerAutomate/Dockerfile` (or `./Dockerfile` if root)
   - **Instance Type**: `Free`

---

### Step 3: Configure Production Environment Variables on Render
In the **Environment** tab on your Render Web Service dashboard, add the following environment variables:

| Key | Value | Description |
| :--- | :--- | :--- |
| `USE_LOCAL_DYNAMODB` | `false` | Instructs `dynamo_logger` to connect to production AWS DynamoDB |
| `AWS_REGION` | `us-east-1` | AWS region hosting your DynamoDB tables |
| `AWS_ACCESS_KEY_ID` | `your_aws_access_key` | AWS credentials for DynamoDB `Logs` & `AbstractLogs` |
| `AWS_SECRET_ACCESS_KEY` | `your_aws_secret_key` | AWS secret key |
| `GEMINI_API_KEY` | `your_gemini_api_key` | Google Gemini API Key |
| `PORT` | `8020` | Service listening port |

---

### Step 4: Deploy & Test Endpoint
1. Click **Create Web Service** (or **Deploy**). Render will build the Docker container and launch the FastAPI server.
2. Once the deploy succeeds, Render provides your live HTTPS URL (e.g. `https://audio-analyzer-service.onrender.com`).
3. You can verify health by sending a `POST` request to `https://audio-analyzer-service.onrender.com/generate/song-names`:

```bash
curl -X POST "https://audio-analyzer-service.onrender.com/generate/song-names" \
     -H "Content-Type: application/json" \
     -d '{"idol": "Ganesha", "totalSongToGenerate": 2}'
```

#### Expected Live Response:
```json
{
  "stage": "AudioAnalyzer",
  "step": "GENERATE_SONG_NAMES",
  "song_names": [
    "Jai Ganesh Deva",
    "Ganesh Chalisa"
  ]
}
```

---

## 🎵 Music Model Prompting Strategies (`/generate/lyrics`)

The `/generate/lyrics` endpoint inspects the `music_model` field using regular expressions and dynamically tailors both **lyrics structure tags** and **musical style prompts** according to model-specific prompting requirements:

### 1. ACE-Step 1.5 (`ace_step_1.5` / `ace step`)
- **Reference**: [Rikunarita ACE-Step 1.5 Prompt Guide](https://note.com/rikunarita/n/n5c9d53950b27?hl=en)
- **Regex Match**: `r"ace[\s_-]*step"`
- **Lyrics Structure**: Explicit Title-case bracketed sections on their own lines: `[Intro]`, `[Verse 1]`, `[Pre-Chorus]`, `[Chorus]`, `[Bridge]`, `[Outro]`.
- **Rhythm & Pacing Strategy**: ACE-Step sings at roughly 2 to 3 words per second. Lyrics are generated with rhythmic syllabic balance and regular stanza pacing to avoid rushed vocals or dead space.
- **Style Caption Strategy**: Comma-separated descriptive tags specifying Genre, concrete traditional and acoustic Instrumentation (e.g., bansuri flute, dholak, tabla, harmonium), BPM/tempo, and vocal timbre (e.g., devotional, powerful male lead vocal, chorus).

### 2. MiniMax Music 3 (`minimax music 3` / `minimax 3`)
- **Reference**: [MiniMax Music 3 Prompting Guide (Hugging Face / multimodalart)](https://huggingface.co/spaces/multimodalart/minimax-music3-prompting-guide)
- **Regex Match**: `r"mini[\s_-]*max"`
- **Lyrics Structure**: Strict lowercase structural tags: `[intro]`, `[verse]`, `[pre-chorus]`, `[chorus]`, `[bridge]`, `[outro]`.
- **Isolation Rule (Critical)**: Every section tag is placed on its own standalone line. Lyrics are never placed on the same line as a tag, preventing MiniMax from dropping words.
- **Style Caption Strategy**: Focused musical description containing genre, emotional arc, vocal quality, and traditional instrumentation separated by commas.

### 3. YuE 2 (`yue2` / `yue`)
- **Reference**: [YuE 2 Prompting Guide (Song Creator Pro)](https://songcreator.pro/blog/yue2-prompting-guide)
- **Regex Match**: `r"\byue\b|\byue[\s_-]*2\b"`
- **Lyrics Structure**: Lowercase structural tags: `[verse 1]`, `[verse 2]`, `[chorus]`, `[bridge]`, `[outro]`. Unstable `[intro]` tags are avoided, starting directly into `[verse 1]`.
- **Double-Newline Rule (Critical)**: Every section block is strictly separated by two newline characters (`\n\n`) to prevent YuE from looping or scrambling ~30-second audio generation chunks.
- **Style Caption Strategy**: Space-delimited open-vocabulary tags covering: `[Genre] [Instrument] [Mood] [Gender] [Timbre/Vocal Quality]` (e.g., `devotional bhajan bansuri tabla uplifting male resonant bright vocal`).

