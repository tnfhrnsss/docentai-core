#!/usr/bin/env python3
"""
Gemini Explanation API 테스트 스크립트
config/prompts/explain_prompt.txt를 사용해서 Gemini API를 호출하고 응답을 확인합니다.
"""
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.client.gemini import get_gemini_client
from config.settings import get_settings


def load_prompt_template():
    """프롬프트 템플릿 로드"""
    prompt_path = project_root / "config/prompts/explain_prompt.txt"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")

    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def test_gemini_explanation():
    """Gemini API를 사용한 자막 설명 테스트"""
    print("=" * 80)
    print("Gemini Explanation API Test")
    print("=" * 80)

    # 1. Load prompt template
    print("\n[1] Loading prompt template...")
    prompt_template = load_prompt_template()
    print(f"✓ Prompt template loaded ({len(prompt_template)} characters)")

    # 2. Prepare test data
    print("\n[2] Preparing test data...")
    test_data = {
        "video_title": "Friends - Season 1, Episode 1",
        "language": "Korean",
        "subtitle_text": "I'm gonna go get one of those job things.",
        "metadata_context": "- Genre: Sitcom\n- Year: 1994\n- Setting: Coffee shop in New York",
        "reference_context": "",  # Empty for basic test
        "context_subtitles": """## 이전 자막
[12.5초] There's nothing to tell! [웃음소리]
[15.2초] He's just some guy I work with.
[18.7초] Come on, you're going out with a guy!""",
        "non_verbal_cues": "## 비언어적 표현\n배경음악, 웃음소리",
    }

    print("Test data:")
    for key, value in test_data.items():
        preview = value[:50] + "..." if len(value) > 50 else value
        print(f"  - {key}: {preview}")

    # 3. Bind variables to prompt template
    print("\n[3] Binding variables to prompt template...")
    final_prompt = prompt_template.format(**test_data)
    print(f"✓ Final prompt ready ({len(final_prompt)} characters)")

    print("\n" + "-" * 80)
    print("Final Prompt:")
    print("-" * 80)
    print(final_prompt)
    print("-" * 80)

    # 4. Check Gemini API settings
    print("\n[4] Checking Gemini API settings...")
    settings = get_settings()

    if not settings.GEMINI_API_KEY:
        print("✗ ERROR: GEMINI_API_KEY is not set!")
        print("  Please set GEMINI_API_KEY in .env file")
        return

    print(f"✓ API Key: {settings.GEMINI_API_KEY[:10]}...")
    print(f"✓ Model: {settings.GEMINI_MODEL_NAME}")

    # 5. Call Gemini API
    print("\n[5] Calling Gemini API...")
    try:
        gemini_client = get_gemini_client()
        response = gemini_client.generate_multimodal(
            prompt=final_prompt,
            images=None,  # No image for basic test
            temperature=0.7,
        )

        print("✓ API call successful!")

        # 6. Display response
        print("\n" + "=" * 80)
        print("Gemini Response:")
        print("=" * 80)
        print(response)
        print("=" * 80)

        print(f"\n✓ Response length: {len(response)} characters")

    except Exception as e:
        print(f"✗ API call failed: {str(e)}")
        import traceback
        traceback.print_exc()


def test_with_image():
    """이미지를 포함한 Gemini API 테스트"""
    print("\n\n" + "=" * 80)
    print("Gemini Explanation API Test (with Image)")
    print("=" * 80)

    # Check if test image exists
    test_image_path = project_root / "data/uploads"

    if not test_image_path.exists():
        print(f"✗ Image upload directory not found: {test_image_path}")
        print("  Skipping image test...")
        return

    # Find first image in uploads directory
    image_files = list(test_image_path.glob("*.jpg")) + \
                  list(test_image_path.glob("*.png")) + \
                  list(test_image_path.glob("*.jpeg"))

    if not image_files:
        print(f"✗ No test images found in: {test_image_path}")
        print("  Skipping image test...")
        return

    test_image = str(image_files[0])
    print(f"\n[1] Using test image: {test_image}")

    # Load prompt template
    prompt_template = load_prompt_template()

    # Prepare test data
    test_data = {
        "video_title": "Friends - Season 1, Episode 1",
        "language": "Korean",
        "subtitle_text": "I'm gonna go get one of those job things.",
        "metadata_context": "- Genre: Sitcom\n- Year: 1994",
        "reference_context": "",
        "context_subtitles": "",
        "non_verbal_cues": "",
    }

    final_prompt = prompt_template.format(**test_data)

    print("\n[2] Calling Gemini API with image...")
    try:
        gemini_client = get_gemini_client()
        response = gemini_client.generate_multimodal(
            prompt=final_prompt,
            images=[test_image],
            temperature=0.7,
        )

        print("✓ API call successful!")

        print("\n" + "=" * 80)
        print("Gemini Response (with Image):")
        print("=" * 80)
        print(response)
        print("=" * 80)

    except Exception as e:
        print(f"✗ API call failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        # Test 1: Basic explanation without image
        test_gemini_explanation()

        # Test 2: Explanation with image (if available)
        # test_with_image()

        print("\n" + "=" * 80)
        print("Test completed!")
        print("=" * 80)

    except KeyboardInterrupt:
        print("\n\n✗ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
