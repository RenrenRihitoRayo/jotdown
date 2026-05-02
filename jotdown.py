#!/usr/bin/env python3
"""
Jotdown v0.1 Parser
Converts Jotdown markup to HTML with single-pass left-to-right streaming.
"""

import re
from enum import Enum
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
import webbrowser


@dataclass
class Header:
    level: int
    text: str
    id: Optional[str] = None


@dataclass
class Link:
    text: str
    url: str
    is_image: bool = False


class JotdownParser:
    """Parses Jotdown markup into HTML."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.length = len(text)

    def parse(self, setup=True) -> str:
        """Parse entire document and return HTML."""
        blocks = self._parse_blocks()
        return ("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"if setup else"")+self._render_blocks_to_html(blocks)

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

            # Must be at line start for block constructs
            if not self._at_line_start():
                # This shouldn't happen if skipping works correctly
                self.pos += 1
                continue

            # Try header
            if self._peek() == '#':
                blocks.append(self._parse_header())
                continue

            # Try ordered list
            if re.match(r'^\d+\.', self.text[self.pos:]):
                blocks.append(self._parse_ordered_list())
                continue

            # Try unordered list
            if self.text[self.pos:self.pos + 2] == '..':
                blocks.append(self._parse_unordered_list())
                continue

            # Try block wrappers
            if self._peek() == '!' and self._peek(1) in ['[', 's', 'h']:
                if self.text[self.pos:self.pos + 2] == '![':
                    blocks.append(self._parse_separator_block())
                    continue
                elif self.text[self.pos:self.pos + 7] == '!style[':
                    blocks.append(self._parse_style_block())
                    continue
                elif self.text[self.pos:self.pos + 6] == '!html[':
                    blocks.append(self._parse_html_block())
                    continue

            # Otherwise parse as paragraph
            blocks.append(self._parse_paragraph())

        return blocks

    def _parse_header(self) -> Dict[str, Any]:
        """Parse header at line start."""
        level = 0
        while self.pos < self.length and self.text[self.pos] == '#':
            level += 1
            self.pos += 1

        # Skip spaces
        while self.pos < self.length and self.text[self.pos] == ' ':
            self.pos += 1

        # Check for explicit ID
        header_id = None
        if self._peek() == '<':
            self.pos += 1
            header_id = ""
            while self.pos < self.length and self.text[self.pos] != '>':
                header_id += self.text[self.pos]
                self.pos += 1
            if self._peek() == '>':
                self.pos += 1
            # Skip space after ID
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
            # Stop at block boundaries
            if self._at_line_start():
                if self.text[self.pos] in ['#', '`'] or self.text[self.pos:self.pos + 3] == '```':
                    break

            line = self._consume_line()
            if line.strip():
                lines.append(line)
            else:
                # Empty line ends paragraph
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
            # Handle escape
            if text[pos] == '\\' and pos + 1 < len(text):
                result.append({
                    'type': 'text',
                    'content': text[pos + 1]
                })
                pos += 2
                continue

            # Try inline code
            if text[pos] == '`':
                token, new_pos = self._parse_inline_code(text, pos)
                if token:
                    result.append(token)
                    pos = new_pos
                    continue

            # Try link
            if text[pos] == '[':
                token, new_pos = self._parse_link(text, pos)
                if token:
                    result.append(token)
                    pos = new_pos
                    continue

            # Try formatting: (*...), (**...), (_...), etc.
            if text[pos] == '(' and pos + 1 < len(text) and text[pos + 1] in '*_-^%':
                token, new_pos = self._parse_formatting(text, pos)
                if token:
                    result.append(token)
                    pos = new_pos
                    continue

            # Regular text
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

        # Check for language tag
        if pos < len(text) and text[pos] == '<':
            pos += 1
            while pos < len(text) and text[pos] != '>':
                language += text[pos]
                pos += 1
            if pos < len(text):
                pos += 1  # Skip >
            if pos < len(text) and text[pos] == ' ':
                pos += 1

        # Find closing backtick
        code = ""
        while pos < len(text) and text[pos] != '`':
            code += text[pos]
            pos += 1

        if pos >= len(text):
            return None, start_pos

        pos += 1  # Consume closing backtick

        return {
            'type': 'inline_code',
            'content': code,
            'language': language
        }, pos

    def _parse_link(self, text: str, start_pos: int) -> Tuple[Optional[Dict], int]:
        """Parse [text](url) or [!img source](url)"""
        pos = start_pos + 1
        is_image = False

        # Check for image marker
        if pos < len(text) and text[pos] == '!':
            is_image = True
            pos += 1
            # [!img source]
            if pos + 2 < len(text) and text[pos:pos + 3] == 'img':
                pos += 3
                if pos < len(text) and text[pos] == ' ':
                    pos += 1

        # Read until ]
        link_text = ""
        while pos < len(text) and text[pos] != ']':
            link_text += text[pos]
            pos += 1

        if pos >= len(text):
            return None, start_pos

        pos += 1  # Consume ]

        # Must have (url)
        if pos >= len(text) or text[pos] != '(':
            return None, start_pos

        pos += 1
        url = ""
        while pos < len(text) and text[pos] != ')':
            url += text[pos]
            pos += 1

        if pos >= len(text):
            return None, start_pos

        pos += 1  # Consume )

        return {
            'type': 'image_link' if is_image else 'link',
            'text': link_text,
            'url': url
        }, pos

    def _parse_formatting(self, text: str, start_pos: int) -> Tuple[Optional[Dict], int]:
        """Parse (*text), (**text), (_text), (_*text), etc."""
        pos = start_pos + 1
        
        # Collect markers
        bold = False
        italic = False
        underline = False
        strikethrough = False
        subscript = False
        superscript = False
        subsup = False

        # Parse regular markers
        while pos < len(text) and text[pos] in '*_-^%':
            if text[pos] == '*':
                bold = True
            elif text[pos] == '_':
                if not underline:
                    underline = True
                elif underline:
                    underline = False
                    subscript = True
                elif subscript:
                    underline = True
            elif text[pos] == '%':
                subsup = True
            elif text[pos] == '-':
                strikethrough = True
            elif text[pos] == '^':
                superscript = True
            pos += 1

        # Collect content until )
        content = ""
        k = 1
        while pos < len(text) and k:
            if text[pos] == '(':
                k += 1
            elif text[pos] == ')':
                k -= 1
            if not k: break
            content += text[pos]
            pos += 1

        if pos >= len(text) or not content:
            return None, start_pos

        pos += 1  # Consume )
        return {
            'type': 'formatted',
            'content': content,
            'bold': bold,
            'italic': italic,
            'underline': underline,
            'strikethrough': strikethrough,
            'subscript': subscript,
            'superscript': superscript,
            'subsup': subsup
        }, pos

    def _render_blocks_to_html(self, blocks: List[Dict]) -> str:
        """Render blocks to HTML."""
        html = []

        for block in blocks:
            if block['type'] == 'header':
                level = block['level']
                text = self._escape_html(block['text'])
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
                # Sort by numeric value
                items = sorted(block['items'], key=lambda x: x[0])
                list_html = '<ol>'
                for _, text in items:
                    list_html += '<li>' + self._render_inline_html(text) + '</li>'
                list_html += '</ol>'
                html.append(list_html)

            elif block['type'] == 'alphabetic_list':
                # Preserve source order
                list_html = '<ol>'
                for _, text in block['items']:
                    list_html += '<li>' + self._render_inline_html(text) + '</li>'
                list_html += '</ol>'
                html.append(list_html)

            elif block['type'] == 'unordered_list':
                # Render as numbered list
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
                # Parse content independently
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
                content = JotdownParser(token["content"]).parse(False)[3:-4]
                if token['bold']:
                    content = f'<strong>{content}</strong>'
                if token['underline']:
                    content = f'<u>{content}</u>'
                if token['strikethrough']:
                    content = f'<s>{content}</s>'
                if token['subscript']:
                    content = f'<sub>{content}</sub>'
                if token['superscript']:
                    content = f'<sup>{content}</sup>'
                if token['subsup']:
                    lower, upper = content.split("::")
                    content = f'<span style="display:inline-flex; flex-direction:column; line-height:1; vertical-align:middle;"><span style="font-size:0.75em;">{upper}</span><span style="font-size:0.75em;">{lower}</span></span>'
                html += content

        return html

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))


if __name__ == '__main__':
    example = """
S (%10::13) 2x dx = 69 
"""

    parser = JotdownParser(example)
    html = parser.parse()
    open("file.html", "w").write(html)
    print(html)