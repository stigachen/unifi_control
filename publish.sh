#!/usr/bin/env bash
# Build and push a multi-arch (amd64 + arm64) image to Docker Hub.
#
# Usage:
#   ./publish.sh              # tags as :latest only
#   ./publish.sh v0.2.0       # tags as :v0.2.0 AND :latest
#
# Prerequisites (one-time):
#   docker login                                 # log in to Docker Hub as stigachen
#   docker buildx create --name multi --use      # create a buildx builder
#   docker buildx inspect --bootstrap            # confirm it supports linux/amd64,linux/arm64
set -euo pipefail

IMAGE="${IMAGE:-stigachen/unifi-control}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
VERSION="${1:-}"

TAGS=(--tag "${IMAGE}:latest")
if [[ -n "${VERSION}" ]]; then
  TAGS+=(--tag "${IMAGE}:${VERSION}")
fi

echo ">> Building ${IMAGE} for ${PLATFORMS}"
echo ">> Tags: ${TAGS[*]}"

docker buildx build \
  --platform "${PLATFORMS}" \
  "${TAGS[@]}" \
  --push \
  .

echo
echo ">> Pushed:"
for tag in "${TAGS[@]}"; do
  [[ "${tag}" == "--tag" ]] && continue
  echo "   ${tag}"
done
echo
echo ">> Pull from any host with:"
echo "   docker pull ${IMAGE}:${VERSION:-latest}"
