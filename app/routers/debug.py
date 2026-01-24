"""
Debug Router
디버깅 및 테스트용 엔드포인트
"""
from fastapi import APIRouter, Request
from app.utils import get_client_ip, get_all_ip_info, is_local_ip

router = APIRouter(prefix="/api/debug", tags=["Debug"])


@router.get("/ip")
async def get_ip_info(request: Request):
    """
    클라이언트 IP 정보 확인

    모든 IP 관련 헤더와 정보를 반환합니다.
    디버깅 및 테스트용으로 사용하세요.
    """
    client_ip = get_client_ip(request)

    return {
        "client_ip": client_ip,
        "is_local": is_local_ip(client_ip),
        "all_info": get_all_ip_info(request),
        "headers": {
            "x-forwarded-for": request.headers.get("X-Forwarded-For"),
            "x-real-ip": request.headers.get("X-Real-IP"),
            "user-agent": request.headers.get("User-Agent"),
        },
    }


@router.get("/request-info")
async def get_request_info(request: Request):
    """
    전체 요청 정보 확인

    Request 객체의 모든 정보를 반환합니다.
    """
    return {
        "method": request.method,
        "url": str(request.url),
        "base_url": str(request.base_url),
        "path": request.url.path,
        "query_params": dict(request.query_params),
        "client": {
            "host": request.client.host if request.client else None,
            "port": request.client.port if request.client else None,
        },
        "headers": dict(request.headers),
    }
