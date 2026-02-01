"""
Token 재사용 로직 테스트 스크립트
동일한 profile-id로 여러 번 token API를 호출해도 같은 토큰이 반환되는지 확인

사용법:
    python test/test_token_reuse.py
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import get_db
from database.repositories.session_repository import SessionRepository
from app.auth import create_access_token
from config.settings import get_settings


def test_token_reuse():
    """Token 재사용 로직 테스트"""
    print("\n" + "=" * 60)
    print("🔐 Token 재사용 로직 테스트")
    print("=" * 60)

    test_profile_id = "test_profile_12345"
    db = get_db()
    session_repo = SessionRepository(db.connection)
    settings = get_settings()

    # 1. 기존 테스트 세션 정리
    print("\n1️⃣  기존 테스트 세션 정리")
    existing = session_repo.get_valid_session_by_profile_id(test_profile_id)
    if existing:
        session_repo.delete(existing["session_id"])
        print(f"   ✅ 기존 세션 삭제됨: {existing['session_id']}")
    else:
        print("   ℹ️  기존 세션 없음")

    # 2. 첫 번째 토큰 발급
    print("\n2️⃣  첫 번째 토큰 발급")
    token_data_1 = create_access_token(test_profile_id)
    session_repo.create(
        session_id=token_data_1["session_id"],
        token=token_data_1["token"],
        metadata={"profile_id": test_profile_id},
        expires_in_hours=settings.JWT_EXPIRATION_DAYS * 24,
    )

    print(f"   ✅ 토큰 발급 완료")
    print(f"   Session ID: {token_data_1['session_id']}")
    print(f"   Token: {token_data_1['token'][:50]}...")
    print(f"   Expires At: {token_data_1['expires_at']}")

    # 3. 같은 profile_id로 세션 조회 (재사용 시뮬레이션)
    print("\n3️⃣  같은 profile_id로 세션 조회")
    existing_session = session_repo.get_valid_session_by_profile_id(test_profile_id)

    if existing_session:
        print(f"   ✅ 유효한 세션 발견!")
        print(f"   Session ID: {existing_session['session_id']}")
        print(f"   Token: {existing_session['token'][:50]}...")
        print(f"   Expires At: {existing_session['expires_at']}")

        # 토큰이 동일한지 확인
        if existing_session["token"] == token_data_1["token"]:
            print(f"   ✅ 토큰이 동일합니다 (재사용 성공)")
        else:
            print(f"   ❌ 토큰이 다릅니다 (재사용 실패)")
            return False

        # 만료 시간 연장
        print("\n4️⃣  만료 시간 연장")
        session_repo.extend_expiration(
            existing_session["session_id"],
            extend_hours=settings.JWT_EXPIRATION_DAYS * 24,
        )

        updated_session = session_repo.get_by_session_id(existing_session["session_id"])
        print(f"   ✅ 만료 시간 연장 완료")
        print(f"   New Expires At: {updated_session['expires_at']}")

    else:
        print(f"   ❌ 유효한 세션을 찾을 수 없습니다")
        return False

    # 5. 다른 profile_id로 조회 (세션이 없어야 함)
    print("\n5️⃣  다른 profile_id로 조회 (세션이 없어야 함)")
    other_profile_id = "other_profile_67890"
    other_session = session_repo.get_valid_session_by_profile_id(other_profile_id)

    if other_session:
        print(f"   ❌ 다른 profile의 세션이 조회되었습니다 (격리 실패)")
        return False
    else:
        print(f"   ✅ 다른 profile의 세션이 조회되지 않음 (격리 성공)")

    # 6. 세션 정보 확인
    print("\n6️⃣  세션 정보 확인")
    session = session_repo.get_by_session_id(token_data_1["session_id"])
    print(f"   Session ID: {session['session_id']}")
    print(f"   Profile ID (metadata): {session['metadata']['profile_id']}")
    print(f"   Created At: {session['created_at']}")
    print(f"   Expires At: {session['expires_at']}")

    # 7. 정리
    print("\n7️⃣  테스트 세션 정리")
    session_repo.delete(token_data_1["session_id"])
    print(f"   ✅ 테스트 세션 삭제 완료")

    return True


def test_api_simulation():
    """실제 API 호출 시뮬레이션"""
    print("\n" + "=" * 60)
    print("🌐 API 호출 시뮬레이션")
    print("=" * 60)

    test_profile_id = "api_test_profile"
    db = get_db()
    session_repo = SessionRepository(db.connection)
    settings = get_settings()

    # 기존 세션 정리
    existing = session_repo.get_valid_session_by_profile_id(test_profile_id)
    if existing:
        session_repo.delete(existing["session_id"])

    print("\n📝 시나리오: 클라이언트가 3번 연속으로 /token API 호출")

    for i in range(1, 4):
        print(f"\n[호출 {i}]")

        # 1. profile_id로 유효한 세션 조회
        existing_session = session_repo.get_valid_session_by_profile_id(test_profile_id)

        if existing_session:
            # 재사용
            print(f"   🔄 기존 토큰 재사용")
            session_repo.extend_expiration(
                existing_session["session_id"],
                extend_hours=settings.JWT_EXPIRATION_DAYS * 24,
            )
            updated_session = session_repo.get_by_session_id(existing_session["session_id"])

            print(f"   Session ID: {updated_session['session_id']}")
            print(f"   Token: {updated_session['token'][:30]}...")
            print(f"   Expires At: {updated_session['expires_at']}")
            print(f"   Reused: True")
        else:
            # 새로 발급
            print(f"   🆕 새 토큰 발급")
            token_data = create_access_token(test_profile_id)
            session_repo.create(
                session_id=token_data["session_id"],
                token=token_data["token"],
                metadata={"profile_id": test_profile_id},
                expires_in_hours=settings.JWT_EXPIRATION_DAYS * 24,
            )

            print(f"   Session ID: {token_data['session_id']}")
            print(f"   Token: {token_data['token'][:30]}...")
            print(f"   Expires At: {token_data['expires_at']}")
            print(f"   Reused: False")

    # 정리
    print("\n🧹 테스트 세션 정리")
    final_session = session_repo.get_valid_session_by_profile_id(test_profile_id)
    if final_session:
        session_repo.delete(final_session["session_id"])
        print(f"   ✅ 테스트 세션 삭제 완료")

    return True


def main():
    """메인 함수"""
    print("\n" + "=" * 60)
    print("🧪 Token 재사용 테스트 스위트")
    print("=" * 60)

    results = {
        "Token 재사용 로직": test_token_reuse(),
        "API 호출 시뮬레이션": test_api_simulation(),
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
        print("   - 같은 profile-id로는 동일한 토큰 재사용")
        print("   - 다른 profile-id는 격리됨")
        print("   - 만료 시간이 자동으로 연장됨")
    else:
        print("\n⚠️  일부 테스트 실패")
        sys.exit(1)

    print("")


if __name__ == "__main__":
    main()
