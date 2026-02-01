#!/bin/bash

# GCP Cloud Run 빠른 재배포 스크립트
# 이미지 빌드 -> 푸시 -> 재배포만 수행 (설정 변경 없음)

set -e

# 설정값
PROJECT_ID="docentai-484704"
SERVICE_NAME="docentai-api"
REGION="asia-northeast3"
IMAGE_NAME="docentai-api"
REGISTRY="asia-northeast3-docker.pkg.dev"
REPOSITORY="docentai-repo"
FULL_IMAGE_PATH="${REGISTRY}/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}"

echo "======================================"
echo "🚀 빠른 재배포 시작"
echo "======================================"
echo ""

# 인증 확인
ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null)
if [ -z "$ACTIVE_ACCOUNT" ]; then
    echo "❌ gcloud 인증이 필요합니다."
    echo "   로컬: gcloud auth login"
    echo "   Cloud Shell: 이미 인증되어 있어야 함"
    exit 1
fi
echo "✅ 인증: $ACTIVE_ACCOUNT"
echo ""

# 1. 이미지 빌드
echo "📦 Docker 이미지 빌드 중 (amd64)..."
docker build --platform linux/amd64 -t ${IMAGE_NAME}:latest .
echo "✅ 빌드 완료"
echo ""

# 2. 태깅
echo "🏷️  이미지 태깅 중..."
docker tag ${IMAGE_NAME}:latest ${FULL_IMAGE_PATH}:latest
echo "✅ 태깅 완료"
echo ""

# 3. 푸시
echo "⬆️  이미지 푸시 중..."
docker push ${FULL_IMAGE_PATH}:latest --quiet
echo "✅ 푸시 완료"
echo ""

# 4. 재배포
echo "🔄 Cloud Run 재배포 중..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${FULL_IMAGE_PATH}:latest \
    --region ${REGION} \
    --quiet

echo ""
echo "======================================"
echo "✅ 재배포 완료!"
echo "======================================"

# 서비스 URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format='value(status.url)')
echo ""
echo "🌐 서비스 URL: ${SERVICE_URL}"
echo ""
