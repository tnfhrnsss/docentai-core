"""
Client IP 추출 유틸리티
FastAPI Request 객체에서 실제 클라이언트 IP를 추출합니다.
프록시/로드밸런서 환경(GCP, AWS 등)을 고려합니다.
"""
from typing import Optional
from fastapi import Request


def get_client_ip(request: Request) -> str:
    """
    클라이언트의 실제 IP 주소를 추출합니다.

    프록시/로드밸런서 뒤에 있을 때를 고려하여 다음 순서로 IP를 확인합니다:
    1. X-Forwarded-For 헤더 (가장 왼쪽 IP = 실제 클라이언트)
    2. X-Real-IP 헤더
    3. request.client.host (직접 연결된 IP)

    Args:
        request: FastAPI Request 객체

    Returns:
        str: 클라이언트 IP 주소

    Examples:
        >>> from fastapi import Request, Depends
        >>> @app.get("/api/test")
        >>> async def test_endpoint(request: Request):
        >>>     client_ip = get_client_ip(request)
        >>>     return {"client_ip": client_ip}
    """
    # 1. X-Forwarded-For 헤더 확인 (프록시/로드밸런서 사용 시)
    # GCP Load Balancer, Cloud Run, AWS ALB 등에서 자동으로 설정됨
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For: client, proxy1, proxy2
        # 가장 왼쪽이 실제 클라이언트 IP
        client_ip = forwarded_for.split(",")[0].strip()
        return client_ip

    # 2. X-Real-IP 헤더 확인 (Nginx 등에서 사용)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # 3. 직접 연결된 클라이언트 IP (프록시 없을 때)
    if request.client:
        return request.client.host

    # 4. 알 수 없는 경우
    return "unknown"


def get_all_ip_info(request: Request) -> dict:
    """
    디버깅용: 모든 IP 관련 정보를 반환합니다.

    Args:
        request: FastAPI Request 객체

    Returns:
        dict: IP 관련 모든 정보

    Examples:
        >>> ip_info = get_all_ip_info(request)
        >>> print(ip_info)
        {
            "client_ip": "203.0.113.1",
            "x_forwarded_for": "203.0.113.1, 10.0.0.1",
            "x_real_ip": None,
            "request_client_host": "10.0.0.1",
            "request_client_port": 54321
        }
    """
    return {
        "client_ip": get_client_ip(request),
        "x_forwarded_for": request.headers.get("X-Forwarded-For"),
        "x_real_ip": request.headers.get("X-Real-IP"),
        "request_client_host": request.client.host if request.client else None,
        "request_client_port": request.client.port if request.client else None,
    }


def is_local_ip(ip: str) -> bool:
    """
    로컬/사설 IP인지 확인합니다.

    Args:
        ip: IP 주소 문자열

    Returns:
        bool: 로컬 IP이면 True
    """
    if ip == "unknown":
        return False

    # 로컬/사설 IP 대역
    local_ranges = [
        "127.",          # 127.0.0.0/8 (localhost)
        "10.",           # 10.0.0.0/8 (private)
        "172.16.",       # 172.16.0.0/12 (private)
        "172.17.",
        "172.18.",
        "172.19.",
        "172.20.",
        "172.21.",
        "172.22.",
        "172.23.",
        "172.24.",
        "172.25.",
        "172.26.",
        "172.27.",
        "172.28.",
        "172.29.",
        "172.30.",
        "172.31.",
        "192.168.",      # 192.168.0.0/16 (private)
        "::1",           # IPv6 localhost
        "fc00:",         # IPv6 private
        "fd00:",         # IPv6 private
    ]

    return any(ip.startswith(prefix) for prefix in local_ranges)
