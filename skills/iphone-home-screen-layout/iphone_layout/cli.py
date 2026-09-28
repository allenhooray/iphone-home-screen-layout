import argparse
import json
import sys
from .adapter import Cfgutil
from .core import LayoutError, classify, conserved, preview, validate, digest, require
from .workflow import snapshot, check_snapshot, plan, execute, save


def load(path):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def main(argv=None):
    parser = argparse.ArgumentParser(description='macOS iPhone Home Screen layout skill CLI')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('read', 'backup', 'import', 'plan', 'validate', 'diff', 'apply', 'restore'):
        p = sub.add_parser(name)
        if name in ('read', 'backup', 'import', 'apply', 'restore'):
            p.add_argument('--ecid', required=True)
        if name in ('read', 'backup', 'apply', 'restore'):
            p.add_argument('--cfgutil', help='Explicit cfgutil executable path')
        if name in ('read', 'backup', 'import', 'plan'):
            p.add_argument('--out', required=True, help='New file; existing files are never overwritten')
        if name in ('import', 'apply', 'restore'):
            p.add_argument('file')
        if name in ('plan', 'validate', 'diff'):
            p.add_argument('snapshot')
        if name == 'plan':
            p.add_argument('rules')
        if name in ('validate', 'diff'):
            p.add_argument('layout', help='Normalized target Layout JSON')
        if name in ('apply', 'restore'):
            p.add_argument('--expect-plan-sha256', help='Digest from preview; required for commit')
            p.add_argument('--commit', action='store_true', help='Actually write; default is preview only')
            p.add_argument('--backups', default='.iphone-layout-backups')
    args = parser.parse_args(argv)
    try:
        if args.command in ('read', 'backup'):
            adapter = Cfgutil(args.ecid, args.cfgutil)
            save(args.out, snapshot(adapter.ecid, adapter.read()))
        elif args.command == 'import':
            save(args.out, snapshot(args.ecid, load(args.file)))
        elif args.command == 'plan':
            source = check_snapshot(load(args.snapshot))
            target = classify(source['layout'], load(args.rules))
            save(args.out, plan(source, target))
            print(preview(source['layout'], target))
            print('plan_sha256: ' + digest(plan(source, target)))
        elif args.command in ('validate', 'diff'):
            source = check_snapshot(load(args.snapshot))
            target = load(args.layout)
            conserved(source['layout'], target)
            print(preview(source['layout'], target) if args.command == 'diff' else 'Valid; icon inventory preserved')
        else:
            adapter = Cfgutil(args.ecid, args.cfgutil)
            proposal = load(args.file)
            if args.commit:
                require(args.expect_plan_sha256 == digest(proposal), 'Commit requires matching --expect-plan-sha256 from preview')
            print(json.dumps(execute(adapter, proposal, args.backups, args.commit,
                                     args.command == 'restore'), ensure_ascii=False, indent=2))
        return 0
    except (LayoutError, OSError, ValueError, KeyError, TypeError) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
