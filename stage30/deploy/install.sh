#!/bin/sh
set -eu
cd "$(dirname "$0")"
[ "$(id -u)" = 0 ] || { echo 'Run from the ADB root shell'; exit 1; }
for tool in sha256sum su id stat cp mkdir chmod chown grep awk mount systemctl; do command -v "$tool" >/dev/null; done
grep -q 'BUILD_ID="20261005064926"' /etc/os-release || { echo 'Verified V1 build required'; exit 1; }
[ "$(sha256sum /usr/bin/asteroid-launcher | awk '{print $1}')" = fa6ba6d39c3ae682417d777462241811b230fb9d2acdca0299234fcfee580f54 ] || { echo 'Original compositor changed; refusing installation'; exit 1; }
sha256sum -c SHA256SUMS
./aurora-preview --session-check
gui_uid=$(id -u ceres)
gui_gid=$(id -g ceres)
[ "$gui_uid" != 0 ]
[ -S "/run/user/$gui_uid/bus" ] || { echo 'GUI session bus is not running'; exit 1; }
gui() { su -s /bin/sh ceres -c "XDG_RUNTIME_DIR=/run/user/$gui_uid DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$gui_uid/bus $1"; }
gui 'systemctl --user is-active asteroid-launcher.service'
for file in /etc/systemd/system/aurora-helper.service /etc/systemd/system/aurora-rollback.service; do
    if [ -e "$file" ] || [ -L "$file" ]; then
        [ ! -L "$file" ] && grep -q '# Aurora Stage30' "$file" || { echo 'An unrelated service file exists'; exit 1; }
    fi
done
if [ -e /var/lib/aurora ] || [ -L /var/lib/aurora ]; then
    [ ! -L /var/lib/aurora ] && [ -f /var/lib/aurora/STAGE30 ] && [ "$(stat -c %u /var/lib/aurora)" = 0 ] || { echo 'An unrelated installation directory exists'; exit 1; }
fi
override=/home/ceres/.config/systemd/user/asteroid-launcher.service.d/90-aurora-stage30.conf
if [ -e "$override" ] || [ -L "$override" ]; then
    [ ! -L "$override" ] && grep -q '# Aurora Stage30' "$override" || { echo 'An unrelated user override exists'; exit 1; }
    echo 'Restore the previous launcher before reinstalling Stage30.'; exit 1
fi
was_ro=0
if awk '$2=="/" && $4 ~ /(^|,)ro(,|$)/ {found=1} END {exit !found}' /proc/mounts; then
    mount -o remount,rw /
    was_ro=1
fi
finish() { if [ "$was_ro" = 1 ]; then mount -o remount,ro / || true; fi; }
trap finish EXIT
umask 022
mkdir -p /var/lib/aurora
cp -R ./qml ./compositor /var/lib/aurora/
cp ./aurora-compositor ./aurora-helper ./ui.qml ./desktop.js ./restore.sh /var/lib/aurora/
printf 'Aurora Stage30\n' > /var/lib/aurora/STAGE30
chown -R 0:0 /var/lib/aurora
chmod -R a+rX /var/lib/aurora
chmod 755 /var/lib/aurora /var/lib/aurora/aurora-compositor /var/lib/aurora/aurora-helper
cat > /var/lib/aurora/user-override.conf <<'UNIT'
# Aurora Stage30
[Service]
ExecStart=
ExecStart=/var/lib/aurora/aurora-compositor -plugin evdevtouch $LIPSTICK_OPTIONS --systemd
Environment="QML_IMPORT_PATH=/var/lib/aurora/qml:/usr/lib/qml"
UNIT
cat > /etc/systemd/system/aurora-helper.service <<UNIT
# Aurora Stage30
[Unit]
Description=Aurora local kernel-log helper and startup recovery
After=local-fs.target
[Service]
ExecStart=/var/lib/aurora/aurora-helper $gui_uid
User=root
Group=$gui_gid
RuntimeDirectory=aurora
RuntimeDirectoryMode=0750
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true
RestrictAddressFamilies=AF_UNIX
CapabilityBoundingSet=CAP_SYSLOG CAP_SYS_PTRACE
UnsetEnvironment=LD_PRELOAD LD_LIBRARY_PATH QT_PLUGIN_PATH QML_IMPORT_PATH
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/aurora-rollback.service <<'UNIT'
# Aurora Stage30
[Unit]
Description=Restore the previous launcher if Aurora did not load
[Service]
Type=oneshot
ExecStart=/bin/sh /var/lib/aurora/restore.sh --unless-ready
UNIT
systemctl daemon-reload
systemctl enable aurora-helper.service
# Arm independent recovery before changing the GUI process.
systemctl restart aurora-helper.service
gui 'mkdir -p /home/ceres/.config/systemd/user/asteroid-launcher.service.d && cp /var/lib/aurora/user-override.conf /home/ceres/.config/systemd/user/asteroid-launcher.service.d/90-aurora-stage30.conf'
gui 'systemctl --user daemon-reload && systemctl --user restart asteroid-launcher.service'
echo 'Aurora scene is starting. The independent helper restores the previous launcher if readiness is missing after 60 seconds.'
