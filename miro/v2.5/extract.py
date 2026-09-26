"""Extract representative formulas + cached values from the Master Scheduling workbook.

Reads the .xlsm as a ZIP of XML (stdlib only). For every table column it records the
formula found in a representative data row's CELL (cells are what calculate; stored
table column formulas are recorded separately because several disagree with the cells),
plus a set of named non-table control cells. Output: formulas.json.
"""
import json, re, sys, zipfile
import xml.etree.ElementTree as ET

M = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

# table -> representative data row (a product row, not a header/dough row)
REP_ROW = {'Products': 2, 'Dough': 2, 'UniqueDough': 2, 'Pans': 4, 'SalesOrders': 2,
           'Sunday': 3, 'Monday': 3, 'Tuesday': 3, 'Wednesday': 3, 'Thursday': 3, 'Friday': 3,
           'DSD_DSnD': 8, 'Dist_DSnD': 287, 'DoughWeight': 5, 'Mix_Slice': 7, 'Oven_Info': 411}
EXTRA_ROWS = {'DoughWeight': 4, 'Mix_Slice': 6, 'Oven_Info': 410}  # dough / pan header rows

CELLS = {
    'Sunday': ['A3', 'B1', 'U3'], 'Monday': ['B1', 'D3', 'E3'],
    'Daily Supply & Demand': ['B1', 'H2', 'H3', 'C5', 'DT2', 'W1', 'W2', 'W3', 'W4', 'A8', 'A287',
                              'H283', 'H284', 'H285', 'BI284', 'C287', 'D287', 'E287', 'AW8']
                             + [f'{c}{r}' for r in (1, 2, 3, 4) for c in ('W', 'AD', 'AK', 'AR', 'AY', 'BF')],
    'DoughWeights': ['A4', 'F2'],
    'Mix-Slice-Oven': ['K4', 'O1', 'O2', 'T2', 'BK1', 'Q3', 'R3',
                       'A6', 'A410', 'CA500', 'Y1', 'M7', 'N7', 'N6', 'ZZ7']
                      # rows 1-2: Breadline / MCS LINE planned bags and hours for each day
                      + [f'{c}{r}' for r in (1, 2) for c in ('AD', 'AI', 'AN', 'AS', 'AX', 'BC',
                                                             'BD', 'BE', 'BF', 'BG', 'BH', 'BI')],
    'MCS Schedule': ['A2', 'H2', 'E4', 'A5', 'F5', 'F29', 'N5', 'D4'],
    'Breadline Schedule': ['A2', 'H2', 'E4', 'A5', 'G5', 'N5', 'D4'],
    'Recon': [f'{c}{r}' for r in range(1, 16) for c in 'ABCDEFG'],
    'Dist Shipping Schedule': ['B2', 'C2', 'C3'],
    'Critical Lookup Information': ['V10'],
}

def clean(f):
    if f is None:
        return None
    f = re.sub(r'_xl(fn|pm|ws)\.', '', f)
    return re.sub(r'(\w+)\[\[#This Row\],\[([^\]]+)\]\]', r'[@\2]', f)   # Table[[#This Row],[Col]] -> [@Col]

def col2n(c):
    n = 0
    for ch in c:
        n = n * 26 + ord(ch) - 64
    return n

def n2col(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def shift(f, dr, dc):
    """Re-anchor a shared formula's A1 references from the master cell to a child cell.
    Skips string literals, quoted sheet names and structured-reference brackets."""
    if not f or (dr == 0 and dc == 0):
        return f
    out, i = [], 0
    for m in re.finditer(r'"[^"]*"|\'[^\']*\'|\[[^\]]*\]|[^"\'\[]+', f):
        seg = m.group(0)
        if seg[0] in '"\'[':
            out.append(seg)
            continue
        def rep(r):
            c = r.group(2) if r.group(1) else n2col(col2n(r.group(2)) + dc)
            n = r.group(4) if r.group(3) else str(int(r.group(4)) + dr)
            return f"{r.group(1)}{c}{r.group(3)}{n}"
        out.append(re.sub(r"(?<![A-Za-z0-9_.])(\$?)([A-Z]{1,3})(\$?)(\d+)(?![A-Za-z0-9_(])", rep, seg))
    return ''.join(out)

def rc(ref):
    m = re.match(r'([A-Z]+)(\d+)', ref)
    return int(m.group(2)), col2n(m.group(1))

def main(path):
    z = zipfile.ZipFile(path)
    ss = [''.join(t.text or '' for t in si.iter(M + 't'))
          for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall(M + 'si')]
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = {r.get('Id'): r.get('Target') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    sheet_file, table_sheet = {}, {}
    for s in wb.find(M + 'sheets'):
        p = 'xl/' + rels[s.get(R + 'id')]
        sheet_file[s.get('name')] = p
        rp = p.replace('worksheets/', 'worksheets/_rels/') + '.rels'
        if rp in z.namelist():
            for r in ET.fromstring(z.read(rp)):
                if 'table' in r.get('Type'):
                    table_sheet[r.get('Target').split('/')[-1]] = s.get('name')
    tables = {}
    for n in z.namelist():
        if n.startswith('xl/tables/table'):
            t = ET.fromstring(z.read(n))
            m = re.match(r'([A-Z]+)(\d+):([A-Z]+)(\d+)', t.get('ref'))
            cols = []
            for i, c in enumerate(t.find(M + 'tableColumns')):
                cf = c.find(M + 'calculatedColumnFormula')
                cols.append({'name': c.get('name'), 'col': n2col(col2n(m.group(1)) + i),
                             'stored': clean(cf.text) if cf is not None else None})
            tables[t.get('name')] = {'sheet': table_sheet[n.split('/')[-1]], 'ref': t.get('ref'),
                                     'rows': int(m.group(4)) - int(m.group(2)), 'cols': cols}
    # which cells to read, per sheet
    want = {}
    for tn, row in REP_ROW.items():
        tb = tables[tn]
        for c in tb['cols']:
            want.setdefault(tb['sheet'], set()).add(f"{c['col']}{row}")
            if tn in EXTRA_ROWS:
                want[tb['sheet']].add(f"{c['col']}{EXTRA_ROWS[tn]}")
    for sh, cells in CELLS.items():
        want.setdefault(sh, set()).update(cells)
    got, masters = {}, {}
    for sh, cells in want.items():
        path_ = sheet_file[sh]
        for ev, el in ET.iterparse(z.open(path_)):
            if el.tag != M + 'c':
                continue
            f = el.find(M + 'f')
            if f is not None and f.get('t') == 'shared' and f.text:
                masters[(sh, f.get('si'))] = (f.text, el.get('r'))
            r = el.get('r')
            if r in cells:
                v = el.find(M + 'v')
                val = None if v is None else (ss[int(v.text)] if el.get('t') == 's' else v.text)
                ftxt = None
                if f is not None:
                    ftxt = f.text if f.text else ('@shared:' + f.get('si', '?'))
                got[f'{sh}!{r}'] = [ftxt, val]
            el.clear()
    for k, (ftxt, val) in got.items():
        if ftxt and ftxt.startswith('@shared:'):
            mt = masters.get((k.split('!')[0], ftxt.split(':')[1]))
            if mt:
                (r1, c1), (r2, c2) = rc(mt[1]), rc(k.split('!')[1])
                got[k][0] = shift(mt[0], r2 - r1, c2 - c1)
            else:
                got[k][0] = None
        got[k][0] = clean(got[k][0])
    for tn, tb in tables.items():
        for c in tb['cols']:
            for tag, row in (('cell', REP_ROW.get(tn)), ('header_row_cell', EXTRA_ROWS.get(tn))):
                if row:
                    c[tag] = got.get(f"{tb['sheet']}!{c['col']}{row}")
    out = {'tables': tables, 'cells': {k: v for k, v in got.items()
                                       if any(k == f'{s}!{c}' for s, cs in CELLS.items() for c in cs)}}
    json.dump(out, open(sys.argv[2], 'w'), indent=1)
    print(f"tables: {len(tables)} | cells: {len(out['cells'])} -> {sys.argv[2]}")

if __name__ == '__main__':
    main(sys.argv[1])
