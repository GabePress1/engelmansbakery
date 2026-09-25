"""Check the generated frames for overlaps and spot-check card formulas against the workbook.

1. Overlap: rebuilds every widget's absolute box from frame*.svg. Cards are a fixed
   320x88. Text boxes use the widths Miro measured on this board (per-character rates
   below are the measured maxima, rounded up). A diagram's authored x/y is its top-left.
   Every pair of non-frame widgets must be disjoint, every widget must sit inside
   its frame, and frames must not touch.
2. Formulas: reads 10 cells straight from the .xlsm sheet XML (not via formulas.json)
   and checks each card that quotes them carries the same text.

Usage: python3 verify.py <workbook.xlsm>
"""
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PX_PER_CHAR = {(67, True): 42, (22, True): 13.4, (22, False): 13.2}
TEXT_H = {67: 96, 22: 31}


def boxes():
    out = []
    for path in sorted(glob.glob(os.path.join(HERE, 'frame*.svg'))):
        root = ET.parse(path).getroot()
        for el in root:
            if el.tag.endswith('g'):
                fx, fy = map(float, re.findall(r'-?\d+', el.get('transform')))
                fr = el[0]
                fbox = (fx, fy, float(fr.get('width')), float(fr.get('height')))
                out.append(('frame', el.get('id'), fbox, None))
                for ch in list(el)[1:]:
                    x, y = float(ch.get('x')), float(ch.get('y'))
                    if ch.tag.endswith('text'):
                        fs = int(ch.get('font-size'))
                        w = len(ch.text) * PX_PER_CHAR[(fs, ch.get('font-weight') == 'bold')]
                        h = TEXT_H[fs]
                        b = (fx + x, fy + y - h * 0.7, w, h)
                    else:
                        b = (fx + x, fy + y, float(ch.get('width')), float(ch.get('height')))
                    out.append(('item', ch.get('id'), b, fbox))
            elif el.get('data-type') == 'diagram':   # loose diagram: absolute top-left
                w, h = float(el.get('width')), float(el.get('height'))
                b = (float(el.get('x')), float(el.get('y')), w, h)
                out.append(('item', el.get('id'), b, None))
    return out


def overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def inside(a, f):
    return f[0] <= a[0] and f[1] <= a[1] and a[0] + a[2] <= f[0] + f[2] and a[1] + a[3] <= f[1] + f[3]


def check_layout():
    bs = boxes()
    frames = [b for b in bs if b[0] == 'frame']
    items = [b for b in bs if b[0] == 'item']
    problems = []
    for i, a in enumerate(frames):
        for b in frames[i + 1:]:
            if overlap(a[2], b[2]):
                problems.append(f'frames overlap: {a[1]} {b[1]}')
    for i, a in enumerate(items):
        if a[3] and not inside(a[2], a[3]):
            problems.append(f'{a[1]} leaves its frame')
        for b in items[i + 1:]:
            if overlap(a[2], b[2]):
                problems.append(f'overlap: {a[1]} {b[1]}')
    # each diagram must sit inside the frame it illustrates
    for d in [b for b in items if b[1].startswith('d')]:
        f = next(fr for fr in frames if fr[1] == 'f' + d[1][1:])
        if not inside(d[2], f[2]):
            problems.append(f'{d[1]} is not inside {f[1]}')
    print(f'layout: {len(frames)} frames, {len(items)} widgets, {len(problems)} problems')
    for p in problems:
        print('  ', p)
    return not problems


SPOT = [  # (sheet file, cell, text the card must contain)
    ('sheet19', 'P2', None), ('sheet20', 'I2', None), ('sheet1', 'J3', None),
    ('sheet10', 'AW8', None), ('sheet10', 'H8', None), ('sheet10', 'DC287', None),
    ('sheet11', 'F5', None), ('sheet12', 'N7', None), ('sheet12', 'P411', None),
    ('sheet13', 'F29', None),
]


def raw_formula(z, sheet, cell):
    """Formula text of one cell from the sheet XML, following a shared formula to its master."""
    target, masters = None, {}
    for _, el in ET.iterparse(z.open(f'xl/worksheets/{sheet}.xml')):
        if el.tag.endswith('}c'):
            f = next((c for c in el if c.tag.endswith('}f')), None)
            if f is not None and f.get('t') == 'shared' and f.text:
                masters[f.get('si')] = (f.text, el.get('r'))
            if el.get('r') == cell:
                target = f
                target_si = None if f is None else f.get('si')
                target_text = None if f is None else f.text
            el.clear()
    if target is None:
        return None
    if target_text:
        return target_text
    return ('SHARED', masters.get(target_si))


def norm(f):
    f = re.sub(r'_xl(fn|pm|ws)\.', '', f)
    return re.sub(r'(\w+)\[\[#This Row\],\[([^\]]+)\]\]', r'[@\2]', f)


def check_formulas(xlsm):
    import extract
    z = zipfile.ZipFile(xlsm)
    svgs = ''.join(open(p).read() for p in glob.glob(os.path.join(HERE, 'frame*.svg')))
    svgs = svgs.replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    ok = 0
    for sheet, cell, _ in SPOT:
        f = raw_formula(z, sheet, cell)
        if isinstance(f, tuple):
            text, anchor = f[1]
            (r1, c1), (r2, c2) = extract.rc(anchor), extract.rc(cell)
            f = extract.shift(text, r2 - r1, c2 - c1)
        f = norm(f)
        found = ('=' + f) in svgs
        ok += found
        print(f"  {'OK ' if found else 'MISSING'} {sheet}!{cell}: ={f[:90]}{'...' if len(f) > 90 else ''}")
    print(f'formulas: {ok}/{len(SPOT)} found verbatim on cards')
    return ok == len(SPOT)


if __name__ == '__main__':
    good = check_layout()
    if len(sys.argv) > 1:
        good = check_formulas(sys.argv[1]) and good
    sys.exit(0 if good else 1)
