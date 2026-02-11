#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

VERSION_FILE=".version"

# 최초 버전
if [ ! -f "$VERSION_FILE" ]; then
  echo "0.1.0" > "$VERSION_FILE"
fi

BASE_VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
NEXT_VERSION="$(echo "$BASE_VERSION" | awk -F. -v OFS=. '{$NF=$NF+1; print}')"

echo "$NEXT_VERSION" > "$VERSION_FILE"

GIT_SHA="$(git rev-parse --short HEAD)"
git diff --quiet || GIT_SHA="${GIT_SHA}-dirty"

IMAGE_VERSION="${NEXT_VERSION}-${GIT_SHA}"

echo "▶ Build version: $IMAGE_VERSION"
export IMAGE_TAG="$IMAGE_VERSION"

docker compose build

# latest 태깅
docker tag "sevensplit-v2:$IMAGE_VERSION" "sevensplit-v2:latest"

echo "✅ Tagged:"
echo " - sevensplit-v2:$IMAGE_VERSION"
echo " - sevensplit-v2:latest"
