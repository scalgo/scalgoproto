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
	return False

def testOut(path:str) -> bool:
	return False

def testIn(path:str) -> bool:
	return False

def testInDefault(path:str) -> bool:
	return False

def testOutComplex(path:str) -> bool:
	return False

def testInComplex(path:str) -> bool:
	return False

def testOutVL(path:str) -> bool:
    return False

def testInVL(path:str) -> bool:
	return False

def testOutExtend1(path:str)->bool:
	return False

def testInExtend1(path:str) -> bool:
	return False

def testOutExtend2(path:str) -> bool:
	return False

def testInExtend2(path:str) -> bool:
	return False

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
