chars = ['꩜ ', '!', '#', '$', '%', '&', '*', '@', ',', '.', '?', '^', '_', '¡', '¿', '“', '›', '‽', '+', '⁺', '=', '±', '»', '§', '¶', '÷', '×', '∅', '√', '≈', '↑', '→', '↓', '←', '⇆', 'μ', '·', '†', '‡', '•', '‰', '☀️', '★', '♠', '♣', '♥', '♦', '✂️', '✓', '€', '∞', '0', '1', '2', '∞', 'A', 'B', 'C', 'Π', 'π', 'Ω']

size_map = []
for char in chars:
    size_map.append(char + ': ' + str(len(char.encode('utf-8'))/2))


# size_map = {
#     {
#         'char': char,
#         'length': length
#     },
# }

`꩜ : 2.0`
`!: 0.5`
`#: 0.5`
`$: 0.5`
`%: 0.5`
`&: 0.5`
`*: 0.5`
`@: 0.5`
`,: 0.5`
`.: 0.5`
`?: 0.5`
`^: 0.5`
`_: 0.5`
`¡: 1.0`
`¿: 1.0`
`“: 1.5`
`›: 1.5`
`‽: 1.5`
`+: 0.5`
`⁺: 1.5`
`=: 0.5`
`±: 1.0`
`»: 1.0`
`§: 1.0`
`¶: 1.0`
`÷: 1.0`
`×: 1.0`
`∅: 1.5`
`√: 1.5`
`≈: 1.5`
`↑: 1.5`
`→: 1.5`
`↓: 1.5`
`←: 1.5`
`⇆: 1.5`
`μ: 1.0`
`·: 1.0`
`†: 1.5`
`‡: 1.5`
`•: 1.5`
`‰: 1.5`
`☀️: 3.0`
`★: 1.5`
`♠: 1.5`
`♣: 1.5`
`♥: 1.5`
`♦: 1.5`
`✂️: 3.0`
`✓: 1.5`
`€: 1.5`
`∞: 1.5`
`0: 0.5`
`1: 0.5`
`2: 0.5`
`∞: 1.5`
`A: 0.5`
`B: 0.5`
`C: 0.5`
`Π: 1.0`
`π: 1.0`
`Ω: 1.0`
