"""Build the Logic Spec row that sits under the main v2.5 sections.

Input: specs.json, a list of verified specs (one per section 0-9), each with title,
subtitle, a Mermaid flowchart (row subgraphs, see spec_flow.py) and four sections
(inputs, formulas, example, questions). The specs were drafted and adversarially checked
against the workbook.

Output: spec0.svg ... spec9.svg, one frame per section, placed directly below that
section's main frame with the same x and width (widened if the Doc needs it):
  title / subtitle        as in the main row
  flowchart 1600x900      nested in the frame at (64, 240), top-left anchored
  Doc                     784 wide at (1728, 240): the four sections as one Markdown
                          document (spec_doc.py), sized by Miro to its text
The first build used grey panels with a heading and a body textArea each. Miro drew the
multi-line bodies as if they were one line tall, centred on the box, so the text started
halfway down each panel and ran out of it. A Doc is laid out by Miro itself.
Doc heights come from spec_doc_heights.json (the measured heights) when present,
otherwise an estimate; frames are sized to fit.

Send each file with canvas_update_from_svg, which places exactly.
"""
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

from spec_doc import doc_markdown

HERE = os.path.dirname(os.path.abspath(__file__))
PAD, TOP, GAP = 64, 240, 32
DIA_W, DIA_H = 1600, 900
ROW_Y = 2910                      # main row ends at 450 + 2060 (frame 3); 400 px gutter
DOC_X, DOC_W = PAD + DIA_W + PAD, 784
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
    nodes, groups, open_group = {}, set(), None
    for l in lines[1:]:
        t = l.strip()
        assert not t.startswith('classDef'), (n, 'classDef not allowed', t)
        g = re.match(r'^subgraph ([a-z][a-z0-9]*)\["([^"]*)"\]$', t)
        if g:
            assert open_group is None, (n, 'nested subgraph', t)
            assert LABEL_OK.match(g.group(2)) and len(g.group(2)) <= 46, (n, 'bad subgraph title', t)
            open_group = g.group(1)
            groups.add(open_group)
            continue
        if t == 'direction LR':
            assert open_group, (n, 'direction outside a subgraph')
            continue
        if t == 'end':
            assert open_group, (n, 'end without subgraph')
            open_group = None
            continue
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
            refs = re.findall(r'\b([a-z][a-z0-9]*)\b', re.sub(r'"[^"]*"', '', t))
            for ref in refs:
                assert ref in nodes or ref in groups, (n, 'edge to undeclared node', ref, t)
            # a node linked outside its row makes Mermaid ignore the row's direction
            assert all(r in groups for r in refs) or open_group, (n, 'edge outside the rows', t)
            assert not open_group or not any(r in groups for r in refs), (n, 'row edge inside a row', t)
    assert open_group is None, (n, 'unclosed subgraph')
    assert 8 <= len(nodes) <= 22, (n, 'node count', len(nodes))
    return lines


def mermaid_body(src, n):
    lines = check_mermaid(src, n)
    out, depth = [], 1
    for l in lines[1:]:
        t = l.strip()
        if t == 'end':
            depth -= 1
        out.append('    ' * depth + t)
        if t.startswith('subgraph '):
            depth += 1
    body = 'flowchart TD\n' + CLASSDEF + '\n' + '\n'.join(out) + '\n'
    return esc(body).replace('&quot;', '"')          # quotes are fine in element text


def est_doc_h(md):
    """Rough Doc height: about 95 characters a line at 784 px, 26 px lines, headings extra.
    Only used until spec_doc_heights.json holds the measured height."""
    h = 120
    for line in md.splitlines():
        if line.startswith('# '):
            h += 70
        elif line.startswith('## '):
            h += 60
        elif line:
            h += 28 * math.ceil(len(line) / 80)
    return h


def frame_svg(spec, main, doc_h=None):
    n = spec['section']
    fx = main['x']
    width = max(main['w'], DOC_X + DOC_W + PAD)
    md = doc_markdown(spec)
    doc_h = doc_h or est_doc_h(md)
    height = max(TOP + DIA_H, TOP + doc_h + 40) + PAD     # 40: room if the client draws the Doc taller
    title = esc(spec['title'])
    parts = [f'<g id="sf{n}" transform="translate({fx},{ROW_Y})" data-frame="{title}">',
             f'  <rect data-type="frame" x="0" y="0" width="{width}" height="{height}" fill="#ffffff" data-title="{title}"/>',
             # fixed-width text boxes: auto-sized <text> was measured a little narrow and wrapped
             f'  <textArea id="st{n}" x="{PAD}" y="53" width="{width - 2 * PAD}" font-size="67" font-weight="bold" font-family="noto_sans" fill="#1a1a1a">{title}</textArea>',
             f'  <textArea id="ss{n}" x="{PAD}" y="162" width="{width - 2 * PAD}" font-size="22" font-family="noto_sans" fill="#595959">{esc(spec["subtitle"])}</textArea>',
             f'  <foreignObject id="sd{n}" x="{PAD}" y="{TOP}" width="{DIA_W}" height="{DIA_H}" data-type="diagram" data-title="{title}">\n{mermaid_body(spec["mermaid"], n)}</foreignObject>',
             f'  <foreignObject id="doc{n}" x="{DOC_X}" y="{TOP}" width="{DOC_W}" height="{doc_h}" data-type="doc">\n{esc(md).replace("&quot;", chr(34))}</foreignObject>',
             '</g>']
    svg = '<svg xmlns="http://www.w3.org/2000/svg">\n' + '\n'.join(parts) + '\n</svg>\n'
    ET.fromstring(svg)
    assert len(spec['subtitle']) * 13 < width - 2 * PAD, (n, 'subtitle too long')
    assert len(spec['title']) * 42 < width - 2 * PAD, (n, 'title too long')
    return svg, width, height


def main():
    specs = json.load(open(os.path.join(HERE, 'specs.json')))
    mains = {m['frame']: m for m in json.load(open(os.path.join(HERE, 'manifest.json')))}
    hpath = os.path.join(HERE, 'spec_doc_heights.json')
    heights = json.load(open(hpath)) if os.path.exists(hpath) else {}
    out = []
    for spec in sorted(specs, key=lambda s: s['section']):
        n = spec['section']
        svg, w, h = frame_svg(spec, mains[n], heights.get(str(n)))
        open(os.path.join(HERE, f'spec{n}.svg'), 'w').write(svg)
        out.append({'section': n, 'x': mains[n]['x'], 'y': ROW_Y, 'w': w, 'h': h, 'bytes': len(svg)})
        print(out[-1])
    json.dump(out, open(os.path.join(HERE, 'spec_manifest.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
