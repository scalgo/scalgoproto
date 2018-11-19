# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-

def cescape(v:bytes) -> str:
	ans = []
	cmap = {
		0: "\\0",
		34: "\"",
		9: "\\t",
		10: "\\n",
		13: "\\r"
	}
	for c in v:
		if c in cmap:
			ans.append(cmap[c])
		elif 32 <= c <= 125:
			ans.append(chr(c))
		else:
			ans.append("\\x%02x"%c)
	return "".join(ans)

def getuname(n:str) -> str:
	return n[0].upper() + n[1:]
