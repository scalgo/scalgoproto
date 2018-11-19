# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
import sys, scalgoproto, base

def getV(data: bytes, i:int) -> int:
	if i < len(data): return data[i]
	return -1

def validateOut(data: bytes, path:str) -> bool:
	exp = open(path, "rb").read()
	if data == exp: return True
	print("Wrong output")
	for i in range(0, max(len(data), len(exp)), 16):
		print("%08X | "%i, end="")
		for j in range(i, i+16):
			if getV(exp,j) == getV(data, j): print("\033[0m", end="")
			else: print("\033[92m", end="")
			if j < len(exp): print("%02X"%exp[j], end="")
			else: print("  ", end="")
			if j % 4 == 3: print(" ", end="")
		print("| ", end="")
		for j in range(i, i+16):
			if getV(exp,j) == getV(data, j): print("\033[0m", end="")
			else: print("\033[91m", end="")
			if j < len(data): print("%02X"%data[j], end="")
			else: print("  ", end="")
			if j % 4 == 3: print(" ", end="")
		print("\033[0m", end="")
		print("| ", end="")
		for j in range(i, i+16):
			if getV(exp,j) == getV(data, j): print("\033[0m", end="")
			else: print("\033[92m", end="")
			if j < len(exp) and 32 <= exp[j] <= 126: print(chr(exp[j]), end="")
			elif j < len(exp): print('.', end="")
			else: print(" ", end="")
			if j % 4 == 3: print(" ", end="")
		print("| ", end="")
		for j in range(i, i+16):
			if getV(exp,j) == getV(data, j): print("\033[0m", end="")
			else: print("\033[91m", end="")
			if j < len(data) and 32 <= data[j] <= 126: print(chr(data[j]), end="")
			elif j < len(data): print('.', end="")
			else: print(" ", end="")
			if j % 4 == 3: print(" ", end="")
			print("\033[0m", end="")
		print()
	return False

def readIn(path:str) -> bytes:
	return open(path, "rb").read()

def require(v, e) -> bool:
	if e == v: return False
	print("Error expected '%s' found '%s'"%(e,v), file=sys.stderr)
	return True

def testOutDefault(path:str) -> bool:
	w = scalgoproto.Writer()
	s = w.constructTable(base.SimpleOut)
	data = w.finalize(s)
	return validateOut(data, path)

def testOut(path:str) -> bool:
	w = scalgoproto.Writer()
	s = w.constructTable(base.SimpleOut)
	s.addE(base.MyEnum.c)
	s.addS(base.MyStruct(42, 27.0, True))
	s.addB(True)
	s.addU8(242)
	s.addU16(4024)
	s.addU32(124474)
	s.addU64(5465778)
	s.addI8(-40)
	s.addI16(4025)
	s.addI32(124475)
	s.addI64(5465779)
	s.addF(2.0)
	s.addD(3.0)
	s.addOs(base.MyStruct(43, 28.0, False))
	s.addOb(False)
	s.addOu8(252)
	s.addOu16(4034)
	s.addOu32(124464)
	s.addOu64(5465768)
	s.addOi8(-60)
	s.addOi16(4055)
	s.addOi32(124465)
	s.addOi64(5465729)
	s.addOf(5.0)
	s.addOd(6.4)
	data = w.finalize(s)
	return validateOut(data, path)

def testIn(path:str) -> bool:
	r = scalgoproto.Reader(readIn(path))
	s = r.root(base.SimpleIn)
	if require(s.hasE(), True): return False
	if require(s.getE(), base.MyEnum.c): return False
	if require(s.getS().x, 42): return False
	if require(s.getS().y, 27.0): return False
	if require(s.getS().z, True): return False
	if require(s.getB(), True): return False
	if require(s.getU8(), 242): return False
	if require(s.getU16(), 4024): return False
	if require(s.getU32(), 124474): return False
	if require(s.getU64(), 5465778): return False
	if require(s.getI8(), -40): return False
	if require(s.getI16(), 4025): return False
	if require(s.getI32(), 124475): return False
	if require(s.getI64(), 5465779): return False
	if require(s.getF(), 2.0): return False
	if require(s.getD(), 3.0): return False
	if require(s.hasOs(), True): return False
	if require(s.hasOb(), True): return False
	if require(s.hasOu8(), True): return False
	if require(s.hasOu16(), True): return False
	if require(s.hasOu32(), True): return False
	if require(s.hasOu64(), True): return False
	if require(s.hasOi8(), True): return False
	if require(s.hasOi16(), True): return False
	if require(s.hasOi32(), True): return False
	if require(s.hasOi64(), True): return False
	if require(s.hasOf(), True): return False
	if require(s.hasOd(), True): return False
	if require(s.getOs().x, 43): return False
	if require(s.getOs().y, 28.0): return False
	if require(s.getOs().z, False): return False
	if require(s.getOb(), False): return False
	if require(s.getOu8(), 252): return False
	if require(s.getOu16(), 4034): return False
	if require(s.getOu32(), 124464): return False
	if require(s.getOu64(), 5465768): return False
	if require(s.getOi8(), -60): return False
	if require(s.getOi16(), 4055): return False
	if require(s.getOi32(), 124465): return False
	if require(s.getOi64(), 5465729): return False
	if require(s.getOf(), 5.0): return False
	if require(s.getOd(), 6.4): return False
	if require(s.hasNe(), False): return False
	if require(s.hasNs(), False): return False
	if require(s.hasNb(), False): return False
	if require(s.hasNu8(), False): return False
	if require(s.hasNu16(), False): return False
	if require(s.hasNu32(), False): return False
	if require(s.hasNu64(), False): return False
	if require(s.hasNi8(), False): return False
	if require(s.hasNi16(), False): return False
	if require(s.hasNi32(), False): return False
	if require(s.hasNi64(), False): return False
	if require(s.hasNf(), False): return False
	if require(s.hasNd(), False): return False
	return True

def testInDefault(path:str) -> bool:
	r = scalgoproto.Reader(readIn(path))
	s = r.root(base.SimpleIn)
	if require(s.getS().x, 0): return False
	if require(s.getS().y, 0): return False
	if require(s.getS().z, False): return False
	if require(s.getB(), False): return False
	if require(s.getU8(), 2): return False
	if require(s.getU16(), 3): return False
	if require(s.getU32(), 4): return False
	if require(s.getU64(), 5): return False
	if require(s.getI8(), 6): return False
	if require(s.getI16(), 7): return False
	if require(s.getI32(), 8): return False
	if require(s.getI64(), 9): return False
	if require(s.getF(), 10.0): return False
	if require(s.getD(), 11.0): return False
	if require(s.hasOs(), False): return False
	if require(s.hasOb(), False): return False
	if require(s.hasOu8(), False): return False
	if require(s.hasOu16(), False): return False
	if require(s.hasOu32(), False): return False
	if require(s.hasOu64(), False): return False
	if require(s.hasOi8(), False): return False
	if require(s.hasOi16(), False): return False
	if require(s.hasOi32(), False): return False
	if require(s.hasOi64(), False): return False
	if require(s.hasOf(), False): return False
	if require(s.hasOd(), False): return False
	if require(s.hasNs(), False): return False
	if require(s.hasNb(), False): return False
	if require(s.hasNu8(), False): return False
	if require(s.hasNu16(), False): return False
	if require(s.hasNu32(), False): return False
	if require(s.hasNu64(), False): return False
	if require(s.hasNi8(), False): return False
	if require(s.hasNi16(), False): return False
	if require(s.hasNi32(), False): return False
	if require(s.hasNi64(), False): return False
	if require(s.hasNf(), False): return False
	if require(s.hasNd(), False): return False
	return True

def testOutComplex(path:str) -> bool:
	w = scalgoproto.Writer()

	m = w.constructTable(base.MemberOut)
	m.addId(42)

	l = w.constructInt32List(31)
	for i in range(31):
		l.add(i, 100-2*i)

	l2 = w.constructEnumList(base.MyEnum, 2)
	l2.add(0, base.MyEnum.a)

	l3 = w.constructStructList(base.MyStruct, 1)

	b = w.constructBytes(b"bytes")
	t = w.constructText("text")

	l4 = w.constructTextList(2)
	l4.add(0, t)
	l5 = w.constructBytesList(1)
	l5.add(0, b)

	l6 = w.constructTableList(base.MemberOut, 3)
	l6.add(0, m)
	l6.add(2, m)

	s = w.constructTable(base.ComplexOut)
	s.addMember(m)
	s.addText(t)
	s.addBytes(b)
	s.addList(l)
	s.addStructList(l3)
	s.addEnumList(l2)
	s.addTextList(l4)
	s.addBytesList(l5)
	s.addMemberList(l6)

	data = w.finalize(s)
	return validateOut(data, path)

def testInComplex(path:str) -> bool:
	r = scalgoproto.Reader(readIn(path))

	s = r.root(base.ComplexIn)
	if require(s.hasNmember(), False): return False
	if require(s.hasNtext(), False): return False
	if require(s.hasNbytes(), False): return False
	if require(s.hasText(), True): return False
	if require(s.hasBytes(), True): return False
	if require(s.getText(), "text"): return False
	if require(s.getBytes(), b"bytes"): return False
	if require(s.hasMember(), True): return False
	m = s.getMember()
	if require(m.getId(), 42): return False

	if require(s.hasList(), True): return False
	if require(s.hasNlist(), False): return False
	l = s.getList()

	if require(len(l), 31): return False

	for i in range(31):
		if require(l[i], 100-2*i): return False

	if require(s.hasEnumList(), True): return False

	l2 = s.getEnumList()

	if require(l2.has(0), True): return False
	if require(l2.has(1), False): return False
	if require(l2[0], base.MyEnum.a): return False
	if require(len(l2), 2): return False

	if require(s.hasStructList(), True): return False
	l3 = s.getStructList()
	if require(len(l3), 1): return False

	if require(s.hasTextList(), True): return False
	l4 = s.getTextList()
	if require(len(l4), 2): return False
	if require(l4.has(0), True): return False
	if require(l4.has(1), False): return False
	if require(l4[0], "text"): return False

	if require(s.hasBytesList(), True): return False
	l5 = s.getBytesList()
	if require(len(l5), 1): return False
	if require(l5.has(0), True): return False
	if require(l5[0], b"bytes"): return False

	if require(s.hasMemberList(), True): return False
	l6 = s.getMemberList()
	if require(len(l6), 3): return False
	if require(l6.has(0), True): return False
	if require(l6.has(1), False): return False
	if require(l6.has(2), True): return False
	if require(l6[0].getId(), 42): return False
	if require(l6[2].getId(), 42): return False
	return True

def testOutVL(path:str) -> bool:
	w = scalgoproto.Writer()
	name = w.constructText("nilson")
	u = w.constructTable(base.VLUnionOut)
	u.addMonkey().addName(name)

	u2 = w.constructTable(base.VLUnionOut)
	u2.addText().addText("foobar")

	t = w.constructTable(base.VLTextOut)
	t.addId(45)
	t.addText("cake")

	b = w.constructTable(base.VLBytesOut)
	b.addId(46)
	b.addBytes(b"hi")

	l = w.constructTable(base.VLListOut)
	l.addId(47)
	ll = l.addList(2)
	ll.add(0, 24)
	ll.add(1, 99)

	root = w.constructTable(base.VLRootOut)
	root.addU(u)
	root.addU2(u2)
	root.addT(t)
	root.addB(b)
	root.addL(l)
	data = w.finalize(root)
	return validateOut(data, path)

def testInVL(path:str) -> bool:
	o = readIn(path)
	r = scalgoproto.Reader(o)
	s = r.root(base.VLRootIn)

	if require(s.hasU(), True): return False
	u = s.getU()
	if require(u.isMonkey(), True): return False
	monkey = u.getMonkey()
	if require(monkey.hasName(), True): return False
	if require(monkey.getName(), "nilson"): return False

	if require(s.hasU2(), True): return False
	u2 = s.getU2()
	if require(u2.isText(), True): return False
	u2t = u2.getText()
	if require(u2t.hasText(), True): return False
	if require(u2t.getText(), "foobar"): return False
	
	if require(s.hasT(), True): return False
	t = s.getT()
	if require(t.getId(), 45): return False
	if require(t.hasText(), True): return False
	if require(t.getText(), "cake"): return False

	if require(s.hasB(), True): return False
	b = s.getB()
	if require(b.getId(), 46): return False
	if require(b.hasBytes(), True): return False
	if require(b.getBytes(),  b"hi"): return False

	if require(s.hasL(), True): return False
	l = s.getL()
	if require(l.getId(), 47): return False
	if require(l.hasList(), True): return False
	ll = l.getList()
	if require(len(ll), 2): return False
	if require(ll[0], 24): return False
	if require(ll[1], 99): return False
	return True

def testOutExtend1(path:str)->bool:
	w = scalgoproto.Writer()
	root = w.constructTable(base.Gen1Out)
	root.addAa(77)
	data = w.finalize(root)
	return validateOut(data, path)

def testInExtend1(path:str) -> bool:
	data = readIn(path)
	r = scalgoproto.Reader(data)
	s = r.root(base.Gen2In)
	if require(s.getAa(), 77): return False
	if require(s.getBb(), 42): return False
	if require(s.hasType(), False): return False
	return True

def testOutExtend2(path:str) -> bool:
	w = scalgoproto.Writer()
	root = w.constructTable(base.Gen2Out)
	root.addAa(80)
	root.addBb(81)
	cake = root.addCake()
	cake.addV(45)
	data = w.finalize(root)
	return validateOut(data, path)

def testInExtend2(path:str) -> bool:
	o = readIn(path)
	r = scalgoproto.Reader(o)
	s = r.root(base.Gen3In)
	if require(s.getAa(), 80): return False
	if require(s.getBb(), 81): return False
	if require(s.isCake(), True): return False
	if require(s.getCake().getV(), 45): return False
	if require(s.getE(), base.MyEnum.c): return False
	if require(s.getS().x, 0): return False
	if require(s.getS().y, 0): return False
	if require(s.getS().z, 0): return False
	if require(s.getB(), False): return False
	if require(s.getU8(), 2): return False
	if require(s.getU16(), 3): return False
	if require(s.getU32(), 4): return False
	if require(s.getU64(), 5): return False
	if require(s.getI8(), 6): return False
	if require(s.getI16(), 7): return False
	if require(s.getI32(), 8): return False
	if require(s.getI64(), 9): return False
	if require(s.getF(), 10): return False
	if require(s.getD(), 11): return False
	if require(s.hasOs(), False): return False
	if require(s.hasOb(), False): return False
	if require(s.hasOu8(), False): return False
	if require(s.hasOu16(), False): return False
	if require(s.hasOu32(), False): return False
	if require(s.hasOu64(), False): return False
	if require(s.hasOi8(), False): return False
	if require(s.hasOi16(), False): return False
	if require(s.hasOi32(), False): return False
	if require(s.hasOi64(), False): return False
	if require(s.hasOf(), False): return False
	if require(s.hasOd(), False): return False
	if require(s.hasMember(), False): return False
	if require(s.hasText(), False): return False
	if require(s.hasBytes(), False): return False
	if require(s.hasList(), False): return False
	if require(s.hasEnumList(), False): return False
	if require(s.hasStructList(), False): return False
	if require(s.hasTextList(), False): return False
	if require(s.hasBytesList(), False): return False
	if require(s.hasMemberList(), False): return False
	return True

def main() -> None:
	ans = False
	test = sys.argv[1]
	path = sys.argv[2]
	ans = False
	if test == "out_default": ans = testOutDefault(path)
	elif test == "out": ans = testOut(path)
	elif test == "in": ans = testIn(path)
	elif test == "in_default": ans = testInDefault(path)
	elif test == "out_complex": ans = testOutComplex(path)
	elif test == "in_complex": ans = testInComplex(path)
	elif test == "out_vl": ans = testOutVL(path)
	elif test == "in_vl": ans = testInVL(path)
	elif test == "out_extend1": ans = testOutExtend1(path)
	elif test == "in_extend1": ans = testInExtend1(path)
	elif test == "out_extend2": ans = testOutExtend2(path)
	elif test == "in_extend2": ans = testInExtend2(path)
	if not ans: sys.exit(1)

main()
