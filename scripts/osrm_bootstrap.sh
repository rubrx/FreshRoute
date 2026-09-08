#!/usr/bin/env bash
# osrm_bootstrap.sh — one-time OSRM preprocessing for the India OSM extract.
#
# Downloads the Geofabrik India extract (~1.4 GB), runs the OSRM MLD pipeline
# (extract → partition → customize), and leaves ready-to-serve artifacts in
# ./data/osrm/.
#
# After this succeeds, `docker compose --profile osrm up -d osrm` serves
# routes at http://localhost:5000.
#
# Prereqs: docker (compose v2), curl, ~10 GB free disk, ~30–60 min on a
# broadband connection + decent laptop.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OSRM_DIR="${REPO_ROOT}/data/osrm"
EXTRACT_URL="${OSRM_EXTRACT_URL:-https://download.geofabrik.de/asia/india-latest.osm.pbf}"
PBF="${OSRM_DIR}/india-latest.osm.pbf"
OSRM_IMAGE="osrm/osrm-backend:latest"
PROFILE="/opt/car.lua"

mkdir -p "${OSRM_DIR}"

log() { printf '\n\033[1;36m[osrm-bootstrap]\033[0m %s\n' "$*"; }

if [[ -f "${OSRM_DIR}/india-latest.osrm.mldgr" ]]; then
  log "Preprocessed artifacts already exist in ${OSRM_DIR}. Delete them to re-run."
  log "Files:"
  ls -lh "${OSRM_DIR}" | sed 's/^/    /'
  exit 0
fi

if [[ ! -f "${PBF}" ]]; then
  log "Downloading Geofabrik India extract from ${EXTRACT_URL}"
  log "This is ~1.4 GB. Grab a coffee."
  curl -L --fail --progress-bar -o "${PBF}.tmp" "${EXTRACT_URL}"
  mv "${PBF}.tmp" "${PBF}"
else
  log "Extract already downloaded at ${PBF}"
fi

log "Pulling OSRM image ${OSRM_IMAGE}"
docker pull "${OSRM_IMAGE}"

log "Step 1/3: osrm-extract (this is the slow one — 15–30 min)"
docker run --rm -v "${OSRM_DIR}:/data" "${OSRM_IMAGE}" \
  osrm-extract -p "${PROFILE}" /data/india-latest.osm.pbf

log "Step 2/3: osrm-partition"
docker run --rm -v "${OSRM_DIR}:/data" "${OSRM_IMAGE}" \
  osrm-partition /data/india-latest.osrm

log "Step 3/3: osrm-customize"
docker run --rm -v "${OSRM_DIR}:/data" "${OSRM_IMAGE}" \
  osrm-customize /data/india-latest.osrm

log "Done. Preprocessed files:"
ls -lh "${OSRM_DIR}" | sed 's/^/    /'
log "Start the routing server with:  docker compose --profile osrm up -d osrm"
