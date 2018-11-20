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

#define xstr(a) str(a)
#define str(a) #a
#define REQUIRE(e, v) if ((e) != (v)) {std::cout << "Error '" << str(e) << "' gave " << (e) << " expected " << v << std::endl; return 1;}
#define REQUIREQ(e, v) if ((e) != (v)) {std::cout << "Error '" << str(e) << "' wrong result" << std::endl; return 1;}

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
		s.addS({MyEnum::d, {42, 27.0, true}, false, 8, 9, 10, 11, -8, -9, -10, -11, 27.0, 22.0});
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
		REQUIRE(s.hasE(), true);
		REQUIREQ(s.getE(), MyEnum::c);
		REQUIREQ(s.getS().e, MyEnum::d);
		REQUIRE(s.getS().s.x, 42);
		REQUIRE(s.getS().s.y, 27.0);
		REQUIRE(s.getS().s.z, true);
		REQUIRE(s.getS().b, false);
		REQUIRE(s.getS().u8, 8);
		REQUIRE(s.getS().u16, 9);
		REQUIRE(s.getS().u32, 10);
		REQUIRE(s.getS().u64, 11);
		REQUIRE(s.getS().i8, -8);
		REQUIRE(s.getS().i16, -9);
		REQUIRE(s.getS().i32, -10);
		REQUIRE(s.getS().i64, -11);
		REQUIRE(s.getS().f, 27.0);
		REQUIRE(s.getS().d, 22.0);
		REQUIRE(s.getB(), true);
		REQUIRE(s.getU8(), 242);
		REQUIRE(s.getU16(), 4024);
		REQUIRE(s.getU32(), 124474);
		REQUIRE(s.getU64(), 5465778);
		REQUIRE(s.getI8(), -40);
		REQUIRE(s.getI16(), 4025);
		REQUIRE(s.getI32(), 124475);
		REQUIRE(s.getI64(), 5465779);
		REQUIRE(s.getF(), 2.0);
		REQUIRE(s.getD(), 3.0);
		REQUIRE(s.hasOs(), true);
		REQUIRE(s.hasOb(), true);
		REQUIRE(s.hasOu8(), true);
		REQUIRE(s.hasOu16(), true);
		REQUIRE(s.hasOu32(), true);
		REQUIRE(s.hasOu64(), true);
		REQUIRE(s.hasOi8(), true);
		REQUIRE(s.hasOi16(), true);
		REQUIRE(s.hasOi32(), true);
		REQUIRE(s.hasOi64(), true);
		REQUIRE(s.hasOf(), true);
		REQUIRE(s.hasOd(), true);
		REQUIRE(s.getOs().x, 43);
		REQUIRE(s.getOs().y, 28.0);
		REQUIRE(s.getOs().z, false);
		REQUIRE(s.getOb(), false);
		REQUIRE(s.getOu8(), 252);
		REQUIRE(s.getOu16(), 4034);
		REQUIRE(s.getOu32(), 124464);
		REQUIRE(s.getOu64(), 5465768);
		REQUIRE(s.getOi8(), -60);
		REQUIRE(s.getOi16(), 4055);
		REQUIRE(s.getOi32(), 124465);
		REQUIRE(s.getOi64(), 5465729);
		REQUIRE(s.getOf(), 5.0);
		REQUIRE(s.getOd(), 6.4);
		REQUIRE(s.hasNe(), false);
		REQUIRE(s.hasNs(), false);
		REQUIRE(s.hasNb(), false);
		REQUIRE(s.hasNu8(), false);
		REQUIRE(s.hasNu16(), false);
		REQUIRE(s.hasNu32(), false);
		REQUIRE(s.hasNu64(), false);
		REQUIRE(s.hasNi8(), false);
		REQUIRE(s.hasNi16(), false);
		REQUIRE(s.hasNi32(), false);
		REQUIRE(s.hasNi64(), false);
		REQUIRE(s.hasNf(), false);
		REQUIRE(s.hasNd(), false);
	} else if (!strcmp(argv[1], "in_default")) {
		auto o = readIn(argv[2]);
		scalgoproto::Reader r(o.data(), o.size());
		auto s = r.root<SimpleIn>();
		REQUIREQ(s.getS().e, MyEnum::a	);
		REQUIRE(s.getS().s.x, 0);
		REQUIRE(s.getS().s.y, 0);
		REQUIRE(s.getS().s.z, false);
		REQUIRE(s.getS().b, false);
		REQUIRE(s.getS().u8, 0);
		REQUIRE(s.getS().u16, 0);
		REQUIRE(s.getS().u32, 0);
		REQUIRE(s.getS().u64, 0);
		REQUIRE(s.getS().i8, 0);
		REQUIRE(s.getS().i16, 0);
		REQUIRE(s.getS().i32, 0);
		REQUIRE(s.getS().i64, 0);
		REQUIRE(s.getS().f, 0);
		REQUIRE(s.getS().d, 0);
		REQUIRE(s.getB(), false);
		REQUIRE(s.getU8(), 2);
		REQUIRE(s.getU16(), 3);
		REQUIRE(s.getU32(), 4);
		REQUIRE(s.getU64(), 5);
		REQUIRE(s.getI8(), 6);
		REQUIRE(s.getI16(), 7);
		REQUIRE(s.getI32(), 8);
		REQUIRE(s.getI64(), 9);
		REQUIRE(s.getF(), 10.0);
		REQUIRE(s.getD(), 11.0);
		REQUIRE(s.hasOs(), false);
		REQUIRE(s.hasOb(), false);
		REQUIRE(s.hasOu8(), false);
		REQUIRE(s.hasOu16(), false);
		REQUIRE(s.hasOu32(), false);
		REQUIRE(s.hasOu64(), false);
		REQUIRE(s.hasOi8(), false);
		REQUIRE(s.hasOi16(), false);
		REQUIRE(s.hasOi32(), false);
		REQUIRE(s.hasOi64(), false);
		REQUIRE(s.hasOf(), false);
		REQUIRE(s.hasOd(), false);
		REQUIRE(s.hasNs(), false);
		REQUIRE(s.hasNb(), false);
		REQUIRE(s.hasNu8(), false);
		REQUIRE(s.hasNu16(), false);
		REQUIRE(s.hasNu32(), false);
		REQUIRE(s.hasNu64(), false);
		REQUIRE(s.hasNi8(), false);
		REQUIRE(s.hasNi16(), false);
		REQUIRE(s.hasNi32(), false);
		REQUIRE(s.hasNi64(), false);
		REQUIRE(s.hasNf(), false);
		REQUIRE(s.hasNd(), false);
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
		REQUIRE(s.hasNmember(), false);
		REQUIRE(s.hasNtext(), false);
		REQUIRE(s.hasNbytes(), false);
		REQUIRE(s.hasText(), true);
		REQUIRE(s.hasBytes(), true);
		REQUIRE(s.getText(), "text");
		REQUIRE(s.getBytes().second, 5);
		REQUIRE(memcmp(s.getBytes().first, "bytes", 5), 0);
		REQUIRE(s.hasMember(), true);
		auto m = s.getMember();
		REQUIRE(m.getId(), 42);

		REQUIRE(s.hasList(), true);
		REQUIRE(s.hasNlist(), false);
		auto l = s.getList();
		auto rl = s.getListRaw();

		REQUIRE(l.size(), 31);
		REQUIRE(rl.second, 31);

		for (int i=0; i < 31; ++i) {
			REQUIRE(rl.first[i], 100-2*i);
			REQUIRE(l[i], 100-2*i);
		}

		REQUIRE(s.hasEnumList(), true);
		auto l2 = s.getEnumList();
		REQUIRE(l2.has(0), true);
		REQUIRE(l2.has(1), false);
		REQUIREQ(l2[0], MyEnum::a);
		REQUIRE(l2.size(), 2);

		REQUIRE(s.hasStructList(), true);
		auto l3 = s.getStructList();
		REQUIRE(l3.size(), 1);
		
		REQUIRE(s.hasTextList(), true);
		auto l4 = s.getTextList();
		REQUIRE(l4.size(), 2);
		REQUIRE(l4.has(0), true);
		REQUIRE(l4.has(1), false);
		REQUIRE(l4[0], "text");

		REQUIRE(s.hasBytesList(), true);
		auto l5 = s.getBytesList();
		REQUIRE(l5.size(), 1);
		REQUIRE(l5.has(0), true);
		REQUIRE(l5.front().second, 5);
		REQUIRE(memcmp(l5.front().first, "bytes", 5), 0);

		REQUIRE(s.hasMemberList(), true);
		auto l6 = s.getMemberList();
		REQUIRE(l6.size(), 3);
		REQUIRE(l6.has(0), true);
		REQUIRE(l6.has(1), false);
		REQUIRE(l6.has(2), true);
		REQUIRE(l6[0].getId(), 42);
		REQUIRE(l6[2].getId(), 42);
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

		REQUIRE(s.hasU(), true);
		auto u = s.getU();
		REQUIRE(u.isMonkey(), true);
		auto monkey = u.getMonkey();
		REQUIRE(monkey.hasName(), true);
		REQUIRE(monkey.getName(), "nilson");

		REQUIRE(s.hasU2(), true);
		auto u2 = s.getU2();
		REQUIRE(u2.isText(), true);
		auto u2t = u2.getText();
		REQUIRE(u2t.hasText(), true);
		REQUIRE(u2t.getText(), "foobar");
		
		REQUIRE(s.hasT(), true);
		auto t = s.getT();
		REQUIRE(t.getId(), 45);
		REQUIRE(t.hasText(), true);
		REQUIRE(t.getText(), "cake");

		REQUIRE(s.hasB(), true);
		auto b = s.getB();
		REQUIRE(b.getId(), 46);
		REQUIRE(b.hasBytes(), true);
		REQUIRE(b.getBytes().second,  2);
		REQUIRE(memcmp(b.getBytes().first, "hi", 2), 0);

		REQUIRE(s.hasL(), true);
		auto l = s.getL();
		REQUIRE(l.getId(), 47);
		REQUIRE(l.hasList(), true);
		auto ll = l.getList();
		REQUIRE(ll.size(), 2);
		REQUIRE(ll[0], 24);
		REQUIRE(ll[1], 99);
		return 0;		
	} else if (!strcmp(argv[1], "out_extend1")) {
		scalgoproto::Writer w;
		auto root = w.construct<Gen1Out>();
		root.addAa(77);
		auto [data, size] = w.finalize(root);
		return !validateOut(data, size, argv[2]);
	} else if (!strcmp(argv[1], "in_extend1")) {
		auto o = readIn(argv[2]);
		scalgoproto::Reader r(o.data(), o.size());
		auto s = r.root<Gen2In>();
		REQUIRE(s.getAa(), 77);
		REQUIRE(s.getBb(), 42);
		REQUIRE(s.hasType(), false);
		return 0;
	} else if (!strcmp(argv[1], "out_extend2")) {
		scalgoproto::Writer w;
		auto root = w.construct<Gen2Out>();
		root.addAa(80);
		root.addBb(81);
		auto cake = root.addCake();
		cake.addV(45);
		auto [data, size] = w.finalize(root);
		return !validateOut(data, size, argv[2]);
	} else if (!strcmp(argv[1], "in_extend2")) {
		auto o = readIn(argv[2]);
		scalgoproto::Reader r(o.data(), o.size());
		auto s = r.root<Gen3In>();
		REQUIRE(s.getAa(), 80);
		REQUIRE(s.getBb(), 81);
		REQUIRE(s.isCake(), true);
		REQUIRE(s.getCake().getV(), 45);
		REQUIREQ(s.getE(), MyEnum::c);
		REQUIRE(s.getS().x, 0);
		REQUIRE(s.getS().y, 0);
		REQUIRE(s.getS().z, 0);
		REQUIRE(s.getB(), false);
		REQUIRE(s.getU8(), 2);
		REQUIRE(s.getU16(), 3);
		REQUIRE(s.getU32(), 4);
		REQUIRE(s.getU64(), 5);
		REQUIRE(s.getI8(), 6);
		REQUIRE(s.getI16(), 7);
		REQUIRE(s.getI32(), 8);
		REQUIRE(s.getI64(), 9);
		REQUIRE(s.getF(), 10);
		REQUIRE(s.getD(), 11);
		REQUIRE(s.hasOs(), false);
		REQUIRE(s.hasOb(), false);
		REQUIRE(s.hasOu8(), false);
		REQUIRE(s.hasOu16(), false);
		REQUIRE(s.hasOu32(), false);
		REQUIRE(s.hasOu64(), false);
		REQUIRE(s.hasOi8(), false);
		REQUIRE(s.hasOi16(), false);
		REQUIRE(s.hasOi32(), false);
		REQUIRE(s.hasOi64(), false);
		REQUIRE(s.hasOf(), false);
		REQUIRE(s.hasOd(), false);
		REQUIRE(s.hasMember(), false);
		REQUIRE(s.hasText(), false);
		REQUIRE(s.hasBytes(), false);
		REQUIRE(s.hasList(), false);
		REQUIRE(s.hasEnumList(), false);
		REQUIRE(s.hasStructList(), false);
		REQUIRE(s.hasTextList(), false);
		REQUIRE(s.hasBytesList(), false);
		REQUIRE(s.hasMemberList(), false);
		return 0;
	} else {
		return 1;
	}
	return 0;
}
