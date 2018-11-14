// -*- mode: c++; tab-width: 4; indent-tabs-mode: t; eval: (progn (c-set-style "stroustrup") (c-set-offset 'innamespace 0)); -*-
// vi:set ts=4 sts=4 sw=4 noet :
#include "test.hh"
#include <iostream>
#include <fstream>
#include <cstdio>
#include <vector>

constexpr bool writeMode = false;

bool validateOut(const char * data, size_t size, const char * file) {
	if (writeMode) {
		std::ofstream os(file, std::ifstream::binary);
		os.write(data, size);
	} else {
		std::ifstream is(file, std::ifstream::binary);
		is.seekg (0, is.end);
		auto length = is.tellg();
		is.seekg (0, is.beg);
		if (length != (int)size) return false;
		std::vector<char> o;
		o.resize(size);
		is.read(o.data(), size);
		if (memcmp(o.data(), data, size)) return false;
	}
	return true;
}

std::vector<char> readIn(const char * file) {
	std::ifstream is(file, std::ifstream::binary);
	is.seekg (0, is.end);
	auto length = is.tellg();
	is.seekg (0, is.beg);
	std::vector<char> o;
	o.resize(length);
	is.read(o.data(), length);
	return o;
}

int main(int, char ** argv) {
	if (!strcmp(argv[1], "out_default")) {
		scalgoproto::Writer w;
		auto s = w.construct<SimpleOut>();
		auto [data, size] = w.finalize(s);
		return !validateOut(data, size, argv[2]);
	} else if (!strcmp(argv[1], "out")) {
		scalgoproto::Writer w;
		auto s = w.construct<SimpleOut>();
		s.addE(MyEnum::c);
		s.addS({42, 27.0, true});
		s.addB(true);
		s.addU8(242);
		s.addU16(4024);
		s.addU32(124474);
		s.addU64(5465778);
		s.addI8(-40);
		s.addI16(4025);
		s.addI32(124475);
		s.addI64(5465779);
		s.addF(2.0);
		s.addD(3.0);
		s.addOs({43, 28.0, false});
		s.addOb(false);
		s.addOu8(252);
		s.addOu16(4034);
		s.addOu32(124464);
		s.addOu64(5465768);
		s.addOi8(-60);
		s.addOi16(4055);
		s.addOi32(124465);
		s.addOi64(5465729);
		s.addOf(5.0);
		s.addOd(6.4);
		auto [data, size] = w.finalize(s);
		return !validateOut(data, size, argv[2]);
	} else if (!strcmp(argv[1], "in")) {
		auto o = readIn(argv[2]);
		scalgoproto::Reader r(o.data(), o.size());
		auto s = r.root<SimpleIn>();
		if (s.getS().x != 42) return 1;
		if (s.getS().y != 27.0) return 1;
		if (s.getS().z != true) return 1;
		if (s.getB() != true) return 1;
		if (s.getU8() != 242) return 1;
		if (s.getU16() != 4024) return 1;
		if (s.getU32() != 124474) return 1;
		if (s.getU64() != 5465778) return 1;
		if (s.getI8() != -40) return 1;
		if (s.getI16() != 4025) return 1;
		if (s.getI32() != 124475) return 1;
		if (s.getI64() != 5465779) return 1;
		if (s.getF() != 2.0) return 1;
		if (s.getD() != 3.0) return 1;
		if (!s.hasOs()) return 1;
		if (!s.hasOb()) return 1;
		if (!s.hasOu8()) return 1;
		if (!s.hasOu16()) return 1;
		if (!s.hasOu32()) return 1;
		if (!s.hasOu64()) return 1;
		if (!s.hasOi8()) return 1;
		if (!s.hasOi16()) return 1;
		if (!s.hasOi32()) return 1;
		if (!s.hasOi64()) return 1;
		if (!s.hasOf()) return 1;
		if (!s.hasOd()) return 1;
		if (s.getOs().x != 43) return 1;
		if (s.getOs().y != 28.0) return 1;
		if (s.getOs().z != false) return 1;
		if (s.getOb() != false) return 1;
		if (s.getOu8() != 252) return 1;
		if (s.getOu16() != 4034) return 1;
		if (s.getOu32() != 124464) return 1;
		if (s.getOu64() != 5465768) return 1;
		if (s.getOi8() != -60) return 1;
		if (s.getOi16() != 4055) return 1;
		if (s.getOi32() != 124465) return 1;
		if (s.getOi64() != 5465729) return 1;
		if (s.getOf() != 5.0) return 1;
		if (s.getOd() != 6.4) return 1;
		if (s.hasNs()) return 1;
		if (s.hasNb()) return 1;
		if (s.hasNu8()) return 1;
		if (s.hasNu16()) return 1;
		if (s.hasNu32()) return 1;
		if (s.hasNu64()) return 1;
		if (s.hasNi8()) return 1;
		if (s.hasNi16()) return 1;
		if (s.hasNi32()) return 1;
		if (s.hasNi64()) return 1;
		if (s.hasNf()) return 1;
		if (s.hasNd()) return 1;
	} else if (!strcmp(argv[1], "in_default")) {
		auto o = readIn(argv[2]);
		scalgoproto::Reader r(o.data(), o.size());
		auto s = r.root<SimpleIn>();
		if (s.getS().x != 0) return 1;
		if (s.getS().y != 0) return 1;
		if (s.getS().z != false) return 1;
		if (s.getB() != false) return 1;
		if (s.getU8() != 2) return 1;
		if (s.getU16() != 3) return 1;
		if (s.getU32() != 4) return 1;
		if (s.getU64() != 5) return 1;
		if (s.getI8() != 6) return 1;
		if (s.getI16() != 7) return 1;
		if (s.getI32() != 8) return 1;
		if (s.getI64() != 9) return 1;
		if (s.getF() != 10.0) return 1;
		if (s.getD() != 11.0) return 1;
		if (s.hasOs()) return 1;
		if (s.hasOb()) return 1;
		if (s.hasOu8()) return 1;
		if (s.hasOu16()) return 1;
		if (s.hasOu32()) return 1;
		if (s.hasOu64()) return 1;
		if (s.hasOi8()) return 1;
		if (s.hasOi16()) return 1;
		if (s.hasOi32()) return 1;
		if (s.hasOi64()) return 1;
		if (s.hasOf()) return 1;
		if (s.hasOd()) return 1;
		if (s.hasNs()) return 1;
		if (s.hasNb()) return 1;
		if (s.hasNu8()) return 1;
		if (s.hasNu16()) return 1;
		if (s.hasNu32()) return 1;
		if (s.hasNu64()) return 1;
		if (s.hasNi8()) return 1;
		if (s.hasNi16()) return 1;
		if (s.hasNi32()) return 1;
		if (s.hasNi64()) return 1;
		if (s.hasNf()) return 1;
		if (s.hasNd()) return 1;
	} else if (!strcmp(argv[1], "out_complex")) {
		scalgoproto::Writer w;
		auto m = w.construct<MemberOut>();
		m.addId(42);
		auto l = w.constructList<std::int32_t>(31);
		for (size_t i=0; i < 31; ++i)
			l.add(i, 100-2*i);
		auto l2 = w.constructList<MyEnum>(2);
		l2.add(0, MyEnum::a);
		auto l3 = w.constructList<MyStruct>(1);
		auto b = w.constructBytes("bytes", 5);
		auto t = w.constructText("text");

		auto l4 = w.constructTextList(2);
		l4.add(0, t);
		auto l5 = w.constructBytesList(1);
		l5.add(0, b);

		auto l6 = w.constructList<MemberOut>(3);
		l6.add(0, m);
		l6.add(2, m);

		auto s = w.construct<ComplexOut>();
		s.addMember(m);
		s.addText(t);
		s.addBytes(b);
		s.addList(l);
		s.addStructList(l3);
		s.addEnumList(l2);
		s.addTextList(l4);
		s.addBytesList(l5);
		s.addMemberList(l6);
		auto [data, size] = w.finalize(s);
		return !validateOut(data, size, argv[2]);
	} else if (!strcmp(argv[1], "in_complex")) {
		auto o = readIn(argv[2]);
		scalgoproto::Reader r(o.data(), o.size());
		auto s = r.root<ComplexIn>();
		if (s.hasNmember()) return 1;
		if (s.hasNtext()) return 1;
		if (s.hasNbytes()) return 1;
		if (!s.hasText()) return 1;
		if (!s.hasBytes()) return 1;
		if (s.getText() != "text") return 1;
		if (s.getBytes().second != 5 || memcmp(s.getBytes().first, "bytes", 5)) return 1;
		if (!s.hasMember()) return 1;
		auto m = s.getMember();
		if (m.getId() != 42) return 1;

		if (!s.hasList()) return 1;
		if (s.hasNlist()) return 1;
		auto l = s.getList();
		auto rl = s.getListRaw();

		if (l.size() != 31 || rl.second != 31) return 1;

		for (int i=0; i < 31; ++i) {
			if (rl.first[i] != 100-2*i) return 1;
			if (l[i] != 100-2*i) return 1;
		}

		if (!s.hasEnumList()) return 1;
		auto l2 = s.getEnumList();
		if (!l2.has(0)) return 1;
		if (l2.has(1)) return 1;
		if (l2[0] != MyEnum::a) return 1;
		if (l2.size() != 2) return 1;

		if (!s.hasStructList()) return 1;
		auto l3 = s.getStructList();
		if (l3.size() != 1) return 1;
		
		if (!s.hasTextList()) return 1;
		auto l4 = s.getTextList();
		if (l4.size() != 2) return 1;
		if (!l4.has(0)) return 1;
		if (l4.has(1)) return 1;
		if (l4[0] != "text") return 1;

		if (!s.hasBytesList()) return 1;
		auto l5 = s.getBytesList();
		if (l5.size() != 1) return 1;
		if (!l5.has(0)) return 1;
		if (l5.front().second != 5 || memcmp(l5.front().first, "bytes", 5)) return 1;

		if (!s.hasMemberList()) return 1;
		auto l6 = s.getMemberList();
		if (l6.size() != 3) return 1;
		if (!l6.has(0)) return 1;
		if (l6.has(1)) return 1;
		if (!l6.has(2)) return 1;
		if (l6[0].getId() != 42) return 1;
		if (l6[2].getId() != 42) return 1;
		return 0;
	} else if (!strcmp(argv[1], "out_vl")) {
		scalgoproto::Writer w;
		auto name = w.constructText("nilson");
		auto u = w.construct<VLUnionOut>();
		u.addMonkey().addName(name);

		auto u2 = w.construct<VLUnionOut>();
		u2.addText().addText("foobar");

		auto t = w.construct<VLTextOut>();
		t.addId(45);
		t.addText("cake");

		auto b = w.construct<VLBytesOut>();
		b.addId(46);
		b.addBytes("hi", 2);

		auto l = w.construct<VLListOut>();
		l.addId(47);
		auto ll = l.addList(2);
		ll.add(0, 24);
		ll.add(1, 99);

		auto root = w.construct<VLRootOut>();
		root.addU(u);
		root.addU2(u2);
		root.addT(t);
		root.addB(b);
		root.addL(l);
		auto [data, size] = w.finalize(root);
		return !validateOut(data, size, argv[2]);
	} else if (!strcmp(argv[1], "in_vl")) {
		auto o = readIn(argv[2]);
		scalgoproto::Reader r(o.data(), o.size());
		auto s = r.root<VLRootIn>();

		if (!s.hasU()) return 1;
		auto u = s.getU();
		if (!u.isMonkey()) return 1;
		auto monkey = u.getMonkey();
		if (!monkey.hasName()) return 1;
		if (monkey.getName() != "nilson") return 1;

		if (!s.hasU2()) return 1;
		auto u2 = s.getU2();
		if (!u2.isText()) return 1;
		auto u2t = u2.getText();
		if (!u2t.hasText()) return 1;
		if (u2t.getText() != "foobar") return 1;
		
		if (!s.hasT()) return 1;
		auto t = s.getT();
		if (t.getId() != 45) return 1;
		if (!t.hasText()) return 1;
		if (t.getText() != "cake") return 1;

		if (!s.hasB()) return 1;
		auto b = s.getB();
		if (b.getId() != 46) return 1;
		if (!b.hasBytes()) return 1;
		if (b.getBytes().second != 2 || memcmp(b.getBytes().first, "hi", 2)) return 1;

		if (!s.hasL()) return 1;
		auto l = s.getL();
		if (l.getId() != 47) return 1;
		if (!l.hasList()) return 1;
		auto ll = l.getList();
		if (ll.size() != 2) return 1;
		if (ll[0] != 24) return 1;
		if (ll[1] != 99) return 1;
		return 0;		
	} else {
		return 1;
	}
	return 0;
}
