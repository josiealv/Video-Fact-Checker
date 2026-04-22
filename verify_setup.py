#!/usr/bin/env python3
"""Verify Video Fact-Checker API setup and configuration."""

import sys
import os

def check_python_version():
    """Check Python version."""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} (need 3.8+)")
        return False

def check_dependencies():
    """Check required packages."""
    required = [
        'fastapi', 'uvicorn', 'pydantic', 'httpx', 
        'openai', 'dotenv', 'youtube_transcript_api'
    ]
    missing = []
    
    for package in required:
        try:
            if package == 'dotenv':
                __import__('dotenv')
            elif package == 'youtube_transcript_api':
                __import__('youtube_transcript_api')
            else:
                __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} (missing)")
            missing.append(package)
    
    return len(missing) == 0

def check_api_keys():
    """Check API keys configuration."""
    from config import get_youtube_data_api_key, get_openai_api_key, get_serper_api_key
    
    keys = {
        'YouTube': get_youtube_data_api_key(),
        'OpenAI': get_openai_api_key(),
        'Serper': get_serper_api_key()
    }
    
    all_set = True
    for name, key in keys.items():
        if key:
            print(f"✅ {name} API key ({len(key)} chars)")
        else:
            print(f"❌ {name} API key (not set)")
            all_set = False
    
    return all_set

def check_files():
    """Check required files exist."""
    required_files = [
        'main.py', 'evaluator.py', 'parser.py', 'orchestrator.py',
        'youtube_fetch.py', 'search_service.py', 'ranking_engine.py',
        'formatter.py', 'models.py', 'config.py',
        'evaluation_config.json', 'requirements.txt', '.env'
    ]
    
    missing = []
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} (missing)")
            missing.append(file)
    
    return len(missing) == 0

def check_imports():
    """Check all modules can be imported."""
    modules = [
        'main', 'evaluator', 'parser', 'orchestrator',
        'youtube_fetch', 'search_service', 'ranking_engine',
        'formatter', 'models', 'config'
    ]
    
    failed = []
    for module in modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except Exception as e:
            print(f"❌ {module} ({str(e)[:50]})")
            failed.append(module)
    
    return len(failed) == 0

def check_documentation():
    """Check documentation files exist."""
    docs = [
        'README.md', 'QUICKSTART.md', 'TESTING.md', 
        'DOCS_INDEX.md'
    ]
    
    missing = []
    for doc in docs:
        if os.path.exists(doc):
            print(f"✅ {doc}")
        else:
            print(f"⚠️  {doc} (optional)")
    
    return True  # Documentation is optional

def main():
    """Run all verification checks."""
    print("=" * 60)
    print("Video Fact-Checker API - Setup Verification")
    print("=" * 60)
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("API Keys", check_api_keys),
        ("Required Files", check_files),
        ("Module Imports", check_imports),
        ("Documentation", check_documentation),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n{name}:")
        print("-" * 60)
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Error: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} {name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n✅ All checks passed! Ready to run.")
        print("\nNext steps:")
        print("  1. Start server: uvicorn main:app --reload")
        print("  2. Open docs: http://localhost:8000/docs")
        print("  3. Run tests: python test_suite.py")
        return 0
    else:
        print("\n❌ Some checks failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  - Install dependencies: pip install -r requirements.txt")
        print("  - Configure API keys: cp .env.example .env (then edit)")
        print("  - Check file permissions")
        return 1

if __name__ == "__main__":
    sys.exit(main())
