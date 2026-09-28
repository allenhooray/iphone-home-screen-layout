"""Pure layout transformations. No device or network access."""
import copy
import difflib
import hashlib
import json
import re
from collections import Counter


class LayoutError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise LayoutError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def ecid(value):
    require(isinstance(value, str) and re.fullmatch(r'(?:0[xX][0-9a-fA-F]+|[0-9]+)', value), 'ECID must be decimal or 0x hexadecimal')
    return str(int(value, 16 if value.lower().startswith('0x') else 10))


def validate(layout):
    require(isinstance(layout, dict) and set(layout) == {'version', 'dock', 'pages'}, 'Invalid layout fields')
    require(type(layout['version']) is int and layout['version'] == 1, 'Unsupported layout version')
    ids = []

    def icon(item, folders=True):
        require(isinstance(item, dict), 'Icon must be an object')
        if item.get('type') == 'icon':
            require(set(item) == {'type', 'id'} and isinstance(item['id'], str) and item['id'].strip(), 'Invalid icon ID')
            ids.append(item['id'])
        else:
            require(folders and set(item) == {'type', 'name', 'pages'} and item.get('type') == 'folder', 'Unknown item or nested folder')
            require(isinstance(item['name'], str) and item['name'].strip(), 'Empty folder name')
            require(isinstance(item['pages'], list) and 1 <= len(item['pages']) <= 15, 'Folder requires 1–15 pages')
            for page in item['pages']:
                require(isinstance(page, list) and 1 <= len(page) <= 9, 'Folder page requires 1–9 icons')
                for entry in page:
                    icon(entry, False)

    require(isinstance(layout['dock'], list) and len(layout['dock']) <= 4, 'Dock capacity is 4')
    require(isinstance(layout['pages'], list) and 1 <= len(layout['pages']) <= 15, 'Home screen requires 1–15 pages')
    for item in layout['dock']:
        icon(item)
    for page in layout['pages']:
        require(isinstance(page, list) and len(page) <= 24, 'Home screen page capacity is 24')
        for item in page:
            icon(item)
    require(len(ids) == len(set(ids)), 'Duplicate icon IDs are unsupported')
    return Counter(ids)


def decode(raw):
    require(isinstance(raw, list) and len(raw) >= 2, 'Expected cfgutil dock + home pages array; unsupported output is not converted')

    def icon(value):
        if isinstance(value, str):
            return {'type': 'icon', 'id': value}
        require(isinstance(value, list) and len(value) >= 2 and isinstance(value[0], str), 'Unknown cfgutil icon type')
        content = value[1:]
        if all(isinstance(v, str) for v in content):
            content = [content]
        require(all(isinstance(p, list) and all(isinstance(v, str) for v in p) for p in content), 'Mixed folder format or nested folder')
        return {'type': 'folder', 'name': value[0], 'pages': [[icon(v) for v in p] for p in content]}

    require(all(isinstance(p, list) for p in raw), 'Invalid cfgutil page')
    pages = [[icon(v) for v in p] for p in raw]
    result = {'version': 1, 'dock': pages[0], 'pages': pages[1:]}
    validate(result)
    return result


def encode(layout):
    validate(layout)

    def icon(item):
        if item['type'] == 'icon':
            return item['id']
        pages = [[i['id'] for i in p] for p in item['pages']]
        return [item['name']] + (pages[0] if len(pages) == 1 else pages)

    return [[icon(v) for v in p] for p in [layout['dock']] + layout['pages']]


def conserved(before, after):
    require(validate(before) == validate(after), 'Icon inventory changed: missing or added IDs')


def preview(before, after):
    return '\n'.join(difflib.unified_diff(
        json.dumps(before, ensure_ascii=False, indent=2).splitlines(),
        json.dumps(after, ensure_ascii=False, indent=2).splitlines(),
        fromfile='current', tofile='proposed', lineterm='')) or '(no changes)'


def classify(layout, rules):
    """Explicit ID groups only; preserve dock and all unassigned items."""
    validate(layout)
    require(isinstance(rules, dict) and set(rules) == {'groups'} and isinstance(rules['groups'], list), 'Rules require groups array')
    selected = []
    names = []
    groups = []
    for group in rules['groups']:
        require(isinstance(group, dict) and set(group) == {'name', 'ids'}, 'Invalid group fields')
        require(isinstance(group['name'], str) and group['name'].strip(), 'Empty group name')
        require(isinstance(group['ids'], list) and group['ids'] and all(isinstance(i, str) for i in group['ids']), 'Group needs icon IDs')
        names.append(group['name'])
        selected.extend(group['ids'])
        groups.append({'type': 'folder', 'name': group['name'], 'pages': [
            [{'type': 'icon', 'id': i} for i in group['ids'][n:n+9]] for n in range(0, len(group['ids']), 9)]})
    require(len(names) == len(set(names)) and len(selected) == len(set(selected)), 'Repeated group name or assignment')
    dock_only = {'version': 1, 'dock': layout['dock'], 'pages': [[]]}
    require(not (set(selected) & set(validate(dock_only))), 'Classification keeps dock fixed')
    require(set(selected) <= set(validate(layout)), 'Unknown icon ID in rules')
    chosen = set(selected)
    result = copy.deepcopy(layout)
    for page in result['pages']:
        kept = []
        for item in page:
            if item['type'] == 'icon':
                if item['id'] not in chosen:
                    kept.append(item)
            else:
                item['pages'] = [[i for i in p if i['id'] not in chosen] for p in item['pages']]
                item['pages'] = [p for p in item['pages'] if p]
                if item['pages']:
                    kept.append(item)
        page[:] = kept
    for group in groups:
        if len(result['pages'][-1]) == 24:
            result['pages'].append([])
        result['pages'][-1].append(group)
    conserved(layout, result)
    return result
