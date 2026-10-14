#!/usr/bin/env python3
"""Research-only kernel build workaround for two NDP BAM status reads.

For kernels with CONFIG_SPS_SUPPORT_NDP_BAM disabled, avoid compiling two
NDP-only status queries that reference unavailable P_HALT bit masks. Leave
the existing conservative return-false paths untouched.

This does not validate the hardware behavior and must not be used as a
reason to boot/flash an otherwise unverified kernel.
"""
from pathlib import Path
import sys


def patch_status_query(source: str, symbol: str) -> str:
    needle = f"if (bam_read_reg_field(base, P_HALT, pipe, {symbol})) {{"
    if source.count(needle) != 1:
        raise ValueError(f"Expected exactly one {symbol} query; got {source.count(needle)}")

    position = source.index(needle)
    line_start = source.rfind("\n", 0, position) + 1
    opening = source.find("{", position + len(needle) - 1)
    if opening == -1:
        raise ValueError(f"No body found for {symbol}")

    # Match the enclosing if body's closing brace. The affected blocks
    # contain only logging and a 'return true', but verify that shape.
    depth = 0
    end = -1
    for i in range(opening, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end < 0:
        raise ValueError(f"Unbalanced C braces near {symbol}")
    block = source[line_start:end]
    if "return true;" not in block:
        raise ValueError(f"Unexpected query shape near {symbol}")
    if "#if" in block or "#endif" in block:
        raise ValueError(f"Unexpected preprocessor directives near {symbol}")
    return (
        source[:line_start]
        + "#ifdef CONFIG_SPS_SUPPORT_NDP_BAM\n"
        + block
        + "\n#endif"
        + source[end:]
    )


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("Usage: patch_bam_ndp.py BAM_C KERNEL_CONFIG")
    target = Path(sys.argv[1])
    config = Path(sys.argv[2]).read_text(encoding="utf-8")
    if "# CONFIG_SPS_SUPPORT_NDP_BAM is not set" not in config.splitlines():
        sys.exit("Unsupported kernel config; NDP BAM flag not explicitly disabled")

    original = target.read_text(encoding="utf-8")
    patched = original
    for symbol in ("P_HALT_P_LAST_DESC_ZLT", "P_HALT_P_PIPE_EMPTY"):
        patched = patch_status_query(patched, symbol)
    if patched == original:
        sys.exit("Patch had no effect")
    target.write_text(patched, encoding="utf-8")
    print("Guarded exactly two NDP BAM status checks in local CI kernel checkout")


if __name__ == "__main__":
    main()
