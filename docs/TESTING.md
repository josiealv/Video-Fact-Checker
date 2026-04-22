# Testing Guide

Comprehensive testing instructions for the Video Fact-Checker API.

## Table of Contents

1. [Unit Tests](#unit-tests)
2. [Integration Tests](#integration-tests)
3. [API Tests](#api-tests)
4. [Performance Tests](#performance-tests)
5. [Test Videos](#test-videos)

---

## Unit Tests

### Test Parser

Test claim extraction from transcripts:

```bash
python test_parser.py
```

**Expected Output:**
```
['President Trump writing on his social media platform', 
 'early Sunday that the US Navy will begin', 
 'the process of blockading all ships trying to enter or leave the Strait of Hormuz']
```

### Test Categorization

```python
from evaluator import categorize_claim

test_cases = [
    ("President Trump announced new sanctions", "Politics"),
    ("The study found 95% efficacy in clinical trials", "STEM"),
    ("Taylor Swift broke streaming records on Spotify", "Pop Culture"),
    ("The algorithm has O(n log n) time complexity", "SWE_TECH"),
    ("Congress passed the infrastructure bill", "Politics"),
    ("The protein binds to DNA sequences", "STEM"),
]

print("=== CATEGORIZATION TESTS ===")
for claim, expected in test_cases:
    result = categorize_claim(claim)
    status = "✅" if result == expected else "❌"
    print(f"{status} Expected: {expected:12} Got: {result:12} | {claim[:50]}")
```

### Test Pattern Matching

```python
import re
import json

EVAL_CONFIG = json.load(open('evaluation_config.json'))

# Test STEM patterns
stem_patterns = [re.compile(p, re.I) for p in EVAL_CONFIG['patterns']['stem']]
test_text = "The study found that explosives detonated at the steel beams"

matches = sum(1 for p in stem_patterns if p.search(test_text))
print(f"STEM matches: {matches}")  # Should be > 0

# Test Politics patterns
pol_patterns = [re.compile(p, re.I) for p in EVAL_CONFIG['patterns']['politics']]
test_text = "President Trump announced military action after 9/11"

matches = sum(1 for p in pol_patterns if p.search(test_text))
print(f"Politics matches: {matches}")  # Should be > 0
```

### Test Source Ranking

```python
from ranking_engine import SourceRanker
from models import SourceArticle, TopicType

ranker = SourceRanker()

# Test Politics sources
sources = [
    SourceArticle(
        url="https://www.reuters.com/article",
        publisher="Reuters",
        title="Test Article",
        topic_type=TopicType.POLITICS,
        citation_count=5,
        has_structured_data=True
    ),
    SourceArticle(
        url="https://example.com/blog",
        publisher="Random Blog",
        title="Test Article",
        topic_type=TopicType.POLITICS,
        citation_count=0,
        has_structured_data=False
    )
]

ranked = ranker.rank_sources(sources)
print(f"Top source: {ranked[0].publisher}")  # Should be "Reuters"
print(f"Score: {ranker.score(ranked[0])}")   # Should be 1.0
```

---

## Integration Tests

### Test Full Analysis Pipeline

```python
from youtube_fetch import fetch_youtube_for_analysis
from evaluator import run_initial_analysis
from main import _build_claim_models

url = "https://www.youtube.com/watch?v=isLp97eL60s"

print("=== INTEGRATION TEST ===")

# Step 1: Fetch video
print("1. Fetching video...")
bundle = fetch_youtube_for_analysis(url)
print(f"   ✅ Title: {bundle.title[:50]}...")

# Step 2: Analyze
print("2. Analyzing video...")
analysis = run_initial_analysis(
    url,
    bundle.transcript_text,
    title=bundle.title,
    description=bundle.description,
    tags=bundle.tags
)
print(f"   ✅ Category: {analysis.topic_category}")
print(f"   ✅ Claims: {len(analysis.claims)}")

# Step 3: Build claim models
print("3. Building claim models...")
video_key = bundle.video_id
claims = _build_claim_models(analysis, video_key)
print(f"   ✅ Claim models: {len(claims)}")

# Step 4: Check claim categories
categories = set(c.topic_tag for c in claims)
print(f"   ✅ Categories: {categories}")

print("\n✅ Integration test passed!")
```

### Test Claim Registration

```python
from orchestrator import register_video_claims, get_registered_claims
from models import Claim

video_id = "test_video_123"
claims = [
    Claim(
        statement="Test claim 1",
        source_video_id=video_id,
        topic_tag="Politics",
        timestamp=None
    ),
    Claim(
        statement="Test claim 2",
        source_video_id=video_id,
        topic_tag="STEM",
        timestamp=None
    )
]

# Register
register_video_claims(video_id, claims)

# Retrieve
retrieved = get_registered_claims(video_id)

assert len(retrieved) == 2, "Should retrieve 2 claims"
assert retrieved[0].statement == "Test claim 1"
print("✅ Claim registration test passed!")
```

---

## API Tests

### Test with cURL

#### 1. Health Check

```bash
curl http://localhost:8000/health
```

**Expected:**
```json
{"status": "ok"}
```

#### 2. Analyze Video

```bash
curl -X POST http://localhost:8000/analyze-video \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=isLp97eL60s"
  }' | jq
```

**Expected Fields:**
- `eligible_for_fact_check`: true
- `topic_category`: "Politics"
- `claims`: array of claims
- `from_cache`: false (first time)

#### 3. Fact-Check Video

```bash
curl -X POST http://localhost:8000/fact-check \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=isLp97eL60s"
  }' | jq
```

**Expected Fields:**
- `summary`: string with evaluation results
- `flagged_claims`: array of contradicted claims
- `top_educational_sources`: array of credible sources
- `claims_evaluated`: number

### Test with Python Requests

```python
import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    print("✅ Health check passed")

def test_analyze_video():
    response = requests.post(
        f"{BASE_URL}/analyze-video",
        json={"video_url": "https://www.youtube.com/watch?v=isLp97eL60s"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["eligible_for_fact_check"] == True
    assert data["topic_category"] == "Politics"
    assert len(data["claims"]) > 0
    print(f"✅ Analyze video passed ({len(data['claims'])} claims)")

def test_fact_check():
    response = requests.post(
        f"{BASE_URL}/fact-check",
        json={"video_url": "https://www.youtube.com/watch?v=isLp97eL60s"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "claims_evaluated" in data
    assert data["claims_evaluated"] > 0
    print(f"✅ Fact-check passed ({data['claims_evaluated']} claims)")

# Run tests
test_health()
test_analyze_video()
test_fact_check()
print("\n✅ All API tests passed!")
```

### Test Error Handling

```python
import requests

BASE_URL = "http://localhost:8000"

# Test invalid URL
response = requests.post(
    f"{BASE_URL}/analyze-video",
    json={"video_url": "https://invalid-url.com"}
)
assert response.status_code == 400
print("✅ Invalid URL handled correctly")

# Test missing video
response = requests.post(
    f"{BASE_URL}/analyze-video",
    json={"video_url": "https://www.youtube.com/watch?v=INVALID123"}
)
assert response.status_code == 400
print("✅ Missing video handled correctly")

# Test video without captions
response = requests.post(
    f"{BASE_URL}/analyze-video",
    json={"video_url": "https://www.youtube.com/watch?v=VIDEO_NO_CAPTIONS"}
)
assert response.status_code == 400
print("✅ No captions handled correctly")
```

---

## Performance Tests

### Test Caching

```python
import time
import requests

BASE_URL = "http://localhost:8000"
url = "https://www.youtube.com/watch?v=isLp97eL60s"

# First request (no cache)
start = time.time()
response1 = requests.post(
    f"{BASE_URL}/analyze-video",
    json={"video_url": url}
)
time1 = time.time() - start
assert response1.json()["from_cache"] == False

# Second request (cached)
start = time.time()
response2 = requests.post(
    f"{BASE_URL}/analyze-video",
    json={"video_url": url}
)
time2 = time.time() - start
assert response2.json()["from_cache"] == True

print(f"First request: {time1:.2f}s")
print(f"Cached request: {time2:.2f}s")
print(f"Speedup: {time1/time2:.1f}x")
assert time2 < time1 * 0.1, "Cache should be much faster"
print("✅ Caching test passed!")
```

### Test Concurrent Requests

```python
import asyncio
import httpx

async def test_concurrent():
    urls = [
        "https://www.youtube.com/watch?v=isLp97eL60s",
        "https://www.youtube.com/watch?v=FeasKVBFySw",
    ]
    
    async with httpx.AsyncClient() as client:
        tasks = [
            client.post(
                "http://localhost:8000/analyze-video",
                json={"video_url": url},
                timeout=60.0
            )
            for url in urls
        ]
        responses = await asyncio.gather(*tasks)
    
    for i, response in enumerate(responses):
        assert response.status_code == 200
        print(f"✅ Request {i+1} completed")
    
    print("✅ Concurrent requests test passed!")

asyncio.run(test_concurrent())
```

---

## Test Videos

### Politics Category

**Trump Iran Blockade**
- URL: `https://www.youtube.com/watch?v=isLp97eL60s`
- Expected Category: Politics
- Expected Claims: ~17
- Topics: Iran, military, negotiations, nuclear weapons

### STEM Category

**9/11 Demolition Analysis**
- URL: `https://www.youtube.com/watch?v=FeasKVBFySw`
- Expected Category: STEM
- Expected Claims: ~23
- Topics: Explosives, demolition, engineering, structural analysis

### Mixed Categories

Videos with claims spanning multiple categories should have individual claims categorized correctly.

---

## Automated Test Suite

Create `test_suite.py`:

```python
#!/usr/bin/env python3
"""Comprehensive test suite for Video Fact-Checker API."""

import sys
import requests
from evaluator import categorize_claim
from parser import extract_claims

BASE_URL = "http://localhost:8000"

def test_parser():
    """Test claim extraction."""
    transcript = "President Trump announced sanctions. The study found 95% efficacy."
    claims = extract_claims(transcript)
    assert len(claims) >= 1, "Should extract at least 1 claim"
    print("✅ Parser test passed")

def test_categorization():
    """Test topic categorization."""
    tests = [
        ("President Trump announced sanctions", "Politics"),
        ("The study found 95% efficacy", "STEM"),
    ]
    for claim, expected in tests:
        result = categorize_claim(claim)
        assert result == expected, f"Expected {expected}, got {result}"
    print("✅ Categorization test passed")

def test_api_health():
    """Test health endpoint."""
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    print("✅ API health test passed")

def test_api_analyze():
    """Test analyze endpoint."""
    response = requests.post(
        f"{BASE_URL}/analyze-video",
        json={"video_url": "https://www.youtube.com/watch?v=isLp97eL60s"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["eligible_for_fact_check"] == True
    assert len(data["claims"]) > 0
    print(f"✅ API analyze test passed ({len(data['claims'])} claims)")

def main():
    """Run all tests."""
    print("=== Running Test Suite ===\n")
    
    tests = [
        test_parser,
        test_categorization,
        test_api_health,
        test_api_analyze,
    ]
    
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {len(tests) - failed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
```

Run with:
```bash
python test_suite.py
```

---

## Continuous Testing

### Watch Mode

```bash
# Install watchdog
pip install watchdog

# Run tests on file changes
watchmedo shell-command \
  --patterns="*.py" \
  --recursive \
  --command='python test_suite.py' \
  .
```

### Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
python test_suite.py
if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

---

## Troubleshooting Tests

**Tests timing out:**
- Increase timeout values
- Check API key quotas
- Verify network connectivity

**Categorization tests failing:**
- Check `evaluation_config.json` patterns
- Verify pattern compilation (no regex errors)
- Test individual patterns in isolation

**API tests failing:**
- Ensure server is running (`uvicorn main:app`)
- Check API keys are configured in `.env`
- Verify port 8000 is not in use

**Cache tests failing:**
- Clear cache between test runs
- Restart server to reset cache
- Check cache size limits in config

---

## Test Coverage

To measure test coverage:

```bash
pip install pytest pytest-cov
pytest --cov=. --cov-report=html
```

View report:
```bash
open htmlcov/index.html
```

---

## Next Steps

1. Add unit tests for all modules
2. Implement integration test suite
3. Set up CI/CD pipeline
4. Add performance benchmarks
5. Create load testing scenarios
