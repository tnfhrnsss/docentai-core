#!/usr/bin/env python3
"""
Google Search Grounding 테스트 스크립트
Gemini API의 Grounding 기능을 테스트하고 출처 정보를 확인합니다.
"""
import sys
import json
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.client.gemini import get_gemini_client, GeminiClient
from config.settings import get_settings


def test_grounding_basic():
    """기본 Grounding 테스트"""
    print("=" * 80)
    print("Google Search Grounding Test")
    print("=" * 80)

    # 1. Check Gemini API settings
    print("\n[1] Checking Gemini API settings...")
    settings = get_settings()

    if not settings.GEMINI_API_KEY:
        print("✗ ERROR: GEMINI_API_KEY is not set!")
        print("  Please set GEMINI_API_KEY in .env file")
        return

    print(f"✓ API Key: {settings.GEMINI_API_KEY[:10]}...")
    print(f"✓ Model: {settings.GEMINI_MODEL_NAME}")

    # 2. Prepare test prompt
    print("\n[2] Preparing test prompt...")
    test_prompt = """
You are analyzing a subtitle from the TV show "Friends".

Subtitle: "I'm gonna go get one of those job things."

Please explain:
1. What this line means in context
2. Who typically says lines like this in Friends
3. What episode this might be from

Use web search to find accurate information about Friends episodes.
"""

    print("Test prompt:")
    print(test_prompt)

    # 3. Call Gemini API with Grounding
    print("\n[3] Calling Gemini API with Google Search Grounding...")
    try:
        from app.client.gemini import GeminiClient
        gemini_client = GeminiClient(enable_grounding=True)
        result = gemini_client.generate_multimodal_with_grounding(
            prompt=test_prompt,
            images=None,
            temperature=0.7,
        )

        print("✓ API call successful!")

        # 4. Display response text
        print("\n" + "=" * 80)
        print("Gemini Response:")
        print("=" * 80)
        print(result["text"])
        print("=" * 80)

        # 5. Display grounding metadata
        print("\n[4] Extracting grounding metadata...")

        if result["grounding_metadata"]:
            print("✓ Grounding metadata found!")

            # Parse metadata
            parsed = GeminiClient.parse_grounding_metadata(result["grounding_metadata"])

            # Display search queries
            if parsed["search_queries"]:
                print(f"\n📊 Search Queries Used ({len(parsed['search_queries'])}):")
                for idx, query in enumerate(parsed["search_queries"], 1):
                    print(f"  {idx}. {query}")
            else:
                print("\n⚠️  No search queries found")

            # Display web sources
            if parsed["web_sources"]:
                print(f"\n🔗 Web Sources ({len(parsed['web_sources'])}):")
                for idx, source in enumerate(parsed["web_sources"], 1):
                    print(f"\n  {idx}. {source.get('title', 'No title')}")
                    print(f"     URL: {source.get('uri', 'No URL')}")
                    if source.get("snippet"):
                        print(f"     Snippet: {source['snippet'][:100]}...")
            else:
                print("\n⚠️  No web sources found")

            # Display search entry point
            if parsed["search_entry_point"]:
                print(f"\n🔍 Search Entry Point:")
                print(f"  {parsed['search_entry_point']}")

            # 6. Format for database storage
            print("\n[5] Formatting for database storage...")
            reference_data = {
                "query": test_prompt[:200],  # Store first 200 chars of prompt
                "items": [
                    {
                        "title": source.get("title", ""),
                        "snippet": source.get("snippet", ""),
                        "url": source.get("uri", ""),
                    }
                    for source in parsed["web_sources"]
                ],
                "search_queries": parsed["search_queries"],
            }

            print("\n📦 Reference Data (for videos_reference table):")
            print(json.dumps(reference_data, indent=2, ensure_ascii=False))

        else:
            print("⚠️  No grounding metadata found in response")
            print("   The model may not have used web search for this query")

    except Exception as e:
        print(f"✗ API call failed: {str(e)}")
        import traceback
        traceback.print_exc()


def test_grounding_with_video_context():
    """비디오 컨텍스트를 포함한 Grounding 테스트"""
    print("\n\n" + "=" * 80)
    print("Google Search Grounding Test (with Video Context)")
    print("=" * 80)

    # Load prompt template
    prompt_path = project_root / "config/prompts/explain_prompt.txt"

    if not prompt_path.exists():
        print(f"✗ Prompt template not found: {prompt_path}")
        return

    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    print("\n[1] Using explain_prompt.txt template")

    # Prepare test data
    test_data = {
        "video_title": "Friends - Season 1, Episode 1 (The Pilot)",
        "language": "Korean",
        "subtitle_text": "I'm gonna go get one of those job things.",
        "metadata_context": "- Genre: Sitcom\n- Year: 1994\n- Setting: Central Perk",
        "reference_context": "",
        "context_subtitles": """## 이전 자막
[12.5초] There's nothing to tell!
[15.2초] He's just some guy I work with.
[18.7초] Come on, you're going out with a guy!""",
        "non_verbal_cues": "## 비언어적 표현\n웃음소리, 배경음악",
    }

    final_prompt = prompt_template.format(**test_data)

    print("\n[2] Calling Gemini API with grounding...")
    try:
        from app.client.gemini import GeminiClient
        gemini_client = GeminiClient(enable_grounding=True)
        result = gemini_client.generate_multimodal_with_grounding(
            prompt=final_prompt,
            images=None,
            temperature=0.7,
        )

        print("✓ API call successful!")

        print("\n" + "=" * 80)
        print("Gemini Response:")
        print("=" * 80)
        print(result["text"])
        print("=" * 80)

        # Parse and display grounding data
        if result["grounding_metadata"]:
            parsed = GeminiClient.parse_grounding_metadata(result["grounding_metadata"])

            if parsed["web_sources"]:
                print(f"\n🔗 Found {len(parsed['web_sources'])} web sources")
                for idx, source in enumerate(parsed["web_sources"], 1):
                    print(f"  {idx}. {source.get('title', 'No title')}")
                    print(f"     {source.get('uri', 'No URL')}")

                # Format for database
                reference_data = {
                    "query": f"Explain subtitle from {test_data['video_title']}",
                    "items": [
                        {
                            "title": source.get("title", ""),
                            "snippet": source.get("snippet", ""),
                            "url": source.get("uri", ""),
                        }
                        for source in parsed["web_sources"]
                    ],
                    "search_queries": parsed["search_queries"],
                }

                print("\n📦 Ready for videos_reference table:")
                print(json.dumps(reference_data, indent=2, ensure_ascii=False))
            else:
                print("\n⚠️  No web sources found")

    except Exception as e:
        print(f"✗ API call failed: {str(e)}")
        import traceback
        traceback.print_exc()


def test_grounding_and_save_to_db():
    """Grounding 결과를 실제로 DB에 저장하는 테스트"""
    print("\n\n" + "=" * 80)
    print("Google Search Grounding + Database Save Test")
    print("=" * 80)

    from database import get_db
    from database.repositories import ReferenceRepository

    print("\n[1] Calling Gemini API with grounding...")

    test_prompt = """
Explain the cultural significance of the TV show "Friends" and its impact on 1990s television.
Include information about the main characters and setting.
"""

    try:
        from app.client.gemini import GeminiClient
        gemini_client = GeminiClient(enable_grounding=True)
        result = gemini_client.generate_multimodal_with_grounding(
            prompt=test_prompt,
            images=None,
            temperature=0.7,
        )

        print("✓ API call successful!")
        print(f"\nResponse: {result['text'][:200]}...\n")

        if result["grounding_metadata"]:
            parsed = GeminiClient.parse_grounding_metadata(result["grounding_metadata"])

            if parsed["web_sources"]:
                print(f"✓ Found {len(parsed['web_sources'])} web sources")

                # Format for database
                reference_data = {
                    "query": "Friends TV show cultural significance",
                    "items": [
                        {
                            "title": source.get("title", ""),
                            "snippet": source.get("snippet", ""),
                            "url": source.get("uri", ""),
                        }
                        for source in parsed["web_sources"]
                    ],
                    "search_queries": parsed["search_queries"],
                }

                # Save to database
                print("\n[2] Saving to database...")
                db = get_db()
                ref_repo = ReferenceRepository(db.connection)

                test_video_id = "test_friends_s01e01"

                ref_id = ref_repo.create(
                    video_id=test_video_id,
                    reference=json.dumps(reference_data, ensure_ascii=False),
                    metadata={
                        "source": "gemini_grounding",
                        "search_queries": parsed["search_queries"],
                        "num_sources": len(parsed["web_sources"]),
                    },
                )

                print(f"✓ Saved to database with ID: {ref_id}")

                # Verify saved data
                print("\n[3] Verifying saved data...")
                saved_ref = ref_repo.get_by_id(ref_id)

                if saved_ref:
                    print("✓ Data verified!")
                    print(f"  Video ID: {saved_ref['video_id']}")
                    print(f"  Created: {saved_ref['created_at']}")
                    print(f"  Metadata: {saved_ref['metadata']}")

                    # Test get_reference_content
                    print("\n[4] Testing get_reference_content...")
                    content = ref_repo.get_reference_content(test_video_id)
                    if content:
                        print("✓ Reference content retrieved:")
                        print("-" * 80)
                        print(content)
                        print("-" * 80)
                    else:
                        print("⚠️  No content retrieved")

                else:
                    print("✗ Failed to retrieve saved data")

            else:
                print("⚠️  No web sources to save")

        else:
            print("⚠️  No grounding metadata found")

    except Exception as e:
        print(f"✗ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        # Test 1: Basic grounding
        test_grounding_basic()

        # Test 2: Grounding with video context
        # test_grounding_with_video_context()

        # Test 3: Save to database
        # test_grounding_and_save_to_db()

        print("\n" + "=" * 80)
        print("All tests completed!")
        print("=" * 80)

    except KeyboardInterrupt:
        print("\n\n✗ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
