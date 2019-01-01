// -*- mode: c++; tab-width: 4; indent-tabs-mode: t; eval: (progn (c-set-style "stroustrup") (c-set-offset 'innamespace 0)); -*-
// vi:set ts=4 sts=4 sw=4 noet :

#include "test.hh"

#include "union.hh"

Table3In forCopy(scalgoproto::Writer & w) {
	auto root = w.construct<Table3Out>();	

	auto v1 = root.addV1();
	v1.a().addV1("text1");
	v1.b().addV1("text2");

	auto v2 = root.addV2();
	v2.a().addV2("bytes1", 6);
	v2.b().addV2(std::pair("bytes2", 6));
	
	auto v3 = root.addV3();
	v3.a().addV3().setA(1);
	v3.b().addV3().setA(2);

	auto v4 = root.addV4();
	v4.a().addV4().setA(3);
	v4.b().addV4().setA(4);

	auto v5 = root.addV5();
	v5.a().addV5(1)[0] = "text3";
	v5.b().addV5(1)[0] = "text4";

	auto v6 = root.addV6();
	v6.a().addV6(1)[0] = std::pair("bytes5", 6);
	v6.b().addV6(1)[0] = w.constructBytes("bytes4", 6);

	auto v7 = root.addV7();
	v7.a().addV7(1).add(0).setA(1);
	v7.b().addV7(1).add(0).setA(2);
	
	auto v8 = root.addV8();
	v8.a().addV8(1).add(0).setA(3);
	v8.b().addV8(1).add(0).setA(4);
	
	auto v9 = root.addV9();
	v9.a().addV9(1)[0] = 12;
	v9.b().addV9(1)[0] = 12;

	auto v10 = root.addV10();
	v10.a().addV10(1)[0] = true;
	v10.b().addV10(1)[0] = true;

	scalgoproto::Reader r(w.finalize(root));
	return r.root<Table3In>();
}

int main(int, char ** argv) {
	if (!strcmp(argv[1], "out")) {
		scalgoproto::Writer win;
		auto i = forCopy(win);
		
		scalgoproto::Writer w;
		auto root = w.construct<Table3Out>();
		
		auto v1 = root.addV1();
		v1.a().addV1("text1");
		v1.b().addV1("text2");
		v1.c().setV1(w.constructText("text3"));
		//v1.d().addV1(i.v1().a().v1());
		//v1.e().addV1(i.v1().b().v1());

		auto [data, size] = w.finalize(root);
		return !validateOut(data, size, argv[2]);
	} else if (!strcmp(argv[1], "in")) {
		// scalgoproto::Writer w;
		// auto s = w.construct<SimpleOut>();
		// s.setE(MyEnum::c);
		// s.setS({MyEnum::d, {42, 27.0, true}, false, 8, 9, 10, 11, -8, -9, -10, -11, 27.0, 22.0});
		// s.setB(true);
		// s.setU8(242).setU16(4024).setU32(124474).setU64(5465778);
		// s.setI8(-40).setI16(4025).setI32(124475).setI64(5465779);
		// s.setF(2.0).setD(3.0);
		// s.setOs({43, 28.0, false});
		// s.setOb(false);
		// s.setOu8(252).setOu16(4034).setOu32(124464).setOu64(5465768);
		// s.setOi8(-60).setOi16(4055).setOi32(124465).setOi64(5465729);
		// s.setOf(5.0).setOd(6.4);
		// auto [data, size] = w.finalize(s);
		// return !validateOut(data, size, argv[2]);
	}
	return 1;
}


