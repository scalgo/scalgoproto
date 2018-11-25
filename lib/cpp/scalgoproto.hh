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

class Out;
class Writer;
class In;
class Reader;
struct EnumTag;
struct BoolTag;
struct PodTag;
struct TableTag;
struct ListTag;
struct TextTag;
struct BytesTag;
struct UnknownTag;

template <typename, typename>
class ListAccessHelp;

class Error: public std::runtime_error {
public:
	Error() : std::runtime_error("Error") {}
};

class TextOut {
	friend class Writer;
	friend class Out;
	template <typename, typename> friend class ListAccessHelp;
protected:
	std::uint32_t offset;
};

class BytesOut {
	friend class Writer;
	friend class Out;
	template <typename, typename> friend class ListAccessHelp;
protected:
	std::uint32_t offset;
};


template <typename T> struct MetaMagic {using t=UnknownTag;};
template <> struct MetaMagic<bool> {using t=BoolTag;};
template <> struct MetaMagic<std::uint8_t> {using t=PodTag;};
template <> struct MetaMagic<std::uint16_t> {using t=PodTag;};
template <> struct MetaMagic<std::uint32_t> {using t=PodTag;};
template <> struct MetaMagic<std::uint64_t> {using t=PodTag;};
template <> struct MetaMagic<std::int8_t> {using t=PodTag;};
template <> struct MetaMagic<std::int16_t> {using t=PodTag;};
template <> struct MetaMagic<std::int32_t> {using t=PodTag;};
template <> struct MetaMagic<std::int64_t> {using t=PodTag;};
template <> struct MetaMagic<float> {using t=PodTag;};
template <> struct MetaMagic<double> {using t=PodTag;};

template <typename Tag, typename T>
struct ListAccessHelp {};

template <uint32_t mult>
uint64_t computeSize(uint64_t v) {
	if constexpr (mult == 0) return (v+7)>>3;
	return v * mult;
};


class Reader {
private:
	friend class In;
	template <typename, typename>
	friend class ListAccessHelp;

	const char * data;
	size_t size;

	template <uint32_t magic, uint32_t mult=1, uint32_t add=0>
	uint32_t readObjectSize_(uint32_t offset) const {
		// Validate that the offset is within the reader boundary
		if ( uint64_t(offset) + 8 >= size) throw Error();
		// Check that we have the right magic
		uint32_t word;
		memcpy(&word, data+offset, 4);
		if (word != magic) throw Error();
		// Read size and check that the object is within the reader boundary
		memcpy(&word, data+offset+4, 4);
		if (computeSize<mult>(word) + offset + 8 + add> size) throw Error();
		return word;
	}
public:
	Reader(const char * data, size_t size) noexcept : data(data), size(size) {};

	template <typename T>
	T root() const {
		std::uint32_t magic, offset;
		memcpy(&magic, data, 4);
		memcpy(&offset, data+4, 4);
		if (magic != 0xB5C0C4B3) throw Error();
		std::uint32_t size = T::readSize_(*this, offset);
		return T(*this, data+offset+8, size);
	}
};


template <typename T>
struct ListAccessHelp<BoolTag, T> {
	static constexpr bool optional = false;
	static constexpr size_t mult = 0;
	static constexpr int def = 0;
	static bool get(const Reader &, const char * start, std::uint32_t index) noexcept {
		const size_t bit = index & 7;
		const size_t byte = index >> 3;
		std::uint8_t v;
		memcpy(&v, start + byte, 1);
		return (v >> bit) & 1;
	}
	static void set(char * data, std::uint32_t offset, std::uint32_t index, const bool & value) noexcept {
		const size_t bit = index & 7;
		const size_t byte = index >> 3;
		std::uint8_t v;
		memcpy(&v, data + offset + byte, 1);
		v = value ? v | (1 << bit) : (v & ~(1<<bit));
		memcpy(data + offset + byte, &v, 1);
	}
};

template <typename T>
struct ListAccessHelp<PodTag, T> {
	static constexpr bool optional = false;
	static constexpr size_t mult = sizeof(T);
	static constexpr int def = 0;
	static T get(const Reader &, const char * start, std::uint32_t index) noexcept {
		T ans;
		memcpy(&ans, start + index * sizeof(T), sizeof(T));
		return ans;
	}
	static void set(char * data, std::uint32_t offset, std::uint32_t index, const T & value) noexcept {
		memcpy(data + offset + index * sizeof(T), &value, sizeof(T));
	}
};

template <typename T>
struct ListAccessHelp<EnumTag, T> {
	static constexpr bool optional = true;
	static constexpr size_t mult = 1;
	static constexpr int def = 255;
	static bool has(const char * start, std::uint32_t index) noexcept {
		return ((const unsigned char *)(start))[index] != 255;
	}
	static T get(const Reader &, const char * start, std::uint32_t index) noexcept {
		T ans;
		memcpy(&ans, start + index * sizeof(T), sizeof(T));
		return ans;
	}
	static void set(char * data, std::uint32_t offset, std::uint32_t index, const T & value) noexcept {
		memcpy(data + offset + index * sizeof(T), &value, sizeof(T));
	}
};

template <typename T>
struct ListAccessHelp<TextTag, T> {
	static constexpr bool optional = true;
	static constexpr size_t mult = 4;
	static constexpr int def = 0;
	static bool has(const char * start, std::uint32_t index) noexcept {
		std::uint32_t off;
		memcpy(&off, start + index * 4, 4);
		return off != 0;
	}
	static std::string_view get(const Reader & reader, const char * start, std::uint32_t index) {
		std::uint32_t off;
		memcpy(&off, start + index * 4, 4);
		assert(off != 0);
		const std::uint32_t size = reader.readObjectSize_<0xD812C8F5, 1, 1>(off);
		if (reader.data[off+8+size] != 0) throw Error();
		return std::string_view(reader.data+off+8, size);
	}
	static void set(char * data, std::uint32_t offset, std::uint32_t index, const TextOut & value) noexcept {
		memcpy(data + offset + index * 4, &value.offset, 4);
	}
};

template <typename T>
struct ListAccessHelp<BytesTag, T> {
	static constexpr bool optional = true;
	static constexpr size_t mult = 4;
	static constexpr int def = 0;
	static bool has(const char * start, std::uint32_t index) noexcept {
		std::uint32_t off;
		memcpy(&off, start + index * 4, 4);
		return off != 0;
	}
	static std::pair<const void *, size_t> get(const Reader & reader, const char * start, std::uint32_t index) noexcept {
		std::uint32_t off;
		memcpy(&off, start + index * 4, 4);
		assert(off != 0);
		const std::uint32_t size = reader.readObjectSize_<0xDCDBBE10>(off);
		return std::make_pair(reader.data+off+8, size);
	}
	static void set(char * data, std::uint32_t offset, std::uint32_t index, const BytesOut & value) noexcept {
		memcpy(data + offset + index * 4, &value.offset, 4);
	}
};


template <typename T>
struct ListAccessHelp<TableTag, T> {
	static constexpr bool optional = true;
	static constexpr size_t mult = 4;
	static constexpr int def = 0;
	static bool has(const char * start, std::uint32_t index) noexcept {
		std::uint32_t off;
		memcpy(&off, start + index * 4, 4);
		return off != 0;
	}

	static T get(const Reader & reader, const char * start, std::uint32_t index) noexcept {
		std::uint32_t off;
		memcpy(&off, start + index * 4, 4);
		assert(off != 0);
		const std::uint32_t size = T::readSize_(reader, off);
		return T(reader, reader.data + off+8, size);
	}

	static void set(char * data, std::uint32_t offset, std::uint32_t index, T v) noexcept {
		std::uint32_t o = v.offset - 8;
		memcpy(data + offset + index * 4, &o, 4);
	}
};


template <typename T>
using ListAccess = ListAccessHelp<typename MetaMagic<T>::t, T>;

template <typename T>
class ListIn;

template <typename T>
class ListInIterator {
private:
	const Reader & reader;
	const char * start;
	std::uint32_t index;
	using A = ListAccess<T>;
	friend class ListIn<T>;
	ListInIterator(const Reader & reader, const char * start, std::uint32_t index) noexcept : reader(reader), start(start), index(index) {}
public:
	using value_type = T;
	using size_type = std::size_t;

	ListInIterator(const ListInIterator &) = default;
	ListInIterator(ListInIterator &&) = default;
	ListInIterator & operator=(const ListInIterator &) = default;
	ListInIterator & operator=(ListInIterator &&) = default;

	explicit operator bool() const noexcept {
		if constexpr(A::optional)
			return A::has(start, index);
		else
			return true;
	}

	value_type operator*() const noexcept {
		if constexpr(A::optional)
			assert(A::has(start, index));
		return A::get(reader, start, index);
	}

	//Compare
	bool operator < (const ListInIterator & o) const noexcept {return index < o.index;}
	bool operator > (const ListInIterator & o) const noexcept {return index > o.index;}
	bool operator <= (const ListInIterator & o) const noexcept {return index <= o.index;}
	bool operator >= (const ListInIterator & o) const noexcept {return index >= o.index;}
	bool operator != (const ListInIterator & o) const noexcept {return index != o.index;}
	bool operator == (const ListInIterator & o) const noexcept {return index == o.index;}

	// Movement
	ListInIterator & operator++() noexcept {index++;}
	ListInIterator & operator--() noexcept {index--;}
	ListInIterator operator++(int) noexcept {ListInIterator t=*this; index++; return t;}
	ListInIterator operator--(int)  noexcept {ListInIterator t=*this; index--; return t;}
	ListInIterator operator+(int delta) const noexcept {ListInIterator t=*this; t += delta; return t;}
	ListInIterator operator-(int delta) const noexcept {ListInIterator t=*this; t -= delta; return t;}
	ListInIterator & operator+=(int delta) noexcept {index += delta;}
	ListInIterator & operator-=(int delta) noexcept {index -= delta;}
};


template <typename T>
class ListIn {
	friend class In;
	const Reader & reader;
	const char * start;
	const std::uint32_t size_;

 	ListIn(const Reader & reader, const char * start, std::uint32_t size) noexcept : reader(reader), start(start), size_(size) {}
	using A = ListAccess<T>;
public:
	static constexpr bool noexceptGet = noexcept(A::get(std::declval<const Reader&>(), std::declval<const char *>(), 0));

	using value_type = T;
	using size_type = std::size_t;
	using iterator = ListInIterator<T>;

	bool hasFront() const noexcept {return !empty() && has(0);}
	value_type front() const noexcept(noexceptGet) {assert(hasFront()); return A::get(reader, start, 0);}
	bool hasBack() const noexcept {return !empty() && has(size_-1);}
	value_type back() const noexcept(noexceptGet) {assert(hasBack()); return A::get(reader, start, size_-1);}
	size_type size() const noexcept {return size_;}
	bool empty() const noexcept {return size_ == 0;}
	iterator begin() const noexcept {return ListInIterator(reader, start, 0);}
	iterator end() const noexcept {return ListInIterator(reader, start, size_);}
	value_type at(size_type pos) const {
		if (pos >= size_) throw std::out_of_range("out of range");
		if (!has(pos)) throw std::out_of_range("unset member");
		return A::get(reader, start, pos);
	};
	value_type operator[] (size_type pos) const noexcept(noexceptGet) {
		assert(pos < size_ && has(pos)); 
		return A::get(reader, start, pos);
	}

	bool has(size_type pos) const noexcept {
		(void) pos;
		if constexpr (A::optional) return A::has(start, pos);
		return true;
	}
};

class In {
protected:
	const Reader & reader;
	const char * start;
	const uint32_t size;

	In(const Reader & reader, const char * start, uint32_t size) noexcept : reader(reader), start(start), size(size) {}

	template <typename T, uint32_t o>
	T getInnerUnchecked_() const noexcept {
		T ans;
		assert(o + sizeof(T) <= size);
		memcpy(&ans, start+ o, sizeof(T));
		return ans;
	}

	template <typename T, uint32_t o>
	T getInner_(T def) const noexcept {
		if (o + sizeof(T) > size) return def;
		return getInnerUnchecked_<T, o>();
	}


	template <typename T, uint32_t o>
	T getInner_() const noexcept {
		T ans;
		if (o + sizeof(T) > size)
			memset(&ans, 0, sizeof(T));
		else
			memcpy(&ans, start+ o, sizeof(T));
		return ans;
	}

	template <typename T, uint32_t o>
	T getTable_() const {
		const uint32_t off = getInnerUnchecked_<std::uint32_t, o>();
		const uint32_t size = T::readSize_(reader, off);
		return T(reader, reader.data+off+8, size);
	}

	template <typename T, uint32_t o>
	ListIn<T> getList_() const {
		const uint32_t off = getInnerUnchecked_<std::uint32_t, o>();
		uint32_t size = reader.readObjectSize_<0x3400BB46, ListAccess<T>::mult>(off);
		return ListIn<T>(reader, reader.data+off+8, size);
	}

	template <typename T, uint32_t o>
	std::pair<const T *, size_t> getListRaw_() const {
		const uint32_t off = getInnerUnchecked_<std::uint32_t, o>();
		const uint32_t size = reader.readObjectSize_<0x3400BB46, sizeof(T)>(off);
		return std::make_pair(reinterpret_cast<const T *>(reader.data+off+8), size);
	}	


	template <uint32_t o, uint8_t bit, uint8_t def>
	uint8_t getBit_() const noexcept {
		if (o < size)
			return *(const uint8_t *)(start + o) & 1 << bit;
		return def;
	}

	template <uint32_t o>
	std::string_view getText_() const {
		const uint32_t off = getInnerUnchecked_<std::uint32_t, o>();
		const uint32_t size = reader.readObjectSize_<0xD812C8F5>(off);
		return std::string_view(reader.data+off+8, size);
	}

	template <uint32_t o>
	std::pair<const void *, size_t> getBytes_() const {
		const uint32_t off = getInnerUnchecked_<std::uint32_t, o>();
		const uint32_t size = reader.readObjectSize_<0xDCDBBE10>(off);
		return std::make_pair(reader.data+off+8, size);
	}

	template <uint32_t o, uint32_t mult=1, uint32_t add=0>
	uint32_t getVLSize_() const {
		//Get the size of a vl object making throwing if it does not fit within the reader
		const uint32_t s = getInnerUnchecked_<std::uint32_t, o>();
		if (start + size + uint64_t(s)*mult + add > reader.data + reader.size) throw Error();
		return s;
	}

	template <typename T, uint32_t o>
	ListIn<T> getVLList_() const {
		return ListIn<T>(reader, start+size, getVLSize_<o, ListAccess<T>::mult>());
	}

	template <typename T, uint32_t o>
	std::pair<const T *, size_t> getVLListRaw_() const {
		return std::make_pair(reinterpret_cast<const T *>(start+size), getVLSize_<o, sizeof(T)>());
	}	

	template <typename T, uint32_t o>
	T getVLTable_() const {
		return T(reader, start+size, getVLSize_<o>());
	}

	template <uint32_t o>
	std::string_view getVLText_() const {
		const uint32_t s = getVLSize_<o, 1, 1>();
		if (start[size+s] != 0) throw Error(); //Check that the string is null terminated
		return std::string_view(start + size, s);
	}

	template <uint32_t o>
	std::pair<const void *, size_t> getVLBytes_() const {
		return std::make_pair(start + size, getVLSize_<o>());
	}

	template <uint32_t magic, uint32_t mult=1, uint32_t add=0>
	static uint32_t readObjectSize_(const Reader & reader, uint32_t offset) {
		return reader.readObjectSize_<magic, mult, add>(offset);
	}
};


template <>
struct MetaMagic<TextOut> {using t=TextTag;};
template <>
struct MetaMagic<std::string_view> {using t=TextTag;};

template <>
struct MetaMagic<BytesOut> {using t=BytesTag;};
template <>
struct MetaMagic<std::pair<const void *, size_t>> {using t=BytesTag;};

template <typename T>
class ListOut {
protected:
	friend class Writer;
	friend class Out;
	Writer & writer;
	uint32_t offset;
	uint32_t size_;
	using A=ListAccess<T>;
	ListOut(Writer & writer, uint32_t offset, uint32_t size_): writer(writer), offset(offset), size_(size_) {}
public:
	using value_type = T;
	void add(uint32_t index, value_type value) noexcept;
	uint32_t size() const noexcept {return size_;}
};

template <typename A>
struct MetaMagic<ListOut<A>> {using t=ListTag;};

class Writer {
private:
	char * data = nullptr;
	size_t size = 0;
	size_t capacity = 0;
	friend class Out;
	template <typename> friend class ListOut;
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

	TextOut constructText(std::string_view text) {
		TextOut o;
		o.offset = size;
		expand(text.size()+9);
		write((uint32_t)0xD812C8F5, o.offset);
		write((uint32_t)text.size(), o.offset+4);
		memcpy(data+o.offset+8, text.data(), text.size());
		data[o.offset+8+text.size()] = 0;
		return o;
	}

	BytesOut constructBytes(const void * data, size_t size) {
		BytesOut o;
		o.offset = this->size;
		expand(size+8);
		write((uint32_t)0xDCDBBE10, o.offset);
		write((uint32_t)size, o.offset+4);
		memcpy(this->data+o.offset+8, data, size);
		return o;
	}

	template <typename T>
	ListOut<T> constructList(size_t size) {
		using A = ListAccess<T>;
		ListOut<T> o(*this, this->size, size);
		expand(computeSize<A::mult>(size)+8);
		write((uint32_t)0x3400BB46, o.offset);
		write((uint32_t)size, o.offset+4);
		o.offset += 8;
		memset(data+o.offset, A::def, computeSize<A::mult>(size));
		return o;
	}

	ListOut<TextOut> constructTextList(size_t size) {return constructList<TextOut>(size);}
	ListOut<BytesOut> constructBytesList(size_t size) {return constructList<BytesOut>(size);}
};

template <typename T>
void ListOut<T>::add(uint32_t index, value_type value) noexcept {
	assert(index < size_);
	A::set(writer.data, offset, index, value);
}

class Out {
protected:
	friend class Writer;
	template <typename, typename> friend class ListAccessHelp;

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

	template <typename T, uint32_t offset>
	void setList_(ListOut<T> t) noexcept {
		setInner_<std::uint32_t, offset>(t.offset-8);
	}

	template <uint32_t offset>
	void setText_(TextOut t) noexcept {
		setInner_<std::uint32_t, offset>(t.offset);
	}

	template <uint32_t offset>
	void setBytes_(BytesOut t) noexcept {
		setInner_<std::uint32_t, offset>(t.offset);
	}

	template <typename T>
	T constructUnionMember_() const noexcept {
		return T(writer, false);
	}

	template <uint32_t offset>
	void addVLBytes_(const char *data, size_t size) noexcept {
		setInner_<uint32_t, offset>(size);
		auto start = writer.size;
		writer.expand(size);
		memcpy(writer.data+start, data, size);
	}

	template <uint32_t offset>
	void addVLText_(std::string_view str) noexcept {
		setInner_<uint32_t, offset>(str.size());
		auto start = writer.size;
		writer.expand(str.size()+1);
		memcpy(writer.data+start, str.data(), str.size());
		writer.data[start+str.size()] = 0;
	}

	template <uint32_t offset, typename T>
	ListOut<T> addVLList_(size_t size) noexcept {
		setInner_<uint32_t, offset>(size);
		using A = ListAccess<T>;
		ListOut<T> o(writer, writer.size, size);
		size_t bsize = computeSize<A::mult>(size);
		writer.expand(bsize);
		memset(writer.data+o.offset, A::def, bsize);
		return o;
	}
};


std::pair<const char *, size_t> Writer::finalize(const Out & root) {
	write((std::uint32_t)0xB5C0C4B3, 0);
	write(root.offset - 8, 4);
	return std::make_pair(data, size);
}

} //namespace scalgoproto
