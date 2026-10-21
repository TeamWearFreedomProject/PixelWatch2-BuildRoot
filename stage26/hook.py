#!/usr/bin/env python3
"""Insert one recorded configuration hook in the pinned generic builder."""
from pathlib import Path
import sys


def patch(text):
    needle='make O="$OUT" $MAKEOPTS $deviceinfo_kernel_defconfig\n'
    if text.count(needle)!=1:raise ValueError('Unexpected upstream builder shape')
    return text.replace(needle,needle+
        '/usr/bin/python3 "$AURORA_STAGE26_PROJECT/stage26/configure.py" "$OUT/.config" "$AURORA_STAGE26_INITRAMFS"\n'
        'make O="$OUT" $MAKEOPTS olddefconfig\n'
        '/usr/bin/python3 "$AURORA_STAGE26_PROJECT/stage26/verify_config.py" "$AURORA_STAGE26_BASELINE" "$OUT/.config"\n')


if __name__=='__main__':
    root=Path(sys.argv[1]);p=root/'build-kernel.sh';p.write_text(patch(p.read_text()))
    p=root/'build.sh';text=p.read_text();needle='ALLOWED_HOST_TOOLS="bash git perl sh sync tar yes"'
    if text.count(needle)!=1:raise SystemExit('Unexpected host-tool whitelist')
    p.write_text(text.replace(needle,'ALLOWED_HOST_TOOLS="bash git perl sh sync tar yes gzip"'))
