#!/usr/bin/env bash
set -euo pipefail

# Purpose:
# Keep torrent client container state OUTSIDE monitored storage roots.
# Default layout:
#   compose: /opt/afterclaw/docker/torrents
#   runtime data: /var/lib/afterclaw/torrents/{client}/...
#   downloads: /var/lib/afterclaw/torrents/downloads/{client}
#
# Usage:
#   sudo bash scripts/setup_torrent_docker.sh
#   sudo DATA_ROOT=/var/lib/afterclaw/torrents DOWNLOADS_ROOT=/var/lib/afterclaw/torrents/downloads bash scripts/setup_torrent_docker.sh

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root: sudo bash $0"
  exit 1
fi

APP_ROOT="${APP_ROOT:-/opt/afterclaw}"
COMPOSE_ROOT="${COMPOSE_ROOT:-${APP_ROOT}/docker/torrents}"
DATA_ROOT="${DATA_ROOT:-/var/lib/afterclaw/torrents}"
DOWNLOADS_ROOT="${DOWNLOADS_ROOT:-/var/lib/afterclaw/torrents/downloads}"
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
TZ_VALUE="${TZ:-Asia/Shanghai}"

mkdir -p "${COMPOSE_ROOT}" "${DATA_ROOT}" "${DOWNLOADS_ROOT}"
install -d -m 0750 "${DATA_ROOT}"

for c in deluge transmission rtorrent; do
  install -d -m 0750 "${DATA_ROOT}/${c}/config" "${DATA_ROOT}/${c}/session"
  install -d -m 0755 "${DOWNLOADS_ROOT}/${c}" "${DOWNLOADS_ROOT}/${c}/watch"
done

cat > "${COMPOSE_ROOT}/compose.yml" <<EOF
services:
  deluge:
    image: lscr.io/linuxserver/deluge:latest
    container_name: deluge
    environment:
      - PUID=${PUID}
      - PGID=${PGID}
      - TZ=${TZ_VALUE}
      - DELUGE_LOGLEVEL=error
    volumes:
      - ${DATA_ROOT}/deluge/config:/config
      - ${DOWNLOADS_ROOT}/deluge:/downloads
      - ${DOWNLOADS_ROOT}/deluge/watch:/watch
    ports:
      - "8112:8112"
      - "58846:58846"
      - "58946:58946"
      - "58946:58946/udp"
    restart: unless-stopped

  transmission:
    image: lscr.io/linuxserver/transmission:latest
    container_name: transmission
    environment:
      - PUID=${PUID}
      - PGID=${PGID}
      - TZ=${TZ_VALUE}
    volumes:
      - ${DATA_ROOT}/transmission/config:/config
      - ${DOWNLOADS_ROOT}/transmission:/downloads
      - ${DOWNLOADS_ROOT}/transmission/watch:/watch
    ports:
      - "9091:9091"
      - "51413:51413"
      - "51413:51413/udp"
    restart: unless-stopped

  rtorrent:
    image: jesec/rtorrent:latest
    container_name: rtorrent
    environment:
      - TZ=${TZ_VALUE}
    volumes:
      - ${DATA_ROOT}/rtorrent/config:/config
      - ${DATA_ROOT}/rtorrent/session:/session
      - ${DOWNLOADS_ROOT}/rtorrent:/downloads
      - ${DOWNLOADS_ROOT}/rtorrent/watch:/watch
    ports:
      - "50000:50000"
      - "50000:50000/udp"
    restart: unless-stopped
EOF

chmod 0640 "${COMPOSE_ROOT}/compose.yml"
chown -R root:root "${DATA_ROOT}" "${COMPOSE_ROOT}"
chown -R "${PUID}:${PGID}" "${DOWNLOADS_ROOT}/deluge" "${DOWNLOADS_ROOT}/transmission" "${DOWNLOADS_ROOT}/rtorrent" || true

echo "Compose file: ${COMPOSE_ROOT}/compose.yml"
echo "Data root   : ${DATA_ROOT}"
echo "Downloads   : ${DOWNLOADS_ROOT}"
echo "Start with  : docker compose -f ${COMPOSE_ROOT}/compose.yml up -d"
