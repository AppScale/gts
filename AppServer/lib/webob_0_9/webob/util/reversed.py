## Backport of reversed

def reversed(seq):
    return iter(list(seq)[::-1])
