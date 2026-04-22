# Quick Start Guide

Get the Video Fact-Checker API running in 5 minutes.

## Prerequisites

- Python 3.8+
- API keys (YouTube, OpenAI, Serper)

## Setup

### 1. Install Dependencies

```bash
cd video_fact_checker
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
cp .env.example .env
```

Edit `.env`:
```bash
YOUTUBE_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
SERPER_API_KEY=your_key_here
```

### 3. Start Server

```bash
uvicorn main:app --reload
```

Server runs at: `http://localhost:8000`

## Test It

### Option 1: Browser

Open `http://localhost:8000/docs` and use the interactive API.

### Option 2: cURL

```bash
# Analyze video
curl -X POST http://localhost:8000/analyze-video \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://www.youtube.com/watch?v=isLp97eL60s"}'

# Fact-check video
curl -X POST http://localhost:8000/fact-check \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://www.youtube.com/watch?v=isLp97eL60s"}'
```

### Option 3: Python

```python
import requests

# Analyze
response = requests.post(
    "http://localhost:8000/analyze-video",
    json={"video_url": "https://www.youtube.com/watch?v=isLp97eL60s"}
)
print(response.json())

# Fact-check
response = requests.post(
    "http://localhost:8000/fact-check",
    json={"video_url": "https://www.youtube.com/watch?v=isLp97eL60s"}
)
print(response.json())
```

## What It Does

1. **Fetches** video metadata and transcript from YouTube
2. **Categorizes** content (Politics, STEM, Pop Culture, SWE_TECH)
3. **Extracts** checkable claims from transcript
4. **Searches** for credible sources using Google (Serper API)
5. **Ranks** sources by credibility (topic-specific scoring)
6. **Verifies** claims using GPT-4o-mini
7. **Returns** report with verdicts and sources

## Example Output

```json
{
  "summary": "Evaluated 17 claims: ~82.4% align with reputable sources",
  "flagged_claims": [
    {
      "claim": "Iran has 10,000 nuclear weapons",
      "verdict": "contradicted",
      "refutation_source": {
        "url": "https://www.reuters.com/...",
        "publisher": "Reuters",
        "credibility_score": 1.0
      }
    }
  ],
  "top_educational_sources": [
    {
      "url": "https://www.bbc.com/...",
      "publisher": "BBC",
      "credibility_score": 1.0
    }
  ]
}
```

## Test Videos

- **Politics**: `https://www.youtube.com/watch?v=isLp97eL60s` (Trump Iran)
- **STEM**: `https://www.youtube.com/watch?v=FeasKVBFySw` (9/11 engineering)

## Troubleshooting

**"YouTube API key is not set"**
→ Check `.env` file has `YOUTUBE_API_KEY`

**"Video not eligible"**
→ Video needs captions/transcripts enabled

**"Fact check failed"**
→ Verify all API keys are set correctly

## Next Steps

- Read full [README.md](README.md) for detailed documentation
- Check [docs/TESTING.md](docs/TESTING.md) for comprehensive testing guide
- Review [docs/DOCS_INDEX.md](docs/DOCS_INDEX.md) for all documentation

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /analyze-video` | Analyze eligibility + extract claims |
| `POST /fact-check` | Full fact-check pipeline |
| `GET /health` | Health check |
| `GET /docs` | Interactive API documentation |

## Performance

- First request: ~10-30 seconds (fetching + analysis + search)
- Cached requests: < 1 second
- Concurrent requests: Use `--workers 4` flag

## Development

```bash
# Run with auto-reload
uvicorn main:app --reload

# Run tests
python test_parser.py

# Test categorization
python -c "from evaluator import categorize_claim; print(categorize_claim('President Trump announced sanctions'))"
```

## Production

```bash
# Run with multiple workers
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# With logging
uvicorn main:app --log-level info --access-log
```

That's it! You're ready to fact-check YouTube videos. 🎉
