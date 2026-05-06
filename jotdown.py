#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import html as _html
import re
import argparse
import sys


@dataclass
class THeader:
    level: int
    text: str
    anchor: Optional[str] = None

@dataclass
class TOlItem:
    number: int
    text: str

@dataclass
class TUlItem:
    text: str

@dataclass
class TUlItemAny:
    text: str

@dataclass
class TRomanItem:
    value: int
    text: str
    upper: bool

@dataclass
class TBlockOpen:
    kind: str

@dataclass
class TBlockClose:
    pass

@dataclass
class TParaLine:
    text: str

@dataclass
class TParaBreak:
    pass

@dataclass
class TRawContent:
    raw: str
    kind: str

@dataclass
class TForcedPara:
    raw: str

@dataclass
class TTableRow:
    cells: list
    is_header: bool
    aligns: list = None

@dataclass
class IText:
    content: str

@dataclass
class IInlineCode:
    content: str
    language: str = "raw"

@dataclass
class ILink:
    text_tokens: list
    url: str

@dataclass
class IImage:
    src: str
    url: str
    default: str = "image"

@dataclass
class IFormatOpen:
    bold: bool = False
    em_italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    subscript: bool = False
    superscript: bool = False
    subsup: bool = False
    sym: bool = False
    idio_italic: bool = False

@dataclass
class IFormatClose:
    pass

@dataclass
class ISymbol:
    content: str

@dataclass
class THrLine:
    pass


_ROMAN_VALUES = [
    (1000,'m'),(900,'cm'),(500,'d'),(400,'cd'),
    (100,'c'),(90,'xc'),(50,'l'),(40,'xl'),
    (10,'x'),(9,'ix'),(5,'v'),(4,'iv'),(1,'i'),
]

def _to_roman(n, upper=False):
    result = ''
    for val, sym in _ROMAN_VALUES:
        while n >= val:
            result += sym
            n -= val
    return result.upper() if upper else result

def _from_roman(s):
    s = s.lower()
    val = 0
    two = {}
    pairs = [('cm',900),('cd',400),('xc',90),('xl',40),('ix',9),('iv',4)]
    for p,pv in pairs:
        two[p] = pv
    singles = {'m':1000,'d':500,'c':100,'l':50,'x':10,'v':5,'i':1}
    i = 0
    while i < len(s):
        if i+1 < len(s) and s[i:i+2] in two:
            val += two[s[i:i+2]]
            i += 2
        elif s[i] in singles:
            val += singles[s[i]]
            i += 1
        else:
            return None
    return val if val > 0 else None

_ROMAN_RE = re.compile(r'^([ivxlcdmIVXLCDM]+)\.\s*')

def _match_roman(rest):
    m = _ROMAN_RE.match(rest)
    if not m:
        return None, None
    s = m.group(1)
    upper = s == s.upper()
    val = _from_roman(s)
    if val is None:
        return None, None
    return m, upper


class _InlineLexer:
    def __init__(self, text):
        self._s = text
        self._pos = 0

    def lex(self):
        tokens = []
        while self._pos < len(self._s):
            ch = self._ch()
            if ch == '\\':
                self._pos += 1
                nxt = self._ch()
                if nxt is not None:
                    tokens.append(IText(content=nxt))
                    self._pos += 1
            elif ch == '`':
                tokens.append(self._lex_code())
            elif ch == '[':
                tokens.append(self._lex_link())
            elif ch == '(' and self._pos + 1 < len(self._s) and self._s[self._pos + 1] in '*_-^%.':
                tokens.extend(self._lex_format())
            else:
                tokens.append(self._lex_text())
        return tokens

    def _lex_code(self):
        self._pos += 1
        language = ''
        if self._ch() == '\\' and self._pos + 1 < len(self._s) and self._s[self._pos + 1] == '<':
            self._pos += 1
        elif self._ch() == '<':
            self._pos += 1
            while self._pos < len(self._s) and self._s[self._pos] != '>':
                language += self._s[self._pos]
                self._pos += 1
            if self._ch() == '>': self._pos += 1
            if self._ch() == ' ': self._pos += 1
        code = ''
        while self._pos < len(self._s) and self._s[self._pos] != '`':
            if self._s[self._pos] == '\\' and self._pos + 1 < len(self._s) and self._s[self._pos + 1] == '`':
                code += '`'
                self._pos += 2
            elif self._s[self._pos] == '\\' and self._pos + 1 < len(self._s) and self._s[self._pos + 1] == '\\':
                code += '\\'
                self._pos += 2
            else:
                code += self._s[self._pos]
                self._pos += 1
        if self._ch() == '`': self._pos += 1
        if code.startswith('\n'): code = code[1:]
        if code.endswith('\n'): code = code[:-1]
        return IInlineCode(content=code, language=language)

    def _lex_link(self):
        self._pos += 1
        is_image = False
        if self._ch() == '!':
            self._pos += 1
            is_image = True
            if self._s[self._pos:self._pos+3] == 'img':
                self._pos += 3
                if self._ch() == ' ': self._pos += 1
        inner = ''
        while self._pos < len(self._s) and self._s[self._pos] != ']':
            inner += self._s[self._pos]
            self._pos += 1
        if self._ch() == ']': self._pos += 1
        if self._ch() != '(':
            return IText(content=('[!img ' if is_image else '[') + inner + ']')
        self._pos += 1
        url = ''
        while self._pos < len(self._s) and self._s[self._pos] != ')':
            url += self._s[self._pos]
            self._pos += 1
        if self._ch() == ')': self._pos += 1
        if is_image:
            default = "image"
            if "??" in inner:
                inner, default = inner.split("??", 1)
            return IImage(src=inner, url=url, default=default)
        return ILink(text_tokens=_InlineLexer(inner).lex(), url=url)

    def _lex_format(self):
        self._pos += 1
        bold = em_italic = underline = strikethrough = False
        subscript = superscript = subsup = sym = idio_italic = False
        while self._pos < len(self._s) and self._s[self._pos] in '*_-^%.':
            m = self._s[self._pos]
            if m == '*':
                if not bold:        bold = True
                elif not em_italic: bold = False; em_italic = True
                else:               bold = True
            elif m == '_':
                if not underline:   underline = True
                elif not subscript: underline = False; subscript = True
                else:               underline = True
            elif m == '.':
                if not sym:         sym = True
                elif not idio_italic: sym = False; idio_italic = True
                else:               sym = True
            elif m == '-': strikethrough = True
            elif m == '^': superscript = True
            elif m == '%': subsup = True
            self._pos += 1
        fmt = IFormatOpen(bold=bold, em_italic=em_italic, underline=underline,
            strikethrough=strikethrough, subscript=subscript, superscript=superscript,
            subsup=subsup, sym=sym, idio_italic=idio_italic)
        content = self._read_balanced(')')
        if sym:
            symbol = ISymbol(content='<br>' if content == 'br' else f'&{content};')
            return [fmt, symbol, IFormatClose()]
        return [fmt] + _InlineLexer(content).lex() + [IFormatClose()]

    def _lex_text(self):
        buf = ''
        while self._pos < len(self._s):
            ch = self._s[self._pos]
            if ch in '\\`[': break
            if ch == '(' and self._pos + 1 < len(self._s) and self._s[self._pos + 1] in '*_-^%.': break
            buf += ch
            self._pos += 1
        return IText(content=buf)

    def _ch(self):
        return self._s[self._pos] if self._pos < len(self._s) else None

    def _read_balanced(self, close):
        depth = 1
        buf = []
        while self._pos < len(self._s) and depth > 0:
            ch = self._s[self._pos]
            if ch == '(':   depth += 1; buf.append(ch)
            elif ch == close:
                depth -= 1
                if depth > 0: buf.append(ch)
            else: buf.append(ch)
            self._pos += 1
        return ''.join(buf)


def _line_starts_block(rest):
    return (
        rest.startswith('#')
        or rest.startswith('![')
        or rest.startswith('!style[')
        or rest.startswith('!html[')
        or rest.startswith('!p[')
        or rest.startswith('!![')
        or rest.startswith('..')
        or rest.startswith('.i ')
        or rest.startswith('.i\n')
        or rest.startswith('.I ')
        or rest.startswith('.I\n')
        or rest.startswith(',,')
        or rest.startswith(': ')
        or rest.startswith(';\n')
        or rest.startswith('; ')
        or bool(re.match(r'\d+\.', rest))
        or bool(_ROMAN_RE.match(rest) and _from_roman(_ROMAN_RE.match(rest).group(1)) is not None)
    )

def _skip_backtick_spans(line):
    if line.startswith('`'):
        return ''
    return line


_ALIGN_CHARS = {'^': 'center', '>': 'right', '<': 'left'}

def _parse_table_cells(line):
    raw_cells = []
    buf = []
    i = 0
    while i < len(line):
        if line[i] == '\\' and i + 1 < len(line) and line[i + 1] == '|':
            buf.append('|')
            i += 2
        elif line[i] == '|':
            raw_cells.append(''.join(buf))
            buf = []
            i += 1
        else:
            buf.append(line[i])
            i += 1
    raw_cells.append(''.join(buf))

    cells = []
    aligns = []
    for raw in raw_cells:
        stripped = raw.strip()
        align = None
        if len(stripped) >= 2 and stripped[-2] == '\\' and stripped[-1] in _ALIGN_CHARS:
            stripped = stripped[:-2] + stripped[-1]
        elif stripped and stripped[-1] in _ALIGN_CHARS:
            align = _ALIGN_CHARS[stripped[-1]]
            stripped = stripped[:-1].rstrip()
        cells.append(stripped)
        aligns.append(align)
    return cells, aligns


class JotdownLexer:
    def __init__(self, source):
        self._src = source
        self._pos = 0

    def lex(self):
        tokens = []
        self._skip_blank()
        while self._pos < len(self._src):
            result = self._lex_block()
            if result is None:
                self._pos += 1
            elif isinstance(result, list):
                tokens.extend(result)
            else:
                tokens.append(result)
            self._skip_blank()
        return tokens

    @staticmethod
    def lex_inline(text):
        return _InlineLexer(text).lex()

    def _lex_block(self):
        rest = self._rest()
        if rest.startswith('#'):             return self._lex_header()
        if rest.startswith('!['):            return self._lex_nested_block('separator')
        if rest.startswith('!style['):       return self._lex_raw_block('style')
        if rest.startswith('!html['):        return self._lex_raw_block('html')
        if rest.startswith('!p['):           return self._lex_forced_para()
        if rest.startswith('!!['):           return self._lex_nested_block('hard-separator')
        if rest.startswith('..'):            return self._lex_uln_run()
        if rest.startswith('.i ') or rest.startswith('.i\n'): return self._lex_roman_run(upper=False)
        if rest.startswith('.I ') or rest.startswith('.I\n'): return self._lex_roman_run(upper=True)
        if rest.startswith(',,'):            return self._lex_ul_run()
        if rest.startswith('---'):           return self._lex_hr()
        if rest.startswith(': ') or rest.startswith(';\n') or rest.startswith('; '):
            return self._lex_table_run()
        if re.match(r'\d+\.', rest):         return self._lex_ol_run()
        m, upper = _match_roman(rest)
        if m:                                return self._lex_roman_ol_run(upper)
        return self._lex_paragraph()

    def _lex_hr(self):
        self._pos += 3
        self._skip_blank()
        return [THrLine()]

    def _lex_header(self):
        level = 0
        while self._ch() == '#': level += 1; self._pos += 1
        while self._ch() == ' ': self._pos += 1
        anchor = None
        if self._ch() == '<':
            self._pos += 1
            anchor = self._read_until('>')
            if self._ch() == '>': self._pos += 1
            while self._ch() == ' ': self._pos += 1
        return THeader(level=level, text=self._consume_line().strip(), anchor=anchor)

    def _lex_table_run(self):
        tokens = []
        first = True
        col_aligns = None
        while self._pos < len(self._src):
            rest = self._rest()
            if rest.startswith(': '):
                self._pos += 2
                line = self._consume_line()
                cells, aligns = _parse_table_cells(line)
                is_header = first
                if is_header:
                    col_aligns = aligns
                    tokens.append(TTableRow(cells=cells, is_header=True, aligns=aligns))
                else:
                    tokens.append(TTableRow(cells=cells, is_header=False, aligns=col_aligns))
                first = False
            elif rest.startswith('; ') or rest.startswith(';\n'):
                self._pos += 2
                line = self._consume_line()
                cells, aligns = _parse_table_cells(line)
                tokens.append(TTableRow(cells=cells, is_header=False, aligns=col_aligns))
                first = False
            else:
                break
            self._skip_blank_lines()
        return tokens

    def _lex_ol_run(self):
        tokens = []
        while self._pos < len(self._src):
            m = re.match(r'(\d+)\.\s*', self._rest())
            if not m: break
            number = int(m.group(1))
            self._pos += len(m.group(0))
            tokens.append(TOlItem(number=number, text=self._consume_line()))
            self._skip_blank_lines()
            tokens.extend(self._lex_interleaved_para(lambda r: bool(re.match(r'\d+\.', r))))
        return tokens

    def _lex_roman_ol_run(self, upper):
        tokens = []
        while self._pos < len(self._src):
            m, u = _match_roman(self._rest())
            if not m or u != upper: break
            val = _from_roman(m.group(1))
            self._pos += len(m.group(0))
            tokens.append(TRomanItem(value=val, text=self._consume_line(), upper=upper))
            self._skip_blank_lines()
            tokens.extend(self._lex_interleaved_para(
                lambda r, up=upper: bool(_match_roman(r)[0]) and _match_roman(r)[1] == up
            ))
        return tokens

    def _lex_uln_run(self):
        tokens = []
        while self._pos < len(self._src) and self._rest().startswith('..'):
            self._pos += 2
            while self._ch() == ' ': self._pos += 1
            tokens.append(TUlItem(text=self._consume_line()))
            self._skip_blank_lines()
            tokens.extend(self._lex_interleaved_para(lambda r: r.startswith('..')))
        return tokens

    def _lex_roman_run(self, upper):
        prefix = '.I' if upper else '.i'
        tokens = []
        while self._pos < len(self._src):
            rest = self._rest()
            if not (rest.startswith(prefix + ' ') or rest.startswith(prefix + '\n')): break
            self._pos += 2
            while self._ch() == ' ': self._pos += 1
            tokens.append(TRomanItem(value=None, text=self._consume_line(), upper=upper))
            self._skip_blank_lines()
            tokens.extend(self._lex_interleaved_para(
                lambda r, p=prefix: r.startswith(p + ' ') or r.startswith(p + '\n')
            ))
        return tokens

    def _lex_ul_run(self):
        tokens = []
        while self._pos < len(self._src) and self._rest().startswith(',,'):
            self._pos += 2
            while self._ch() == ' ': self._pos += 1
            tokens.append(TUlItemAny(text=self._consume_line()))
            self._skip_blank_lines()
            tokens.extend(self._lex_interleaved_para(lambda r: r.startswith(',,')))
        return tokens

    def _lex_interleaved_para(self, is_same_list):
        saved = self._pos
        tokens = []
        inside_backtick = False
        while self._pos < len(self._src):
            rest = self._rest()
            if not inside_backtick and is_same_list(rest):
                break
            if not inside_backtick:
                logical = _skip_backtick_spans(rest)
                if logical and _line_starts_block(logical):
                    if logical.startswith('!p['):
                        tokens.append(self._lex_forced_para())
                        saved = self._pos
                        self._skip_blank_lines()
                        continue
                    self._pos = saved
                    return []
            line = self._consume_line()
            if not inside_backtick and not line.strip():
                tokens.append(TParaBreak())
                self._skip_blank_lines()
                rest2 = self._rest()
                if is_same_list(rest2):
                    break
                logical2 = _skip_backtick_spans(rest2)
                if logical2 and _line_starts_block(logical2):
                    if not logical2.startswith('!p['):
                        break
                continue
            tokens.append(TParaLine(text=line))
            saved = self._pos
            i = 0
            while i < len(line):
                if line[i] == '\\' and i + 1 < len(line) and line[i + 1] == '`':
                    i += 2
                elif line[i] == '`':
                    inside_backtick = not inside_backtick
                    i += 1
                else:
                    i += 1
        return tokens

    def _lex_nested_block(self, kind):
        self._pos += {'separator': 2, 'style': 7, 'html': 6, 'hard-separator': 3}[kind]
        raw = self._read_balanced(']')
        inner = JotdownLexer(raw).lex()
        return [TBlockOpen(kind=kind)] + inner + [TBlockClose()]

    def _lex_raw_block(self, kind):
        self._pos += {'style': 7, 'html': 6}[kind]
        return TRawContent(raw=self._read_balanced(']'), kind=kind)

    def _lex_forced_para(self):
        self._pos += 3
        return TForcedPara(raw=self._read_balanced(']'))

    def _lex_paragraph(self):
        tokens = []
        inside_backtick = False
        while self._pos < len(self._src):
            rest = self._rest()
            if not inside_backtick:
                logical_start = _skip_backtick_spans(rest)
                if logical_start and _line_starts_block(logical_start):
                    break
            line = self._consume_line()
            if not inside_backtick and not line.strip():
                tokens.append(TParaBreak())
                break
            tokens.append(TParaLine(text=line))
            i = 0
            while i < len(line):
                if line[i] == '\\' and i + 1 < len(line) and line[i + 1] == '`':
                    i += 2
                elif line[i] == '`':
                    inside_backtick = not inside_backtick
                    i += 1
                else:
                    i += 1
        return tokens

    def _ch(self):
        return self._src[self._pos] if self._pos < len(self._src) else None

    def _rest(self):
        return self._src[self._pos:]

    def _consume_line(self):
        start = self._pos
        while self._pos < len(self._src) and self._src[self._pos] != '\n':
            self._pos += 1
        result = self._src[start:self._pos]
        if self._pos < len(self._src): self._pos += 1
        return result

    def _read_until(self, stop):
        start = self._pos
        while self._pos < len(self._src) and self._src[self._pos] != stop:
            self._pos += 1
        return self._src[start:self._pos]

    def _read_balanced(self, close):
        open_ch = '[' if close == ']' else '('
        depth = 1
        buf = []
        while self._pos < len(self._src) and depth > 0:
            ch = self._src[self._pos]
            if ch == open_ch:   depth += 1; buf.append(ch)
            elif ch == close:
                depth -= 1
                if depth > 0: buf.append(ch)
            else: buf.append(ch)
            self._pos += 1
        return ''.join(buf)

    def _skip_blank_lines(self):
        while self._pos < len(self._src):
            start = self._pos
            while self._pos < len(self._src) and self._src[self._pos] == ' ':
                self._pos += 1
            if self._pos < len(self._src) and self._src[self._pos] == '\n':
                self._pos += 1
            else:
                self._pos = start
                break

    def _skip_blank(self):
        ...


class JotdownHTMLCompiler:
    styles = """\
<style>
.table-row-0-center {
    padding: 0.20em 0.40em;
    border:1px solid #ccc;
    text-align: center;
}

.table-row-1-center {
    padding: 0.20em 0.40em;
    border:1px solid #ccc;
    background: #f0f0f0;
    text-align: center;
}

.table-row-0-left {
    padding: 0.20em 0.40em;
    border:1px solid #ccc;
    text-align: left;
}

.table-row-1-left {
    padding: 0.20em 0.40em;
    border:1px solid #ccc;
    background: #f0f0f0;
    text-align: left;
}

.table-row-0-right {
    padding: 0.20em 0.40em;
    border:1px solid #ccc;
    text-align: right;
}

.table-row-1-right {
    padding: 0.20em 0.40em;
    border:1px solid #ccc;
    background: #f0f0f0;
    text-align: right;
}
</style>
"""
    def compile(self, tokens, *, standalone=True):
        body = '\n'.join(self._compile_blocks(tokens))
        if standalone:
            return '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n' + JotdownHTMLCompiler.styles + "\n" + body
        return body

    def _compile_blocks(self, tokens):
        out = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]

            if isinstance(tok, THeader):
                out.append(self._render_header(tok)); i += 1

            elif isinstance(tok, TOlItem):
                inner = []
                while i < len(tokens) and isinstance(tokens[i], (TOlItem, TParaLine, TParaBreak, TForcedPara)):
                    inner.append(tokens[i]); i += 1
                out.append(self._render_ol(inner))

            elif isinstance(tok, TRomanItem):
                inner = []
                upper = tok.upper
                while i < len(tokens) and isinstance(tokens[i], (TRomanItem, TParaLine, TParaBreak, TForcedPara)):
                    if isinstance(tokens[i], TRomanItem) and tokens[i].upper != upper: break
                    inner.append(tokens[i]); i += 1
                out.append(self._render_roman(inner, upper))

            elif isinstance(tok, TUlItem):
                inner = []
                while i < len(tokens) and isinstance(tokens[i], (TUlItem, TParaLine, TParaBreak, TForcedPara)):
                    inner.append(tokens[i]); i += 1
                out.append(self._render_uln(inner))

            elif isinstance(tok, TUlItemAny):
                inner = []
                while i < len(tokens) and isinstance(tokens[i], (TUlItemAny, TParaLine, TParaBreak, TForcedPara)):
                    inner.append(tokens[i]); i += 1
                out.append(self._render_ul(inner))

            elif isinstance(tok, TTableRow):
                inner = []
                while i < len(tokens) and isinstance(tokens[i], TTableRow):
                    inner.append(tokens[i]); i += 1
                out.append(self._render_table(inner))

            elif isinstance(tok, TParaLine):
                lines = []
                while i < len(tokens) and isinstance(tokens[i], (TParaLine, TParaBreak)):
                    if isinstance(tokens[i], TParaBreak): i += 1; break
                    lines.append(tokens[i].text); i += 1
                out.append(self._render_para(lines))

            elif isinstance(tok, TBlockOpen) and tok.kind == 'separator':
                i += 1
                inner, depth = [], 1
                while i < len(tokens) and depth > 0:
                    if isinstance(tokens[i], TBlockOpen): depth += 1
                    elif isinstance(tokens[i], TBlockClose):
                        depth -= 1
                        if depth == 0: i += 1; break
                    inner.append(tokens[i]); i += 1
                inner_html = self.compile(inner, standalone=False)
                out.append(
                    f'<div class="separator-block" style="font-size:0.90em;display:block;'
                    f'width:auto;padding-left:1.5rem;">{inner_html}</div>'
                )

            elif isinstance(tok, TBlockOpen) and tok.kind == 'hard-separator':
                i += 1
                inner, depth = [], 1
                while i < len(tokens) and depth > 0:
                    if isinstance(tokens[i], TBlockOpen): depth += 1
                    elif isinstance(tokens[i], TBlockClose):
                        depth -= 1
                        if depth == 0: i += 1; break
                    inner.append(tokens[i]); i += 1
                inner_html = self.compile(inner, standalone=False)
                out.append(f"<div class=\"hard-separator-block\">\n{inner_html}\n</div>")

            elif isinstance(tok, THrLine):
                out.append('<hr>'); i += 1

            elif isinstance(tok, TRawContent):
                if tok.kind == 'style':
                    out.append(f'<style>\n{tok.raw}\n</style>')
                else:
                    out.append(tok.raw)
                i += 1

            elif isinstance(tok, TForcedPara):
                out.append(self._render_forced_para(tok)); i += 1

            else:
                i += 1

        return out

    def _render_header(self, tok):
        tag = f'h{tok.level}'
        content = self._render_inline(JotdownLexer.lex_inline(tok.text))
        if tok.anchor:
            return f'<{tag} id="{_esc(tok.anchor)}">{content}</{tag}>'
        return f'<{tag}>{content}</{tag}>'

    def _render_table(self, rows):
        thead_rows = [r for r in rows if r.is_header]
        tbody_rows = [r for r in rows if not r.is_header]

        ref_row = (thead_rows or tbody_rows or [None])[0]
        col_aligns = ref_row.aligns if ref_row and ref_row.aligns else []

        def align_style(col_idx):
            a = col_aligns[col_idx] if col_idx < len(col_aligns) else None
            return a or 'center'

        table_style = (
            'border-collapse:collapse;width:100%;'
            'font-family:inherit;margin:1em 0;'
        )
        parts = [f'<table class="table-block" style="{table_style}">']

        if thead_rows:
            parts.append('<thead>')
            for row in thead_rows:
                cells_html = ''.join(
                    f'<th class="table-header" style="text-align:{align_style(ci)};padding:0.5em 0.40em;border:1px solid #ccc;'
                    f'background:#d0d0f0;font-weight:600;">'
                    f'{self._render_inline(JotdownLexer.lex_inline(cell))}</th>'
                    for ci, cell in enumerate(row.cells)
                )
                parts.append(f'<tr>{cells_html}</tr>')
            parts.append('</thead>')

        if tbody_rows:
            parts.append('<tbody>')
            for ri, row in enumerate(tbody_rows):
                row_class = 'table-row-0' if ri % 2 == 0 else 'table-row-1'
                cells_html = ''.join(
                    f'<td class="{row_class}-{align_style(ci)}">'
                    f'{self._render_inline(JotdownLexer.lex_inline(cell))}</td>'
                    for ci, cell in enumerate(row.cells)
                )
                parts.append(f'<tr>{cells_html}</tr>')
            parts.append('</tbody>')

        parts.append('</table>')
        return '\n'.join(parts)

    def _render_ol(self, tokens):
        return f'<ol>\n{self._render_list_body(tokens, TOlItem)}\n</ol><br>'

    def _render_roman(self, tokens, upper):
        items = [t for t in tokens if isinstance(t, TRomanItem)]
        if all(t.value is not None for t in items):
            sorted_items = iter(sorted(items, key=lambda t: t.value))
        else:
            sorted_items = iter(items)
        rebuilt = []
        for t in tokens:
            if isinstance(t, TRomanItem):
                rebuilt.append(next(sorted_items))
            else:
                rebuilt.append(t)
        style = 'list-style-type:upper-roman' if upper else 'list-style-type:lower-roman'
        return f'<ol style="{style}">\n{self._render_list_body(rebuilt, TRomanItem)}\n</ol>\n<br>'

    def _render_uln(self, tokens):
        return f'<ol>\n{self._render_list_body(tokens, TUlItem)}\n</ol>\n<br>'

    def _render_ul(self, tokens):
        return f'<ul>\n{self._render_list_body(tokens, TUlItemAny)}\n</ul>\n<br>'

    def _render_list_body(self, tokens, item_type):
        if item_type is TOlItem:
            sorted_items = iter(sorted(
                [t for t in tokens if isinstance(t, item_type)],
                key=lambda x: x.number
            ))
            tokens = [next(sorted_items) if isinstance(t, item_type) else t for t in tokens]

        rows = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if isinstance(tok, item_type):
                rows.append(f'<li>{self._render_inline(JotdownLexer.lex_inline(tok.text))}</li>')
                i += 1
            elif isinstance(tok, TParaLine):
                lines = []
                while i < len(tokens) and isinstance(tokens[i], TParaLine):
                    lines.append(tokens[i].text)
                    i += 1
                rows.append(self._render_para(lines))
            elif isinstance(tok, TForcedPara):
                rows.append(self._render_forced_para(tok))
                i += 1
            else:
                i += 1
        return '\n'.join(rows)

    def _render_forced_para(self, tok):
        return JotdownHTMLCompiler().compile(JotdownLexer(tok.raw).lex(), standalone=False)

    def _render_para(self, lines):
        return f'<p>{self._render_inline(JotdownLexer.lex_inline(chr(10).join(lines)))}</p>'

    def _render_inline(self, tokens):
        stack = []
        out = []
        for tok in tokens:
            if isinstance(tok, IText):
                out.append(_esc(tok.content.replace('\n', ' ')))
            elif isinstance(tok, IInlineCode):
                code = _esc(tok.content)
                is_multiline = '\n' in tok.content
                if is_multiline:
                    lang_attr = f' class="language-{_esc(tok.language)}"' if tok.language else ''
                    out.append(f'<pre><code{lang_attr}>{code}</code></pre>')
                elif tok.language:
                    out.append(f'<code class="language-{_esc(tok.language)}">{code}</code>')
                else:
                    out.append(f'<code>{code}</code>')
            elif isinstance(tok, ILink):
                label = self._render_inline(tok.text_tokens)
                out.append(f'<a href="{_esc(tok.url)}">{label}</a>')
            elif isinstance(tok, IImage):
                out.append(f'<a href="{_esc(tok.url)}"><img src="{_esc(tok.src)}" alt="{_esc(tok.default)}"></a>')
            elif isinstance(tok, ISymbol):
                out.append(tok.content)
            elif isinstance(tok, IFormatOpen):
                if tok.subsup:
                    stack.append(['__subsup__'])
                    out.append('\x00SUBSUP_OPEN\x00')
                else:
                    opens, closes = self._format_tags(tok)
                    out.extend(opens)
                    stack.append(closes)
            elif isinstance(tok, IFormatClose):
                if stack:
                    closes = stack.pop()
                    if closes == ['__subsup__']:
                        joined = ''.join(out)
                        marker = '\x00SUBSUP_OPEN\x00'
                        idx = joined.rfind(marker)
                        if idx != -1:
                            content = joined[idx + len(marker):]
                            before = joined[:idx]
                            parts = content.split('::', 1)
                            lower = parts[0] if len(parts) > 0 else ''
                            upper = parts[1] if len(parts) > 1 else ''
                            subsup_html = (
                                '<span style="display:inline-flex;flex-direction:column;'
                                'line-height:1;vertical-align:middle;">'
                                f'<span style="font-size:0.5em;position:relative;top:-0.25em;">{upper}</span>'
                                f'<span style="font-size:0.5em;position:relative;top:0.25em;">{lower}</span>'
                                '</span>'
                            )
                            out = list(before) + [subsup_html]
                    else:
                        out.extend(reversed(closes))
        while stack:
            closes = stack.pop()
            if closes != ['__subsup__']:
                out.extend(reversed(closes))
        return ''.join(out)

    @staticmethod
    def _format_tags(fmt):
        opens, closes = [], []
        def wrap(o, c): opens.append(o); closes.append(c)
        if fmt.bold:          wrap('<strong>', '</strong>')
        if fmt.em_italic:     wrap('<em>', '</em>')
        if fmt.idio_italic:   wrap('<i>', '</i>')
        if fmt.underline:     wrap('<u>', '</u>')
        if fmt.strikethrough: wrap('<s>', '</s>')
        if fmt.subscript:     wrap('<sub style="font-size:0.60em;">', '</sub>')
        if fmt.superscript:   wrap('<sup style="font-size:0.60em;">', '</sup>')
        return opens, closes


def parse(source, *, standalone=True):
    tokens = JotdownLexer(source).lex()
    return JotdownHTMLCompiler().compile(tokens, standalone=standalone)


def _esc(text):
    return _html.escape(text, quote=True)


def main():
    p = argparse.ArgumentParser(
        prog='jotdown',
        description='Compile Jotdown markup to HTML.',
    )
    p.add_argument('file', nargs='?', metavar='FILE', help='Input file (default: stdin)')
    p.add_argument('-o', '--output', metavar='FILE', help='Output file (default: stdout)')
    p.add_argument('--fragment', action='store_true', help='Emit an HTML fragment instead of a standalone document')
    args = p.parse_args()

    source = open(args.file, encoding='utf-8').read() if args.file else sys.stdin.read()
    result = parse(source, standalone=not args.fragment)

    if args.output:
        open(args.output, 'w', encoding='utf-8').write(result)
    else:
        sys.stdout.write(result)


if __name__ == '__main__':
    main()