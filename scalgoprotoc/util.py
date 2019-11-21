# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
from typing import List


def cescape(v: bytes) -> str:
    ans = []
    cmap = {0: "\\0", 34: '"', 9: "\\t", 10: "\\n", 13: "\\r"}
    for c in v:
        if c in cmap:
            ans.append(cmap[c])
        elif 32 <= c <= 125:
            ans.append(chr(c))
        else:
            ans.append("\\x%02x" % c)
    return "".join(ans)


def ucamel(n: str) -> str:
    """Convert a string in upper or lower camel case to upper camel case"""
    return n[0].upper() + n[1:]


def lcamel(n: str) -> str:
    """Convert a string in upper or lower camel case to lower camel case"""
    return n[0].lower() + n[1:]

def usnake(n: str) -> str:
    out: List[str] = []
    for c in n:
        if c.isupper() and out:
            out.append("_")
            out.append(c.upper())
        else:
            out.append(c.upper())
    return "".join(out)

def snake(n: str) -> str:
    """Convert a string in upper or lower camel case to snake case"""
    out: List[str] = []
    for c in n:
        if c.isupper() and out:
            out.append("_")
            out.append(c.lower())
        else:
            out.append(c.lower())
    return "".join(out)
