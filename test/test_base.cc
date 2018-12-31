// -*- mode: c++; tab-width: 4; indent-tabs-mode: t; eval: (progn (c-set-style "stroustrup") (c-set-offset 'innamespace 0)); -*-
// vi:set ts=4 sts=4 sw=4 noet :

#include "test.hh"

#include "base.hh"
#include "complex2.hh"

using namespace scalgoprototest;
using namespace scalgoprototest2;

int main(int, char ** argv) {
	if (!strcmp(argv[1], "out_default")) {
		scalgoproto::Writer w;
		auto s = w.construct<SimpleOut>();
		auto [data, size] = w.finalize(s);
		return !validateOut(data, size, argv[2]);
	} else if (!strcmp(argv[1], "out")) {
		scalgoproto::Writer w;
		auto s = w.construct<SimpleOut>();
		s.setE(MyEnum::c);
		s.setS({MyEnum::d, {42, 27.0, true}, false, 8, 9, 10, 11, -8, -9, -10, -11, 27.0, 22.0});
		s.setB(true);
		s.setU8(242).setU16(4024).setU32(124474).setU64(5465778);
		s.setI8(-40).setI16(4025).setI32(124475).setI64(5465779);
		s.setF(2.0).setD(3.0);
		s.setOs({43, 28.0, false});
		s.setOb(false);
		s.setOu8(252).setOu16(4034).setOu32(124464).setOu64(5465768);
		s.setOi8(-60).setOi16(4055).setOi32(124465).setOi64(5465729);
		s.setOf(5.0).setOd(6.4);
		auto [data, size] = w.finalize(s);
		return !validateOut(data, size, argv[2]);
	} else if (!strcmp(argv[1], "in")) {
		auto o = readIn(argv[2]);
		scalgoproto::Reader r(o.data(), o.size());
		auto s = r.root<SimpleIn>();
		REQUIRE(s.hasE(), true);
		REQUIREQ(s.e(), MyEnum::c);
		REQUIREQ(s.s().e, MyEnum::d);
		REQUIRE(s.s().s.x, 42);
		REQUIRE(s.s().s.y, 27.0);
		REQUIRE(s.s().s.z, true);
		REQUIRE(s.s().b, false);
		REQUIRE(s.s().u8, 8);
		REQUIRE(s.s().u16, 9);
		REQUIRE(s.s().u32, 10);
		REQUIRE(s.s().u64, 11);
		REQUIRE(s.s().i8, -8);
		REQUIRE(s.s().i16, -9);
		REQUIRE(s.s().i32, -10);
		REQUIRE(s.s().i64, -11);
		REQUIRE(s.s().f, 27.0);
		REQUIRE(s.s().d, 22.0);
		REQUIRE(s.b(), true);
		REQUIRE(s.u8(), 242);
		REQUIRE(s.u16(), 4024);
		REQUIRE(s.u32(), 124474);
		REQUIRE(s.u64(), 5465778);
		REQUIRE(s.i8(), -40);
		REQUIRE(s.i16(), 4025);
		REQUIRE(s.i32(), 124475);
		REQUIRE(s.i64(), 5465779);
		REQUIRE(s.f(), 2.0);
		REQUIRE(s.d(), 3.0);
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
		REQUIRE(s.os().x, 43);
		REQUIRE(s.os().y, 28.0);
		REQUIRE(s.os().z, false);
		REQUIRE(s.ob(), false);
		REQUIRE(s.ou8(), 252);
		REQUIRE(s.ou16(), 4034);
		REQUIRE(s.ou32(), 124464);
		REQUIRE(s.ou64(), 5465768);
		REQUIRE(s.oi8(), -60);
		REQUIRE(s.oi16(), 4055);
		REQUIRE(s.oi32(), 124465);
		REQUIRE(s.oi64(), 5465729);
		REQUIRE(s.of(), 5.0);
		REQUIRE(s.od(), 6.4);
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
		REQUIREQ(s.s().e, MyEnum::a	);
		REQUIRE(s.s().s.x, 0);
		REQUIRE(s.s().s.y, 0);
		REQUIRE(s.s().s.z, false);
		REQUIRE(s.s().b, false);
		REQUIRE(s.s().u8, 0);
		REQUIRE(s.s().u16, 0);
		REQUIRE(s.s().u32, 0);
		REQUIRE(s.s().u64, 0);
		REQUIRE(s.s().i8, 0);
		REQUIRE(s.s().i16, 0);
		REQUIRE(s.s().i32, 0);
		REQUIRE(s.s().i64, 0);
		REQUIRE(s.s().f, 0);
		REQUIRE(s.s().d, 0);
		REQUIRE(s.b(), false);
		REQUIRE(s.u8(), 2);
		REQUIRE(s.u16(), 3);
		REQUIRE(s.u32(), 4);
		REQUIRE(s.u64(), 5);
		REQUIRE(s.i8(), 6);
		REQUIRE(s.i16(), 7);
		REQUIRE(s.i32(), 8);
		REQUIRE(s.i64(), 9);
		REQUIRE(s.f(), 10.0);
		REQUIRE(s.d(), 11.0);
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
		m.setId(42);
		auto l = w.constructList<std::int32_t>(31);
		for (size_t i=0; i < 31; ++i)
			l[i] = 100-2*i;
		auto l2 = w.constructList<MyEnum>(2);
		l2[0] = MyEnum::a;
		auto l3 = w.constructList<MyStruct>(1);
		auto b = w.constructBytes("bytes", 5);
		auto t = w.constructText("text");

		auto l4 = w.constructTextList(2);
		l4[0] = t;
		auto l5 = w.constructBytesList(1);
		l5[0] = b;

		auto l6 = w.constructList<MemberOut>(3);
		l6[0] = m;
		l6[2] = m;

		auto l7 = w.constructList<float>(2);
		l7[1] = 98.0;

		auto l8 = w.constructList<double>(3);
		l8[2] = 78.0;

		auto l9 = w.constructList<uint8_t>(2);
		l9[0] = 4;

		auto l10 = w.constructList<bool>(10);
		l10[0] = true;
		l10[2] = true;
		l10[8] = true;

		auto s = w.construct<ComplexOut>();
		s.setMember(m).setText(t).setMyBytes(b);
		s.setIntList(l);
		s.setStructList(l3);
		s.setEnumList(l2);
		s.setTextList(l4);
		s.setBytesList(l5);
		s.setMemberList(l6);
		s.setF32list(l7);
		s.setF64list(l8);
		s.setU8list(l9);
		s.setBlist(l10);

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
		REQUIRE(s.hasMyBytes(), true);
		REQUIRE(s.text(), "text");
		REQUIRE(s.myBytes().second, 5);
		REQUIRE(memcmp(s.myBytes().first, "bytes", 5), 0);
		REQUIRE(s.hasMember(), true);
		auto m = s.member();
		REQUIRE(m.id(), 42);

		REQUIRE(s.hasIntList(), true);
		REQUIRE(s.hasNintList(), false);
		auto l = s.intList();
		auto rl = s.intListRaw();

		REQUIRE(l.size(), 31);
		REQUIRE(rl.second, 31);

		for (int i=0; i < 31; ++i) {
			REQUIRE(rl.first[i], 100-2*i);
			REQUIRE(l[i], 100-2*i);
		}

		REQUIRE(s.hasEnumList(), true);
		auto l2 = s.enumList();
		REQUIRE(l2.has(0), true);
		REQUIRE(l2.has(1), false);
		REQUIREQ(l2[0], MyEnum::a);
		REQUIRE(l2.size(), 2);

		REQUIRE(s.hasStructList(), true);
		auto l3 = s.structList();
		REQUIRE(l3.size(), 1);
		
		REQUIRE(s.hasTextList(), true);
		auto l4 = s.textList();
		REQUIRE(l4.size(), 2);
		REQUIRE(l4.has(0), true);
		REQUIRE(l4.has(1), false);
		REQUIRE(l4[0], "text");

		REQUIRE(s.hasBytesList(), true);
		auto l5 = s.bytesList();
		REQUIRE(l5.size(), 1);
		REQUIRE(l5.has(0), true);
		REQUIRE(l5.front().second, 5);
		REQUIRE(memcmp(l5.front().first, "bytes", 5), 0);

		REQUIRE(s.hasMemberList(), true);
		auto l6 = s.memberList();
		REQUIRE(l6.size(), 3);
		REQUIRE(l6.has(0), true);
		REQUIRE(l6.has(1), false);
		REQUIRE(l6.has(2), true);
		REQUIRE(l6[0].id(), 42);
		REQUIRE(l6[2].id(), 42);

		REQUIRE(s.hasF32list(), true);
		auto l7 = s.f32list();
		REQUIRE(l7.size(), 2);
		REQUIRE(l7[0], 0.0);
		REQUIRE(l7[1], 98.0);

		REQUIRE(s.hasF64list(), true);
		auto l8 = s.f64list();
		REQUIRE(l8.size(), 3);
		REQUIRE(l8[0], 0.0);
		REQUIRE(l8[1], 0.0);
		REQUIRE(l8[2], 78.0);

		REQUIRE(s.hasU8list(), true);
		auto l9 = s.u8list();
		REQUIRE(l9.size(), 2);
		REQUIRE(l9[0], 4);
		REQUIRE(l9[1], 0);

		REQUIRE(s.hasBlist(), true);
		auto l10 = s.blist();
		REQUIRE(l10.size(), 10);
		REQUIRE(l10[0], true);
		REQUIRE(l10[1], false);
		REQUIRE(l10[2], true);
		REQUIRE(l10[3], false);
		REQUIRE(l10[4], false);
		REQUIRE(l10[5], false);
		REQUIRE(l10[6], false);
		REQUIRE(l10[7], false);
		REQUIRE(l10[8], true);
		REQUIRE(l10[9], false);

		return 0;
	} else if (!strcmp(argv[1], "out_complex2")) {
		scalgoproto::Writer w;

		auto m = w.construct<MemberOut>();
		m.setId(42);

		auto b = w.constructBytes("bytes", 5);
		auto t = w.constructText("text");

		auto l = w.constructList<NamedUnionEnumList>(2);
		l[0] = NamedUnionEnumList::x;
		l[1] = NamedUnionEnumList::z;

		auto l2 = w.constructList<Complex2L>(1);
		l2[0] = {2, true};

		auto l3 = w.constructList<NamedUnionOut>(2);
		l3[0].setText(t);
		l3[1].setMyBytes(b);

		auto r = w.construct<Complex2Out>();
		r.u1().setMember(m);
		r.u2().setText(t);
		r.u3().setMyBytes(b);
		r.u4().setEnumList(l);
		r.u5().setA();

		auto m2 = r.addHat();
		m2.setId(43);

		r.setL(l2);
		r.setS({Complex2SX::p, {8}});
		r.setL2(l3);

		auto [data, size] = w.finalize(r);
		return !validateOut(data, size, argv[2]);
	} else if (!strcmp(argv[1], "in_complex2")) {
		auto o = readIn(argv[2]);
		scalgoproto::Reader r(o.data(), o.size());
		auto s = r.root<Complex2In>();
		REQUIRE(s.u1().isMember(), true);
		REQUIRE(s.u1().member().id(), 42);
		REQUIRE(s.u2().isText(), true);
		REQUIRE(s.u2().text(), "text");
		REQUIRE(s.u3().isMyBytes(), true);
		REQUIRE(s.u3().myBytes().second, 5);
		REQUIRE(memcmp(s.u3().myBytes().first, "bytes", 5), 0);
		REQUIRE(s.u4().isEnumList(), true);
		auto l = s.u4().enumList();
		REQUIRE(l.size(), 2);
		REQUIREQ(l[0], NamedUnionEnumList::x);
		REQUIREQ(l[1], NamedUnionEnumList::z);
		REQUIRE(s.u5().isA(), true);
		REQUIRE(s.hasHat(), true);
		REQUIRE(s.hat().id(), 43);

		REQUIRE(s.hasL(), true);
		auto l2 = s.l();
		REQUIRE(l2.size(), 1);
		REQUIRE(l2[0].a, 2);
		REQUIRE(l2[0].b, true);
		REQUIREQ(s.s().x, Complex2SX::p)
		REQUIRE(s.s().y.z, 8);

		REQUIRE(s.hasL2(), true);
		auto l3 = s.l2();
		REQUIRE(l3[0].isText(), true);
		REQUIRE(l3[0].text(), "text");
		REQUIRE(l3[1].isMyBytes(), true);
		REQUIRE(l3[1].myBytes().second, 5);
		REQUIRE(memcmp(l3[1].myBytes().first, "bytes", 5), 0);
	} else if (!strcmp(argv[1], "out_inplace")) {
		scalgoproto::Writer w;
		auto name = w.constructText("nilson");
		auto u = w.construct<InplaceUnionOut>();
		u.u().addMonkey().setName(name);

		auto u2 = w.construct<InplaceUnionOut>();
		u2.u().addText().addT("foobar");

		auto t = w.construct<InplaceTextOut>();
		t.setId(45);
		t.addT("cake");

		auto b = w.construct<InplaceBytesOut>();
		b.setId(46);
		b.addB("hi", 2);

		auto l = w.construct<InplaceListOut>();
		l.setId(47);
		auto ll = l.addL(2);
		ll[0] = 24;
		ll[1] = 99;

		auto root = w.construct<InplaceRootOut>();
		root.setU(u).setU2(u2).setT(t).setB(b).setL(l);
		auto [data, size] = w.finalize(root);
		return !validateOut(data, size, argv[2]);
	} else if (!strcmp(argv[1], "in_inplace")) {
		auto o = readIn(argv[2]);
		scalgoproto::Reader r(o.data(), o.size());
		auto s = r.root<InplaceRootIn>();

		REQUIRE(s.hasU(), true);
		auto u = s.u();
		REQUIRE(u.u().isMonkey(), true);
		auto monkey = u.u().monkey();
		REQUIRE(monkey.hasName(), true);
		REQUIRE(monkey.name(), "nilson");

		REQUIRE(s.hasU2(), true);
		auto u2 = s.u2();
		REQUIRE(u2.u().isText(), true);
		auto u2t = u2.u().text();
		REQUIRE(u2t.hasT(), true);
		REQUIRE(u2t.t(), "foobar");
		
		REQUIRE(s.hasT(), true);
		auto t = s.t();
		REQUIRE(t.id(), 45);
		REQUIRE(t.hasT(), true);
		REQUIRE(t.t(), "cake");

		REQUIRE(s.hasB(), true);
		auto b = s.b();
		REQUIRE(b.id(), 46);
		REQUIRE(b.hasB(), true);
		REQUIRE(b.b().second,  2);
		REQUIRE(memcmp(b.b().first, "hi", 2), 0);

		REQUIRE(s.hasL(), true);
		auto l = s.l();
		REQUIRE(l.id(), 47);
		REQUIRE(l.hasL(), true);
		auto ll = l.l();
		REQUIRE(ll.size(), 2);
		REQUIRE(ll[0], 24);
		REQUIRE(ll[1], 99);
		return 0;		
	} else if (!strcmp(argv[1], "out_extend1")) {
		scalgoproto::Writer w;
		auto root = w.construct<Gen1Out>();
		root.setAa(77);
		auto [data, size] = w.finalize(root);
		return !validateOut(data, size, argv[2]);
	} else if (!strcmp(argv[1], "in_extend1")) {
		auto o = readIn(argv[2]);
		scalgoproto::Reader r(o.data(), o.size());
		auto s = r.root<Gen2In>();
		REQUIRE(s.aa(), 77);
		REQUIRE(s.bb(), 42);
		REQUIRE(s.hasU(), false);
		return 0;
	} else if (!strcmp(argv[1], "out_extend2")) {
		scalgoproto::Writer w;
		auto root = w.construct<Gen2Out>();
		root.setAa(80);
		root.setBb(81);
		auto cake = root.u().addCake();
		cake.setV(45);
		auto [data, size] = w.finalize(root);
		return !validateOut(data, size, argv[2]);
	} else if (!strcmp(argv[1], "in_extend2")) {
		auto o = readIn(argv[2]);
		scalgoproto::Reader r(o.data(), o.size());
		auto s = r.root<Gen3In>();
		REQUIRE(s.aa(), 80);
		REQUIRE(s.bb(), 81);
		REQUIRE(s.u().isCake(), true);
		REQUIRE(s.u().cake().v(), 45);
		REQUIREQ(s.e(), MyEnum::c);
		REQUIRE(s.s().x, 0);
		REQUIRE(s.s().y, 0);
		REQUIRE(s.s().z, 0);
		REQUIRE(s.b(), false);
		REQUIRE(s.u8(), 2);
		REQUIRE(s.u16(), 3);
		REQUIRE(s.u32(), 4);
		REQUIRE(s.u64(), 5);
		REQUIRE(s.i8(), 6);
		REQUIRE(s.i16(), 7);
		REQUIRE(s.i32(), 8);
		REQUIRE(s.i64(), 9);
		REQUIRE(s.f(), 10);
		REQUIRE(s.d(), 11);
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
		REQUIRE(s.hasMbytes(), false);
		REQUIRE(s.hasIntList(), false);
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
