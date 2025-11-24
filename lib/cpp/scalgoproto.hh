// -*- mode: c++; tab-width: 4; indent-tabs-mode: t; eval: (progn (c-set-style "stroustrup") (c-set-offset 'innamespace 0)); -*-
// vi:set ts=4 sts=4 sw=4 noet :
#ifndef __SCALGOPROTO_HH__
#define __SCALGOPROTO_HH__
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <limits>
#include <memory>
#include <stdexcept>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <utility>

namespace scalgoproto {

static constexpr std::uint32_t ROOTMAGIC = 0xB5C0C4B3;
static constexpr std::uint32_t LISTMAGIC = 0x3400BB46;
static constexpr std::uint32_t TEXTMAGIC = 0xD812C8F5;
static constexpr std::uint32_t BYTESMAGIC = 0xDCDBBE10;
static constexpr std::uint32_t DIRECTLISTMAGIC = 0xE2C6CC05;

class Out;
class UnionOut;
class TableOut;
class InplaceUnionOut;
class Writer;
class In;
class TableIn;
class Reader;
template <bool>
class UnionIn;
struct EnumTag;
struct BoolTag;
struct PodTag;
struct TableTag;
struct ListTag;
struct TextTag;
struct BytesTag;
struct UnionTag;
struct UnknownTag;

using Bytes = std::pair<const char *, size_t>;

template <typename T>
class ListOut;

template <typename T>
class DirectListOut;

template <typename T>
class DirectListIn;

template <typename, typename>
class ListAccessHelp;

class Error : public std::runtime_error {
public:
	Error(const char * what)
		: std::runtime_error(what) {}
};

class MagicError: public Error {
public:
	uint32_t got;
	uint32_t expected;

	MagicError(uint32_t got, uint32_t expected): Error("magic error"), got(got), expected(expected) {}
};

class OutOfBoundsError: public Error {
public:
	OutOfBoundsError(): Error("out of bounds access") {}
};

class InvalidTextError: public Error {
public:
	InvalidTextError(): Error("text not null terminated or not utf-8") {}
};

class TooLargeItemSizeError: public Error {
public:
	size_t size;
	TooLargeItemSizeError(size_t size) : Error("too large item size"), size(size) {}
};

class TextOut {
	friend class Writer;
	friend class Out;
	template <typename, typename>
	friend class ListAccessHelp;

protected:
	std::uint64_t offset_;
};

class BytesOut {
	friend class Writer;
	friend class Out;
	template <typename, typename>
	friend class ListAccessHelp;

protected:
	std::uint64_t offset_;
};

template <typename T>
struct MetaMagic {
	using t = UnknownTag;
};
template <>
struct MetaMagic<bool> {
	using t = BoolTag;
};
template <>
struct MetaMagic<std::uint8_t> {
	using t = PodTag;
};
template <>
struct MetaMagic<std::uint16_t> {
	using t = PodTag;
};
template <>
struct MetaMagic<std::uint32_t> {
	using t = PodTag;
};
template <>
struct MetaMagic<std::uint64_t> {
	using t = PodTag;
};
template <>
struct MetaMagic<std::int8_t> {
	using t = PodTag;
};
template <>
struct MetaMagic<std::int16_t> {
	using t = PodTag;
};
template <>
struct MetaMagic<std::int32_t> {
	using t = PodTag;
};
template <>
struct MetaMagic<std::int64_t> {
	using t = PodTag;
};
template <>
struct MetaMagic<float> {
	using t = PodTag;
};
template <>
struct MetaMagic<double> {
	using t = PodTag;
};

template <typename T>
struct EnumSize {};

template <typename Tag, typename T>
class ListAccessHelp {};

template <std::uint64_t mult>
std::uint64_t computeSize(std::uint64_t v) {
	if constexpr (mult == 0) return (v + 7) >> 3;
	return v * mult;
};

struct Ptr {
	const char * start;
	std::uint64_t size;
};

static inline std::uint64_t read48_(const char * data) noexcept {
	std::uint64_t ans = 0;
	memcpy(&ans, data, 6);
	return ans;
}

static inline void write48_(char * data, std::uint64_t v) noexcept {
	assert((v & 0xFFFF000000000000ul) == 0);
	memcpy(data, &v, 6);
}

class Reader {
private:
	friend class In;
	friend class TableIn;
	template <typename, typename>
	friend class ListAccessHelp;
	template <bool>
	friend class UnionIn;
	template <typename>
	friend class DirectListIn;

	const char * data;
	size_t size;

	template <std::uint32_t magic, std::uint64_t mult = 1, std::uint64_t add = 0>
	Ptr getPtr_(std::uint64_t offset) const {
		// Validate that the offset is within the reader boundary
		if (offset + 10 > size) throw OutOfBoundsError();
		if (offset == 0) return Ptr{data, 0};
		// Check that we have the right magic
		std::uint32_t read_magic;
		memcpy(&read_magic, data + offset, 4);
		if (read_magic != magic) throw MagicError(read_magic, magic);
		// Read size and check that the object is within the reader boundary
		// mult * 2^48 + 2^48 + 8 + 1 >= 2^64
		static_assert(mult < 65534,
					  "Structs of a size greater than 65534 are currently not supported");
		const std::uint64_t read_size = read48_(data + offset + 4);
		if (computeSize<mult>(read_size) + offset + 10 + add > size) throw OutOfBoundsError();
		return Ptr{data + offset + 10, read_size};
	}

	template <std::uint64_t mult = 1, std::uint64_t add = 0>
	Ptr getPtrInplace_(const char * start, std::uint64_t s) const {
		static_assert(mult < 65534,
					  "Structs of a size greater than 65534 are currently not supported");
		if (start + computeSize<mult>(s) + add > data + size) throw OutOfBoundsError();
		return Ptr{start, s};
	}

	void validateTextPtr_(Ptr p) const {
		if (p.start[p.size] != '\0') throw InvalidTextError();
	}

public:
	Reader(const char * data, size_t size) noexcept
		: data(data)
		, size(size){};

	explicit Reader(scalgoproto::Bytes bytes) noexcept
		: data(bytes.first)
		, size(bytes.second){};

	template <typename T>
	T root() const {
		std::uint32_t magic;
		memcpy(&magic, data, 4);
		std::uint64_t offset = read48_(data + 4);
		if (magic != ROOTMAGIC) throw MagicError(magic, ROOTMAGIC);
		return T(this, getPtr_<T::MAGIC>(offset));
	}
};

class In {
protected:
	template <typename T, typename... TT>
	static T getObject_(TT &&... tt) noexcept(noexcept(T(std::forward<TT>(tt)...))) {
		return T(std::forward<TT>(tt)...);
	}

	static std::string_view getText_(const Reader * reader, Ptr p) {
		if (p.size == 0) return std::string_view("");
		reader->validateTextPtr_(p);
		return std::string_view(p.start, p.size);
	}

	static Bytes getBytes_(Ptr p) noexcept { return Bytes(p.start, p.size); }

	template <typename T>
	static std::pair<const T *, size_t> getListRaw_(Ptr p) noexcept {
		return {reinterpret_cast<const T *>(p.start), (size_t)p.size};
	}
};

template <typename T>
struct ListAccessHelp<BoolTag, T> : public In {
	using IN = bool;
	static constexpr bool optional = false;
	static constexpr bool hasAdd = false;
	static constexpr std::uint64_t mult = 0;
	static constexpr int def = 0;
	static bool get(const Reader *, const char * start, std::uint64_t index) noexcept {
		const size_t bit = index & 7;
		const size_t byte = index >> 3;
		std::uint8_t v;
		memcpy(&v, start + byte, 1);
		return (v >> bit) & 1;
	}

	class Setter {
		template <typename>
		friend class ListOut;
		char * const byte;
		const size_t bit;
		Setter(Writer & writer, std::uint64_t offset, std::uint64_t index);

	public:
		void operator=(bool value) noexcept {
			std::uint8_t v;
			memcpy(&v, byte, 1);
			v = value ? v | (1 << bit) : (v & ~(1 << bit));
			memcpy(byte, &v, 1);
		}
	};

	static void copy(Writer & writer, std::uint64_t offset, const Reader *,
					 const char * start, std::uint64_t size);
};

template <typename T>
struct ListAccessHelp<PodTag, T> : public In {
	using IN = T;
	static constexpr bool optional = false;
	static constexpr bool hasAdd = false;
	static constexpr uint64_t mult = sizeof(T);
	static constexpr int def = 0;
	static T get(const Reader *, const char * start, std::uint64_t index) noexcept {
		T ans;
		memcpy(&ans, start + index * sizeof(T), sizeof(T));
		return ans;
	}
	class Setter {
		template <typename>
		friend class ListOut;
		char * location;
		Setter(Writer & writer, std::uint64_t offset, std::uint64_t index);

	public:
		void operator=(const T & value) noexcept { memcpy(location, &value, sizeof(T)); }
	};

	static void copy(Writer & writer, std::uint64_t offset, const Reader *,
					 const char * start, std::uint64_t size);
};

template <typename T>
struct ListAccessHelp<EnumTag, T> : public In {
	using IN = T;
	static constexpr bool optional = true;
	static constexpr bool hasAdd = false;
	static constexpr std::uint64_t mult = 1;
	static constexpr int def = 255;
	static bool has(const char * start, std::uint64_t index) noexcept {
		return ((const unsigned char *)(start))[index] < EnumSize<T>::size();
	}
	static T get(const Reader *, const char * start, std::uint64_t index) noexcept {
		T ans;
		memcpy(&ans, start + index * sizeof(T), sizeof(T));
		return ans;
	}

	class Setter {
		template <typename>
		friend class ListOut;
		Setter(Writer & writer, std::uint64_t offset, std::uint64_t index);
		char * const location;

	public:
		void operator=(const T & value) noexcept { memcpy(location, &value, sizeof(T)); }
	};

	static void copy(Writer & writer, std::uint64_t offset, const Reader *,
					 const char * start, std::uint64_t size);
};

template <typename T>
struct ListAccessHelp<TextTag, T> : public In {
	using IN = std::string_view;
	static constexpr bool optional = true;
	static constexpr bool hasAdd = false;
	static constexpr std::uint64_t mult = 6;
	static constexpr int def = 0;

	static bool has(const char * start, std::uint64_t index) noexcept {
		std::uint64_t off = read48_(start + index * 6);
		return off != 0;
	}
	static std::string_view get(const Reader * reader, const char * start,
								std::uint64_t index) {
		std::uint64_t off = read48_(start + index * 6);
		Ptr p = reader->getPtr_<TEXTMAGIC, 1, 1>(off);
		return getText_(reader, p);
	}
	class Setter {
		template <typename>
		friend class ListOut;
		Setter(Writer & writer, std::uint64_t offset, std::uint64_t index);
		Writer & writer;
		std::uint64_t offset;

	public:
		T operator=(const T & value) noexcept;
		TextOut operator=(std::string_view t);
	};

	static void copy(Writer & writer, std::uint64_t offset, const Reader *,
					 const char * start, std::uint64_t size);
};

template <typename T>
struct ListAccessHelp<BytesTag, T> : public In {
	using IN = Bytes;
	static constexpr bool optional = true;
	static constexpr bool hasAdd = false;
	static constexpr std::uint64_t mult = 6;
	static constexpr int def = 0;
	static bool has(const char * start, std::uint64_t index) noexcept {
		std::uint64_t off = read48_(start + index * 6);
		return off != 0;
	}
	static Bytes get(const Reader * reader, const char * start,
					 std::uint64_t index) {
		std::uint64_t off = read48_(start + index * 6);
		return getBytes_(reader->getPtr_<BYTESMAGIC>(off));
	}
	class Setter {
		template <typename>
		friend class ListOut;
		Setter(Writer & writer, std::uint64_t offset, std::uint64_t index);
		char * const location;
		Writer & writer;

	public:
		void operator=(const T & value) noexcept { write48_(location, value.offset_); }
		void operator=(Bytes bytes) noexcept;
	};

	static void copy(Writer & writer, std::uint64_t offset, const Reader *,
					 const char * start, std::uint64_t size);
};

template <typename T>
struct ListAccessHelp<TableTag, T> : public In {
	using IN = typename T::IN;
	static constexpr bool optional = true;
	static constexpr bool hasAdd = true;
	static constexpr std::uint64_t mult = 6;
	static constexpr int def = 0;
	static bool has(const char * start, std::uint64_t index) noexcept {
		std::uint64_t off = read48_(start + index * 6);
		return off != 0;
	}

	static T get(const Reader * reader, const char * start,
				 std::uint64_t index) {
		std::uint64_t off = read48_(start + index * 6);
		return getObject_<T>(reader, reader->getPtr_<T::MAGIC>(off));
	}

	static T add(Writer & w, std::uint64_t offset, std::uint64_t index);

	class Setter {
		template <typename>
		friend class ListOut;
		Setter(Writer & writer, std::uint64_t offset, std::uint64_t index);
		char * const location;

	public:
		void operator=(const T & value) noexcept {
			write48_(location, value.offset_ - 10);
		}
	};

	static void copy(Writer & writer, std::uint64_t offset, const Reader *,
					 const char * start, std::uint64_t size);
};

template <typename T>
struct ListAccessHelp<UnionTag, T> : public In {
	using IN = typename T::IN;
	static constexpr bool optional = true;
	static constexpr bool hasAdd = false;

	static constexpr std::uint64_t mult = 8;
	static constexpr int def = 0;
	static bool has(const char * start, std::uint64_t index) noexcept {
		std::uint16_t type;
		memcpy(&type, start + index * 8, 2);
		return type != 0;
	}

	static T get(const Reader * reader, const char * start,
				 std::uint64_t index) noexcept(noexcept(getObject_<T>(reader, uint16_t(), uint64_t()))) {
		std::uint16_t type;
		memcpy(&type, start + index * 8, 2);
		std::uint64_t off = read48_(start + index * 8 + 2);
		return getObject_<T>(reader, type, off);
	}

	static void copy(Writer & writer, std::uint64_t offset, const Reader *,
					 const char * start, std::uint64_t size);

	using Setter = T;
};

template <typename T>
using ListAccess = ListAccessHelp<typename MetaMagic<T>::t, T>;

template <typename T>
class ListIn;

template <typename T>
class ListInIterator {
private:
	const Reader * reader;
	const char * start;
	std::uint64_t index;
	using A = ListAccess<T>;
	friend class ListIn<T>;
	ListInIterator(const Reader * reader, const char * start,
				   std::uint64_t index) noexcept
		: reader(reader)
		, start(start)
		, index(index) {}

public:
	using value_type = T;
	using size_type = std::size_t;
	using difference_type = std::ptrdiff_t;
	using pointer = T *;
	using reference = T &;
	using iterator_category = std::random_access_iterator_tag;

	ListInIterator(const ListInIterator &) = default;
	ListInIterator(ListInIterator &&) = default;
	ListInIterator & operator=(const ListInIterator &) = default;
	ListInIterator & operator=(ListInIterator &&) = default;

	explicit operator bool() const noexcept {
		if constexpr (A::optional)
			return A::has(start, index);
		else
			return true;
	}

	value_type operator*() const noexcept {
		return A::get(reader, start, index);
	}

	// Compare
	bool operator<(const ListInIterator & o) const noexcept { return index < o.index; }
	bool operator>(const ListInIterator & o) const noexcept { return index > o.index; }
	bool operator<=(const ListInIterator & o) const noexcept { return index <= o.index; }
	bool operator>=(const ListInIterator & o) const noexcept { return index >= o.index; }
	bool operator!=(const ListInIterator & o) const noexcept { return index != o.index; }
	bool operator==(const ListInIterator & o) const noexcept { return index == o.index; }

	// Movement
	ListInIterator & operator++() noexcept {
		index++;
		return *this;
	}
	ListInIterator & operator--() noexcept {
		index--;
		return *this;
	}
	ListInIterator operator++(int) noexcept {
		ListInIterator t = *this;
		index++;
		return t;
	}
	ListInIterator operator--(int) noexcept {
		ListInIterator t = *this;
		index--;
		return t;
	}
	ListInIterator operator+(difference_type delta) const noexcept {
		ListInIterator t = *this;
		t += delta;
		return t;
	}
	ListInIterator operator-(difference_type delta) const noexcept {
		ListInIterator t = *this;
		t -= delta;
		return t;
	}
	ListInIterator & operator+=(difference_type delta) noexcept {
		index += delta;
		return *this;
	}
	ListInIterator & operator-=(difference_type delta) noexcept {
		index -= delta;
		return *this;
	}

	difference_type operator-(const ListInIterator & o) const noexcept {
		return difference_type(index) - difference_type(o.index);
	}
};

template <typename T>
class ListIn : public In {
	friend class In;
	const Reader * reader_;
	const char * start_;
	const std::uint64_t size_;
	template <typename>
	friend class ListOut;

	ListIn(const Reader * reader, Ptr p) noexcept
		: reader_(reader)
		, start_(p.start)
		, size_(p.size) {}
	using A = ListAccess<T>;

public:
	static constexpr bool noexceptGet =
		noexcept(A::get(std::declval<const Reader *>(), std::declval<const char *>(), 0));

	using value_type = T;
	using size_type = std::size_t;
	using iterator = ListInIterator<T>;

	ListIn(const Reader * reader) noexcept : reader_(reader), start_(nullptr), size_(0) {}

	bool hasFront() const noexcept { return !empty() && has(0); }
	value_type front() const noexcept(noexceptGet) {
		assert(!empty());
		return A::get(reader_, start_, 0);
	}
	bool hasBack() const noexcept { return !empty() && has(size_ - 1); }
	value_type back() const noexcept(noexceptGet) {
		assert(!empty());
		return A::get(reader_, start_, size_ - 1);
	}
	size_type size() const noexcept { return size_; }
	bool empty() const noexcept { return size_ == 0; }
	iterator begin() const noexcept { return iterator(reader_, start_, 0); }
	iterator end() const noexcept { return iterator(reader_, start_, size_); }
	value_type at(size_type pos) const {
		if (pos >= size_) throw std::out_of_range("out of range");
		return A::get(reader_, start_, pos);
	};
	value_type operator[](size_type pos) const noexcept(noexceptGet) {
		assert(pos < size_);
		return A::get(reader_, start_, pos);
	}

	bool has(size_type pos) const noexcept {
		(void)pos;
		if constexpr (A::optional) return A::has(start_, pos);
		return true;
	}
};


template <typename T>
class DirectListInIterator: public In {
private:
	const Reader * reader;
	const char * start;
	std::uint32_t item_size;
	std::uint64_t index;
	friend class DirectListIn<T>;
	DirectListInIterator(const Reader * reader, const char * start,
				std::uint32_t item_size,
				std::uint64_t index) noexcept
		: reader(reader)
		, start(start)
		, item_size(item_size)
		, index(index) {}

public:
	using value_type = T;
	using size_type = std::size_t;
	using difference_type = std::ptrdiff_t;
	using pointer = T *;
	using reference = T &;
	using iterator_category = std::random_access_iterator_tag;

	DirectListInIterator(const DirectListInIterator &) = default;
	DirectListInIterator(DirectListInIterator &&) = default;
	DirectListInIterator & operator=(const DirectListInIterator &) = default;
	DirectListInIterator & operator=(DirectListInIterator &&) = default;

	value_type operator*() const noexcept(noexcept(getObject_<T>(reader, Ptr{0,0}))) {
		return getObject_<T>(reader, Ptr{start + index * item_size, item_size});
	}

	// Compare
	bool operator<(const DirectListInIterator & o) const noexcept { return index < o.index; }
	bool operator>(const DirectListInIterator & o) const noexcept { return index > o.index; }
	bool operator<=(const DirectListInIterator & o) const noexcept { return index <= o.index; }
	bool operator>=(const DirectListInIterator & o) const noexcept { return index >= o.index; }
	bool operator!=(const DirectListInIterator & o) const noexcept { return index != o.index; }
	bool operator==(const DirectListInIterator & o) const noexcept { return index == o.index; }

	// Movement
	DirectListInIterator & operator++() noexcept {
		index++;
		return *this;
	}
	DirectListInIterator & operator--() noexcept {
		index--;
		return *this;
	}
	DirectListInIterator operator++(int) noexcept {
		DirectListInIterator t = *this;
		index++;
		return t;
	}
	DirectListInIterator operator--(int) noexcept {
		DirectListInIterator t = *this;
		index--;
		return t;
	}
	DirectListInIterator operator+(difference_type delta) const noexcept {
		DirectListInIterator t = *this;
		t += delta;
		return t;
	}
	DirectListInIterator operator-(difference_type delta) const noexcept {
		DirectListInIterator t = *this;
		t -= delta;
		return t;
	}
	DirectListInIterator & operator+=(difference_type delta) noexcept {
		index += delta;
		return *this;
	}
	DirectListInIterator & operator-=(difference_type delta) noexcept {
		index -= delta;
		return *this;
	}

	difference_type operator-(const DirectListInIterator & o) const noexcept {
		return difference_type(index) - difference_type(o.index);
	}
};

template <typename T>
class DirectListIn : public In {
	friend class In;
	const Reader * reader_;
	const char * start_;
	const std::uint64_t size_;
	const std::uint32_t item_size_;

	static std::uint32_t parse_header(const Reader * reader, Ptr p) {
		if (p.start == 0)
			return 1;
		if (p.start + 8 > reader->data + reader->size)
			throw OutOfBoundsError();
		std::uint32_t magic, item_size;
		memcpy(&magic, p.start, 4);
		if (magic != T::MAGIC)
			throw MagicError(magic, T::MAGIC);
		memcpy(&item_size, p.start+4, 4);
		if (item_size > 65534) throw TooLargeItemSizeError(item_size); //Items larger than this is currently not support as it might overflow the multiplication below
		if (p.start + 4 + p.size * item_size > reader->data + reader->size)
			throw OutOfBoundsError();
		return item_size;
	}

	DirectListIn(const Reader * reader, Ptr p) noexcept(false)
		: reader_(reader)
		, start_(p.start+8)
		, size_(p.size)
		, item_size_(p.size == 0 ? 1 : parse_header(reader, p)) {}
public:
	using value_type = T;
	using size_type = std::size_t;
	using iterator = DirectListInIterator<T>;

	DirectListIn(const Reader * reader) noexcept : reader_(reader), start_(nullptr), size_(0), item_size_(0) {}

	value_type front() const noexcept {return (*this)[0];}
	value_type back() const noexcept {return (*this)[size_ - 1];}
	size_type size() const noexcept { return size_; }
	bool empty() const noexcept { return size_ == 0; }
	iterator begin() const noexcept { return iterator(reader_, start_, item_size_, 0); }
	iterator end() const noexcept { return iterator(reader_, start_, item_size_, size_); }
	value_type at(size_type pos) const {
		if (pos >= size_) throw std::out_of_range("out of range");
		return (*this)[pos];
	};
	value_type operator[](size_type pos) const noexcept(noexcept(getObject_<T>(reader_, Ptr{0,0}))) {
		assert(pos < size_);
		return getObject_<T>(reader_, Ptr{start_ + pos * item_size_, item_size_});
	}
};


class TableIn : public In {
protected:
	const Reader * reader_;
	const char * start_;
	std::uint64_t size_;

	TableIn(const Reader * reader, Ptr p)
		: reader_(reader)
		, start_(p.start)
		, size_(p.size) {}


	template <typename T, std::uint64_t o>
	T getInnerUnchecked_() const noexcept {
		T ans;
		assert(o + sizeof(T) <= size_);
		memcpy(&ans, start_ + o, sizeof(T));
		return ans;
	}

	template <typename T, std::uint64_t o>
	T getInner_(T def) const noexcept {
		if (o + sizeof(T) > size_) return def;
		return getInnerUnchecked_<T, o>();
	}

	template <std::uint64_t o>
	std::uint64_t get48_() const noexcept {
		if (o + 6 > size_) return 0;
		return read48_(start_ + o);
	}

	template <typename T, std::uint64_t o>
	T getInner_() const noexcept {
		T ans;
		if (o + sizeof(T) > size_)
			memset(&ans, 0, sizeof(T));
		else
			memcpy(&ans, start_ + o, sizeof(T));
		return ans;
	}

	template <bool inplace, std::uint32_t magic, std::uint64_t o, std::uint64_t mult = 1,
			  std::uint64_t add = 0>
	Ptr getPtr_() const {
		if constexpr (inplace)
			return reader_->getPtrInplace_<mult, add>(start_ + size_, get48_<o>());
		else
			return reader_->getPtr_<magic, mult, add>(get48_<o>());
	}

	template <std::uint64_t o, std::uint8_t bit, std::uint8_t def>
	std::uint8_t getBit_() const noexcept {
		if (o < size_) return *(const std::uint8_t *)(start_ + o) & 1 << bit;
		return def;
	}
};

template <bool inplace>
class UnionIn : public In {
protected:
	friend class In;

	const Reader * reader_;
	const std::uint16_t type_;
	const std::uint64_t offset_;

	UnionIn(const Reader * reader, std::uint16_t type, std::uint64_t offset_)
		: reader_(reader)
		, type_(type)
		, offset_(offset_) {}

	template <std::uint32_t magic, std::uint64_t mult = 1, std::uint64_t add = 0>
	Ptr getPtr_() const {
		return reader_->getPtr_<magic, mult, add>(offset_);
	}
};

template <>
class UnionIn<true> : public In {
protected:
	friend class In;

	const Reader * reader_;
	const std::uint16_t type_;
	const char * start_;
	const std::uint64_t size_;

	UnionIn(const Reader * reader, std::uint16_t type, const char * start,
			std::uint64_t size)
		: reader_(reader)
		, type_(type)
		, start_(start)
		, size_(size) {}

	template <std::uint32_t magic, std::uint64_t mult = 1, std::uint64_t add = 0>
	Ptr getPtr_() const {
		return reader_->getPtrInplace_<mult, add>(start_, size_);
	}
};

template <>
struct MetaMagic<TextOut> {
	using t = TextTag;
};
template <>
struct MetaMagic<std::string_view> {
	using t = TextTag;
};

template <>
struct MetaMagic<BytesOut> {
	using t = BytesTag;
};
template <>
struct MetaMagic<Bytes> {
	using t = BytesTag;
};

template <typename T>
class ListOut {
protected:
	friend class Writer;
	friend class Out;
	Writer & writer_;
	std::uint64_t offset_;
	std::uint64_t size_;
	using A = ListAccess<T>;
	ListOut(Writer & writer, std::uint64_t offset, std::uint64_t size_)
		: writer_(writer)
		, offset_(offset)
		, size_(size_) {}

public:
	using value_type = T;

	/**
	 * Note: The result of this operator must be assigned to immediately,
	 * as it is invalidated when other objects are created in the Writer.
	 */
	typename A::Setter operator[](size_t index) noexcept {
		assert(index < size_);
		return typename A::Setter(writer_, offset_, index);
	}

	template <typename... TT>
	T add(size_t index, TT... vv) {
		assert(index < size_);
		static_assert(A::hasAdd);
		if constexpr (A::hasAdd)
			return A::add(writer_, offset_, index, std::forward<TT>(vv)...);
		else {
			throw OutOfBoundsError();
		}
	}

	std::uint64_t size() const noexcept { return size_; }

	ListOut & copy_(const ListIn<typename A::IN> in) {
		assert(in.size() == size());
		A::copy(writer_, offset_, in.reader_, in.start_, size_);
		return *this;
	}
};

template <typename A>
struct MetaMagic<ListOut<A>> {
	using t = ListTag;
};

template <typename T>
class DirectListOut {
protected:
	friend class Writer;
	friend class Out;
	Writer & writer_;
	std::uint64_t offset_;
	std::uint64_t size_;

	
	DirectListOut(Writer & writer, std::uint64_t offset, std::uint64_t size_)
		: writer_(writer)
		, offset_(offset)
		, size_(size_) {}

public:
	using value_type = T;

	T operator[](size_t index) noexcept;

	std::uint64_t size() const noexcept { return size_; }

	DirectListOut & copy_(const DirectListIn<typename T::IN> in) {
		assert(in.size() == size());
		for (size_t i=0; i < size(); ++i)
			(*this)[i].copy_(in[i]);
		return *this;
	}
};

class WriterBacking {
protected:
	WriterBacking() = default;
public:
	virtual char * setCapacity(size_t newCapacity) = 0;
	virtual void finalizeBacking(size_t finalSize) = 0;
	virtual ~WriterBacking() {}
};

class FileWriterBacking : public WriterBacking {
private:
	int fd;
	void * addr;
	size_t capacity;

	static constexpr size_t PAGE_SIZE = 4096;

public:
	FileWriterBacking() : fd(-1), addr(nullptr), capacity(0) {}
	// Must not copy fd and addr.
	FileWriterBacking(const FileWriterBacking &) = delete;
	FileWriterBacking & operator=(const FileWriterBacking &) = delete;
	// We could in principle implement move semantics, but it is not needed.
	FileWriterBacking(FileWriterBacking &&) = delete;
	FileWriterBacking & operator=(FileWriterBacking &&) = delete;

	int open(const char * path) {
		assert(::sysconf(_SC_PAGE_SIZE) == PAGE_SIZE);
		if (addr != nullptr) return -1;
		fd = ::open(path, O_TRUNC | O_CREAT | O_RDWR | O_CLOEXEC, 0666);
		if (fd == -1) return -1;
		if (::ftruncate(fd, PAGE_SIZE)) {
			// Close the file descriptor, but set errno to the error from ftruncate.
			int oldErrno = errno;
			::close(fd);
			errno = oldErrno;
			fd = -1;
			return -1;
		}
		capacity = PAGE_SIZE;
		addr = ::mmap(nullptr, capacity, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
		if (addr == (void*)-1) {
			addr = nullptr;
			::close(fd);
			capacity = 0;
			fd = -1;
			return -1;
		}
		return 0;
	}

	void finalizeBacking(size_t finalSize) final {
		if (fd == -1) {
			throw std::runtime_error("finalizeBacking() cannot truncate: Already closed");
		}
		if (::ftruncate(fd, finalSize)) {
			throw std::runtime_error("ftruncate() failed in finalizeBacking()");
		}
	}

	void closeInner() {
		if (fd != -1) {
			::close(fd);
			fd = -1;
		}
		if (addr != nullptr) {
			::munmap(addr, capacity);
			addr = nullptr;
			capacity = 0;
		}
	}

	~FileWriterBacking() {
		closeInner();
	}

	char * setCapacity(size_t newCapacity) final {
		if (addr == nullptr)
			throw std::runtime_error("Cannot extend mmap backing after freeing it");
		if (newCapacity == 0) {
			closeInner();
			return nullptr;
		}
		// Round up to nearest multiple of PAGE_SIZE
		newCapacity = (newCapacity + PAGE_SIZE - 1) / PAGE_SIZE * PAGE_SIZE;
		if (newCapacity == capacity) return (char *)addr;
		if (::ftruncate(fd, newCapacity))
			throw std::runtime_error("ftruncate failed");
		void * result = ::mremap(addr, capacity, newCapacity, MREMAP_MAYMOVE);
		if (result == (void *)-1)
			throw std::runtime_error("mremap failed");
		addr = result;
		capacity = newCapacity;
		return (char *)addr;
	}
};

class Writer {
private:
	std::unique_ptr<WriterBacking> backing;
	char * data = nullptr;
	size_t size = 0;
	size_t capacity = 0;
	friend class Out;
	friend class InplaceUnionOut;
	friend class UnionOut;
	friend class TableOut;
	template <typename>
	friend class ListOut;
	template <typename>
	friend class DirectListOut;
	template <typename, typename>
	friend class ListAccessHelp;
	void setCapacity(size_t newCapacity) {
		if (backing) {
			data = backing->setCapacity(newCapacity);
			capacity = newCapacity;
			return;
		}
		if (newCapacity == 0) {
			free(data);
			data = nullptr;
			capacity = 0;
			return;
		}
		data = (char *)realloc(data, newCapacity);
		capacity = newCapacity;
	}

	void expand(std::uint64_t s) {
		while (size + s > capacity) setCapacity(capacity * 2);
		size += s;
	}

	template <typename T>
	void write(const T & t, std::uint64_t offset) noexcept {
		memcpy(data + offset, &t, sizeof(T));
	}

	template <typename T>
	T accessTable(std::uint64_t o) { //TODO noexcept
		return T(*this, o);
	}

	template <typename T>
	T read(std::uint64_t offset) noexcept {
		T v;
		memcpy(&v, data+offset, sizeof(T));
		return v;
	}
public:
	Writer(size_t capacity = 256, std::unique_ptr<WriterBacking> backing = nullptr)
		: backing(std::move(backing)), size(10) {
		setCapacity(capacity);
	}
	Writer(const Writer &) = delete;
	Writer & operator=(const Writer &) = delete;
	Writer(Writer && o)
		: backing(std::move(o.backing))
		, data(o.data)
		, size(o.size)
		, capacity(o.capacity) {
		o.data = nullptr;
		o.size = 0;
		o.capacity = 0;
	}
	Writer & operator=(Writer && o) {
		setCapacity(0);
		backing = std::move(o.backing);
		data = o.data;
		size = o.size;
		capacity = o.capacity;
		o.data = nullptr;
		o.size = 0;
		o.capacity = 0;
		return *this;
	}

	~Writer() {
		setCapacity(0);
		data = nullptr;
		size = 0;
		capacity = 0;
	}

	void clear() noexcept { size = 10; }

	bool isClean() const noexcept { return size == 10; }

	inline Bytes finalize(const TableOut & root);

	template <typename T>
	T construct() noexcept {
		return T(*this, true);
	}

	void write48_(std::uint64_t value, std::uint64_t offset) noexcept {
		scalgoproto::write48_(data + offset, value);
	}

	TextOut constructText(std::string_view text) {
		TextOut o;
		o.offset_ = size;
		expand(text.size() + 11);
		write((std::uint32_t)TEXTMAGIC, o.offset_);
		write48_(text.size(), o.offset_ + 4);
		memcpy(data + o.offset_ + 10, text.data(), text.size());
		data[o.offset_ + 10 + text.size()] = 0;
		return o;
	}

	BytesOut constructBytes(const void * data, size_t size) {
		BytesOut o;
		o.offset_ = this->size;
		expand(size + 10);
		write((std::uint32_t)BYTESMAGIC, o.offset_);
		write48_(size, o.offset_ + 4);
		memcpy(this->data + o.offset_ + 10, data, size);
		return o;
	}

	std::pair<BytesOut, char *> constructBytes(size_t size) {
		BytesOut o;
		o.offset_ = this->size;
		expand(size + 10);
		write((std::uint32_t)BYTESMAGIC, o.offset_);
		write48_(size, o.offset_ + 4);
		return std::pair(o, this->data + o.offset_ + 10);
	}
	
	BytesOut constructBytes(Bytes b) { return constructBytes(b.first, b.second); }

	template <typename T>
	ListOut<T> constructList(size_t size) {
		using A = ListAccess<T>;
		ListOut<T> o(*this, this->size, size);
		expand(computeSize<A::mult>(size) + 10);
		write((std::uint32_t)LISTMAGIC, o.offset_);
		write48_(size, o.offset_ + 4);
		o.offset_ += 10;
		memset(data + o.offset_, A::def, computeSize<A::mult>(size));
		return o;
	}

	template <typename T>
	DirectListOut<T> constructDirectList(size_t size) {
		DirectListOut<T> o(*this, this->size, size);
		expand(18);

		write((std::uint32_t)DIRECTLISTMAGIC, o.offset_);
		write48_(size, o.offset_ + 4);
		write((std::uint32_t)T::MAGIC, o.offset_ + 10);
		write((std::uint32_t)T::SIZE, o.offset_ + 14);
		o.offset_ += 18;

		// Default fill the whole table
		for (size_t i=0; i < size; ++i)
			T(*this, false);

		return o;
	}

	ListOut<TextOut> constructTextList(size_t size) {
		return constructList<TextOut>(size);
	}
	ListOut<BytesOut> constructBytesList(size_t size) {
		return constructList<BytesOut>(size);
	}
};

class Out {
protected:
	friend class Writer;

	template <typename T>
	static std::uint64_t getOffset_(const T & t) noexcept {
		return t.offset_;
	}

	template <typename T, typename... TT>
	static T construct_(TT &&... vv) noexcept {
		return T(std::forward<TT>(vv)...);
	}

	template <typename T>
	static T addInplaceTable_(Writer & writer, size_t start) noexcept {
		assert(writer.size == start);
		(void)start;
		return T(writer, false);
	}

	static void addInplaceBytes_(Writer & writer, size_t start, const char * data,
								 size_t size) noexcept {
		assert(writer.size == start);
		(void)start;
		writer.expand(size);
		memcpy(writer.data + start, data, size);
	}

	static char * addInplaceBytes_(Writer & writer, size_t start, size_t size) noexcept {
		assert(writer.size == start);
		(void)start;
		writer.expand(size);
		return writer.data + start;
	}

	static void addInplaceText_(Writer & writer, size_t start,
								std::string_view str) noexcept {
		assert(writer.size == start);
		(void)start;
		writer.expand(str.size() + 1);
		memcpy(writer.data + start, str.data(), str.size());
		writer.data[start + str.size()] = 0;
	}

	template <typename T>
	static ListOut<T> addInplaceList_(Writer & writer, size_t start,
									  size_t size) noexcept {
		assert(writer.size == start);
		(void)start;
		using A = ListAccess<T>;
		ListOut<T> o(writer, writer.size, size);
		size_t bsize = computeSize<A::mult>(size);
		writer.expand(bsize);
		memset(writer.data + o.offset_, A::def, bsize);
		return o;
	}

	template <typename T>
	static DirectListOut<T> addInplaceDirectList_(Writer & writer, size_t start,
									  size_t size) noexcept {
		assert(writer.size == start);
		(void)start;

		DirectListOut<T> o(writer, writer.size, size);
		writer.expand(8);
		write((std::uint32_t)T::MAGIC, o.offset_ + 0);
		write((std::uint32_t)T::SIZE, o.offset_ + 4);
		o.offset += 8;

		// Default fill the whole table
		for (size_t i=0; i < size; ++i)
			T(writer, false);

		return o;
	}
};

class UnionOut : public Out {
protected:
	friend class Writer;
	template <typename, typename>
	friend class ListAccessHelp;
	template <typename>
	friend class ListOut;

	Writer & writer_;
	std::uint64_t offset_;

	void setType_(std::uint16_t type) noexcept { writer_.write(type, offset_); }
	std::uint16_t getType_() const noexcept {return  writer_.read<uint16_t>(offset_); }

	void setObject_(std::uint64_t p) noexcept { writer_.write48_(p, offset_ + 2); }

	UnionOut(Writer & writer, std::uint64_t offset)
		: writer_(writer)
		, offset_(offset) {}
	UnionOut(Writer & writer, std::uint64_t offset, std::uint64_t index)
		: writer_(writer)
		, offset_(offset + index * 8) {}
};

class InplaceUnionOut : public Out {
protected:
	friend class Writer;
	Writer & writer_;
	std::uint64_t offset_;
	std::uint64_t next_;

	void setType_(std::uint16_t type) noexcept { writer_.write(type, offset_); }
	std::uint16_t getType_() const noexcept { return writer_.read<uint16_t>(offset_); }

	void setSize_(std::uint64_t size) noexcept { writer_.write48_(size, offset_ + 2); }

	InplaceUnionOut(Writer & writer, std::uint64_t offset, std::uint64_t next)
		: writer_(writer)
		, offset_(offset)
		, next_(next) {}
};

class TableOut : public Out {
protected:
	friend class Writer;
	template <typename, typename>
	friend class ListAccessHelp;

	Writer & writer_;
	std::uint64_t offset_;

	TableOut(Writer & writer, bool withHeader, std::uint32_t magic, const char * def,
			 std::uint64_t size)
		: writer_(writer)
		, offset_(writer.size) {
		if (withHeader) {
			writer_.expand(10);
			writer_.write(magic, offset_);
			writer_.write48_(size, offset_ + 4);
			offset_ += 10;
		}
		writer_.expand(size);
		memcpy(writer_.data + offset_, def, size);
	}


	TableOut(Writer & writer, size_t offset)
		: writer_(writer)
		, offset_(offset) {
	}

	template <std::uint64_t o>
	void set48_(std::uint64_t v) noexcept {
		writer_.write48_(v, offset_ + o);
	}

	template <typename T, std::uint64_t o>
	void setInner_(const T & t) {
		writer_.write(t, offset_ + o);
	}

	template <std::uint64_t o, std::uint8_t b>
	void setBit_() noexcept {
		*(std::uint8_t *)(writer_.data + offset_ + o) |= (1 << b);
	}

	template <std::uint64_t o, std::uint8_t b>
	void unsetBit_() noexcept {
		*(std::uint8_t *)(writer_.data + offset_ + o) &= ~(1 << b);
	}

	template <std::uint64_t o, std::uint8_t bit, std::uint8_t>
	std::uint8_t getBit_() const noexcept {
		return *(std::uint8_t *)(writer_.data + offset_ + o) & 1 << bit;
	}

	template <typename T, std::uint64_t offset>
	T getInner_() const noexcept {
		T ans;
		memcpy(&ans, writer_.data + offset_ + offset, sizeof(T));
		return ans;
	}

	template <typename T, std::uint64_t o>
	T getInner_(T) const noexcept {
		return getInner_<T, o>();
	}

	template <std::uint64_t o>
	std::uint64_t get48_() const noexcept {
		return read48_(writer_.data + offset_ + o);
	}
};

template <typename T>
ListAccessHelp<BoolTag, T>::Setter::Setter(Writer & writer, std::uint64_t offset,
										   std::uint64_t index)
	: byte(writer.data + offset + (index >> 3))
	, bit(index & 7) {}

template <typename T>
void ListAccessHelp<BoolTag, T>::copy(Writer & writer, std::uint64_t offset,
									  const Reader *, const char * start,
									  std::uint64_t size) {
	memcpy(writer.data + offset, start, (size + 7) >> 3);
}

template <typename T>
ListAccessHelp<PodTag, T>::Setter::Setter(Writer & writer, std::uint64_t offset,
										  std::uint64_t index)
	: location(writer.data + offset + index * sizeof(T)) {}

template <typename T>
void ListAccessHelp<PodTag, T>::copy(Writer & writer, std::uint64_t offset,
									 const Reader *, const char * start,
									 std::uint64_t size) {
	memcpy(writer.data + offset, start, size * sizeof(T));
}

template <typename T>
ListAccessHelp<EnumTag, T>::Setter ::Setter(Writer & writer, std::uint64_t offset,
											std::uint64_t index)
	: location(writer.data + offset + index * sizeof(T)) {}

template <typename T>
void ListAccessHelp<EnumTag, T>::copy(Writer & writer, std::uint64_t offset,
									  const Reader *, const char * start,
									  std::uint64_t size) {
	memcpy(writer.data + offset, start, size * sizeof(T));
}

template <typename T>
ListAccessHelp<TextTag, T>::Setter::Setter(Writer & writer, std::uint64_t offset,
										   std::uint64_t index)
	: writer(writer)
	, offset(offset + index * 6) {}

template <typename T>
T ListAccessHelp<TextTag, T>::Setter::operator=(const T & value) noexcept {
	write48_(writer.data + offset, value.offset_);
	return value;
}

template <typename T>
TextOut ListAccessHelp<TextTag, T>::Setter::operator=(std::string_view t) {
	// Note, constructText might reallocate writer.data
	auto value = writer.constructText(t);
	write48_(writer.data + offset, value.offset_);
	return value;
}

template <typename T>
void ListAccessHelp<TextTag, T>::copy(Writer & writer, std::uint64_t offset,
									  const Reader * reader, const char * start,
									  std::uint64_t size) {
	for (size_t index = 0; index < size; ++index) {
		std::uint64_t off = read48_(start + index * 6);
		if (off == 0) continue;
		auto t = getText_(reader, reader->getPtr_<TEXTMAGIC, 1, 1>(off));
		auto v = writer.constructText(t);
		write48_(writer.data + offset + 6 * index, v.offset_);
	}
}

template <typename T>
ListAccessHelp<BytesTag, T>::Setter::Setter(Writer & writer, std::uint64_t offset,
											std::uint64_t index)
	: location(writer.data + offset + index * 6)
	, writer(writer) {}

template <typename T>
void ListAccessHelp<BytesTag, T>::copy(Writer & writer, std::uint64_t offset,
									   const Reader * reader, const char * start,
									   std::uint64_t size) {
	for (size_t index = 0; index < size; ++index) {
		std::uint64_t off = read48_(start + index * 6);
		if (off == 0) continue;
		auto b = getBytes_(reader->getPtr_<BYTESMAGIC>(off));
		auto v = writer.constructBytes(b.first, b.second);
		write48_(writer.data + offset + 6 * index, v.offset_);
	}
}

template <typename T>
void ListAccessHelp<BytesTag, T>::Setter::operator=(Bytes bytes) noexcept {
	(*this) = writer.constructBytes(bytes);
}

template <typename T>
ListAccessHelp<TableTag, T>::Setter::Setter(Writer & writer, std::uint64_t offset,
											std::uint64_t index)
	: location(writer.data + offset + index * 6) {}

template <typename T>
T ListAccessHelp<TableTag, T>::add(Writer & w, std::uint64_t offset,
								   std::uint64_t index) {
	auto ans = w.construct<T>();
	write48_(w.data + offset + index * 6, ans.offset_ - 10);
	return ans;
}

template <typename T>
void ListAccessHelp<TableTag, T>::copy(Writer & writer, std::uint64_t offset,
									   const Reader * reader, const char * start,
									   std::uint64_t size) {
	for (size_t index = 0; index < size; ++index) {
		std::uint64_t off = read48_(start + index * 6);
		if (off == 0) continue;
		auto t = getObject_<typename T::IN>(reader, reader->getPtr_<T::MAGIC>(off));
		auto v = writer.construct<T>();
		v.copy_(t);
		write48_(writer.data + offset + 6 * index, v.offset_ - 10);
	}
}

template <typename T>
void ListAccessHelp<UnionTag, T>::copy(Writer & writer, std::uint64_t offset,
									   const Reader * reader, const char * start,
									   std::uint64_t size) {
	for (size_t index = 0; index < size; ++index) {
		std::uint16_t type;
		memcpy(&type, start + index * 8, 2);
		std::uint64_t off = read48_(start + index * 8 + 2);
		if (type == 0 || off == 0) continue;
		auto t = getObject_<typename T::IN>(reader, type, off);
		T(writer, offset, index).copy_(t);
	}
}

Bytes Writer::finalize(const TableOut & root) {
	write(ROOTMAGIC, 0);
	this->write48_(root.offset_ - 10, 4);
	if (backing) backing->finalizeBacking(size);
	return std::make_pair(data, size);
}

template <typename O>
void copy(O out, typename O::IN in) {
	out.copy_(in);
}

template <typename T>
T DirectListOut<T>::operator[](size_t index) noexcept {
	assert(index < size_);
	return writer_.template accessTable<T>(offset_ + T::SIZE * index);
}


} // namespace scalgoproto
#endif //__SCALGOPROTO_HH__
