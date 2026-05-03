#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import html as _html
import re


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
class TBlockOpen:
    kind: str  # "separator" | "style" | "html"

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
    kind: str  # "style" | "html"

@dataclass
class TForcedPara:
    raw: str  # raw Jotdown inline source inside !p[...]


@dataclass
class IText:
    content: str

@dataclass
class IInlineCode:
    content: str
    language: str = ""

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
    content: str  # safe HTML already, e.g. "&nbsp;" or "<br>"

@dataclass
class THrLine:
    pass
    

class _InlineLexer:
    def __init__(self, text: str):
        self._s = text
        self._pos = 0

    def lex(self) -> list:
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
        self._pos += 1  # opening `
        language = ''
        if self._ch() == '<':
            self._pos += 1
            while self._pos < len(self._s) and self._s[self._pos] != '>':
                language += self._s[self._pos]
                self._pos += 1
            if self._ch() == '>': self._pos += 1
            if self._ch() == ' ': self._pos += 1
        code = ''
        # Read until unescaped closing backtick
        while self._pos < len(self._s) and self._s[self._pos] != '`':
            if self._s[self._pos] == '\\' and self._pos + 1 < len(self._s) and self._s[self._pos + 1] == '`':
                # Escaped backtick inside code span — include a literal backtick
                code += '`'
                self._pos += 2
            else:
                code += self._s[self._pos]
                self._pos += 1
        if self._ch() == '`': self._pos += 1
        # Strip exactly one leading newline and one trailing newline (multiline fences)
        if code.startswith('\n'):
            code = code[1:]
        if code.endswith('\n'):
            code = code[:-1]
        return IInlineCode(content=code, language=language)

    def _lex_link(self):
        self._pos += 1  # [
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

        self._pos += 1  # (
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
        self._pos += 1  # (

        bold = False
        em_italic = False
        underline = False
        strikethrough = False
        subscript = False
        superscript = False
        subsup = False
        sym = False
        idio_italic = False

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

        fmt = IFormatOpen(
            bold=bold, em_italic=em_italic, underline=underline,
            strikethrough=strikethrough, subscript=subscript,
            superscript=superscript, subsup=subsup, sym=sym,
            idio_italic=idio_italic,
        )

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

    def _ch(self) -> Optional[str]:
        return self._s[self._pos] if self._pos < len(self._s) else None

    def _read_balanced(self, close: str) -> str:
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


def _line_starts_block(rest: str) -> bool:
    """Return True if *rest* (text from the current position to EOL / EOF)
    looks like the start of a Jotdown block-level construct."""
    return (
        rest.startswith('#')
        or rest.startswith('![')
        or rest.startswith('!style[')
        or rest.startswith('!html[')
        or rest.startswith('!p[')
        or rest.startswith('..')
        or rest.startswith(',,')
        or bool(re.match(r'\d+\.', rest))
    )


def _skip_backtick_spans(line: str) -> str:
    """Return the portion of *line* that lies outside any leading backtick
    code span, so callers can test whether it starts a block-level trigger.
    If the line begins with a backtick the whole line is (the start of) a code
    span — return '' to suppress block-trigger detection.
    """
    if line.startswith('`'):
        return ''   # starts with a code span — not a block trigger
    return line


class JotdownLexer:
    def __init__(self, source: str):
        self._src = source
        self._pos = 0

    def lex(self) -> list:
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
    def lex_inline(text: str) -> list:
        return _InlineLexer(text).lex()

    def _lex_block(self):
        rest = self._rest()

        if rest.startswith('#'):
            return self._lex_header()
        if rest.startswith('!['):
            return self._lex_nested_block('separator')
        if rest.startswith('!style['):
            return self._lex_raw_block('style')
        if rest.startswith('!html['):
            return self._lex_raw_block('html')
        if rest.startswith('!p['):
            return self._lex_forced_para()
        if rest.startswith('..'):
            return self._lex_uln_run()
        if rest.startswith(',,'):
            return self._lex_ul_run()
        if rest.startswith('---'):
            return self._lex_hr()
        if re.match(r'\d+\.', rest):
            return self._lex_ol_run()
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

    def _lex_ol_run(self):
        tokens = []
        while self._pos < len(self._src):
            m = re.match(r'(\d+)\.\s*', self._rest())
            if not m: break
            number = int(m.group(1))
            self._pos += len(m.group(0))
            tokens.append(TOlItem(number=number, text=self._consume_line()))
            self._skip_blank_lines()
            # Absorb any interleaved paragraph lines that are not a new list item
            # or a hard block-level construct (header, other list type, block, hr).
            tokens.extend(self._lex_interleaved_para(lambda r: bool(re.match(r'\d+\.', r))))
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

    def _lex_ul_run(self):
        tokens = []
        while self._pos < len(self._src) and self._rest().startswith(',,'):
            self._pos += 2
            while self._ch() == ' ': self._pos += 1
            tokens.append(TUlItemAny(text=self._consume_line()))
            self._skip_blank_lines()
            tokens.extend(self._lex_interleaved_para(lambda r: r.startswith(',,')))
        return tokens

    def _lex_interleaved_para(self, is_same_list) -> list:
        """Collect paragraph lines that appear between list items.
        Returns TParaLine / TParaBreak tokens to be appended to the list token
        stream, consuming them from source.  Stops (without consuming) as soon
        as a hard block-level trigger OR a new item of the same list kind is
        seen.  If the next non-blank content is a hard block trigger, returns []
        and leaves the source position unchanged."""
        saved = self._pos
        tokens = []
        inside_backtick = False

        while self._pos < len(self._src):
            rest = self._rest()

            # A new item of the same list kind — stop, let the caller loop pick it up
            if not inside_backtick and is_same_list(rest):
                break

            # A hard block trigger that is NOT a paragraph — stop and restore,
            # UNLESS it is !p[...] which is explicitly designed to be absorbed.
            if not inside_backtick:
                logical = _skip_backtick_spans(rest)
                if logical and _line_starts_block(logical):
                    if logical.startswith('!p['):
                        # Absorb the forced-para block directly
                        tok = self._lex_forced_para()
                        tokens.append(tok)
                        saved = self._pos
                        self._skip_blank_lines()
                        continue
                    # Restore to saved so the outer lex() loop handles this block
                    self._pos = saved
                    return []

            line = self._consume_line()

            if not inside_backtick and not line.strip():
                tokens.append(TParaBreak())
                self._skip_blank_lines()
                # Peek: if what follows is still not a same-list item and not a
                # hard block, keep going; otherwise stop
                rest2 = self._rest()
                if is_same_list(rest2):
                    break
                logical2 = _skip_backtick_spans(rest2)
                if logical2 and _line_starts_block(logical2):
                    if logical2.startswith('!p['):
                        pass  # let the main loop absorb it next iteration
                    else:
                        break
                continue

            tokens.append(TParaLine(text=line))
            saved = self._pos  # update saved past consumed content

            # Track backtick span state
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

    def _lex_nested_block(self, kind: str):
        self._pos += {'separator': 2, 'style': 7, 'html': 6}[kind]
        raw = self._read_balanced(']')
        inner = JotdownLexer(raw).lex()
        return [TBlockOpen(kind=kind)] + inner + [TBlockClose()]

    def _lex_raw_block(self, kind: str):
        self._pos += {'style': 7, 'html': 6}[kind]
        return TRawContent(raw=self._read_balanced(']'), kind=kind)

    def _lex_forced_para(self):
        self._pos += 3  # skip '!p['
        return TForcedPara(raw=self._read_balanced(']'))

    def _lex_paragraph(self):
        tokens = []
        # Track whether we are inside an open backtick span that started on a
        # previous line.  When inside_backtick is True, block-level triggers
        # on the current line must be ignored — they are literal code content.
        inside_backtick = False

        while self._pos < len(self._src):
            rest = self._rest()

            if not inside_backtick:
                # Only break for block triggers when we are NOT inside a
                # multi-line backtick span.
                logical_start = _skip_backtick_spans(rest)
                if logical_start and _line_starts_block(logical_start):
                    break

            line = self._consume_line()

            if not inside_backtick and not line.strip():
                tokens.append(TParaBreak())
                break

            tokens.append(TParaLine(text=line))

            # Count unescaped backticks on this line to update span state.
            # An odd count means the open/close balance flips.
            i = 0
            while i < len(line):
                if line[i] == '\\' and i + 1 < len(line) and line[i + 1] == '`':
                    i += 2  # escaped backtick — skip both chars
                elif line[i] == '`':
                    inside_backtick = not inside_backtick
                    i += 1
                else:
                    i += 1

        return tokens

    def _ch(self) -> Optional[str]:
        return self._src[self._pos] if self._pos < len(self._src) else None

    def _rest(self) -> str:
        return self._src[self._pos:]

    def _consume_line(self) -> str:
        start = self._pos
        while self._pos < len(self._src) and self._src[self._pos] != '\n':
            self._pos += 1
        result = self._src[start:self._pos]
        if self._pos < len(self._src): self._pos += 1
        return result

    def _read_until(self, stop: str) -> str:
        start = self._pos
        while self._pos < len(self._src) and self._src[self._pos] != stop:
            self._pos += 1
        return self._src[start:self._pos]

    def _read_balanced(self, close: str) -> str:
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
        """Skip over blank (whitespace-only) lines. Used between list items so
        that paragraphs separated by blank lines are not treated as list
        terminators — only a non-blank, non-list line ends the run."""
        while self._pos < len(self._src):
            start = self._pos
            while self._pos < len(self._src) and self._src[self._pos] == ' ':
                self._pos += 1
            if self._pos < len(self._src) and self._src[self._pos] == '\n':
                self._pos += 1  # consume the blank line and keep going
            else:
                self._pos = start  # non-blank line — restore and stop
                break

    def _skip_blank(self):
        #while self._pos < len(self._src) and self._src[self._pos] in ' \n\t\r':
#            self._pos += 1
        ...


class JotdownHTMLCompiler:
    def compile(self, tokens: list, *, standalone: bool = True) -> str:
        body = '\n'.join(self._compile_blocks(tokens))
        if standalone:
            return '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n' + body
        return body

    def _compile_blocks(self, tokens: list) -> list:
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
            
            elif isinstance(tok, THrLine):
                out.append('<hr>')
                i += 1

            elif isinstance(tok, TRawContent):
                if tok.kind == 'style':
                    out.append(f'<style>{tok.raw}</style>')
                else:
                    out.append(tok.raw)
                i += 1

            elif isinstance(tok, TForcedPara):
                out.append(self._render_forced_para(tok))
                i += 1

            else:
                i += 1

        return out

    def _render_header(self, tok: THeader) -> str:
        tag = f'h{tok.level}'
        content = self._render_inline(JotdownLexer.lex_inline(tok.text))
        if tok.anchor:
            return f'<{tag} id="{_esc(tok.anchor)}">{content}</{tag}>'
        return f'<{tag}>{content}</{tag}>'

    def _render_ol(self, tokens: list) -> str:
        return f'<ol>\n{self._render_list_body(tokens, TOlItem)}\n</ol>'

    def _render_uln(self, tokens: list) -> str:
        return f'<ol>\n{self._render_list_body(tokens, TUlItem)}\n</ol>'

    def _render_ul(self, tokens: list) -> str:
        return f'<ul>\n{self._render_list_body(tokens, TUlItemAny)}\n</ul>'

    def _render_list_body(self, tokens: list, item_type) -> str:
        # For ol, sort item tokens by number while preserving interleaved para order.
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
                # Batch consecutive TParaLines into one <p>
                lines = []
                while i < len(tokens) and isinstance(tokens[i], TParaLine):
                    lines.append(tokens[i].text)
                    i += 1
                rows.append(self._render_para(lines))
            elif isinstance(tok, TForcedPara):
                rows.append(self._render_forced_para(tok))
                i += 1
            else:
                i += 1  # TParaBreak and anything else: skip
        return '\n'.join(rows)

    def _render_forced_para(self, tok: TForcedPara) -> str:
        return JotdownHTMLCompiler().compile(JotdownLexer(tok.raw).lex(), standalone=False)

    def _render_para(self, lines: list) -> str:
        # Join lines with newline so that inline code spanning multiple lines
        # retains its internal whitespace. Plain prose lines are joined with a
        # space further below in _render_inline for IText tokens.
        return f'<p>{self._render_inline(JotdownLexer.lex_inline(chr(10).join(lines)))}</p>'

    def _render_inline(self, tokens: list) -> str:
        stack: list[list[str]] = []
        out = []

        for tok in tokens:
            if isinstance(tok, IText):
                # Collapse newlines between prose words into spaces
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
                                f'<span style="font-size:0.40em;position:relative;top:-0.5em;">{upper}</span>'
                                f'<span style="font-size:0.40em;position:relative;top:0.5em;">{lower}</span>'
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
    def _format_tags(fmt: IFormatOpen):
        opens, closes = [], []

        def wrap(o, c):
            opens.append(o); closes.append(c)

        if fmt.bold:          wrap('<strong>', '</strong>')
        if fmt.em_italic:     wrap('<em>', '</em>')
        if fmt.idio_italic:   wrap('<i>', '</i>')
        if fmt.underline:     wrap('<u>', '</u>')
        if fmt.strikethrough: wrap('<s>', '</s>')
        if fmt.subscript:     wrap('<sub style="font-size:0.60em;">', '</sub>')
        if fmt.superscript:   wrap('<sup style="font-size:0.60em;">', '</sup>')

        return opens, closes


def parse(source: str, *, standalone: bool = True) -> str:
    tokens = JotdownLexer(source).lex()
    return JotdownHTMLCompiler().compile(tokens, standalone=standalone)


def _esc(text: str) -> str:
    return _html.escape(text, quote=True)


if __name__ == '__main__':
    example = r"""
# Jotdown

## Why use it?

.. Jotdown is lighter to use.
.. Jotdown's Specs will be tightly handled.
.. Jotdown is easy to implement.

## Is this file an example of Jotdown?

Yes.

## Examples

.. Lists
!p[
### Ordered List

1. 1
3. 3
2. 2

Does not preserve source order and follows
numbering.

### Numbered Unordered List

.. 1
.. 3
.. 2

Preserves source order. Uses <ol>

### Unordeted List.

,, 1
,, 3
,, 3

Preserves source order, uses <ul>
]
.. Code Blocks
!p[

`<python>import this`
`<c>printf("Hello, world!\n");`(.br)
`<python>
def fib(n):
    ...
`
]
.. Jotdown has dedicated HTML and Style blocks!
!p[
`<Jotdown>
!style[
p {
    color: red;
}
]

!html[<h1>Yes></h1>]
`
]

.. Jotdown uses block based nesting!
!p[
`<Jotdown>
![
Regular nesting
]

!p[
treat all content as a paragraph
]
`
]
"""
    result = parse(example)
    open("out.html", "w").write(result)
    print(result)