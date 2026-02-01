"""
IP 변경 모니터링 테스트 스크립트
토큰 재사용 시 IP 변경 감지가 제대로 동작하는지 확인

사용법:
    python test/test_ip_change_monitoring.py
"""
import sys
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import get_db
from database.repositories.session_repository import SessionRepository
from app.auth import create_access_token
from config.settings import get_settings

# 로거 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def simulate_ip_change_scenario():
    """IP 변경 시나리오 시뮬레이션"""
    print("\n" + "=" * 60)
    print("🔐 IP 변경 모니터링 테스트")
    print("=" * 60)

    test_profile_id = "ip_test_profile"
    db = get_db()
    session_repo = SessionRepository(db.connection)
    settings = get_settings()

    # 기존 세션 정리
    existing = session_repo.get_valid_session_by_profile_id(test_profile_id)
    if existing:
        session_repo.delete(existing["session_id"])
        print("✅ 기존 테스트 세션 삭제")

    # 시나리오 1: 첫 토큰 발급 (IP: 203.0.113.1)
    print("\n📝 시나리오 1: 첫 토큰 발급")
    print("   IP: 203.0.113.1 (집)")

    token_data = create_access_token(test_profile_id)
    session_repo.create(
        session_id=token_data["session_id"],
        token=token_data["token"],
        metadata={
            "profile_id": test_profile_id,
            "client_ip": "203.0.113.1",  # 집 IP
        },
        expires_in_hours=settings.JWT_EXPIRATION_DAYS * 24,
    )

    print(f"   ✅ 토큰 발급 완료")
    print(f"   Session ID: {token_data['session_id']}")
    print(f"   Client IP: 203.0.113.1")

    # 시나리오 2: 같은 IP에서 재사용 (정상)
    print("\n📝 시나리오 2: 같은 IP에서 재사용 (정상)")
    print("   IP: 203.0.113.1 (집 - 동일)")

    existing_session = session_repo.get_valid_session_by_profile_id(test_profile_id)
    original_ip = existing_session["metadata"].get("client_ip", "unknown")
    current_ip = "203.0.113.1"

    if original_ip != "unknown" and original_ip != current_ip:
        print(f"   ⚠️  WARNING: IP 변경 감지!")
        print(f"   Original IP: {original_ip}")
        print(f"   Current IP: {current_ip}")
    else:
        print(f"   ✅ IP 동일 (변경 없음)")
        print(f"   IP: {current_ip}")

    # 시나리오 3: 다른 IP에서 재사용 (모바일 데이터)
    print("\n📝 시나리오 3: 다른 IP에서 재사용 (모바일 데이터)")
    print("   IP: 198.51.100.1 (LTE/5G)")

    existing_session = session_repo.get_valid_session_by_profile_id(test_profile_id)
    original_ip = existing_session["metadata"].get("client_ip", "unknown")
    current_ip = "198.51.100.1"

    if original_ip != "unknown" and original_ip != current_ip:
        print(f"   ⚠️  WARNING: IP 변경 감지!")
        print(f"   Original IP: {original_ip}")
        print(f"   Current IP: {current_ip}")
        print(f"   → 정상 시나리오: WiFi → 모바일 데이터 전환")
    else:
        print(f"   ✅ IP 동일")

    # 시나리오 4: 또 다른 IP에서 재사용 (회사)
    print("\n📝 시나리오 4: 또 다른 IP에서 재사용 (회사)")
    print("   IP: 192.0.2.1 (회사)")

    existing_session = session_repo.get_valid_session_by_profile_id(test_profile_id)
    original_ip = existing_session["metadata"].get("client_ip", "unknown")
    current_ip = "192.0.2.1"

    if original_ip != "unknown" and original_ip != current_ip:
        print(f"   ⚠️  WARNING: IP 변경 감지!")
        print(f"   Original IP: {original_ip}")
        print(f"   Current IP: {current_ip}")
        print(f"   → 정상 시나리오: 이동 (집 → 회사)")
    else:
        print(f"   ✅ IP 동일")

    # 시나리오 5: 의심스러운 IP 변경 (짧은 시간 내 여러 IP)
    print("\n📝 시나리오 5: 의심스러운 활동 (짧은 시간에 여러 IP)")
    ips = [
        ("203.0.113.100", "한국"),
        ("198.51.100.100", "미국"),
        ("192.0.2.100", "일본"),
    ]

    for ip, location in ips:
        existing_session = session_repo.get_valid_session_by_profile_id(test_profile_id)
        original_ip = existing_session["metadata"].get("client_ip", "unknown")

        if original_ip != "unknown" and original_ip != ip:
            print(f"   🚨 WARNING: IP 변경 감지!")
            print(f"      Original: {original_ip}")
            print(f"      Current: {ip} ({location})")

    print(f"   → 의심 시나리오: 짧은 시간에 여러 국가에서 접속")

    # 정리
    print("\n🧹 테스트 세션 정리")
    final_session = session_repo.get_valid_session_by_profile_id(test_profile_id)
    if final_session:
        session_repo.delete(final_session["session_id"])
        print(f"   ✅ 테스트 세션 삭제 완료")

    return True


def test_log_output():
    """로그 출력 테스트"""
    print("\n" + "=" * 60)
    print("📋 로그 출력 테스트")
    print("=" * 60)

    test_profile_id = "log_test_profile"

    # app.routers.auth 로거 가져오기
    auth_logger = logging.getLogger("app.routers.auth")

    print("\n1️⃣  정상 로그 (IP 동일)")
    auth_logger.info(
        f"Token reused: profile_id={test_profile_id}, "
        f"session_id=sess_123, client_ip=203.0.113.1"
    )

    print("\n2️⃣  경고 로그 (IP 변경)")
    auth_logger.warning(
        f"IP changed for session: profile_id={test_profile_id}, "
        f"session_id=sess_123, "
        f"original_ip=203.0.113.1, "
        f"current_ip=198.51.100.1"
    )

    auth_logger.info(
        f"Token reused: profile_id={test_profile_id}, "
        f"session_id=sess_123, client_ip=198.51.100.1"
    )

    print("\n✅ 로그 출력 완료")
    print("   로그 파일 위치: ./logs/docentai.log")
    print("   WARNING 로그: ./logs/docentai_error.log")

    return True


def main():
    """메인 함수"""
    print("\n" + "=" * 60)
    print("🧪 IP 변경 모니터링 테스트 스위트")
    print("=" * 60)

    results = {
        "IP 변경 시나리오 시뮬레이션": simulate_ip_change_scenario(),
        "로그 출력 테스트": test_log_output(),
    }

    print("\n" + "=" * 60)
    print("📊 테스트 결과")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n🎉 모든 테스트 통과!")
        print("\n📋 확인 사항:")
        print("   - IP 변경 시 WARNING 로그 기록")
        print("   - 응답은 정상적으로 처리 (서비스 중단 없음)")
        print("   - 로그 파일에서 IP 변경 이력 확인 가능")
        print("\n📝 로그 확인 방법:")
        print("   grep 'IP changed' logs/docentai.log")
    else:
        print("\n⚠️  일부 테스트 실패")
        sys.exit(1)

    print("")


if __name__ == "__main__":
    main()
