#!/usr/bin/env python3
"""Test suite for video fact-checker components."""

from parser import extract_claims
from evaluator import categorize_claim
from models import SourceArticle, TopicType
from ranking_engine import SourceRanker


def test_parser():
    """Test claim extraction from transcript."""
    print("\n" + "="*80)
    print("TESTING PARSER")
    print("="*80)
    
    transcript = """
    President Trump writing on his social media platform early Sunday that the US Navy 
    will begin the process of blockading all ships trying to enter or leave the Strait of Hormuz.
    """
    claims = extract_claims(transcript)
    print(f"\nExtracted {len(claims)} claims:")
    for claim in claims:
        print(f"  - {claim}")
    print()


def test_source_ranking():
    """Test that low-credibility sources are properly penalized."""
    print("="*80)
    print("TESTING SOURCE RANKING")
    print("="*80)
    
    ranker = SourceRanker()
    
    sources = [
        SourceArticle(
            url="https://quora.com/some-question",
            publisher="Quora",
            title="Random answer",
            topic_type=TopicType.STEM,
            credibility_score=0.0,
            citation_count=0,
            has_structured_data=False,
        ),
        SourceArticle(
            url="https://www.nature.com/articles/science-paper",
            publisher="Nature",
            title="Peer-reviewed research",
            topic_type=TopicType.STEM,
            credibility_score=0.0,
            citation_count=5,
            has_structured_data=True,
        ),
        SourceArticle(
            url="https://towardsdatascience.com/article",
            publisher="Towards Data Science",
            title="Data science tutorial",
            topic_type=TopicType.SWE_TECH,
            credibility_score=0.0,
            citation_count=2,
            has_structured_data=False,
        ),
        SourceArticle(
            url="https://medium.com/@random/blog-post",
            publisher="Medium",
            title="Random blog",
            topic_type=TopicType.SWE_TECH,
            credibility_score=0.0,
            citation_count=0,
            has_structured_data=False,
        ),
    ]
    
    scored = ranker.with_scores(sources)
    ranked = ranker.rank_sources(scored)
    
    print("\nRanked Sources:")
    for i, source in enumerate(ranked, 1):
        print(f"{i}. [{source.credibility_score:.2f}] {source.publisher}")
    
    assert ranked[0].credibility_score == 1.0, "Nature should score 1.0"
    assert ranked[-1].publisher == "Quora", "Quora should rank last"
    assert ranked[-1].credibility_score == 0.05, "Quora should score 0.05"
    
    print("\n✅ Source ranking tests passed!\n")


def test_topic_categorization():
    """Test expanded pattern coverage."""
    print("="*80)
    print("TESTING TOPIC CATEGORIZATION")
    print("="*80)
    
    test_cases = [
        ("The vaccine showed 95% efficacy in clinical trials", "STEM"),
        ("Climate change is causing species extinction", "STEM"),
        ("The Supreme Court ruled on the immigration case", "Politics"),
        ("Congress passed legislation on trade tariffs", "Politics"),
        ("The actor won an Oscar for best performance", "Pop Culture"),
        ("The TikTok video went viral overnight", "Pop Culture"),
        ("Prisma ORM simplifies database queries", "SWE_TECH"),
        ("Docker containers enable kubernetes deployment", "SWE_TECH"),
        ("Dynamic programming optimizes the solution", "SWE_TECH"),
    ]
    
    print("\nCategorization Results:")
    passed = 0
    failed = 0
    
    for claim, expected in test_cases:
        result = categorize_claim(claim)
        status = "✅" if result == expected else "❌"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} [{result:12s}] {claim[:60]}...")
    
    print(f"\nResults: {passed}/{len(test_cases)} passed")
    if failed == 0:
        print("✅ All categorization tests passed!\n")
    else:
        print(f"⚠️  {failed} tests failed\n")


if __name__ == "__main__":
    print("\n" + "╔" + "="*78 + "╗")
    print("║" + " "*25 + "VIDEO FACT-CHECKER TESTS" + " "*29 + "║")
    print("╚" + "="*78 + "╝")
    
    try:
        test_parser()
        test_source_ranking()
        test_topic_categorization()
        
        print("="*80)
        print("ALL TESTS COMPLETED")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
