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

    template <typename T, uint32_t offset>
    T getInner_(T def) const noexcept {
        if (offset + sizeof(T) > size) return def;
        T ans;
        memcpy(&ans, data + offset, sizeof(T));
        return ans;
    }

    template <typename T, uint32_t offset>
    T getInner_() const noexcept {
        T ans;
        if (offset + sizeof(T) > size)
            memset(&ans, 0, sizeof(T));
        else
            memcpy(&ans, data + offset, sizeof(T));
        return ans;
    }

    template <typename T, uint32_t offset>
    T getTable_() const noexcept {
        uint32_t off;
        assert(offset + 4 <= size);
        memcpy(&off, data+offset, 4);
        uint32_t size = T::readSize_(data, off);
		//TODO validate magic
        return T(data, off+8, size);
    }

    template <typename T, uint32_t offset>
    T getVLTable_() const noexcept {
	    return T(data, offset+size, getInner_<std::uint32_t, offset>());
    }

    template <uint32_t offset, uint8_t bit, uint8_t def>
    uint8_t getBit_() const noexcept {
        if (offset < size)
            return *(const uint8_t *)(data + offset) & 1 << bit;
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
public:
    Writer();
    ~Writer();
    void reserve(size_t size);
    void clear();
    std::pair<const char *, size_t> finalize(Out root);
    
    template <typename T>
    T construct() {
        return T(*this);
    }

    void expand(uint32_t s) {
        if (size + s > capacity) reserve(capacity * 2);
        size += s;
    }

    template <typename T>
    void write(const T & t, uint32_t offset) {
        memcpy(data, &t, sizeof(T));
        size += sizeof(T);
    }
};

class Out {
protected:
    uint32_t offset;
    Writer & writer;
  
    Out(Writer & writer): offset(writer.size), writer(writer) {}
  
    Out(Writer & writer, uint32_t magic, uint32_t size): offset(writer.size), writer(writer) {
        writer.expand(size + 8);
        writer.write(magic, offset);
        writer.write(size, offset+4);
        offset += 8;
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
        setInner_<std::uint32_t, offset>(t.offset);
    }
};


} //namespace scalgoproto
