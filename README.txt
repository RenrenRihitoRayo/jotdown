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