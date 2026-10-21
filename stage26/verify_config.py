#!/usr/bin/env python3
"""Fail before compilation when any non-initramfs Kconfig result changes."""
import json
from pathlib import Path
import sys
from assemble import config_delta

if __name__=='__main__':
    changes=config_delta(Path(sys.argv[1]).read_text(),Path(sys.argv[2]).read_text())
    print('STAGE26_PRE_COMPILE_CONFIG_CHECK='+json.dumps(changes,sort_keys=True))
