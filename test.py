# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Test that everything works
"""

import subprocess, sys
from typing import Callable 


failures=[]

def runValidate(schema:str, fail:bool=False)->bool:
	code = subprocess.call(["python3", "scalgoproto.py", "validate", schema])
	return fail == (code != 0)

def runCppSetup(schema: str, cpp: str) -> bool:
	subprocess.check_call(["python3", "scalgoproto.py", "cpp", schema, "tmp/test.hh"])
	subprocess.check_call(["g++", "-ggdb", "-std=c++17", "-Wall", "-Wextra", "-I", "tmp", "-I", ".", cpp, "-o", "tmp/bin"])
	return True

def runCpp(name:str, bin:str) -> bool:
	subprocess.check_call(["tmp/bin", name, bin])
	return True
	
def runTest(name:str, func: Callable[[],bool]) -> bool:
	l = 80 - len(name) - 4
	print("%s> %s <%s"%("="*(l//2 ), name, "="*(l - l//2)))
	ok = False
	try:
		ok = func()
	except:
		pass
	if ok:
		print("SUCCESS")
		return True
	else:
		print("FAILURE")
		failures.append(name)
		return False
		
if __name__ == '__main__':
	runTest("validate base", lambda: runValidate("test/base.spr"))
	runTest("validate update", lambda: runValidate("test/update.spr"))
	if runTest("cpp setup", lambda: runCppSetup("test/base.spr", "test/simple.cc")):
		runTest("cpp out default simple", lambda: runCpp("out_default", "test/simple_default.bin"))
		runTest("cpp in default simple", lambda: runCpp("in_default", "test/simple_default.bin"))
		runTest("cpp out simple", lambda: runCpp("out", "test/simple.bin"))
		runTest("cpp in simple", lambda: runCpp("in", "test/simple.bin"))
		runTest("cpp out complex", lambda: runCpp("out_complex", "test/complex.bin"))
		runTest("cpp in complex", lambda: runCpp("in_complex", "test/complex.bin"))

	print("="*80)
	if not failures:
		print("ALL GOOD")
		sys.exit(0)
	else:
		for t in failures:
			print("%s failed"%t)
		sys.exit(1)
		
