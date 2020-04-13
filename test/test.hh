// -*- mode: c++; tab-width: 4; indent-tabs-mode: t; eval: (progn (c-set-style "stroustrup") (c-set-offset 'innamespace 0)); -*-
// vi:set ts=4 sts=4 sw=4 noet :

#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <iostream>
#include <scalgoproto.hh>
#include <sys/stat.h>
#include <sys/types.h>
#include <vector>

// Change to true to generate new ground truths for committing.
constexpr bool writeMode = false;

inline scalgoproto::Writer getTestWriter(const char * file, bool useMmap) {
	if (!useMmap) return scalgoproto::Writer();
	std::string tempFile = file;
	tempFile += "~";
	auto backing = std::make_unique<scalgoproto::FileWriterBacking>();
	if (backing->open(tempFile.c_str())) {
		std::cout << "open+mmap of " << tempFile << " failed with errno=" << errno << std::endl;
		std::exit(1);
	}
	return scalgoproto::Writer(256, std::move(backing));
}

inline bool validateOut(const char * data, size_t size, const char * file, bool useMmap) {
	if (useMmap && writeMode) {
		std::string tempFile = file;
		tempFile += "~";
		if (::rename(tempFile.c_str(), file)) {
			std::cout << "rename " << tempFile << " failed with errno=" << errno << std::endl;
			return false;
		}
		return true;
	}
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

bool operator!=(const std::pair<const char *, size_t> & l, const std::pair<const char *, size_t> & r) {
	if (l.second != r.second) return true;
	return memcmp(l.first, r.first, l.second) != 0;
}

std::ostream & operator<<(std::ostream & o, std::pair<const char *, size_t> i) {
	char b[123];
	b[0] = 'b';
	b[1] = '"';
	memcpy(b+2, i.first, i.second);
	b[i.second+2] = '"';
	b[i.second+3] = '\0';
	return o << b;
}

#define xstr(a) str(a)
#define str(a) #a
#define REQUIRE(e, v) if ((e) != (v)) {std::cout << "Error '" << str(e) << "' gave " << (e) << " expected " << v << std::endl; return 1;}
#define REQUIRE2(b, e, v) \
if (!b) {std::cout << "Error '" << str(b) << "' must be true " << v << std::endl; return 1;} \
if ((e) != (v)) {std::cout << "Error '" << str(e) << "' gave " << (e) << " expected " << v << std::endl; return 1;}

#define REQUIREQ(e, v) if ((e) != (v)) {std::cout << "Error '" << str(e) << "' wrong result" << std::endl; return 1;}
