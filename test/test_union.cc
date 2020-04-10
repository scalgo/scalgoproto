// -*- mode: c++; tab-width: 4; indent-tabs-mode: t; eval: (progn (c-set-style "stroustrup") (c-set-offset 'innamespace 0)); -*-
// vi:set ts=4 sts=4 sw=4 noet :

#include "test.hh"
#include "union.hh"

scalgoproto::Bytes forCopy(scalgoproto::Writer & w) {
	auto root = w.construct<Table3Out>();	

	auto v1 = root.addV1();
	v1.a().addV1("ctext1");
	v1.b().addV1("ctext2");

	auto v2 = root.addV2();
	v2.a().addV2("cbytes1", 7);
	v2.b().addV2(std::pair("cbytes2", 7));
	
	auto v3 = root.addV3();
	v3.a().addV3().setA(101);
	v3.b().addV3().setA(102);

	auto v4 = root.addV4();
	v4.a().addV4().setA(103);
	v4.b().addV4().setA(104);

	auto v5 = root.addV5();
	v5.a().addV5(1)[0] = "ctext3";
	v5.b().addV5(1)[0] = "ctext4";

	auto v6 = root.addV6();
	v6.a().addV6(1)[0] = std::pair("cbytes3", 7);
	v6.b().addV6(1)[0] = w.constructBytes("cbytes4", 7);

	auto v7 = root.addV7();
	v7.a().addV7(1).add(0).setA(105);
	v7.b().addV7(1).add(0).setA(106);
	
	auto v8 = root.addV8();
	v8.a().addV8(1).add(0).setA(107);
	v8.b().addV8(1).add(0).setA(108);
	
	auto v9 = root.addV9();
	v9.a().addV9(1)[0] = 109;
	v9.b().addV9(1)[0] = 110;

	auto v10 = root.addV10();
	v10.a().addV10(1)[0] = true;
	v10.b().addV10(1)[0] = true;

	return w.finalize(root);
	
}

int main(int, char ** argv) {
	bool useMmap = false;
	if (!strcmp(argv[1], "out")) {
		scalgoproto::Writer win;
		scalgoproto::Reader r(forCopy(win));
		auto i = r.root<Table3In>();

		auto w = getTestWriter(argv[2], useMmap);
		auto root = w.construct<Table3Out>();
		
		auto v1 = root.addV1();
		v1.a().addV1("text1");
		v1.b().addV1("text2");
		v1.c().setV1(w.constructText("text3"));
		v1.d().addV1(i.v1().a().v1());
		v1.e().addV1(i.v1().b().v1());

		auto v2 = root.addV2();
		v2.a().addV2("bytes1", 6);
		v2.b().addV2(scalgoproto::Bytes("bytes2", 6));
		v2.c().setV2(w.constructBytes("bytes3", 6));
		v2.d().addV2(i.v2().a().v2());
		v2.e().addV2(i.v2().b().v2());

		auto v3 = root.addV3();
		v3.a().addV3().setA(1);
		v3.b().addV3().setA(2);
		auto t3 = w.construct<Table1Out>();
		t3.setA(3);
		v3.c().setV3(t3);
		v3.d().addV3(i.v3().a().v3());
		v3.e().addV3(i.v3().b().v3());

		auto v4 = root.addV4();
		v4.a().addV4().setA(4);
		v4.b().addV4().setA(5);
		auto t4 = w.construct<Union1V4Out>();
		t4.setA(6);
		v4.c().setV4(t4);
		v4.d().addV4(i.v4().a().v4());
		v4.e().addV4(i.v4().b().v4());

		auto v5 = root.addV5();
		v5.a().addV5(1)[0] = "text4";
		v5.b().addV5(1)[0] = "text5";
		auto t5 = w.constructTextList(1);
		t5[0] = "text6";
		v5.c().setV5(t5);
		v5.d().addV5(i.v5().a().v5());
		v5.e().addV5(i.v5().b().v5());

		auto v6 = root.addV6();
		v6.a().addV6(1)[0] = scalgoproto::Bytes("bytes4", 6);
		v6.b().addV6(1)[0] = scalgoproto::Bytes("bytes5", 6);
		auto t6 = w.constructBytesList(1);
		t6[0] = scalgoproto::Bytes("bytes6", 6);
		v6.c().setV6(t6);
		v6.d().addV6(i.v6().a().v6());
		v6.e().addV6(i.v6().b().v6());

		auto v7 = root.addV7();
		v7.a().addV7(1).add(0).setA(7);
		v7.b().addV7(1).add(0).setA(8);
		auto t7 = w.constructList<Table1Out>(1);
		t7.add(0).setA(9);
		v7.c().setV7(t7);
		v7.d().addV7(i.v7().a().v7());
		v7.e().addV7(i.v7().b().v7());

		auto v8 = root.addV8();
		v8.a().addV8(1).add(0).setA(10);
		v8.b().addV8(1).add(0).setA(11);
		auto t8 = w.constructList<Union1V8Out>(1);
		t8.add(0).setA(12);
		v8.c().setV8(t8);
		v8.d().addV8(i.v8().a().v8());
		v8.e().addV8(i.v8().b().v8());

		auto v9 = root.addV9();
		v9.a().addV9(1)[0] = 13;
		v9.b().addV9(1)[0] = 14;
		auto t9 = w.constructList<uint32_t>(1);
		t9[0] = 15;
		v9.c().setV9(t9);
		v9.d().addV9(i.v9().a().v9());
		v9.e().addV9(i.v9().b().v9());

		auto v10 = root.addV10();
		v10.a().addV10(1)[0] = true;
		v10.b().addV10(1)[0] = false;
		auto t10 = w.constructList<bool>(1);
		t10[0] = true;
		v10.c().setV10(t10);
		v10.d().addV10(i.v10().a().v10());
		v10.e().addV10(i.v10().b().v10());

		auto [data, size] = w.finalize(root);
		return !validateOut(data, size, argv[2], useMmap);
	} else if (!strcmp(argv[1], "in")) {
		auto o = readIn(argv[2]);
		scalgoproto::Reader r(o.data(), o.size());
		auto i = r.root<Table3In>();

		REQUIRE(i.hasV1(), true);
		auto v1 = i.v1();
		REQUIRE2(v1.hasA() && v1.a().isV1(), v1.a().v1(), "text1");
		REQUIRE2(v1.hasB() && v1.b().isV1(), v1.b().v1(), "text2");
		REQUIRE2(v1.hasC() && v1.c().isV1(), v1.c().v1(), "text3");
		REQUIRE2(v1.hasD() && v1.d().isV1(), v1.d().v1(), "ctext1");
		REQUIRE2(v1.hasE() && v1.e().isV1(), v1.e().v1(), "ctext2");

		REQUIRE(i.hasV2(), true);
		auto v2 = i.v2();
		REQUIRE2(v2.hasA() && v2.a().isV2(), v2.a().v2(), scalgoproto::Bytes("bytes1", 6));
		REQUIRE2(v2.hasB() && v2.b().isV2(), v2.b().v2(), scalgoproto::Bytes("bytes2", 6));
		REQUIRE2(v2.hasC() && v2.c().isV2(), v2.c().v2(), scalgoproto::Bytes("bytes3", 6));
		REQUIRE2(v2.hasD() && v2.d().isV2(), v2.d().v2(), scalgoproto::Bytes("cbytes1", 7));
		REQUIRE2(v2.hasE() && v2.e().isV2(), v2.e().v2(), scalgoproto::Bytes("cbytes2", 7));

		REQUIRE(i.hasV3(), true);
		auto v3 = i.v3();
		REQUIRE2(v3.hasA() && v3.a().isV3(), v3.a().v3().a(), 1);
		REQUIRE2(v3.hasB() && v3.b().isV3(), v3.b().v3().a(), 2);
		REQUIRE2(v3.hasC() && v3.c().isV3(), v3.c().v3().a(), 3);
		REQUIRE2(v3.hasD() && v3.d().isV3(), v3.d().v3().a(), 101);
		REQUIRE2(v3.hasE() && v3.e().isV3(), v3.e().v3().a(), 102);

		REQUIRE(i.hasV4(), true);
		auto v4 = i.v4();
		REQUIRE2(v4.hasA() && v4.a().isV4(), v4.a().v4().a(), 4);
		REQUIRE2(v4.hasB() && v4.b().isV4(), v4.b().v4().a(), 5);
		REQUIRE2(v4.hasC() && v4.c().isV4(), v4.c().v4().a(), 6);
		REQUIRE2(v4.hasD() && v4.d().isV4(), v4.d().v4().a(), 103);
		REQUIRE2(v4.hasE() && v4.e().isV4(), v4.e().v4().a(), 104);

		REQUIRE(i.hasV5(), true);
		auto v5 = i.v5();
		REQUIRE2(v5.hasA() && v5.a().isV5() && v5.a().v5().size() == 1, v5.a().v5()[0], "text4");
		REQUIRE2(v5.hasB() && v5.b().isV5() && v5.b().v5().size() == 1, v5.b().v5()[0], "text5");
		REQUIRE2(v5.hasC() && v5.c().isV5() && v5.c().v5().size() == 1, v5.c().v5()[0], "text6");
		REQUIRE2(v5.hasD() && v5.d().isV5() && v5.d().v5().size() == 1, v5.d().v5()[0], "ctext3");
		REQUIRE2(v5.hasE() && v5.e().isV5() && v5.e().v5().size() == 1, v5.e().v5()[0], "ctext4");

		REQUIRE(i.hasV6(), true);
		auto v6 = i.v6();
		REQUIRE2(v6.hasA() && v6.a().isV6() && v6.a().v6().size() == 1, v6.a().v6()[0], scalgoproto::Bytes("bytes4", 6));
		REQUIRE2(v6.hasB() && v6.b().isV6() && v6.b().v6().size() == 1, v6.b().v6()[0], scalgoproto::Bytes("bytes5", 6));
		REQUIRE2(v6.hasC() && v6.c().isV6() && v6.c().v6().size() == 1, v6.c().v6()[0], scalgoproto::Bytes("bytes6", 6));
		REQUIRE2(v6.hasD() && v6.d().isV6() && v6.d().v6().size() == 1, v6.d().v6()[0], scalgoproto::Bytes("cbytes3", 7));
		REQUIRE2(v6.hasE() && v6.e().isV6() && v6.e().v6().size() == 1, v6.e().v6()[0], scalgoproto::Bytes("cbytes4", 7));
		
		REQUIRE(i.hasV7(), true);
		auto v7 = i.v7();
		REQUIRE2(v7.hasA() && v7.a().isV7() && v7.a().v7().size() == 1, v7.a().v7()[0].a(), 7);
		REQUIRE2(v7.hasB() && v7.b().isV7() && v7.b().v7().size() == 1, v7.b().v7()[0].a(), 8);
		REQUIRE2(v7.hasC() && v7.c().isV7() && v7.c().v7().size() == 1, v7.c().v7()[0].a(), 9);
		REQUIRE2(v7.hasD() && v7.d().isV7() && v7.d().v7().size() == 1, v7.d().v7()[0].a(), 105);
		REQUIRE2(v7.hasE() && v7.e().isV7() && v7.e().v7().size() == 1, v7.e().v7()[0].a(), 106);

		REQUIRE(i.hasV8(), true);
		auto v8 = i.v8();
		REQUIRE2(v8.hasA() && v8.a().isV8() && v8.a().v8().size() == 1, v8.a().v8()[0].a(), 10);
		REQUIRE2(v8.hasB() && v8.b().isV8() && v8.b().v8().size() == 1, v8.b().v8()[0].a(), 11);
		REQUIRE2(v8.hasC() && v8.c().isV8() && v8.c().v8().size() == 1, v8.c().v8()[0].a(), 12);
		REQUIRE2(v8.hasD() && v8.d().isV8() && v8.d().v8().size() == 1, v8.d().v8()[0].a(), 107);
		REQUIRE2(v8.hasE() && v8.e().isV8() && v8.e().v8().size() == 1, v8.e().v8()[0].a(), 108);

		REQUIRE(i.hasV9(), true);
		auto v9 = i.v9();
		REQUIRE2(v9.hasA() && v9.a().isV9() && v9.a().v9().size() == 1, v9.a().v9()[0], 13);
		REQUIRE2(v9.hasB() && v9.b().isV9() && v9.b().v9().size() == 1, v9.b().v9()[0], 14);
		REQUIRE2(v9.hasC() && v9.c().isV9() && v9.c().v9().size() == 1, v9.c().v9()[0], 15);
		REQUIRE2(v9.hasD() && v9.d().isV9() && v9.d().v9().size() == 1, v9.d().v9()[0], 109);
		REQUIRE2(v9.hasE() && v9.e().isV9() && v9.e().v9().size() == 1, v9.e().v9()[0], 110);

		REQUIRE(i.hasV10(), true);
		auto v10 = i.v10();
		REQUIRE2(v10.hasA() && v10.a().isV10() && v10.a().v10().size() == 1, v10.a().v10()[0], true);
		REQUIRE2(v10.hasB() && v10.b().isV10() && v10.b().v10().size() == 1, v10.b().v10()[0], false);
		REQUIRE2(v10.hasC() && v10.c().isV10() && v10.c().v10().size() == 1, v10.c().v10()[0], true);
		REQUIRE2(v10.hasD() && v10.d().isV10() && v10.d().v10().size() == 1, v10.d().v10()[0], true);
		REQUIRE2(v10.hasE() && v10.e().isV10() && v10.e().v10().size() == 1, v10.e().v10()[0], true);

		return 0;
	}
	return 1;
}


