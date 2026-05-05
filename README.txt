# Jotdown

A lighter alternative to Markdown.

## Why use it?

.. Jotdown is lighter to use.
.. Jotdown's Specs will be tightly handled.
.. Jotdown is easy to implement.

## Is this file an example of Jotdown?

Yes.

## Examples

.. Lists
!p[
!p[
### Ordered List

1. 1
3. 3
2. 2

i. 1
iii. 3
ii. 2

I. 1
III. 3
II. 2

!![
Does not preserve source order and follows
numbering.
]

### Numbered Unordered List

.. 1
.. 3
.. 2

!![
Preserves source order. Uses <ol>
]

### Unordered List.

,, 1
,, 3
,, 3
!![
Preserves source order, uses <ul>
]
]
]
.. Code Blocks
!p[
!p[

`<python>import this`
`<c>printf("Hello, world!\n");`(.br)
`<python>
def fib(n):
    ...
`
]
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
.. Support for html entities
!p[
`(.int)` -> (.int)
]
.. Block nesting
`<Jotdown>
!p[
Force anything inside to be treated as a paragraph
]

![
Indent contents and not let it be
part of the external elements.
]

!![
Do not do anything serves as a hard separator.
]
`
.. Formatting
!p[
,, `(*bold)`  - `<strong>` (*example)
,, `(**italic)` - `<em>` (**example)
,, `(_underline)` - `<u>` (_example)
,, `(-strikethrough)` - `<s>` (-example)
,, `(^superscript)` - `<sup>` (^example)
,, `(__subscript)` - `<sub>` (__example)
,, `(%lower::upper)` - stacked sub/superscript (%lower example::upper example)
,, `(.symbol)` - HTML entity, e.g. `(.int)` -> (.int)
,, `(.br)` - line break `<br>`
,, `(..idiom)` - `<i>` (idiomatic/technical italic) (..example)

Math expressions can easily be done without Latex.(.br)
(.int)(%10::13) 2x (..dx)(.br)
(.int)(%10::13) 2(x(^2)/2) (..dx)(.br)
(..F)(x) = x(^2)(.br)
(.int)(%10::13) 2x (..dx) = (..F)(13) - (..F)(10)(.br)
= 13(^2) - 10(^2)(.br)
= 169 - 100(.br)
= 45(__16)(.br)
]

.. Links
!p[
Links: `[text](example.com)`(.br)
Image links: `[!image-src??alt text](example.com)`
(no html shenanigans here)
]

.. Tables!
!p[
.I With Column Labels
!p[
: Name | Age
: Darren | 16
]
.I Without Column Labels
!p[
; Darren | 17
; Reiley | 15
; Phoebe | 19
]
.I Alignments
!p[
: Name> | Age<
: Darren | 17
: Reiley | 15
: Phoebe | 19
]
]