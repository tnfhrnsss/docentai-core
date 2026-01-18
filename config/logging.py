"""
Logging Configuration
로그 파일 로테이션 설정 (일자별/크기별)
"""
import logging
import logging.handlers
import sys
from pathlib import Path


def setup_logging(
    log_dir: str = "./logs",
    log_level: str = "INFO",
    app_name: str = "docentai",
):
    """
    로깅 설정 초기화

    Args:
        log_dir: 로그 파일 저장 디렉토리
        log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        app_name: 애플리케이션 이름 (로그 파일명 prefix)
    """
    # 로그 디렉토리 생성
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # 로그 레벨 설정
    level = getattr(logging, log_level.upper(), logging.INFO)

    # 로그 포맷 설정
    log_format = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Root logger 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 기존 핸들러 제거 (중복 방지)
    root_logger.handlers.clear()

    # 1. 콘솔 핸들러 (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)

    # 2. 일자별 로테이션 핸들러 (매일 자정에 새 파일)
    daily_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_path / f"{app_name}.log",
        when="midnight",  # 매일 자정
        interval=1,  # 1일마다
        backupCount=30,  # 30일치 보관
        encoding="utf-8",
    )
    daily_handler.setLevel(level)
    daily_handler.setFormatter(log_format)
    daily_handler.suffix = "%Y-%m-%d"  # 백업 파일명: app_name.log.2025-01-18
    root_logger.addHandler(daily_handler)

    # 3. 크기별 로테이션 핸들러 (10MB마다 새 파일)
    size_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / f"{app_name}_rotate.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,  # 최대 5개 파일 보관
        encoding="utf-8",
    )
    size_handler.setLevel(level)
    size_handler.setFormatter(log_format)
    root_logger.addHandler(size_handler)

    # 4. 에러 전용 로그 파일
    error_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / f"{app_name}_error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,  # 최대 10개 파일 보관
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(log_format)
    root_logger.addHandler(error_handler)

    # Uvicorn 로거 설정
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers = [console_handler, daily_handler]

    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.handlers = [console_handler, daily_handler, error_handler]

    logging.info(f"✅ 로깅 설정 완료: {log_path} (레벨: {log_level})")

    return root_logger
