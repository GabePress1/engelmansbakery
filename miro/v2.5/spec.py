"""Build the Logic Spec row that sits under the main v2.5 sections.

Input: specs.json, a list of verified specs (one per section 0-8), each with title,
subtitle, a Mermaid `flowchart TD` body, and four panels (inputs, formulas, example,
questions). The specs were drafted and adversarially checked against the workbook.

Output: spec0.svg ... spec8.svg, one frame per section, placed directly below that
section's main frame with the same x and width:
  title / subtitle        as in the main row
  flowchart 1600x900      nested in the frame at (64, 240), top-left anchored
  panels                  right of the flowchart, 1-3 columns depending on frame width,
                          each a soft grey rect with a heading and a body text block
Panel heights are estimated here; after creation the measured text heights can be fed
back with --measured to re-flow the panels (see relayout()).

Send each file with canvas_update_from_svg, which places exactly.
"""
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
PAD, TOP, GAP = 64, 240, 32
DIA_W, DIA_H = 1600, 900
ROW_Y = 2910                      # main row ends at 450 + 2060 (frame 3); 400 px gutter
HEAD_FS, BODY_FS = 26, 18
HEAD_H = 37
CHAR_W = 10.6                     # noto_sans 18 px, measured about 0.58 em per character
LINE_H = 26
PANELS = [('inputs', 'Inputs'), ('formulas', 'Formula reference'),
          ('example', 'Worked example'), ('questions', 'Open questions')]

CLASSDEF = """    classDef terminator fill:#FFFFFF,stroke:#757575,color:#313131
    classDef input fill:#B3E65F,stroke:#6E9A24,color:#2F440B
    classDef export fill:#B8ACFB,stroke:#8A7BE0,color:#231266
    classDef calc fill:#9CE6FF,stroke:#2C97BB,color:#1C4657
    classDef decision fill:#9CE6FF,stroke:#2C97BB,color:#1C4657
    classDef lookup fill:#FFB575,stroke:#CC7830,color:#542700
    classDef output fill:#DDDDD8,stroke:#8A8A7E,color:#434339
    classDef issue fill:#FFC6C6,stroke:#BD0A0A,color:#5C0A0A
"""
CLASSES = {'terminator', 'input', 'export', 'calc', 'decision', 'lookup', 'output', 'issue'}
LABEL_OK = re.compile(r"^[A-Za-z0-9 .,:()+\-*/='_%?\[\]$!]*$")


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def check_mermaid(src, n):
    """Validate against the rules the spec writers were given; return the body lines."""
    lines = [l.rstrip() for l in src.strip().splitlines() if l.strip()]
    assert lines[0].strip() == 'flowchart TD', (n, 'first line')
    nodes = {}
    for l in lines[1:]:
        t = l.strip()
        assert not t.startswith('classDef'), (n, 'classDef not allowed', t)
        for lab in re.findall(r'"([^"]*)"', t):
            for part in lab.split('<br/>'):
                assert LABEL_OK.match(part), (n, 'bad label characters', lab)
                assert len(part) <= 46, (n, 'label line too long', part)
            assert lab.count('<br/>') <= 2, (n, 'more than 3 lines', lab)
        m = re.match(r'^([a-z][a-z0-9]*)\s*(\(\[|\[/|\[|\{\{)"', t)
        if m and '-->' not in t and '-.->' not in t:
            cls = re.search(r':::(\w+)\s*$', t)
            assert cls and cls.group(1) in CLASSES, (n, 'node without a valid class', t)
            nodes[m.group(1)] = cls.group(1)
        else:
            assert re.match(r'^[a-z][a-z0-9]*\s*(-->|-\.->)(\|"[^"]*"\|)?\s*[a-z][a-z0-9]*$', t), (n, 'bad edge', t)
            for ref in re.findall(r'\b([a-z][a-z0-9]*)\b', re.sub(r'"[^"]*"', '', t)):
                assert ref in nodes, (n, 'edge to undeclared node', ref, t)
    assert 8 <= len(nodes) <= 22, (n, 'node count', len(nodes))
    return lines


def mermaid_body(src, n):
    lines = check_mermaid(src, n)
    body = 'flowchart TD\n' + CLASSDEF + '\n' + '\n'.join('    ' + l.strip() for l in lines[1:]) + '\n'
    return esc(body).replace('&quot;', '"')          # quotes are fine in element text


def body_markup(items):
    out = []
    for it in items:
        t = esc(it).replace('&quot;', '"')
        t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
        out.append(t)
    return '<br/><br/>'.join(out)


def est_body_h(items, width):
    cpl = max(10, int((width - 8) / CHAR_W))
    lines = sum(math.ceil(len(re.sub(r'\*\*', '', it)) / cpl) for it in items) + (len(items) - 1)
    return lines * LINE_H + 8


def columns_for(width):
    avail = width - (PAD + DIA_W + PAD) - PAD
    ncol = max(1, min(3, (avail + GAP) // (560 + GAP)))
    colw = (avail - (ncol - 1) * GAP) // ncol
    return [PAD + DIA_W + PAD + i * (colw + GAP) for i in range(ncol)], colw


def layout(spec, width, measured=None):
    """Panel boxes, frame-relative. measured: {panel key: body height} overrides estimates."""
    xs, colw = columns_for(width)
    tops = [TOP] * len(xs)
    boxes = []
    for key, head in PANELS:
        items = spec[key]
        bh = (measured or {}).get(key) or est_body_h(items, colw - 2 * GAP)
        h = GAP + HEAD_H + 16 + bh + GAP
        c = min(range(len(xs)), key=lambda i: tops[i])
        boxes.append({'key': key, 'head': head, 'x': xs[c], 'y': tops[c], 'w': colw, 'h': h, 'bh': bh})
        tops[c] += h + GAP
    height = max(TOP + DIA_H, max(tops) - GAP) + PAD
    return boxes, height


def frame_svg(spec, main, measured=None):
    n = spec['section']
    fx, width = main['x'], main['w']
    boxes, height = layout(spec, width, measured)
    title = esc(spec['title'])
    parts = [f'<g id="sf{n}" transform="translate({fx},{ROW_Y})" data-frame="{title}">',
             f'  <rect data-type="frame" x="0" y="0" width="{width}" height="{height}" fill="#ffffff" data-title="{title}"/>',
             # fixed-width text boxes: auto-sized <text> was measured a little narrow and wrapped
             f'  <textArea id="st{n}" x="{PAD}" y="53" width="{width - 2 * PAD}" font-size="67" font-weight="bold" font-family="noto_sans" fill="#1a1a1a">{title}</textArea>',
             f'  <textArea id="ss{n}" x="{PAD}" y="162" width="{width - 2 * PAD}" font-size="22" font-family="noto_sans" fill="#595959">{esc(spec["subtitle"])}</textArea>']
    for i, b in enumerate(boxes):
        parts.append(f'  <rect id="sp{n}_{i}" x="{b["x"]}" y="{b["y"]}" width="{b["w"]}" height="{b["h"]}" rx="12" fill="#f7f7f7" stroke="#e7e7e7"/>')
        parts.append(f'  <textArea id="sh{n}_{i}" x="{b["x"] + GAP}" y="{b["y"] + GAP}" width="{b["w"] - 2 * GAP}" font-size="{HEAD_FS}" font-weight="bold" font-family="noto_sans" fill="#1a1a1a">{b["head"]}</textArea>')
        parts.append(f'  <textArea id="sb{n}_{i}" x="{b["x"] + GAP}" y="{b["y"] + GAP + HEAD_H + 16}" width="{b["w"] - 2 * GAP}" font-size="{BODY_FS}" font-family="noto_sans" fill="#313131">{body_markup(spec[b["key"]])}</textArea>')
    parts.append(f'  <foreignObject id="sd{n}" x="{PAD}" y="{TOP}" width="{DIA_W}" height="{DIA_H}" data-type="diagram" data-title="{title}">\n{mermaid_body(spec["mermaid"], n)}</foreignObject>')
    parts.append('</g>')
    svg = '<svg xmlns="http://www.w3.org/2000/svg">\n' + '\n'.join(parts) + '\n</svg>\n'
    ET.fromstring(svg)
    assert len(spec['subtitle']) * 13 < width - 2 * PAD, (n, 'subtitle too long')
    assert len(spec['title']) * 42 < width - 2 * PAD, (n, 'title too long')
    return svg, height


def main():
    specs = json.load(open(os.path.join(HERE, 'specs.json')))
    mains = {m['frame']: m for m in json.load(open(os.path.join(HERE, 'manifest.json')))}
    measured = {}
    if '--measured' in sys.argv:
        measured = json.load(open(os.path.join(HERE, 'spec_measured.json')))
    out = []
    for spec in sorted(specs, key=lambda s: s['section']):
        n = spec['section']
        svg, h = frame_svg(spec, mains[n], measured.get(str(n)))
        open(os.path.join(HERE, f'spec{n}.svg'), 'w').write(svg)
        out.append({'section': n, 'x': mains[n]['x'], 'y': ROW_Y, 'w': mains[n]['w'], 'h': h, 'bytes': len(svg)})
        print(out[-1])
    json.dump(out, open(os.path.join(HERE, 'spec_manifest.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
