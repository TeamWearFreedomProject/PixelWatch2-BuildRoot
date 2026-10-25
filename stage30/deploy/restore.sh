#!/bin/sh
set -eu
[ "$(id -u)" = 0 ] || { echo 'Root is required'; exit 1; }
if [ "${1-}" = --unless-ready ] && [ -f /run/aurora/ready ]; then exit 0; fi
gui_uid=$(id -u ceres)
gui() { su -s /bin/sh ceres -c "XDG_RUNTIME_DIR=/run/user/$gui_uid DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$gui_uid/bus $1"; }
override=/home/ceres/.config/systemd/user/asteroid-launcher.service.d/90-aurora-stage30.conf
if [ -e "$override" ] || [ -L "$override" ]; then
    [ ! -L "$override" ] && grep -q '# Aurora Stage30' "$override" || { echo 'User override has changed; refusing to delete it'; exit 1; }
    gui 'rm /home/ceres/.config/systemd/user/asteroid-launcher.service.d/90-aurora-stage30.conf'
fi
was_ro=0
if awk '$2=="/" && $4 ~ /(^|,)ro(,|$)/ {found=1} END {exit !found}' /proc/mounts; then mount -o remount,rw /;was_ro=1;fi
finish() { if [ "$was_ro" = 1 ]; then mount -o remount,ro / || true; fi; }
trap finish EXIT
systemctl disable aurora-helper.service || true
gui 'systemctl --user daemon-reload && systemctl --user restart asteroid-launcher.service'
echo 'Previous compositor and its existing home configuration restored.'
systemctl stop aurora-helper.service || true
