"""
Test URL extraction from text (fallback mechanism)
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.client.gemini import GeminiClient


def test_url_extraction():
    """Test URL extraction from various text formats"""

    # Create client (without API key needed for this test)
    client = GeminiClient.__new__(GeminiClient)

    # Test case 1: Formatted with numbers and titles
    text1 = """
1. '나이브스 아웃' 3편 제목은 '웨이크 업 데드 맨'…내년 공개
URL: https://www.yna.co.kr/view/AKR20240525031400075

2. 나이브스 아웃: 글래스 어니언 - 나무위키
URL: https://namu.wiki/w/%EB%82%98%EC%9D%B4%EB%B8%8C%EC%8A%A4%20%EC%95%84%EC%9B%83

3. Knives Out 3: Everything We Know About Wake Up Dead Man
URL: https://screenrant.com/knives-out-3-wake-up-dead-man-news-updates/
"""

    print("Test 1: Formatted text with numbers and titles")
    print("-" * 60)
    sources1 = client._extract_urls_from_text(text1)
    print(f"Extracted {len(sources1)} sources:")
    for i, source in enumerate(sources1, 1):
        print(f"{i}. Title: {source['title']}")
        print(f"   URL: {source['uri']}")
    print()

    # Test case 2: Only URLs without numbers
    text2 = """
Here are some relevant sources:
URL: https://example.com/article1
URL: https://example.com/article2
"""

    print("Test 2: URLs without titles")
    print("-" * 60)
    sources2 = client._extract_urls_from_text(text2)
    print(f"Extracted {len(sources2)} sources:")
    for i, source in enumerate(sources2, 1):
        print(f"{i}. Title: {source['title']}")
        print(f"   URL: {source['uri']}")
    print()

    # Test case 3: Mixed text with URLs scattered
    text3 = """
According to https://wikipedia.org/wiki/Knives_Out, the movie was released in 2019.
You can read more at https://imdb.com/title/tt8946378 for additional information.
"""

    print("Test 3: URLs scattered in text")
    print("-" * 60)
    sources3 = client._extract_urls_from_text(text3)
    print(f"Extracted {len(sources3)} sources:")
    for i, source in enumerate(sources3, 1):
        print(f"{i}. Title: {source['title']}")
        print(f"   URL: {source['uri']}")
    print()

    # Test case 4: No URLs
    text4 = "This is just plain text without any URLs."

    print("Test 4: No URLs")
    print("-" * 60)
    sources4 = client._extract_urls_from_text(text4)
    print(f"Extracted {len(sources4)} sources")
    print()

    # Summary
    print("=" * 60)
    print("Summary:")
    print(f"✓ Test 1 (formatted): {len(sources1)} sources extracted")
    print(f"✓ Test 2 (URL only): {len(sources2)} sources extracted")
    print(f"✓ Test 3 (scattered): {len(sources3)} sources extracted")
    print(f"✓ Test 4 (no URLs): {len(sources4)} sources extracted")

    # Verify test 1 extracted correct data
    assert len(sources1) == 3, f"Expected 3 sources, got {len(sources1)}"
    assert sources1[0]["title"] == "'나이브스 아웃' 3편 제목은 '웨이크 업 데드 맨'…내년 공개"
    assert sources1[0]["uri"] == "https://www.yna.co.kr/view/AKR20240525031400075"

    print("\n✓ All tests passed!")


if __name__ == "__main__":
    test_url_extraction()
