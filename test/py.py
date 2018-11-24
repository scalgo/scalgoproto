# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
import sys, scalgoproto, base

def get_v(data: bytes, i:int) -> int:
	if i < len(data): return data[i]
	return -1

def validate_out(data: bytes, path:str) -> bool:
	exp = open(path, "rb").read()
	if data == exp: return True
	print("Wrong output")
	for i in range(0, max(len(data), len(exp)), 16):
		print("%08X | "%i, end="")
		for j in range(i, i+16):
			if get_v(exp,j) == get_v(data, j): print("\033[0m", end="")
			else: print("\033[92m", end="")
			if j < len(exp): print("%02X"%exp[j], end="")
			else: print("  ", end="")
			if j % 4 == 3: print(" ", end="")
		print("| ", end="")
		for j in range(i, i+16):
			if get_v(exp,j) == get_v(data, j): print("\033[0m", end="")
			else: print("\033[91m", end="")
			if j < len(data): print("%02X"%data[j], end="")
			else: print("  ", end="")
			if j % 4 == 3: print(" ", end="")
		print("\033[0m", end="")
		print("| ", end="")
		for j in range(i, i+16):
			if get_v(exp,j) == get_v(data, j): print("\033[0m", end="")
			else: print("\033[92m", end="")
			if j < len(exp) and 32 <= exp[j] <= 126: print(chr(exp[j]), end="")
			elif j < len(exp): print('.', end="")
			else: print(" ", end="")
			if j % 4 == 3: print(" ", end="")
		print("| ", end="")
		for j in range(i, i+16):
			if get_v(exp,j) == get_v(data, j): print("\033[0m", end="")
			else: print("\033[91m", end="")
			if j < len(data) and 32 <= data[j] <= 126: print(chr(data[j]), end="")
			elif j < len(data): print('.', end="")
			else: print(" ", end="")
			if j % 4 == 3: print(" ", end="")
			print("\033[0m", end="")
		print()
	return False

def read_in(path:str) -> bytes:
	return open(path, "rb").read()

def require(v, e) -> bool:
	if e == v: return False
	print("Error expected '%s' found '%s'"%(e,v), file=sys.stderr)
	return True

def test_out_default(path:str) -> bool:
	w = scalgoproto.Writer()
	s = w.construct_table(base.SimpleOut)
	data = w.finalize(s)
	return validate_out(data, path)

def test_out(path:str) -> bool:
	w = scalgoproto.Writer()
	s = w.construct_table(base.SimpleOut)
	s.e = base.MyEnum.c
	s.s = base.FullStruct(base.MyEnum.d, base.MyStruct(42, 27.0, True), False, 8, 9, 10, 11, -8, -9, -10, -11, 27.0, 22.0)
	s.b = True
	s.u8 = 242
	s.u16 = 4024
	s.u32 = 124474
	s.u64 = 5465778
	s.i8 = -40
	s.i16 = 4025
	s.i32 = 124475
	s.i64 = 5465779
	s.f = 2.0
	s.d = 3.0
	s.os = base.MyStruct(43, 28.0, False)
	s.ob = False
	s.ou8 = 252
	s.ou16 = 4034
	s.ou32 = 124464
	s.ou64 = 5465768
	s.oi8 = -60
	s.oi16 = 4055
	s.oi32 = 124465
	s.oi64 = 5465729
	s.of = 5.0
	s.od = 6.4
	data = w.finalize(s)
	return validate_out(data, path)

def test_in(path:str) -> bool:
	r = scalgoproto.Reader(read_in(path))
	s = r.root(base.SimpleIn)
	if require(s.has_e, True): return False
	if require(s.e, base.MyEnum.c): return False
	if require(s.s.e, base.MyEnum.d): return False
	if require(s.s.s.x, 42): return False
	if require(s.s.s.y, 27.0): return False
	if require(s.s.s.z, True): return False
	if require(s.s.b, False): return False
	if require(s.s.u8, 8): return False
	if require(s.s.u16, 9): return False
	if require(s.s.u32, 10): return False
	if require(s.s.u64, 11): return False
	if require(s.s.i8, -8): return False
	if require(s.s.i16, -9): return False
	if require(s.s.i32, -10): return False
	if require(s.s.i64, -11): return False
	if require(s.s.f, 27.0): return False
	if require(s.s.d, 22.0): return False
	if require(s.b, True): return False
	if require(s.u8, 242): return False
	if require(s.u16, 4024): return False
	if require(s.u32, 124474): return False
	if require(s.u64, 5465778): return False
	if require(s.i8, -40): return False
	if require(s.i16, 4025): return False
	if require(s.i32, 124475): return False
	if require(s.i64, 5465779): return False
	if require(s.f, 2.0): return False
	if require(s.d, 3.0): return False
	if require(s.has_os, True): return False
	if require(s.has_ob, True): return False
	if require(s.has_ou8, True): return False
	if require(s.has_ou16, True): return False
	if require(s.has_ou32, True): return False
	if require(s.has_ou64, True): return False
	if require(s.has_oi8, True): return False
	if require(s.has_oi16, True): return False
	if require(s.has_oi32, True): return False
	if require(s.has_oi64, True): return False
	if require(s.has_of, True): return False
	if require(s.has_od, True): return False
	if require(s.os.x, 43): return False
	if require(s.os.y, 28.0): return False
	if require(s.os.z, False): return False
	if require(s.ob, False): return False
	if require(s.ou8, 252): return False
	if require(s.ou16, 4034): return False
	if require(s.ou32, 124464): return False
	if require(s.ou64, 5465768): return False
	if require(s.oi8, -60): return False
	if require(s.oi16, 4055): return False
	if require(s.oi32, 124465): return False
	if require(s.oi64, 5465729): return False
	if require(s.of, 5.0): return False
	if require(s.od, 6.4): return False
	if require(s.has_ne, False): return False
	if require(s.has_ns, False): return False
	if require(s.has_nb, False): return False
	if require(s.has_nu8, False): return False
	if require(s.has_nu16, False): return False
	if require(s.has_nu32, False): return False
	if require(s.has_nu64, False): return False
	if require(s.has_ni8, False): return False
	if require(s.has_ni16, False): return False
	if require(s.has_ni32, False): return False
	if require(s.has_ni64, False): return False
	if require(s.has_nf, False): return False
	if require(s.has_nd, False): return False
	return True

def test_in_default(path:str) -> bool:
	r = scalgoproto.Reader(read_in(path))
	s = r.root(base.SimpleIn)
	if require(s.has_e, False): return False
	if require(s.s.e, base.MyEnum.a): return False
	if require(s.s.s.x, 0): return False
	if require(s.s.s.y, 0.0): return False
	if require(s.s.s.z, False): return False
	if require(s.s.b, False): return False
	if require(s.s.u8, 0): return False
	if require(s.s.u16, 0): return False
	if require(s.s.u32, 0): return False
	if require(s.s.u64, 0): return False
	if require(s.s.i8, 0): return False
	if require(s.s.i16, 0): return False
	if require(s.s.i32, 0): return False
	if require(s.s.i64, 0): return False
	if require(s.s.f, 0): return False
	if require(s.s.d, 0): return False
	if require(s.b, False): return False
	if require(s.u8, 2): return False
	if require(s.u16, 3): return False
	if require(s.u32, 4): return False
	if require(s.u64, 5): return False
	if require(s.i8, 6): return False
	if require(s.i16, 7): return False
	if require(s.i32, 8): return False
	if require(s.i64, 9): return False
	if require(s.f, 10.0): return False
	if require(s.d, 11.0): return False
	if require(s.has_os, False): return False
	if require(s.has_ob, False): return False
	if require(s.has_ou8, False): return False
	if require(s.has_ou16, False): return False
	if require(s.has_ou32, False): return False
	if require(s.has_ou64, False): return False
	if require(s.has_oi8, False): return False
	if require(s.has_oi16, False): return False
	if require(s.has_oi32, False): return False
	if require(s.has_oi64, False): return False
	if require(s.has_of, False): return False
	if require(s.has_od, False): return False
	if require(s.has_ns, False): return False
	if require(s.has_nb, False): return False
	if require(s.has_nu8, False): return False
	if require(s.has_nu16, False): return False
	if require(s.has_nu32, False): return False
	if require(s.has_nu64, False): return False
	if require(s.has_ni8, False): return False
	if require(s.has_ni16, False): return False
	if require(s.has_ni32, False): return False
	if require(s.has_ni64, False): return False
	if require(s.has_nf, False): return False
	if require(s.has_nd, False): return False
	return True

def test_out_complex(path:str) -> bool:
	w = scalgoproto.Writer()

	m = w.construct_table(base.MemberOut)
	m.id = 42

	l = w.construct_int32_list(31)
	for i in range(31):
		l[i] = 100-2*i

	l2 = w.construct_enum_list(base.MyEnum, 2)
	l2[0] = base.MyEnum.a

	l3 = w.construct_struct_list(base.MyStruct, 1)

	b = w.construct_bytes(b"bytes")
	t = w.construct_text("text")

	l4 = w.construct_text_list(2)
	l4[0] = t
	l5 = w.construct_bytes_list(1)
	l5[0] = b

	l6 = w.construct_table_list(base.MemberOut, 3)
	l6[0] = m
	l6[2] = m

	l7 = w.construct_float32_list(2)
	l7[1] = 98.0

	l8 = w.construct_float64_list(3)
	l8[2] = 78.0

	l9 = w.construct_uint8_list(2)
	l9[0] = 4

	l10 = w.construct_bool_list(10)
	l10[0] = True
	l10[2] = True
	l10[8] = True

	s = w.construct_table(base.ComplexOut)
	s.member = m
	s.text = t
	s.my_bytes = b
	s.int_list = l
	s.struct_list = l3
	s.enum_list = l2
	s.text_list = l4
	s.bytes_list = l5
	s.member_list = l6
	s.f32list = l7
	s.f64list = l8
	s.u8list = l9
	s.blist = l10

	data = w.finalize(s)
	return validate_out(data, path)

def test_in_complex(path:str) -> bool:
	r = scalgoproto.Reader(read_in(path))

	s = r.root(base.ComplexIn)
	if require(s.has_nmember, False): return False
	if require(s.has_ntext, False): return False
	if require(s.has_nbytes, False): return False
	if require(s.has_text, True): return False
	if require(s.has_my_bytes, True): return False
	if require(s.text, "text"): return False
	if require(s.my_bytes, b"bytes"): return False
	if require(s.has_member, True): return False
	m = s.member
	if require(m.id, 42): return False

	if require(s.has_int_list, True): return False
	if require(s.has_nint_list, False): return False
	l = s.int_list

	if require(len(l), 31): return False

	for i in range(31):
		if require(l[i], 100-2*i): return False

	if require(s.has_enum_list, True): return False
	l2 = s.enum_list
	if require(l2.has(0), True): return False
	if require(l2.has(1), False): return False
	if require(l2[0], base.MyEnum.a): return False
	if require(len(l2), 2): return False

	if require(s.has_struct_list, True): return False
	l3 = s.struct_list
	if require(len(l3), 1): return False

	if require(s.has_text_list, True): return False
	l4 = s.text_list
	if require(len(l4), 2): return False
	if require(l4.has(0), True): return False
	if require(l4.has(1), False): return False
	if require(l4[0], "text"): return False

	if require(s.has_bytes_list, True): return False
	l5 = s.bytes_list
	if require(len(l5), 1): return False
	if require(l5.has(0), True): return False
	if require(l5[0], b"bytes"): return False

	if require(s.has_member_list, True): return False
	l6 = s.member_list
	if require(len(l6), 3): return False
	if require(l6.has(0), True): return False
	if require(l6.has(1), False): return False
	if require(l6.has(2), True): return False
	if require(l6[0].id, 42): return False
	if require(l6[2].id, 42): return False

	if require(s.has_f32list, True): return False
	l7 = s.f32list
	if require(len(l7), 2): return False
	if require(l7[0], 0.0): return False
	if require(l7[1], 98.0): return False

	if require(s.has_f64list, True): return False
	l8 = s.f64list
	if require(len(l8), 3): return False
	if require(l8[0], 0.0): return False
	if require(l8[1], 0.0): return False
	if require(l8[2], 78.0): return False

	if require(s.has_u8list, True): return False
	l9 = s.u8list
	if require(len(l9), 2): return False
	if require(l9[0], 4): return False
	if require(l9[1], 0): return False

	if require(s.has_blist, True): return False
	l10 = s.blist
	if require(len(l10), 10): return False
	if require(l10[0], True): return False
	if require(l10[1], False): return False
	if require(l10[2], True): return False
	if require(l10[3], False): return False
	if require(l10[4], False): return False
	if require(l10[5], False): return False
	if require(l10[6], False): return False
	if require(l10[7], False): return False
	if require(l10[8], True): return False
	if require(l10[9], False): return False

	return True

def test_out_vl(path:str) -> bool:
	w = scalgoproto.Writer()
	name = w.construct_text("nilson")
	u = w.construct_table(base.VLUnionOut)
	u.u_add_monkey().name = name

	u2 = w.construct_table(base.VLUnionOut)
	u2.u_add_text().t = "foobar"

	t = w.construct_table(base.VLTextOut)
	t.id = 45
	t.t = "cake"

	b = w.construct_table(base.VLBytesOut)
	b.id = 46
	b.b = b"hi"

	l = w.construct_table(base.VLListOut)
	l.id = 47
	ll = l.add_l(2)
	ll[0] = 24
	ll[1] = 99

	root = w.construct_table(base.VLRootOut)
	root.u = u
	root.u2 = u2
	root.t = t
	root.b = b
	root.l = l
	data = w.finalize(root)
	return validate_out(data, path)

def test_in_vl(path:str) -> bool:
	o = read_in(path)
	r = scalgoproto.Reader(o)
	s = r.root(base.VLRootIn)

	if require(s.has_u, True): return False
	u = s.u
	if require(u.u_is_monkey, True): return False
	monkey = u.u_monkey
	if require(monkey.has_name, True): return False
	if require(monkey.name, "nilson"): return False

	if require(s.has_u2, True): return False
	u2 = s.u2
	if require(u2.u_is_text, True): return False
	u2t = u2.u_text
	if require(u2t.has_t, True): return False
	if require(u2t.t, "foobar"): return False
	
	if require(s.has_t, True): return False
	t = s.t
	if require(t.id, 45): return False
	if require(t.has_t, True): return False
	if require(t.t, "cake"): return False

	if require(s.has_b, True): return False
	b = s.b
	if require(b.id, 46): return False
	if require(b.has_b, True): return False
	if require(b.b, b"hi"): return False

	if require(s.has_l, True): return False
	l = s.l
	if require(l.id, 47): return False
	if require(l.has_l, True): return False
	ll = l.l
	if require(len(ll), 2): return False
	if require(ll[0], 24): return False
	if require(ll[1], 99): return False
	return True

def test_out_extend1(path:str)->bool:
	w = scalgoproto.Writer()
	root = w.construct_table(base.Gen1Out)
	root.aa = 77
	data = w.finalize(root)
	return validate_out(data, path)

def test_in_extend1(path:str) -> bool:
	data = read_in(path)
	r = scalgoproto.Reader(data)
	s = r.root(base.Gen2In)
	if require(s.aa, 77): return False
	if require(s.bb, 42): return False
	if require(s.has_u, False): return False
	return True

def test_out_extend2(path:str) -> bool:
	w = scalgoproto.Writer()
	root = w.construct_table(base.Gen2Out)
	root.aa = 80
	root.bb = 81
	cake = root.u_add_cake()
	cake.v = 45
	data = w.finalize(root)
	return validate_out(data, path)

def test_in_extend2(path:str) -> bool:
	o = read_in(path)
	r = scalgoproto.Reader(o)
	s = r.root(base.Gen3In)
	if require(s.aa, 80): return False
	if require(s.bb, 81): return False
	if require(s.u_is_cake, True): return False
	if require(s.u_cake.v, 45): return False
	if require(s.e, base.MyEnum.c): return False
	if require(s.s.x, 0): return False
	if require(s.s.y, 0): return False
	if require(s.s.z, 0): return False
	if require(s.b, False): return False
	if require(s.u8, 2): return False
	if require(s.u16, 3): return False
	if require(s.u32, 4): return False
	if require(s.u64, 5): return False
	if require(s.i8, 6): return False
	if require(s.i16, 7): return False
	if require(s.i32, 8): return False
	if require(s.i64, 9): return False
	if require(s.f, 10): return False
	if require(s.d, 11): return False
	if require(s.has_os, False): return False
	if require(s.has_ob, False): return False
	if require(s.has_ou8, False): return False
	if require(s.has_ou16, False): return False
	if require(s.has_ou32, False): return False
	if require(s.has_ou64, False): return False
	if require(s.has_oi8, False): return False
	if require(s.has_oi16, False): return False
	if require(s.has_oi32, False): return False
	if require(s.has_oi64, False): return False
	if require(s.has_of, False): return False
	if require(s.has_od, False): return False
	if require(s.has_member, False): return False
	if require(s.has_text, False): return False
	if require(s.has_mbytes, False): return False
	if require(s.has_int_list, False): return False
	if require(s.has_enum_list, False): return False
	if require(s.has_struct_list, False): return False
	if require(s.has_text_list, False): return False
	if require(s.has_bytes_list, False): return False
	if require(s.has_member_list, False): return False
	return True

def main() -> None:
	ans = False
	test = sys.argv[1]
	path = sys.argv[2]
	ans = False
	if test == "out_default": ans = test_out_default(path)
	elif test == "out": ans = test_out(path)
	elif test == "in": ans = test_in(path)
	elif test == "in_default": ans = test_in_default(path)
	elif test == "out_complex": ans = test_out_complex(path)
	elif test == "in_complex": ans = test_in_complex(path)
	elif test == "out_vl": ans = test_out_vl(path)
	elif test == "in_vl": ans = test_in_vl(path)
	elif test == "out_extend1": ans = test_out_extend1(path)
	elif test == "in_extend1": ans = test_in_extend1(path)
	elif test == "out_extend2": ans = test_out_extend2(path)
	elif test == "in_extend2": ans = test_in_extend2(path)
	if not ans: sys.exit(1)

main()
