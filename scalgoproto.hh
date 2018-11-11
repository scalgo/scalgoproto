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
struct EnumTag;
struct PodTag;
struct TableTag;
struct ListTag;
struct TextTag;
struct BytesTag;
struct UnknownTag;


template <typename, typename>
class ListAccessHelp;


class MagicError: std::runtime_error {
public:
	MagicError() : std::runtime_error("MagicError") {}
};

class TextOut {
	friend class Writer;
	friend class Out;
	template <typename, typename> friend class ListAccessHelp;
protected:
	uint32_t offset;
};

class BytesOut {
	friend class Writer;
	friend class Out;
	template <typename, typename> friend class ListAccessHelp;
protected:
	uint32_t offset;
};


template <typename T> struct MetaMagic {using t=UnknownTag;};
template <> struct MetaMagic<bool> {using t=PodTag;};
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

template <typename T>
struct ListAccessHelp<PodTag, T> {
	static constexpr bool optional = false;
	static constexpr size_t size = sizeof(T);
	static constexpr int def = 0;
	static T get(const char * data, uint32_t offset, uint32_t index) noexcept {
		T ans;
		memcpy(&ans, data + offset + index * sizeof(T), sizeof(T));
		return ans;
	}
	static void set(char * data, uint32_t offset, uint32_t index, const T & value) noexcept {
		memcpy(data + offset + index * sizeof(T), &value, sizeof(T));
	}
};

template <typename T>
struct ListAccessHelp<EnumTag, T> {
	static constexpr bool optional = true;
	static constexpr size_t size = sizeof(T);
	static constexpr int def = 255;
	static bool has(const char * data, uint32_t offset, uint32_t index) noexcept {
		return ((const unsigned char *)(data + offset))[index] != 255;
	}
	static T get(const char * data, uint32_t offset, uint32_t index) noexcept {
		T ans;
		memcpy(&ans, data + offset + index * sizeof(T), sizeof(T));
		return ans;
	}
	static void set(char * data, uint32_t offset, uint32_t index, const T & value) noexcept {
		memcpy(data + offset + index * sizeof(T), &value, sizeof(T));
	}
};

template <typename T>
struct ListAccessHelp<TextTag, T> {
	static constexpr bool optional = true;
	static constexpr size_t size = 4;
	static constexpr int def = 0;
	static bool has(const char * data, uint32_t offset, uint32_t index) noexcept {
		uint32_t off;
		memcpy(&off, data + offset + index * 4, 4);
		return off != 0;
	}
	static std::string_view get(const char * data, uint32_t offset, uint32_t index) noexcept {
		uint32_t off, word;
		memcpy(&off, data + offset + index * 4, 4);
		memcpy(&word, data + off, 4);
		assert(word == 0xD812C8F5);
		memcpy(&word, data + off + 4, 4);
		return std::string_view(data+off+8, word);
	}
	static void set(char * data, uint32_t offset, uint32_t index, const TextOut & value) noexcept {
		memcpy(data + offset + index * 4, &value.offset, 4);
	}
};

template <typename T>
struct ListAccessHelp<BytesTag, T> {
	static constexpr bool optional = true;
	static constexpr size_t size = 4;
	static constexpr int def = 0;
	static bool has(const char * data, uint32_t offset, uint32_t index) noexcept {
		uint32_t off;
		memcpy(&off, data + offset + index * 4, 4);
		return off != 0;
	}
	static std::pair<const void *, size_t> get(const char * data, uint32_t offset, uint32_t index) noexcept {
		uint32_t off, word;
		memcpy(&off, data + offset + index * 4, 4);
		memcpy(&word, data + off, 4);
		assert(word == 0xDCDBBE10);
		memcpy(&word, data + off + 4, 4);
		return std::make_pair(data+off+8, word);
	}
	static void set(char * data, uint32_t offset, uint32_t index, const BytesOut & value) noexcept {
		memcpy(data + offset + index * 4, &value.offset, 4);
	}
};

template <typename T>
using ListAccess = ListAccessHelp<typename MetaMagic<T>::t, T>;


template <typename T>
class ListIn;

template <typename T>
class ListInIterator {
private:
	const char * data;
	std::uint32_t offset;
	std::uint32_t index;
	using A = ListAccess<T>;
	friend class ListIn<T>;
	ListInIterator(const char *data, std::uint32_t offset, std::uint32_t index): data(data), offset(offset), index(index) {}
public:
	using value_type = T;
	using size_type = std::size_t;

	ListInIterator(const ListInIterator &) = default;
	ListInIterator(ListInIterator &&) = default;
	ListInIterator & operator=(const ListInIterator &) = default;
	ListInIterator & operator=(ListInIterator &&) = default;

	explicit operator bool() const noexcept {
		if constexpr(A::optional)
			return A::has(data, offset, index);
		else
			return true;
	}

	value_type operator*() const noexcept {
		if constexpr(A::optional)
			assert(A::has(data, offset, index));
		return A::get(data, offset, index);
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

class In;

template <typename T>
class ListIn {
	friend class In;
	const char * data;
	std::uint32_t offset;
	std::uint32_t size_;
	using A = ListAccess<T>;
public:
	using value_type = T;
	using size_type = std::size_t;
	using iterator = ListInIterator<T>;

	bool hasFront() const noexcept{
		if (empty()) return false;
		if constexpr (A::optional) return A::has(data, offset, 0);
		else return true;
	}
	value_type front() const noexcept {assert(hasFront()); return A::get(data, offset, 0);}
	bool hasBack() const noexcept{
		if (empty()) return false;
		if constexpr (A::optional) return A::has(data, offset, size_-1);
		else return true;
	}
	value_type back() const noexcept {assert(hasBack()); return A::get(data, offset, size_-1);}
	size_type size() const noexcept {return size_;}
	bool empty() const noexcept {return size_ == 0;}
	iterator begin() const noexcept {return ListInIterator(data, offset, 0);}
	iterator end() const noexcept {return ListInIterator(data, offset, size_);}
	value_type at(size_type pos) const {
		if (pos >= size_) throw std::out_of_range("out of range");
		if (!has(pos)) throw std::out_of_range("unset member");
		return A::get(data, offset, pos);
	};
	value_type operator[] (size_type pos) const noexcept {assert(pos < size_ && has(pos)); return A::get(data, offset, pos);}
	bool has(size_type pos) const noexcept {
		if constexpr (A::optional)
			return A::has(data, offset, pos);
		else
			(void)pos;
		return true;
	}
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
	T getTable_() const {
		uint32_t off;
		assert(o + 4 <= size);
		memcpy(&off, data+offset + o, 4);
		uint32_t size = T::readSize_(data, off);
		return T(data, off+8, size);
	}

	template <typename T, uint32_t o>
	ListIn<T> getList_() const {
		uint32_t off;
		assert(o + 4 <= size);
		memcpy(&off, data+offset + o, 4);
		uint32_t size = readSize_(data, off, 0x3400BB46);

		ListIn<T> ans;
		ans.data = data;
		ans.offset = off + 8;
		ans.size_ = size;
		return ans;
	}

	template <typename T, uint32_t o>
	std::pair<const T *, size_t> getListRaw_() const {
		uint32_t off;
		assert(o + 4 <= size);
		memcpy(&off, data+offset + o, 4);
		uint32_t size = readSize_(data, off, 0x3400BB46);
		return std::make_pair(reinterpret_cast<const T *>(data+off+8), size);
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

	template <uint32_t o>
	std::string_view getText_() const {
		uint32_t off;
		assert(o + 4 <= size);
		memcpy(&off, data+offset + o, 4);
		uint32_t size = readSize_(data, off, 0xD812C8F5);
		return std::string_view(data+off+8, size);
	}

	template <uint32_t o>
	std::pair<const void *, size_t> getBytes_() const {
		uint32_t off;
		assert(o + 4 <= size);
		memcpy(&off, data+offset + o, 4);
		uint32_t size = readSize_(data, off, 0xDCDBBE10);
		return std::make_pair(data+off+8, size);
	}
};

class Reader {
private:
	const char * data;
public:
	Reader(const char * data, size_t size): data(data) {(void)size;}

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
	char * data;
	uint32_t offset;
	uint32_t size_;
	using A=ListAccess<T>;
public:
	using value_type = T;
	void add(uint32_t index, value_type value) noexcept {
		assert(index < size_);
		A::set(data, offset, index, value);
	}
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
		ListOut<T> o;
		o.offset = this->size;
		o.size_ = size;
		o.data = data;
		expand(size*A::size+8);
		write((uint32_t)0x3400BB46, o.offset);
		write((uint32_t)size, o.offset+4);
		o.offset += 8;
		memset(data+o.offset, A::def, size*A::size);
		return o;
	}

	ListOut<TextOut> constructTextList(size_t size) {return constructList<TextOut>(size);}
	ListOut<BytesOut> constructBytesList(size_t size) {return constructList<BytesOut>(size);}
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
};


std::pair<const char *, size_t> Writer::finalize(const Out & root) {
	write((std::uint32_t)0xB5C0C4B3, 0);
	write(root.offset - 8, 4);
	return std::make_pair(data, size);
}

} //namespace scalgoproto
