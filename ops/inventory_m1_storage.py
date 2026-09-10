"""只读盘点服务器产物，不加载模型、不读大文件内容、不删除文件。

输入为 results 中记录的绝对产物路径和服务器实际目录；输出为目录大小、
大文件位置及报告引用。例如发现一个旧 run 占用 20 GB，先报告其路径，
而不是因为它未被最新报告引用就删掉。无引用不等于无价值，文件大小
相同也不等于内容重复；本盘点不作内容去重或删除授权。
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'results/m1_storage_inventory.json'


def references():
    refs = {}
    for path in sorted((ROOT / 'results').glob('*.json')):
        if path == OUTPUT:
            continue
        pending = [json.loads(path.read_bytes())]
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
            elif isinstance(value, str) and value.startswith('/') and '/cpmt_outputs/' in value:
                parent, tail = value.split('/cpmt_outputs/', 1)
                stage = tail.split('/', 1)[0]
                if stage:
                    refs.setdefault(parent + '/cpmt_outputs/' + stage, set()).add(path.name)
    return refs


def scan(directory):
    total = 0
    count = 0
    types = Counter()
    largest = []
    markers = Counter()
    links = []
    errors = []
    def error(exc):
        errors.append(str(exc))
    for parent, dirs, files in os.walk(directory, followlinks=False, onerror=error):
        for name in list(dirs):
            path = Path(parent) / name
            if path.is_symlink():
                links.append(str(path))
                dirs.remove(name)
        for name in files:
            path = Path(parent) / name
            if path.is_symlink():
                links.append(str(path))
                continue
            try:
                size = path.stat().st_size
            except OSError as exc:
                errors.append(str(exc))
                continue
            total += size
            count += 1
            types[''.join(path.suffixes[-2:]) or '(no suffix)'] += size
            if name in ('complete.json', 'failure.json') or name.endswith('.completed.json'):
                markers[name] += 1
            largest.append((size, str(path)))
            if len(largest) > 40:
                largest = sorted(largest, reverse=True)[:20]
    return {'path': str(directory), 'logical_bytes': total, 'files': count,
            'bytes_by_suffix': dict(types), 'marker_counts': dict(markers),
            'largest_files': [{'path': path, 'bytes': size} for size, path in sorted(largest, reverse=True)[:20]],
            'symlinks_not_followed': links, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', help='实际 cpmt_outputs 目录；省略时从报告路径推导，不能有多个根目录')
    args = parser.parse_args()
    refs = references()
    roots = {str(Path(path).parent) for path in refs}
    if args.output_root:
        root = Path(args.output_root).resolve(strict=True)
    else:
        if len(roots) != 1:
            raise ValueError(f'cannot infer one output root; recorded roots={sorted(roots)}; specify --output-root')
        root = Path(next(iter(roots))).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('output root is not a directory')
    print(f'STORAGE_INVENTORY_BEGIN root={root} read_only=true', flush=True)
    rows = []
    for path in sorted(root.iterdir()):
        if path.is_symlink():
            rows.append({'path': str(path), 'symlink_not_followed': True})
        elif path.is_dir():
            row = scan(path)
            row['referenced_by_exports'] = sorted(refs.get(str(path), ()))
            rows.append(row)
            print(f'STORAGE_DIR bytes={row["logical_bytes"]} files={row["files"]} errors={len(row["errors"])} path={path}', flush=True)
        elif path.is_file():
            rows.append({'path': str(path), 'logical_bytes': path.stat().st_size, 'root_file': True})
    report = {'schema_version': 'cpmt-storage-inventory-v1', 'root': str(root), 'read_only': True,
              'content_hashes_checked': False, 'deletion_authorized': False, 'entries': rows,
              'recorded_paths_missing_on_this_host': sorted(p for p in refs if not Path(p).exists()),
              'limitations': 'Logical file sizes, not physical disk usage; no symlinks followed; non-atomic snapshot. No reference is not a deletion criterion.'}
    raw = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
    if OUTPUT.exists():
        if OUTPUT.read_bytes() != raw:
            raise ValueError(f'existing inventory differs and is preserved: {OUTPUT}')
    else:
        with OUTPUT.open('xb') as stream:
            stream.write(raw)
    print(f'STORAGE_INVENTORY_OK output={OUTPUT} deleted=0', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'STORAGE_INVENTORY_FAILED {type(error).__name__}: {error}', file=sys.stderr, flush=True)
        raise SystemExit(1)
