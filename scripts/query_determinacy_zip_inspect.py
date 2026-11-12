#!/usr/bin/env python3
"""Read-only ZIP inventory for the query-determinacy pilot; never extract members."""
import argparse
import hashlib
import json
from pathlib import PurePosixPath
import stat
import unicodedata
import zipfile

MAX_MEMBERS = 512
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024


def _sha256(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(CHUNK_BYTES), b''):
        digest.update(chunk)
    return digest.hexdigest()


def _validate_name(info):
    name = info.filename
    if not name or '\\' in name or '\x00' in name or name.startswith('/'):
        raise ValueError('unsafe ZIP member path')
    parts = name.rstrip('/').split('/')
    if any(part in ('', '.', '..') for part in parts) or ':' in parts[0]:
        raise ValueError('unsafe ZIP member path')
    if PurePosixPath(name).is_absolute():
        raise ValueError('unsafe ZIP member path')
    if info.create_system == 3:
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ValueError('symbolic link member is not allowed')
        kind = stat.S_IFMT(mode)
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError('special-file member is not allowed')
    if info.flag_bits & 1:
        raise ValueError('encrypted ZIP member is not supported')
    return unicodedata.normalize('NFC', name.rstrip('/'))


def inspect_archive(path):
    """Return hashes and sizes only; reject unsafe or oversized members before reading."""
    with open(path, 'rb') as source:
        archive_hash = _sha256(source)
        source.seek(0)
        with zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_MEMBERS:
                raise ValueError('too many ZIP members')
            names = set()
            total = 0
            for info in infos:
                canonical = _validate_name(info)
                if canonical in names:
                    raise ValueError('duplicate ZIP member path')
                names.add(canonical)
                if info.file_size > MAX_MEMBER_BYTES:
                    raise ValueError('ZIP member exceeds size limit')
                total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise ValueError('ZIP contents exceed total size limit')
            members = []
            for info in infos:
                if info.is_dir():
                    continue
                with archive.open(info) as member:
                    digest = _sha256(member)  # Reading through EOF also verifies CRC.
                members.append({'path': info.filename, 'size_bytes': info.file_size,
                                'sha256': digest})
        source.seek(0)
        if _sha256(source) != archive_hash:
            raise ValueError('ZIP changed during inspection')
    return {'archive_sha256': archive_hash, 'file_count': len(members),
            'total_uncompressed_bytes': sum(x['size_bytes'] for x in members),
            'members': members, 'extracted': False,
            'content_or_semantics_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', help='path to a local ZIP file')
    args = parser.parse_args()
    try:
        result = inspect_archive(args.archive)
    except (OSError, ValueError, zipfile.BadZipFile, NotImplementedError) as error:
        parser.exit(2, f'ZIP inspection failed: {error}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
