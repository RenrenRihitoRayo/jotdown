#!/usr/bin/env python3
"""
Jotdown v0.1 Parser
Converts Jotdown markup to HTML with single-pass left-to-right streaming.
"""

import re
from typing import List, Dict, Optional, Tuple, Any


class JotdownParser:
    """Parses Jotdown markup into HTML."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.length = len(text)

    def parse(self) -> str:
        """Parse entire document and return HTML."""
        blocks = self._parse_blocks()
        return self._render_blocks_to_html(blocks)

    def _at_line_start(self) -> bool:
        """Check if current position is at line start."""
        return self.pos == 0 or (self.pos > 0 and self.text[self.pos - 1] == '\n')

    def _peek(self, offset: int = 0) -> Optional[str]:
        """Peek at character without consuming."""
        idx = self.pos + offset
        return self.text[idx] if idx < self.length else None

    def _consume(self) -> Optional[str]:
        """Consume and return next character."""
        if self.pos < self.length:
            char = self.text[self.pos]
            self.pos += 1
            return char
        return None

    def _skip_whitespace_lines(self):
        """Skip blank lines."""
        while self.pos < self.length:
            if self.text[self.pos] == '\n':
                self.pos += 1
            elif self.text[self.pos].isspace():
                self.pos += 1
            else:
                break

    def _consume_line(self) -> str:
        """Consume until end of line (newline not included, but consumed)."""
        result = ""
        while self.pos < self.length and self.text[self.pos] != '\n':
            result += self.text[self.pos]
            self.pos += 1
        if self.pos < self.length and self.text[self.pos] == '\n':
            self.pos += 1
        return result

    def _parse_blocks(self) -> List[Dict[str, Any]]:
        """Parse document into blocks."""
        blocks = []

        while self.pos < self.length:
            self._skip_whitespace_lines()
            if self.pos >= self.length:
                break

            if not self._at_line_start():
                self.pos += 1
                continue

            if self._peek() == '#':
                blocks.append(self._parse_header())
                continue

            if re.match(r'^\d+\.', self.text[self.pos:]):
                blocks.append(self._parse_ordered_list())
                continue

            if re.match(r'^[a-z]\.', self.text[self.pos:]):
                blocks.append(self._parse_alphabetic_list())
                continue

            if self.text[self.pos:self.pos + 2] == '..':
                blocks.append(self._parse_unordered_list())
                continue

            if self.text[self.pos:self.pos + 3] == '```':
                blocks.append(self._parse_code_fence())
                continue

            if self.text[self.pos:self.pos + 2] == '![':
                blocks.append(self._parse_separator_block())
                continue

            if self.text[self.pos:self.pos + 7] == '!style[':
                blocks.append(self._parse_style_block())
                continue

            if self.text[self.pos:self.pos + 6] == '!html[':
                blocks.append(self._parse_html_block())
                continue

            blocks.append(self._parse_paragraph())

        return blocks

    def _parse_header(self) -> Dict[str, Any]:
        """Parse header at line start."""
        level = 0
        while self.pos < self.length and self.text[self.pos] == '#':
            level += 1
            self.pos += 1

        while self.pos < self.length and self.text[self.pos] == ' ':
            self.pos += 1

        header_id = None
        if self._peek() == '<':
            self.pos += 1
            header_id = ""
            while self.pos < self.length and self.text[self.pos] != '>':
                header_id += self.text[self.pos]
                self.pos += 1
            if self._peek() == '>':
                self.pos += 1
            if self._peek() == ' ':
                self.pos += 1

        text_content = self._consume_line()

        return {
            'type': 'header',
            'level': level,
            'text': text_content.strip(),
            'id': header_id
        }

    def _parse_ordered_list(self) -> Dict[str, Any]:
        """Parse numeric ordered list."""
        items = []

        while self.pos < self.length and self._at_line_start():
            match = re.match(r'^(\d+)\.\s*', self.text[self.pos:])
            if not match:
                break

            number = int(match.group(1))
            self.pos += len(match.group(0))
            text = self._consume_line()
            items.append((number, text))

        return {
            'type': 'ordered_list',
            'items': items
        }

    def _parse_alphabetic_list(self) -> Dict[str, Any]:
        """Parse alphabetic ordered list."""
        items = []

        while self.pos < self.length and self._at_line_start():
            match = re.match(r'^([a-z])\.\s*', self.text[self.pos:])
            if not match:
                break

            letter = match.group(1)
            self.pos += len(match.group(0))
            text = self._consume_line()
            items.append((letter, text))

        return {
            'type': 'alphabetic_list',
            'items': items
        }

    def _parse_unordered_list(self) -> Dict[str, Any]:
        """Parse unordered list."""
        items = []

        while self.pos < self.length and self._at_line_start():
            if self.text[self.pos:self.pos + 2] != '..':
                break

            self.pos += 2
            if self._peek() == ' ':
                self.pos += 1

            text = self._consume_line()
            items.append(text)

        return {
            'type': 'unordered_list',
            'items': items
        }

    def _parse_code_fence(self) -> Dict[str, Any]:
        """Parse code fence ``` ... ```"""
        self.pos += 3

        language = ""
        while self.pos < self.length and self.text[self.pos] not in ['\n', ' ', '`']:
            language += self.text[self.pos]
            self.pos += 1

        while self.pos < self.length and self.text[self.pos] != '\n':
            self.pos += 1
        if self.pos < self.length:
            self.pos += 1

        content = ""
        while self.pos < self.length:
            if self.text[self.pos:self.pos + 3] == '```':
                self.pos += 3
                while self.pos < self.length and self.text[self.pos] != '\n':
                    self.pos += 1
                if self.pos < self.length:
                    self.pos += 1
                break
            content += self.text[self.pos]
            self.pos += 1

        return {
            'type': 'code_fence',
            'content': content,
            'language': language
        }

    def _parse_separator_block(self) -> Dict[str, Any]:
        """Parse separator block ![ ... ]"""
        self.pos += 2
        content = ""
        depth = 1

        while self.pos < self.length and depth > 0:
            if self.text[self.pos] == '[':
                depth += 1
            elif self.text[self.pos] == ']':
                depth -= 1
                if depth == 0:
                    self.pos += 1
                    break
            content += self.text[self.pos]
            self.pos += 1

        return {
            'type': 'separator_block',
            'content': content
        }

    def _parse_style_block(self) -> Dict[str, Any]:
        """Parse style block !style[ ... ]"""
        self.pos += 7
        content = ""
        depth = 1

        while self.pos < self.length and depth > 0:
            if self.text[self.pos] == '[':
                depth += 1
            elif self.text[self.pos] == ']':
                depth -= 1
                if depth == 0:
                    self.pos += 1
                    break
            content += self.text[self.pos]
            self.pos += 1

        return {
            'type': 'style_block',
            'content': content
        }

    def _parse_html_block(self) -> Dict[str, Any]:
        """Parse HTML block !html[ ... ]"""
        self.pos += 6
        content = ""
        depth = 1

        while self.pos < self.length and depth > 0:
            if self.text[self.pos] == '[':
                depth += 1
            elif self.text[self.pos] == ']':
                depth -= 1
                if depth == 0:
                    self.pos += 1
                    break
            content += self.text[self.pos]
            self.pos += 1

        return {
            'type': 'html_block',
            'content': content
        }

    def _parse_paragraph(self) -> Dict[str, Any]:
        """Parse paragraph block."""
        lines = []

        while self.pos < self.length:
            if self._at_line_start():
                if self.text[self.pos] in ['#', '`'] or self.text[self.pos:self.pos + 3] == '```':
                    break
                if re.match(r'^[\d!.a-z]', self.text[self.pos:]):
                    break

            line = self._consume_line()
            if line.strip():
                lines.append(line)
            else:
                if lines:
                    break

        return {
            'type': 'paragraph',
            'lines': lines
        }

    def _parse_inline(self, text: str) -> List[Dict[str, Any]]:
        """Parse inline elements in text."""
        result = []
        pos = 0

        while pos < len(text):
            if text[pos] == '\\' and pos + 1 < len(text):
                next_char = text[pos + 1]
                result.append({
                    'type': 'text',
                    'content': next_char
                })
                pos += 2
                continue

            if text[pos] == '`':
                token, new_pos = self._parse_inline_code(text, pos)
                if token:
                    result.append(token)
                    pos = new_pos
                    continue

            if text[pos] == '[':
                token, new_pos = self._parse_link(text, pos)
                if token:
                    result.append(token)
                    pos = new_pos
                    continue

            if text[pos] == '(' and pos + 1 < len(text):
                token, new_pos = self._parse_formatting_or_linebreak(text, pos)
                if token:
                    result.append(token)
                    pos = new_pos
                    continue

            chunk = ""
            while pos < len(text) and text[pos] not in '\\`[(':
                chunk += text[pos]
                pos += 1

            if chunk:
                result.append({
                    'type': 'text',
                    'content': chunk
                })

        return result

    def _parse_inline_code(self, text: str, start_pos: int) -> Tuple[Optional[Dict], int]:
        """Parse `code` or `<lang> code`"""
        pos = start_pos + 1
        language = ""

        if pos < len(text) and text[pos] == '<':
            pos += 1
            while pos < len(text) and text[pos] != '>':
                language += text[pos]
                pos += 1
            if pos < len(text):
                pos += 1
            if pos < len(text) and text[pos] == ' ':
                pos += 1

        code = ""
        while pos < len(text) and text[pos] != '`':
            code += text[pos]
            pos += 1

        if pos >= len(text):
            return None, start_pos

        pos += 1

        return {
            'type': 'inline_code',
            'content': code,
            'language': language
        }, pos

    def _parse_link(self, text: str, start_pos: int) -> Tuple[Optional[Dict], int]:
        """Parse [text](url) or [!img source](url)"""
        pos = start_pos + 1
        is_image = False

        if pos < len(text) and text[pos] == '!':
            is_image = True
            pos += 1
            if pos + 2 < len(text) and text[pos:pos + 3] == 'img':
                pos += 3
                if pos < len(text) and text[pos] == ' ':
                    pos += 1

        link_text = ""
        while pos < len(text) and text[pos] != ']':
            link_text += text[pos]
            pos += 1

        if pos >= len(text):
            return None, start_pos

        pos += 1

        if pos >= len(text) or text[pos] != '(':
            return None, start_pos

        pos += 1
        url = ""
        while pos < len(text) and text[pos] != ')':
            url += text[pos]
            pos += 1

        if pos >= len(text):
            return None, start_pos

        pos += 1

        return {
            'type': 'image_link' if is_image else 'link',
            'text': link_text,
            'url': url
        }, pos

    def _parse_formatting_or_linebreak(self, text: str, start_pos: int) -> Tuple[Optional[Dict], int]:
        """Parse (*text), (**text), etc. or line breaks (  )"""
        pos = start_pos + 1

        if pos < len(text) and text[pos].isspace():
            rest = ""
            temp_pos = pos
            while temp_pos < len(text) and text[temp_pos] != ')':
                rest += text[temp_pos]
                temp_pos += 1
            
            if temp_pos < len(text) and text[temp_pos] == ')' and rest.strip() == '':
                return {
                    'type': 'linebreak'
                }, temp_pos + 1

        bold = False
        italic = False
        underline = False
        strikethrough = False
        subscript = False
        superscript = False

        if pos < len(text) and text[pos:pos + 2] == '__':
            subscript = True
            pos += 2
        else:
            while pos < len(text) and text[pos] in '*_-^':
                if text[pos] == '*':
                    bold = True
                elif text[pos] == '_':
                    underline = True
                elif text[pos] == '-':
                    strikethrough = True
                elif text[pos] == '^':
                    superscript = True
                pos += 1

        content = ""
        while pos < len(text) and text[pos] != ')':
            content += text[pos]
            pos += 1

        if pos >= len(text) or not content:
            return None, start_pos

        pos += 1

        return {
            'type': 'formatted',
            'content': content,
            'bold': bold,
            'italic': italic,
            'underline': underline,
            'strikethrough': strikethrough,
            'subscript': subscript,
            'superscript': superscript
        }, pos

    def _render_blocks_to_html(self, blocks: List[Dict]) -> str:
        """Render blocks to HTML."""
        html = []

        for block in blocks:
            if block['type'] == 'header':
                level = block['level']
                text = self._render_inline_html(block['text'])
                tag = f'h{level}'
                if block['id']:
                    html.append(f'<{tag} id="{self._escape_html(block["id"])}">{text}</{tag}>')
                else:
                    html.append(f'<{tag}>{text}</{tag}>')

            elif block['type'] == 'paragraph':
                para_html = '<p>'
                inline_text = ' '.join(block['lines'])
                para_html += self._render_inline_html(inline_text)
                para_html += '</p>'
                html.append(para_html)

            elif block['type'] == 'ordered_list':
                items = sorted(block['items'], key=lambda x: x[0])
                list_html = '<ol>'
                for _, text in items:
                    list_html += '<li>' + self._render_inline_html(text) + '</li>'
                list_html += '</ol>'
                html.append(list_html)

            elif block['type'] == 'alphabetic_list':
                list_html = '<ol>'
                for _, text in block['items']:
                    list_html += '<li>' + self._render_inline_html(text) + '</li>'
                list_html += '</ol>'
                html.append(list_html)

            elif block['type'] == 'unordered_list':
                list_html = '<ol>'
                for text in block['items']:
                    list_html += '<li>' + self._render_inline_html(text) + '</li>'
                list_html += '</ol>'
                html.append(list_html)

            elif block['type'] == 'code_fence':
                code = self._escape_html(block['content'])
                lang = block.get('language', '')
                if lang:
                    html.append(f'<pre><code class="language-{self._escape_html(lang)}">{code}</code></pre>')
                else:
                    html.append(f'<pre><code>{code}</code></pre>')

            elif block['type'] == 'separator_block':
                inner_parser = JotdownParser(block['content'])
                inner_html = inner_parser.parse()
                html.append(f'<div class="separator-block">{inner_html}</div>')

            elif block['type'] == 'style_block':
                html.append(f'<style>{block["content"]}</style>')

            elif block['type'] == 'html_block':
                html.append(block['content'])

        return '\n'.join(html)

    def _render_inline_html(self, text: str) -> str:
        """Render inline elements to HTML."""
        tokens = self._parse_inline(text)
        html = ""

        for token in tokens:
            if token['type'] == 'text':
                html += self._escape_html(token['content'])

            elif token['type'] == 'linebreak':
                html += '<br />'

            elif token['type'] == 'inline_code':
                code = self._escape_html(token['content'])
                lang = token.get('language', '')
                if lang:
                    html += f'<code class="language-{self._escape_html(lang)}">{code}</code>'
                else:
                    html += f'<code>{code}</code>'

            elif token['type'] == 'link':
                text_part = self._escape_html(token['text'])
                url = self._escape_html(token['url'])
                html += f'<a href="{url}">{text_part}</a>'

            elif token['type'] == 'image_link':
                src = self._escape_html(token['text'])
                url = self._escape_html(token['url'])
                html += f'<a href="{url}"><img src="{src}" alt="image" /></a>'

            elif token['type'] == 'formatted':
                content = self._render_inline_html(token['content'])
                if token['bold']:
                    content = f'<strong>{content}</strong>'
                if token['italic']:
                    content = f'<em>{content}</em>'
                if token['underline']:
                    content = f'<u>{content}</u>'
                if token['strikethrough']:
                    content = f'<s>{content}</s>'
                if token['subscript']:
                    content = f'<sub>{content}</sub>'
                if token['superscript']:
                    content = f'<sup>{content}</sup>'
                html += content

        return html

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text.replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;')
                    .replace("'", '&#39;'))


if __name__ == '__main__':
    test_doc = """
# Welcome <intro>

This is a (*italic) test with (**bold) and (_underline).

1. First item
2. Second item
3. Third item

a. Alpha
c. Charlie
b. Bravo

.. Item one
.. Item two
.. Item three

[Link text](https://example.com)

[!img https://example.com/image.png](https://example.com)

`inline code`
`<python> print('hello')`

```python
def hello():
    print("world")
```

Test (  ) linebreak.

!style[
body { color: red; }
]

!html[
<script>console.log('test');</script>
]

![
# Nested header
]
"""

    parser = JotdownParser(test_doc)
    html = parser.parse()
    print(html)