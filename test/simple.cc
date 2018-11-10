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
		if (length != size) return false;
		std::vector<char> o;
		o.resize(size);
		is.read(o.data(), size);
		if (memcmp(o.data(), data, size)) return false;
	}
	return true;
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
		std::ifstream is(argv[2], std::ifstream::binary);
		is.seekg (0, is.end);
		auto length = is.tellg();
		is.seekg (0, is.beg);
		std::vector<char> o;
		o.resize(length);
		is.read(o.data(), length);

		scalgoproto::Reader r(o.data(), length);
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
	} else {
		return 1;
	}
	return 0;
}
