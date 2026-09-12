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
