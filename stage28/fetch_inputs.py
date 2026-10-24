#!/usr/bin/env python3
"""Fetch fixed public SDK and V1 rootfs bytes; never update the watch."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

REPO = Path(__file__).resolve().parent.parent


def obtain(url, target, algorithm, expected, expected_size=None):
    def digest_file():
        digest = hashlib.new(algorithm)
        with target.open('rb') as source:
            while data := source.read(1024 * 1024):
                digest.update(data)
        return digest.hexdigest()
    if target.exists() and digest_file() == expected:
        return {'file': target.name, algorithm: expected, 'bytes': target.stat().st_size, 'url': url}
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + '.part')
    request = urllib.request.Request(url, headers={'User-Agent': 'Aurora-Stage28-native-build'})
    digest = hashlib.new(algorithm)
    count = 0
    print('Download ' + target.name, flush=True)
    with urllib.request.urlopen(request, timeout=90) as response, partial.open('wb') as output:
        while data := response.read(1024 * 1024):
            count += len(data)
            if count > (expected_size or 5 * 1024**3):
                raise ValueError('Input exceeds pinned size limit')
            digest.update(data)
            output.write(data)
    if digest.hexdigest() != expected or (expected_size and count != expected_size):
        partial.unlink(missing_ok=True)
        raise ValueError('Input checksum/size mismatch: ' + target.name)
    partial.replace(target)
    print('Verified ' + target.name + ': ' + str(count) + ' bytes', flush=True)
    return {'file': target.name, algorithm: expected, 'bytes': count, 'url': url}


def main(work):
    pins = json.loads((REPO / 'stage28/pins.json').read_text())
    root = json.loads((REPO / 'stage27/v1-pins.json').read_text())['assets'][0]
    downloads = work / 'downloads'
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(obtain, pins['sdk']['url'], downloads / 'asteroid-sdk.sh', 'sha512', pins['sdk']['sha512']),
            pool.submit(obtain, 'https://github.com/TeamWearFreedomProject/Pixel-Watch-2-Asteroid-OS-Beta/releases/download/V1/' + root['name'],
                        downloads / 'v1.ext4', 'sha256', root['sha256'], root['bytes'])
        ]
        results = [future.result() for future in futures]
    (work / 'inputs.json').write_text(json.dumps(results, indent=2) + '\n')


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
