#!/bin/bash

# GCP Cloud Run 배포 스크립트
# 로컬에서 Docker 이미지를 빌드하고 GCP에 배포합니다.

set -e  # 에러 발생 시 스크립트 중단

# 설정값 (필요에 따라 수정)
PROJECT_ID="docentai-484704"  # GCP 프로젝트 ID
SERVICE_NAME="docentai-api"  # Cloud Run 서비스 이름
REGION="asia-northeast3"  # 서울 리전 (또는 원하는 리전)
IMAGE_NAME="docentai-api"

# Artifact Registry 설정 (GCR 대신 권장)
REGISTRY="asia-northeast3-docker.pkg.dev"
REPOSITORY="docentai-repo"  # Artifact Registry 저장소 이름

# 전체 이미지 경로
FULL_IMAGE_PATH="${REGISTRY}/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}"

echo "======================================"
echo "Docent AI - GCP Cloud Run 배포"
echo "======================================"
echo ""
echo "프로젝트 ID: ${PROJECT_ID}"
echo "서비스 이름: ${SERVICE_NAME}"
echo "리전: ${REGION}"
echo "이미지 경로: ${FULL_IMAGE_PATH}"
echo ""

# 1. gcloud 인증 확인
echo "1. gcloud 인증 상태 확인 중..."
ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null)

if [ -z "$ACTIVE_ACCOUNT" ]; then
    echo "⚠️  gcloud 인증이 필요합니다."
    echo ""
    echo "다음 중 하나를 선택하세요:"
    echo "  1) 로컬 환경: 'gcloud auth login' 실행 (브라우저 열림)"
    echo "  2) Cloud Shell: 이미 인증되어 있음 (이 메시지가 나오면 안 됨)"
    echo ""
    read -p "계속하려면 'gcloud auth login'을 실행하세요. 진행할까요? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        gcloud auth login
        ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
    else
        echo "❌ 배포를 중단합니다."
        exit 1
    fi
fi

echo "✅ 인증 완료: $ACTIVE_ACCOUNT"
echo ""

# 2. 프로젝트 설정
echo "2. GCP 프로젝트 설정 중..."
gcloud config set project ${PROJECT_ID}
echo "✅ 프로젝트 설정 완료"
echo ""

# 3. Docker 이미지 빌드
echo "3. Docker 이미지 빌드 중 (amd64 아키텍처)..."
docker build --platform linux/amd64 -t ${IMAGE_NAME}:latest .
echo "✅ 이미지 빌드 완료"
echo ""

# 4. 이미지 태깅
echo "4. 이미지 태깅 중..."
docker tag ${IMAGE_NAME}:latest ${FULL_IMAGE_PATH}:latest
docker tag ${IMAGE_NAME}:latest ${FULL_IMAGE_PATH}:$(date +%Y%m%d-%H%M%S)
echo "✅ 이미지 태깅 완료"
echo ""

# 5. Artifact Registry 인증 설정
echo "5. Artifact Registry 인증 설정 중..."
gcloud auth configure-docker ${REGISTRY} --quiet
echo "✅ 인증 설정 완료"
echo ""

# 6. 이미지 푸시
echo "6. 이미지를 Artifact Registry에 푸시 중..."
docker push ${FULL_IMAGE_PATH}:latest
echo "✅ 이미지 푸시 완료"
echo ""

# 7. Cloud Run 배포
echo "7. Cloud Run 서비스 배포 중..."
echo "⚠️  참고: 환경 변수는 .env.docker 파일이 이미지에 포함되어 있어 자동으로 로드됩니다."
gcloud run deploy ${SERVICE_NAME} \
    --image ${FULL_IMAGE_PATH}:latest \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --port 8080 \
    --memory 1Gi \
    --cpu 1 \
    --timeout 300 \
    --max-instances 10 \
    --min-instances 0

echo ""
echo "======================================"
echo "✅ 배포 완료!"
echo "======================================"
echo ""

# 서비스 URL 확인
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format='value(status.url)')
echo "🚀 서비스 URL: ${SERVICE_URL}"
echo ""
echo "Health check: ${SERVICE_URL}/health"
echo ""
