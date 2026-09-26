"""Markdown for the Logic Spec Doc widget: the four panels of one spec as one document.

Formulas go in code spans so Markdown never reads their * [ ] _ as formatting; other
names that contain an underscore (DSD_DSnD, S_Floor, _BC.xlsm) go in code spans too.
"""
import re

SECTIONS = [('inputs', 'Inputs'), ('formulas', 'Formula reference'),
            ('example', 'Worked example'), ('questions', 'Open questions')]


def code_names(text):
    """Wrap underscore names in backticks, leaving **bold** labels alone."""
    parts = re.split(r'(\*\*.+?\*\*)', text)
    return ''.join(p if p.startswith('**') else
                   re.sub(r'(?<![`\w])([\w.!]*_[\w!#]*(?:\.[\w!#]+)*)', r'`\1`', p) for p in parts)


def split_top(text):
    """Split at spaces outside brackets and quotes."""
    toks, cur, depth, q = [], '', 0, False
    for ch in text:
        if ch == '"':
            q = not q
        elif not q and ch in '([{':
            depth += 1
        elif not q and ch in ')]}':
            depth -= 1
        if ch == ' ' and depth == 0 and not q:
            toks.append(cur)
            cur = ''
        else:
            cur += ch
    toks.append(cur)
    return [t for t in toks if t]


def is_code(tok):
    return (len(tok) > 1 and '=' in tok) or re.search(r'[A-Za-z_]\(|\w\[|^\w+,\w*\(', tok) is not None


def formula_line(item):
    m = re.match(r'^\*\*(.+?)\*\*\s*(.*)$', item)
    label, rest = m.group(1), m.group(2)
    out = []
    for seg in re.split(r'(\*\*.+?\*\*)', rest):
        if seg.startswith('**'):
            out.append(seg)
            continue
        for tok in split_top(seg):
            if tok.startswith('(') and ' ' in tok or not is_code(tok):
                out.append(code_names(tok))
            else:
                core = tok.rstrip('.,;:')
                out.append('`' + core + '`' + tok[len(core):])
    sep = ' ' if out and out[0].startswith('(') else ': '
    return f'- **{label}**{sep}' + ' '.join(out)


def doc_markdown(spec):
    title = spec['title'].replace(': Logic Spec', '')
    lines = [f'# {title}: details', '']
    for key, head in SECTIONS:
        lines += [f'## {head}', '']
        for it in spec[key]:
            lines.append(formula_line(it) if key == 'formulas' else '- ' + code_names(it))
        lines.append('')
    return '\n'.join(lines)


if __name__ == '__main__':
    import json, sys
    for s in json.load(open('specs.json')):
        if str(s['section']) in sys.argv[1:] or len(sys.argv) == 1:
            print(doc_markdown(s))
