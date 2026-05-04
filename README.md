# Video Fact-Checker API

An automated fact-checking system for YouTube videos that extracts claims from video transcripts, categorizes them by topic, searches for credible sources, and provides verification verdicts.

## Overview

This FastAPI-based service analyzes YouTube videos to:
1. **Extract claims** from video transcripts using pattern-based parsing
2. **Categorize content** by topic (Politics, STEM, Pop Culture, Software Engineering)
3. **Search for sources** using Google (via Serper API) with GPT-4o-mini assessment
4. **Rank sources** by credibility using topic-specific scoring algorithms
5. **Verify claims** by comparing them against top-ranked sources
6. **Generate reports** with verdicts, flagged claims, and educational resources

### Key Features

- **Intelligent Categorization**: Pattern-based topic detection with per-claim categorization
- **Multi-Topic Support**: Handles Politics, STEM, Pop Culture, and Software Engineering content
- **Credibility Scoring**: Topic-aware source ranking (e.g., academic journals for STEM, news outlets for Politics)
- **Caching**: LRU caches for video analysis and fact-check results
- **Async Pipeline**: Efficient parallel source retrieval and assessment

## Architecture

### Core Components

```
┌─────────────────┐
│   FastAPI App   │  main.py - REST API endpoints
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼──┐  ┌──▼────┐
│Analyze│  │ Fact  │
│Video  │  │ Check │
└───┬───┘  └───┬───┘
    │          │
    ├──────────┴─────────────┐
    │                        │
┌───▼────────┐      ┌────────▼────────┐
│ Evaluator  │      │  Orchestrator   │
│ - Category │      │  - Claim Store  │
│ - Claims   │      │  - Pipeline     │
└─────┬──────┘      └────────┬────────┘
      │                      │
┌─────▼──────┐      ┌────────▼────────┐
│   Parser   │      │ Search Service  │
│ - Extract  │      │ - Serper API    │
│ - Filter   │      │ - GPT Assess    │
└────────────┘      └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Ranking Engine  │
                    │ - Score Sources │
                    │ - Topic Rules   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   Formatter     │
                    │ - JSON Report   │
                    └─────────────────┘
```

### Module Breakdown

| Module | Purpose |
|--------|---------|
| `main.py` | FastAPI endpoints: `/analyze-video`, `/fact-check`, `/health` |
| `youtube_fetch.py` | Fetch video metadata (YouTube Data API) and transcripts |
| `evaluator.py` | Video eligibility, topic categorization, claim extraction |
| `parser.py` | Extract checkable claims from transcripts (pattern-based) |
| `orchestrator.py` | Fact-check pipeline: claim registration, source retrieval, verification |
| `search_service.py` | Google search (Serper) + GPT-4o-mini source assessment |
| `ranking_engine.py` | Topic-aware credibility scoring and source ranking |
| `formatter.py` | Generate user-facing JSON reports |
| `models.py` | Pydantic models for claims, sources, verdicts |
| `config.py` | Environment variable loading and API key management |
| `evaluation_config.json` | Regex patterns for topic categorization |

## Prerequisites

- **Python**: 3.8+
- **API Keys**:
  - YouTube Data API v3 (Google Cloud)
  - OpenAI API (GPT-4o-mini)
  - Serper API (Google search)

## Installation

### 1. Clone and Setup Virtual Environment

```bash
cd video_fact_checker
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**Dependencies:**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `pydantic` - Data validation
- `httpx` - Async HTTP client
- `openai` - OpenAI API client
- `youtube-transcript-api` - Transcript fetching
- `python-dotenv` - Environment variable management

### 3. Configure API Keys

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```bash
# YouTube Data API v3 (Google Cloud)
YOUTUBE_API_KEY=your_youtube_api_key_here

# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here

# Serper API (Google search)
SERPER_API_KEY=your_serper_api_key_here
```

**Getting API Keys:**

- **YouTube Data API**: [Google Cloud Console](https://console.cloud.google.com/) → Enable YouTube Data API v3
- **OpenAI API**: [OpenAI Platform](https://platform.openai.com/api-keys)
- **Serper API**: [Serper.dev](https://serper.dev/)

## Running the Server

### Development Mode

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at `http://localhost:8000`

**Interactive API Docs:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### `POST /analyze-video`

Analyze video eligibility and extract claims (no fact-checking).

**Request:**
```json
{
  "video_url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

**Response:**
```json
{
  "eligible_for_fact_check": true,
  "skip_reason": null,
  "topic_category": "Politics",
  "claims": [
    {
      "statement": "President Trump announced new sanctions",
      "source_video_id": "VIDEO_ID",
      "topic_tag": "Politics",
      "timestamp": null
    }
  ],
  "topic_type": "politics",
  "video_url": "https://...",
  "from_cache": false
}
```

### `POST /fact-check`

Complete fact-check pipeline (analyze + verify claims).

**Request:**
```json
{
  "video_url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

**Response:**
```json
{
  "summary": "Evaluated 17 claims: ~82.4% align with retrieved reputable sources...",
  "flagged_claims": [
    {
      "claim": "...",
      "verdict": "contradicted",
      "refutation_source": {
        "url": "https://...",
        "title": "...",
        "publisher": "Reuters",
        "credibility_score": 1.0
      }
    }
  ],
  "top_educational_sources": [
    {
      "url": "https://...",
      "title": "...",
      "publisher": "...",
      "credibility_score": 1.0
    }
  ],
  "video_id": "VIDEO_ID",
  "from_cache": false,
  "claims_evaluated": 17
}
```

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

## Testing

### Manual Testing

#### 1. Test Video Analysis

```bash
curl -X POST http://localhost:8000/analyze-video \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://www.youtube.com/watch?v=isLp97eL60s"}'
```

#### 2. Test Fact-Checking

```bash
curl -X POST http://localhost:8000/fact-check \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://www.youtube.com/watch?v=isLp97eL60s"}'
```

#### 3. Test Health Check

```bash
curl http://localhost:8000/health
```

### Python Testing

#### Run All Tests

```bash
python test_parser.py
```

This runs:
- **Parser tests**: Claim extraction from transcripts
- **Source ranking tests**: Verifies low-credibility sources score 0.05
- **Categorization tests**: Validates expanded pattern coverage

#### Test Categorization

```python
from evaluator import categorize_claim

claims = [
    "President Trump announced new sanctions",
    "The study found 95% efficacy",
    "Taylor Swift broke streaming records",
    "The algorithm has O(n log n) complexity"
]

for claim in claims:
    category = categorize_claim(claim)
    print(f"[{category}] {claim}")
```

**Expected Output:**
```
[Politics] President Trump announced new sanctions
[STEM] The study found 95% efficacy
[Pop Culture] Taylor Swift broke streaming records
[SWE_TECH] The algorithm has O(n log n) complexity
```

#### Test Full Pipeline

```python
from youtube_fetch import fetch_youtube_for_analysis
from evaluator import run_initial_analysis

url = "https://www.youtube.com/watch?v=VIDEO_ID"
bundle = fetch_youtube_for_analysis(url)

analysis = run_initial_analysis(
    url,
    bundle.transcript_text,
    title=bundle.title,
    description=bundle.description,
    tags=bundle.tags
)

print(f"Category: {analysis.topic_category}")
print(f"Claims: {len(analysis.claims)}")
```

### Test Videos

**Politics:**
- Trump Iran blockade: `https://www.youtube.com/watch?v=isLp97eL60s`

**STEM:**
- 9/11 demolition analysis: `https://www.youtube.com/watch?v=FeasKVBFySw`

## Configuration

### Recent Improvements (2024)

#### 1. Enhanced Source Credibility Ranking

**Problem:** Low-quality sources (Quora, Yahoo Answers, personal blogs) were scoring 0.35, allowing them to rank alongside credible sources.

**Solution:** Implemented blocklist system in `ranking_engine.py`:
- Low-credibility hosts now score **0.05** (20x lower than academic sources)
- Blocklisted: quora.com, answers.yahoo.com, ask.com, answers.com, blogspot.com, wordpress.com
- Exception: Verified Medium publications (towardsdatascience.com, betterprogramming.pub, etc.) remain credible
- Applied across all topics: STEM, Politics, Pop Culture, SWE_TECH

**Impact:**
```
Before: Quora (0.35) ≈ Random blog (0.35) << Academic journal (1.0)
After:  Quora (0.05) << Random blog (0.05) <<< Academic journal (1.0)
```

#### 2. Expanded Topic Pattern Coverage

**Problem:** Limited keyword patterns required manual updates for each new video topic, causing miscategorization.

**Solution:** Expanded patterns 3-6x in `evaluation_config.json`:

- **STEM** (8→20 patterns): Added medical/health, climate/environment, astronomy, quantum physics, chemistry, mathematics, epidemiology, energy, geology, conservation
- **Politics** (8→20 patterns): Added judicial system, immigration, trade/economics, regulation, foreign policy, social movements, scandals, local government, constitutional law, surveillance
- **Pop Culture** (4→18 patterns): Added awards shows, social media, beauty/fashion, reality TV, music/film production, fan culture, celebrity drama, internet culture
- **CS/Algorithms** (12→24 patterns): Added data structures (linked list, tree, graph, trie), algorithm paradigms (DP, greedy, backtracking), advanced techniques (two pointer, sliding window, bit manipulation)
- **SWE Terms** (44→260+ terms): Added package managers, modern frameworks (Vue, Svelte, Nuxt), databases (Postgres, MongoDB, Redis), ORMs (Prisma, TypeORM), DevOps (Jenkins, CI/CD, autoscaling), security (JWT, OAuth, encryption), build tools (Webpack, Vite), testing (Jest, Cypress), design patterns (SOLID, DRY)

**Impact:**
- ~80% reduction in manual pattern updates
- Better coverage for medical, climate, judicial, trade, K-pop, tech tutorial videos
- Fewer videos marked as INELIGIBLE_UNCERTAIN

**Why local patterns over vector DB:**
- Fast & deterministic (no API calls, no embedding costs)
- Transparent (see exactly why a video was categorized)
- Sufficient coverage for current scale
- Consider vector DB when processing 10,000+ videos/day or need semantic similarity

### Topic Categorization Patterns

Edit `evaluation_config.json` to customize categorization:

```json
{
  "patterns": {
    "stem": [
      "\\b(study|research|experiment|hypothesis)\\b",
      "\\b(explosive|detonation|demolition)\\b"
    ],
    "politics": [
      "\\b(president|congress|senate|election)\\b",
      "\\b(9/11|terrorism|military|war)\\b"
    ],
    "pop": [
      "\\b(celebrity|gossip|red carpet)\\b",
      "\\b(album|music single|concert)\\b"
    ],
    "cs_algo": [
      "\\bleetcode\\b",
      "time\\s+complexity",
      "\\bhash\\s*map\\b"
    ]
  }
}
```

### Credibility Scoring

Source ranking in `ranking_engine.py` uses topic-specific tiers:

- **Politics/News**: Accredited news outlets (AP, Reuters, NYT) = 1.0, Low-credibility = 0.05
- **STEM**: Academic institutions (.edu, .gov, peer-reviewed journals) = 1.0, Low-credibility = 0.05
- **Pop Culture**: Industry magazines (Rolling Stone, Variety) = 1.0, Low-credibility = 0.05
- **SWE_TECH**: Official documentation (python.org, docs.aws.amazon.com) = 1.0, Low-credibility = 0.05

**Blocklisted sources** (score 0.05):
- quora.com, answers.yahoo.com, ask.com, answers.com
- blogspot.com, wordpress.com
- medium.com (except verified publications)

**Verified Medium publications** (normal scoring):
- towardsdatascience.com, betterprogramming.pub
- javascript.plainenglish.io, levelup.gitconnected.com

**To add blocklisted sources:**
```python
# Edit ranking_engine.py
_LOW_CREDIBILITY_HOSTS = frozenset({
    "quora.com",
    "new-site.com",  # Add here
})
```

**To add verified Medium publications:**
```python
# Edit ranking_engine.py
_VERIFIED_MEDIUM_PUBLICATIONS = frozenset({
    "towardsdatascience.com",
    "new-pub.medium.com",  # Add here
})
```

## Troubleshooting

### Common Issues

**1. "YouTube API key is not set"**
- Ensure `YOUTUBE_API_KEY` or `GOOGLE_API_KEY` is set in `.env`
- Verify the key has YouTube Data API v3 enabled

**2. "Video not eligible for fact-checking"**
- Check if video has captions/transcripts enabled
- Video may be blocked (music videos, satire, memes)
- Check `block_phrases` in `evaluation_config.json`

**3. "Fact check failed"**
- Verify `OPENAI_API_KEY` and `SERPER_API_KEY` are set
- Check API quota limits
- Review server logs for detailed error messages

**4. "No claims extracted"**
- Video transcript may be too short (< 20 words)
- Content may not match checkable patterns
- Check `parser.py` filters (procedural, opinion, questions)

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Project Structure

```
video_fact_checker/
├── main.py                    # FastAPI application
├── youtube_fetch.py           # YouTube API integration
├── evaluator.py               # Categorization & eligibility
├── parser.py                  # Claim extraction
├── orchestrator.py            # Fact-check pipeline
├── search_service.py          # Source retrieval (Serper + GPT)
├── ranking_engine.py          # Credibility scoring
├── formatter.py               # Report generation
├── models.py                  # Pydantic models
├── config.py                  # Configuration management
├── evaluation_config.json     # Categorization patterns
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
├── .env                      # API keys (not in git)
├── test_parser.py            # Parser tests
└── README.md                 # This file
```

## Performance

### Caching

- **Video Analysis**: LRU cache (1000 URLs)
- **Fact-Check Results**: LRU cache (500 video IDs)
- **Pattern Compilation**: Loaded once at startup

### Optimization Tips

1. **Parallel Processing**: Use `--workers` flag for uvicorn
2. **Rate Limiting**: Implement rate limiting for API endpoints
3. **Batch Processing**: Process multiple videos in parallel
4. **Cache Warming**: Pre-populate cache with popular videos

## Contributing

### Adding New Topic Categories

1. Add patterns to `evaluation_config.json`
2. Update `TopicType` enum in `models.py`
3. Add credibility scoring in `ranking_engine.py`
4. Update `_map_topic_to_topic_type()` in `main.py`

### Improving Claim Extraction

Edit `parser.py`:
- Add checkable patterns to `_CHECKABLE_PATTERNS`
- Adjust filters (`_PROCEDURAL`, `_OPINION_LEADERS`)
- Modify `_MIN_LEN` and `_MAX_CLAIMS` thresholds

## License

[Add your license here]

## Documentation

For detailed documentation:
- **Testing Guide**: See [docs/TESTING.md](docs/TESTING.md)
- **All Documentation**: See [docs/DOCS_INDEX.md](docs/DOCS_INDEX.md)

## Support

For issues and questions:
- Check the troubleshooting section above
- Review the [testing guide](docs/TESTING.md)
- Open the interactive API docs at `http://localhost:8000/docs`
