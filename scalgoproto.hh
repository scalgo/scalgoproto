// -*- mode: c++; tab-width: 4; indent-tabs-mode: t; eval: (progn (c-set-style "stroustrup") (c-set-offset 'innamespace 0)); -*-
// vi:set ts=4 sts=4 sw=4 noet :
#include <cstdint>
#include <cstring>
#include <cassert>
#include <limits>
#include <cmath>
#include <stdexcept>
#include <utility>

namespace scalgoproto {

class MagicError: std::runtime_error {
public:
	MagicError() : std::runtime_error("MagicError") {}
};

class In {
protected:
	const char * data;
	uint32_t offset;
	uint32_t size;

	In(const char * data, uint32_t offset, uint32_t size) : data(data), offset(offset), size(size) {};

	template <typename T, uint32_t o>
	T getInner_(T def) const noexcept {
		if (o + sizeof(T) > size) return def;
		T ans;
		memcpy(&ans, data + offset + o, sizeof(T));
		return ans;
	}

	template <typename T, uint32_t o>
	T getInner_() const noexcept {
		T ans;
		if (o + sizeof(T) > size)
			memset(&ans, 0, sizeof(T));
		else
			memcpy(&ans, data + offset+ o, sizeof(T));
		return ans;
	}

	template <typename T, uint32_t o>
	T getTable_() const noexcept {
		uint32_t off;
		assert(o + 8 <= size);
		memcpy(&off, data+offset + o, 4);
		uint32_t size = T::readSize_(data, off);
		return T(data, off+8, size);
	}

	template <typename T, uint32_t o>
	T getVLTable_() const noexcept {
		return T(data, offset+size, getInner_<std::uint32_t, o>());
	}

	template <uint32_t o, uint8_t bit, uint8_t def>
	uint8_t getBit_() const noexcept {
		if (o < size)
			return *(const uint8_t *)(data + offset + o) & 1 << bit;
		return def;
	}

	static uint32_t readSize_(const char * data, uint32_t offset, uint32_t magic) {
		uint32_t word;
		memcpy(&word, data+offset, 4);
		if (word != magic) throw MagicError();
		memcpy(&word, data+offset+4, 4);
		return word;
	}
};

class Reader {
private:
	const char * data;
public:
	Reader(const char * data, size_t size): data(data) {}

	template <typename T>
	T root() {
		uint32_t magic, offset;
		memcpy(&magic, data, 4);
		memcpy(&offset, data+4, 4);
		if (magic != 0xB5C0C4B3)
			throw MagicError();
		uint32_t size = T::readSize_(data, offset);
		return T(data, offset+8, size);
	}
};

class Out;

class Writer {
private:
	char * data = nullptr;
	size_t size = 0;
	size_t capacity = 0;
	friend class Out;

	void reserve(size_t size) {
		if (size <= capacity) return;
		data = (char *)realloc(data, size);
		capacity = size;
	}

	void expand(uint32_t s) {
		while (size + s > capacity) reserve(capacity * 2);
		size += s;
	}

	template <typename T>
	void write(const T & t, uint32_t offset) {
		memcpy(data + offset, &t, sizeof(T));
	}
public:
	Writer(size_t capacity=256): size(8) {reserve(capacity);}
	~Writer() {
		if (data) free(data);
		data = nullptr;
		size = 0;
		capacity = 0;
	}
	
	void clear() {
		size = 8;
	}
  
	inline std::pair<const char *, size_t> finalize(const Out & root);
	
	template <typename T>
	T construct() {
		return T(*this, true);
	}

	
};

class Out {
protected:
	friend class Writer;

	Writer & writer;
	uint32_t offset;

	Out(Writer & writer, bool withHeader, std::uint32_t magic, const char * def, std::uint32_t size): writer(writer), offset(writer.size) {
		if (withHeader) {
			writer.expand(8);
			writer.write(magic, offset);
			writer.write(size, offset+4);
			offset += 8;
		}
		writer.expand(size);
		memcpy(writer.data + offset, def, size);
	}

	template <typename T, uint32_t o>
	void setInner_(const T & t) {
		writer.write(t, offset + o);
	}

	template <uint32_t o, uint8_t b>
	void setBit_() {
		*(uint8_t *)(writer.data + offset + o) |= (1 << b);
	}

	template <uint32_t o, uint8_t b>
	void unsetBit_() {
		*(uint8_t *)(writer.data + offset + o) &= ~(1 << b);
	}
	
	template <typename T, uint32_t offset>
  	T getInner_() const noexcept {
		T ans;
		memcpy(&ans, writer.data + this->offset + offset , sizeof(T));
		return ans;
	}
	
	template <typename T, uint32_t offset>
	void setTable_(T t) noexcept {
		setInner_<std::uint32_t, offset>(t.offset-8);
	}
};


std::pair<const char *, size_t> Writer::finalize(const Out & root) {
	write((std::uint32_t)0xB5C0C4B3, 0);
	write(root.offset - 8, 4);
	return std::make_pair(data, size);
}

} //namespace scalgoproto
