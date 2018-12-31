// -*- mode: c++; tab-width: 4; indent-tabs-mode: t; eval: (progn (c-set-style "stroustrup") (c-set-offset 'innamespace 0)); -*-
// vi:set ts=4 sts=4 sw=4 noet :

#include <iostream>
#include <fstream>
#include <cstdio>
#include <vector>
#include <cstring>

constexpr bool writeMode = false;

inline bool validateOut(const char * data, size_t size, const char * file) {
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

inline std::vector<char> readIn(const char * file) {
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
