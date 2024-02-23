# -*- mode: python; tab-width: 4; indent-tabs-mode: nil; python-indent-offset: 4; coding: utf-8 -*-
import enum
import math
import struct
from abc import abstractmethod, ABC
from typing import (
    Callable,
    ClassVar,
    Generic,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    Optional,
    Any,
)

MESSAGE_MAGIC = 0xB5C0C4B3
TEXT_MAGIC = 0xD812C8F5
BYTES_MAGIC = 0xDCDBBE10
LIST_MAGIC = 0x3400BB46
DIRECT_LIST_MAGIC = 0xE2C6CC05


class Hash(ABC):
    def update(self, data: bytes) -> None:
        pass


def digest(h: Hash, v: Any) -> None:
    if v is None:
        return
    if hasattr(v, "_digest"):
        v._digest(h)
    else:
        h.update(b"\xff\xe0")
        if isinstance(v, enum.IntEnum):
            h.update(str(int(v)).encode("utf-8"))
        elif isinstance(v, (bool, int)):
            h.update(str(v).encode("utf-8"))
        elif isinstance(v, float):
            h.update(struct.pack("<d", v).replace(b"\xff", b"\xff\xef"))
        elif isinstance(v, str):
            h.update(v.encode("utf-8"))
        elif isinstance(v, bytes):
            h.update(v.replace(b"\xff", b"\xff\xef"))
        else:
            assert False


B = TypeVar("B")


class StructType(Generic[B]):
    _WIDTH: ClassVar[int] = 0

    @staticmethod
    @abstractmethod
    def _write(writer: "Writer", offset: int, value: B) -> B:
        ...

    def __str__(self):
        o = []
        for m in self.__slots__:
            o.append("%s: %s" % (m, getattr(self, m)))
        return "{%s}" % ", ".join(o)

    def _to_dict(self):
        o = {}
        for m in self.__slots__:
            v = getattr(self, m)
            if hasattr(v, "_to_dict"):
                v = v._to_dict()
            o[m] = v
        return o

    def _digest(self, h: Hash) -> None:
        h.update(b"\xff\xe1")
        for m in self.__slots__:
            digest(h, getattr(self, m))
        h.update(b"\xff\xe2")


TI = TypeVar("TI", bound="TableIn")
TO = TypeVar("TO", bound="TableOut")
UI = TypeVar("UI", bound="UnionIn")
UO = TypeVar("UO", bound="UnionOut")
E = TypeVar("E", bound=enum.IntEnum)
S = TypeVar("S", bound=StructType)

TT = TypeVar("TT")


def split48_(v: int) -> Tuple[int, int]:
    return (v & 0xFFFFFFFF, v >> 32)


def pack48_(v: int) -> bytes:
    l, h = split48_(v)
    return struct.pack("<IH", l, h)


def join48_(l: int, h: int) -> int:
    return l + (h << 32)


def unpack48_(v: bytes) -> int:
    l, h = struct.unpack("<IH", v)
    return join48_(l, h)


class Adder(Generic[B]):
    def __init__(self, fset: Callable[[TT, B], None]) -> None:
        self.fset = fset
        self.__doc__ = fset.__doc__

    def __set__(self, obj: TT, value: B) -> None:
        self.fset(obj, value)


class ListIn(Sequence[B]):
    """Class for reading a list of B"""

    def __init__(
        self,
        reader: "Reader",
        size: int,
        offset: int,
        getter: Callable[["Reader", int, int], B],
        haser: Callable[["Reader", int, int], bool],
        require_has: bool,
    ) -> None:
        """Private constructor. Use the accessor methods on tables to get an instance"""
        self._reader = reader
        self._offset = offset
        self._size = size
        self._getter = getter
        self._haser = haser
        self._require_has = require_has

    def has(self, idx: int) -> bool:
        """Return True if there is an element on possision idx. Note that idx must be less than size"""
        return self._haser(self._reader, self._offset, idx)

    def __len__(self) -> int:
        return self._size

    def __getitem__(self, idx: int) -> B:
        if idx < 0:
            idx += self._size
        if not 0 <= idx < self._size:
            raise IndexError()
        if self._require_has and not self.has(idx):
            raise IndexError()
        return self._getter(self._reader, self._offset, idx)

    def __str__(self) -> str:
        return "[%s]" % (", ".join(map(str, self)))

    def _to_dict(self):
        o = []
        for v in self:
            if hasattr(v, "_to_dict"):
                v = v._to_dict()
            o.append(v)
        return o

    def _digest(self, h: Hash) -> None:
        h.update(b"\xff\xe3")
        for v in self:
            digest(h, v)
        h.update(b"\xff\xe4")


class TableListIn(ListIn[B]):
    def __init__(
        self,
        reader: "Reader",
        size: int,
        offset: int,
        haser: Callable[["Reader", int, int], bool],
        t: Type[B],
    ) -> None:
        """Private constructor. Use the accessor methods on tables to get an instance"""
        require_has = False
        self._table_type = t
        super().__init__(
            reader,
            size,
            offset,
            self._table_list_getter,
            self._table_list_haser,
            require_has,
        )

    def _table_list_getter(self, r: "Reader", s: int, i: int) -> B:
        ooo = unpack48_(r._data[s + 6 * i : s + 6 * i + 6])
        if ooo == 0:
            return self._table_type(r, 0, 0)
        sss = r._read_size(ooo, self._table_type._MAGIC)
        return self._table_type(r, ooo + 10, sss)

    def _table_list_haser(self, r: "Reader", s: int, i: int) -> bool:
        return unpack48_(r._data[s + 6 * i : s + 6 * i + 6]) != 0


class DirectTableListIn(ListIn[B]):
    def __init__(
        self,
        reader: "Reader",
        size: int,
        offset: int,
        t: Type[B],
        item_size: int,
    ) -> None:
        """Private constructor. Use the accessor methods on tables to get an instance"""
        require_has = False
        self._table_type = t
        self._item_size = item_size
        super().__init__(
            reader,
            size,
            offset,
            self._direct_table_list_getter,
            self._direct_table_list_haser,
            require_has,
        )

    def _direct_table_list_getter(self, r: "Reader", s: int, i: int) -> B:
        return self._table_type(r, s + i * self._item_size, self._item_size)

    def _direct_table_list_haser(self, r: "Reader", s: int, i: int) -> bool:
        return True


class UnionIn(object):
    __slots__ = ["_reader", "_type", "_offset", "_size"]

    def __init__(
        self, reader: "Reader", type: int, offset: int, size: Optional[int] = None
    ):
        """Private constructor. Use the accessor methods on tables or the root method on Reader to get an instance"""
        self._reader = reader
        self._type = type
        self._offset = offset
        self._size = size

    def __str__(self) -> str:
        if self._type == 0:
            return "{}"
        m = self._MEMBERS[self._type - 1]
        if hasattr(self, m):
            return "{%s: %s}" % (m, getattr(self, m))
        return "{%s}" % m

    def _to_dict(self):
        if self._type == 0:
            return {}
        m = self._MEMBERS[self._type - 1]
        if not hasattr(self, m):
            return {m: None}
        v = getattr(self, m)
        if hasattr(v, "_to_dict"):
            v = v._to_dict()
        return {m: v}

    def _digest(self, h: Hash) -> None:
        h.update(b"\xff\xe5%d" % (self._type))
        if self._type == 0:
            return
        m = self._MEMBERS[self._type - 1]
        digest(h, getattr(self, m, None))

    def _get_ptr(self, magic: int) -> Tuple[int, int]:
        if self._size is not None:
            return (self._offset, self._size)
        return (self._offset + 10, self._reader._read_size(self._offset, magic))


class TableIn(object):
    """Base class for reading a table"""

    __slots__ = ["_reader", "_offset", "_size"]
    _MAGIC: int = 0
    _MEMBERS: Sequence[str] = None

    def __init__(self, reader: "Reader", offset: int, size: int) -> None:
        """Private constructor. Use the accessor methods on tables or the root method on Reader to get an instance"""
        self._reader = reader
        self._offset = offset
        self._size = size

    def __str__(self):
        o = []
        for m in self._MEMBERS:
            if getattr(self, "has_" + m, True):
                o.append("%s: %s" % (m, getattr(self, m)))
        return "{%s}" % ", ".join(o)

    def _to_dict(self):
        o = {}
        for m in self._MEMBERS:
            if getattr(self, "has_" + m, True):
                v = getattr(self, m)
                if hasattr(v, "_to_dict"):
                    v = v._to_dict()
                o[m] = v
        return o

    def _digest(self, h: Hash) -> None:
        h.update(b"\xff\xe6")
        for m in self._MEMBERS:
            if getattr(self, "has_" + m, True):
                digest(h, getattr(self, m))
        h.update(b"\xff\xe7")

    def _get_uint48_f(self, o: int) -> int:
        return unpack48_(self._reader._data[self._offset + o : self._offset + o + 6])

    def _get_int8(self, o: int, d: int) -> int:
        return (
            struct.unpack(
                "<b", self._reader._data[self._offset + o : self._offset + o + 1]
            )[0]
            if o < self._size
            else d
        )

    def _get_uint8(self, o: int, d: int) -> int:
        return (
            struct.unpack(
                "<B", self._reader._data[self._offset + o : self._offset + o + 1]
            )[0]
            if o < self._size
            else d
        )

    def _get_int16(self, o: int, d: int) -> int:
        return (
            struct.unpack(
                "<h", self._reader._data[self._offset + o : self._offset + o + 2]
            )[0]
            if o < self._size
            else d
        )

    def _get_uint16(self, o: int, d: int) -> int:
        return (
            struct.unpack(
                "<H", self._reader._data[self._offset + o : self._offset + o + 2]
            )[0]
            if o < self._size
            else d
        )

    def _get_int32(self, o: int, d: int) -> int:
        return (
            struct.unpack(
                "<i", self._reader._data[self._offset + o : self._offset + o + 4]
            )[0]
            if o < self._size
            else d
        )

    def _get_uint32(self, o: int, d: int) -> int:
        return (
            struct.unpack(
                "<I", self._reader._data[self._offset + o : self._offset + o + 4]
            )[0]
            if o < self._size
            else d
        )

    def _get_uint48(self, o: int) -> int:
        return (
            unpack48_(self._reader._data[self._offset + o : self._offset + o + 6])
            if o < self._size
            else 0
        )

    def _get_int64(self, o: int, d: int) -> int:
        return (
            struct.unpack(
                "<q", self._reader._data[self._offset + o : self._offset + o + 8]
            )[0]
            if o < self._size
            else d
        )

    def _get_uint64(self, o: int, d: int) -> int:
        return (
            struct.unpack(
                "<Q", self._reader._data[self._offset + o : self._offset + o + 8]
            )[0]
            if o < self._size
            else d
        )

    def _get_float32(self, o: int, d: float) -> float:
        return (
            struct.unpack(
                "<f", self._reader._data[self._offset + o : self._offset + o + 4]
            )[0]
            if o < self._size
            else d
        )

    def _get_float64(self, o: int, d: float) -> float:
        return (
            struct.unpack(
                "<d", self._reader._data[self._offset + o : self._offset + o + 8]
            )[0]
            if o < self._size
            else d
        )

    def _get_bit(self, o: int, b: int, d: bool) -> bool:
        return (
            self._reader._data[self._offset + o] & (1 << b) != 0
            if o < self._size
            else d
        )

    def _get_ptr(self, o: int, magic: int) -> Tuple[int, int]:
        off = self._get_uint48_f(o)
        if off == 0:
            return (0, 0)
        size = self._reader._read_size(off, magic)
        return (off + 10, size)

    def _get_ptr_inplace(self, o: int, magic: int) -> Tuple[int, int]:
        size = self._get_uint48_f(o)
        return (self._offset + self._size, size)


class Reader(object):
    """Responsible for reading a message"""

    def __init__(self, data: bytes) -> None:
        """data is the message to read from"""
        self._data = data

    def _read_size(self, offset: int, magic: int):
        m, sizelow, sizehigh = struct.unpack("<IIH", self._data[offset : offset + 10])
        if m != magic:
            raise Exception("Expected magic %08X but got %08X" % (magic, m))
        return join48_(sizelow, sizehigh)

    def _get_table_list(
        self, t: Type[TI], off: int, size: int, direct: bool = False
    ) -> ListIn[TI]:
        if not direct:
            return TableListIn[TI](self, size, off, t)
        else:
            magic, item_size = struct.unpack("<II", self._data[off : off + 8])
            if magic != t._MAGIC:
                raise Exception(
                    "Expected scalgoproto magic %08X but got %08X" % (t._MAGIC, magic)
                )

            if off + 8 + item_size * size > len(self._data):
                raise Exception("Invalid table size")

            return DirectTableListIn[TI](self, size, off + 8, t, item_size)

    def _get_union_list(self, t: Type[UI], off: int, size: int) -> ListIn[UI]:
        return ListIn[UI](
            self,
            size,
            off,
            lambda r, s, i: t._read(r, s + i * t._WIDTH),
            lambda r, s, i: True,
            False,
        )

    def _get_bool_list(self, off: int, size: int) -> ListIn[bool]:
        return ListIn[bool](
            self,
            size,
            off,
            lambda r, s, i: (r._data[s + (i >> 3)] >> (i & 7)) & 1 != 0,
            lambda r, s, i: True,
            False,
        )

    def _get_int_list(self, f: str, w: int, off: int, size: int) -> ListIn[int]:
        return ListIn[int](
            self,
            size,
            off,
            lambda r, s, i: struct.unpack("<" + f, r._data[s + i * w : s + i * w + w])[
                0
            ],
            lambda r, s, i: True,
            False,
        )

    def _get_float_list(self, f: str, w: int, off: int, size: int) -> ListIn[float]:
        return ListIn[float](
            self,
            size,
            off,
            lambda r, s, i: struct.unpack("<" + f, r._data[s + i * w : s + i * w + w])[
                0
            ],
            lambda r, s, i: not math.isnan(
                struct.unpack("<" + f, r._data[s + i * w : s + i * w + w])[0]
            ),
            False,
        )

    def _get_struct_list(self, t: Type[S], off: int, size: int) -> ListIn[S]:
        return ListIn[S](
            self,
            size,
            off,
            lambda r, s, i: t._read(r, s + i * t._WIDTH),
            lambda r, s, i: True,
            False,
        )

    def _get_enum_list(self, t: Type[E], off: int, size: int) -> ListIn[E]:
        return ListIn[E](
            self,
            size,
            off,
            lambda r, s, i: t(r._data[s + i]),
            lambda r, s, i: r._data[s + i] != 255,
            True,
        )

    def _get_text_list(self, off: int, size: int) -> ListIn[str]:
        def getter(r: "Reader", s: int, i: int) -> str:
            ooo = unpack48_(r._data[s + 6 * i : s + 6 * i + 6])
            if ooo == 0:
                return ""
            sss = r._read_size(ooo, TEXT_MAGIC)
            return r._data[ooo + 10 : ooo + 10 + sss].decode("utf-8")

        return ListIn[str](
            self,
            size,
            off,
            getter,
            lambda r, s, i: unpack48_(r._data[s + 6 * i : s + 6 * i + 6]) != 0,
            False,
        )

    def _get_bytes_list(self, off: int, size: int) -> ListIn[bytes]:
        def getter(r: "Reader", s: int, i: int) -> bytes:
            ooo = unpack48_(r._data[s + 6 * i : s + 6 * i + 6])
            sss = r._read_size(ooo, BYTES_MAGIC)
            return r._data[ooo + 10 : ooo + 10 + sss]

        return ListIn[bytes](
            self,
            size,
            off,
            getter,
            lambda r, s, i: unpack48_(r._data[s + 6 * i : s + 6 * i + 6]) != 0,
            False,
        )

    def root(self, type: Type[TI]) -> TI:
        """Return root node of message, of type type"""
        magic, offsetlow, offsethigh = struct.unpack("<IIH", self._data[0:10])
        offset = join48_(offsetlow, offsethigh)
        if magic != MESSAGE_MAGIC:
            if magic == 0xFD2FB528:
                raise Exception(
                    "Expected scalgoproto magic %08X " % MESSAGE_MAGIC
                    + "but got the zstd magic instead (%08X). " % magic
                    + "Decompress the data with zstd.decompress() first."
                )
            raise Exception(
                "Expected scalgoproto magic %08X but got %08X" % (MESSAGE_MAGIC, magic)
            )
        size = self._read_size(offset, type._MAGIC)
        return type(self, offset + 10, size)


class TextOut(object):
    def __init__(self, offset: int) -> None:
        self._offset = offset


class BytesOut(object):
    def __init__(self, offset: int) -> None:
        self._offset = offset


class TableOut(object):
    __slots__ = ["_writer", "_offset"]
    _MAGIC: ClassVar[int] = 0
    _SIZE: ClassVar[int] = 0
    _DEFAULT: ClassVar[bytes] = b""

    def __init__(
        self, writer: "Writer", with_header: bool = True, offset: Optional[int] = None
    ) -> None:
        """Private constructor. Use factory methods on writer"""
        assert self._SIZE == len(self._DEFAULT)
        self._writer = writer
        if offset is not None:
            self._offset = offset
        else:
            self._writer._reserve(self._SIZE + 10)
            if with_header:
                sizelow, sizehigh = split48_(self._SIZE)
                writer._write(struct.pack("<IIH", self._MAGIC, sizelow, sizehigh))
            self._offset = writer._used
            writer._write(self._DEFAULT)

    def _set_int8(self, o: int, v: int) -> None:
        self._writer._put(self._offset + o, struct.pack("<b", v))

    def _set_uint8(self, o: int, v: int) -> None:
        self._writer._put(self._offset + o, struct.pack("<B", v))

    def _set_int16(self, o: int, v: int) -> None:
        self._writer._put(self._offset + o, struct.pack("<h", v))

    def _set_uint16(self, o: int, v: int) -> None:
        self._writer._put(self._offset + o, struct.pack("<H", v))

    def _set_int32(self, o: int, v: int) -> None:
        self._writer._put(self._offset + o, struct.pack("<i", v))

    def _set_uint32(self, o: int, v: int) -> None:
        self._writer._put(self._offset + o, struct.pack("<I", v))

    def _set_uint48(self, o: int, v: int) -> None:
        self._writer._put(self._offset + o, pack48_(v))

    def _set_int64(self, o: int, v: int) -> None:
        self._writer._put(self._offset + o, struct.pack("<q", v))

    def _set_uint64(self, o: int, v: int) -> None:
        self._writer._put(self._offset + o, struct.pack("<Q", v))

    def _set_float32(self, o: int, v: float) -> None:
        self._writer._put(self._offset + o, struct.pack("<f", v))

    def _set_float64(self, o: int, v: float) -> None:
        self._writer._put(self._offset + o, struct.pack("<d", v))

    def _set_bit(self, o: int, b: int) -> None:
        self._writer._data[self._offset + o] ^= 1 << b

    def _unset_bit(self, o: int, b: int) -> None:
        self._writer._data[self._offset + o] &= ~(1 << b)

    def _set_table(self, o: int, v: TO) -> None:
        self._writer._put(self._offset + o, pack48_(v._offset - 10))

    def _set_text(self, o: int, v: Union[TextOut, str]) -> None:
        if not isinstance(v, TextOut):
            v = self._writer.construct_text(v)
        self._writer._put(self._offset + o, pack48_(v._offset - 10))

    def _set_bytes(self, o: int, v: Union[BytesOut, bytes]) -> None:
        if not isinstance(v, BytesOut):
            v = self._writer.construct_bytes(v)
        self._writer._put(self._offset + o, pack48_(v._offset - 10))

    def _set_list(self, o: int, v: "OutList") -> None:
        self._writer._put(self._offset + o, pack48_(v._offset - 10))

    def _get_uint16(self, o: int) -> int:
        return struct.unpack(
            "<H", self._writer._data[self._offset + o : self._offset + o + 2]
        )[0]

    def _add_inplace_text(self, o: int, t: str) -> None:
        assert (
            self._writer._used == self._offset + self._SIZE
        ), "No object may be created between table and its implace text"
        tt = t.encode("utf-8")
        self._writer._put(self._offset + o, pack48_(len(tt)))
        self._writer._reserve(len(tt) + 1)
        self._writer._write(tt)
        self._writer._write(b"\0")

    def _add_inplace_bytes(self, o: int, t: bytes) -> None:
        assert (
            self._writer._used == self._offset + self._SIZE
        ), "No object may be created between table and its implace bytes"
        self._writer._put(self._offset + o, pack48_(len(t)))
        self._writer._reserve(len(t))
        self._writer._write(t)

    def _set_inplace_list(self, o: int, size: int) -> None:
        self._writer._put(self._offset + o, pack48_(size))


class UnionOut(object):
    __slots__ = ["_writer", "_offset", "_end"]

    def __init__(self, writer: "Writer", offset: int, end: int) -> None:
        self._writer = writer
        self._offset = offset
        self._end = end

    def _set(self, idx: int, offset: int) -> None:
        offsetlow, offsethigh = split48_(offset)
        self._writer._put(self._offset, struct.pack("<HIH", idx, offsetlow, offsethigh))

    def _set_text(self, idx: int, v: Union[TextOut, str]) -> None:
        if not isinstance(v, TextOut):
            v = self._writer.construct_text(v)
        self._set(idx, v._offset - 10)

    def _set_bytes(self, idx: int, v: Union[BytesOut, bytes]) -> None:
        if not isinstance(v, BytesOut):
            v = self._writer.construct_bytes(v)
        self._set(idx, v._offset - 10)

    def _add_inplace_text(self, idx: int, v: str) -> None:
        assert (
            self._writer._used == self._end
        ), "No object may be created between table and its implace text"
        tt = v.encode("utf-8")
        self._set(idx, len(tt))
        self._writer._reserve(len(tt) + 1)
        self._writer._write(tt)
        self._writer._write(b"\0")

    def _add_inplace_bytes(self, idx: int, t: bytes) -> None:
        assert (
            self._writer._used == self._end
        ), "No object may be created between table and its implace bytes"
        self._set(idx, len(t))
        self._writer._reserve(len(t))
        self._writer._write(t)


class OutList:
    _offset: int = 0
    _size: int = 0

    def __init__(
        self, writer: "Writer", d: bytes, size: int, with_weader: bool
    ) -> None:
        """Private constructor. Use factory methods on writer"""
        self._writer = writer
        writer._reserve(len(d) + 10)
        if with_weader:
            sizelow, sizehigh = split48_(size)
            writer._write(struct.pack("<IIH", LIST_MAGIC, sizelow, sizehigh))
        self._offset = writer._used
        self._size = size
        writer._write(d)

    def __len__(self):
        return self._size

    def _copy(self, inp: ListIn) -> None:
        assert self._size == inp._size
        for i in range(self._size):
            self[i] = inp[i]


class BasicListOut(OutList, Generic[B]):
    def __init__(
        self, writer: "Writer", e: str, w: int, size: int, with_header: bool = True
    ) -> None:
        """Private constructor. Use factory methods on writer"""
        super().__init__(writer, b"\0" * w * size, size, with_header)
        self._e = "<" + e
        self._w = w

    def __setitem__(self, index: int, value: B) -> None:
        """Add value to list at index"""
        assert 0 <= index < self._size
        self._writer._put(self._offset + index * self._w, struct.pack(self._e, value))


class BoolListOut(OutList):
    def __init__(self, writer: "Writer", size: int, with_header: bool = True) -> None:
        """Private constructor. Use factory methods on writer"""
        super().__init__(writer, b"\0" * ((size + 7) >> 3), size, with_header)

    def __setitem__(self, index: int, value: bool) -> None:
        """Add value to list at index"""
        assert 0 <= index < self._size
        if value:
            self._writer._data[self._offset + (index >> 3)] |= 1 << (index & 7)
        else:
            self._writer._data[self._offset + (index >> 3)] &= ~(1 << (index & 7))


class EnumListOut(OutList, Generic[E]):
    def __init__(
        self, writer: "Writer", e: Type[E], size: int, withHeader: bool = True
    ) -> None:
        """Private constructor. Use factory methods on writer"""
        super().__init__(writer, b"\xff" * size, size, withHeader)

    def __setitem__(self, index: int, value: E) -> None:
        """Add value to list at index"""
        self._writer._put(self._offset + index, struct.pack("B", int(value)))


class StructListOut(OutList, Generic[S]):
    def __init__(
        self, writer: "Writer", s: Type[S], size: int, with_header: bool = True
    ) -> None:
        """Private constructor. Use factory methods on writer"""
        super().__init__(writer, b"\0" * s._WIDTH * size, size, with_header)
        self._s = s

    def __setitem__(self, index: int, value: S) -> None:
        """Add value to list at index"""
        assert 0 <= index < self._size
        self._s._write(self._writer, self._offset + index * self._s._WIDTH, value)


class TableListOut(OutList, Generic[TO]):
    def __init__(
        self, writer: "Writer", t: Type[TO], size: int, with_header: bool = True
    ) -> None:
        """Private constructor. Use factory methods on writer"""
        super().__init__(writer, b"\0\0\0\0\0\0" * size, size, with_header)
        self.table = t

    def __setitem__(self, index: int, value: TO) -> None:
        """Add value to list at index"""
        assert 0 <= index < self._size
        if isinstance(value, self.table._IN):
            self.add(index)._copy(value)
            return
        assert isinstance(value, self.table)
        self._writer._put(self._offset + index * 6, pack48_(value._offset - 10))

    def add(self, index: int) -> TO:
        assert 0 <= index < self._size
        res = self._writer.construct_table(self.table)
        self[index] = res
        return res


class DirectTableListOut(OutList, Generic[TO]):
    def __init__(
        self, writer: "Writer", t: Type[TO], size: int, with_header: bool = True
    ) -> None:
        self._writer = writer

        writer._reserve(t._SIZE * size + 18)
        if with_header:
            sizelow, sizehigh = split48_(size)
            writer._write(struct.pack("<IIH", DIRECT_LIST_MAGIC, sizelow, sizehigh))

        self._offset = writer._used
        self._size = size
        writer._write(struct.pack("<II", t._MAGIC, t._SIZE))
        for _ in range(size):
            writer._write(t._DEFAULT)
        self._t = t

    def __getitem__(self, index: int) -> B:
        return self._t(self._writer, offset=self._offset + 8 + index * self._t._SIZE)

    def _copy(self, inp: ListIn) -> None:
        assert self._size == inp._size
        for i in range(self._size):
            self[i]._copy(inp[i])


class TextListOut(OutList):
    def __init__(self, writer: "Writer", size: int, with_header: bool = True) -> None:
        """Private constructor. Use factory methods on writer"""
        super().__init__(writer, b"\0\0\0\0\0\0" * size, size, with_header)

    def __setitem__(self, index: int, value: Union[TextOut, str]) -> None:
        """Add value to list at index"""
        assert 0 <= index < self._size
        if not isinstance(value, TextOut):
            value = self._writer.construct_text(value)
        self._writer._put(self._offset + index * 6, pack48_(value._offset - 10))


class BytesListOut(OutList):
    def __init__(self, writer: "Writer", size: int, with_header: bool = True) -> None:
        """Private constructor. Use factory methods on writer"""
        super().__init__(writer, b"\0\0\0\0\0\0" * size, size, with_header)

    def __setitem__(self, index: int, value: Union[BytesOut, bytes]) -> None:
        """Add value to list at index"""
        assert 0 <= index < self._size
        if not isinstance(value, BytesOut):
            value = self._writer.construct_bytes(value)
        self._writer._put(self._offset + index * 6, pack48_(value._offset - 10))


class UnionListOut(OutList, Generic[UO]):
    def __init__(
        self, writer: "Writer", u: Type[UO], size: int, with_header: bool = True
    ) -> None:
        """Private constructor. Use factory methods on writer"""
        super().__init__(writer, b"\0\0\0\0\0\0\0\0" * size, size, with_header)
        self._u = u

    def __getitem__(self, index: int) -> B:
        return self._u(self._writer, self._offset + index * 8)


class Writer:
    _data: bytearray = None
    _used: int = 0

    def _reserve(self, s: int):
        while self._used + s > len(self._data):
            self._data += b"\0" * len(self._data)

    def _write(self, v: bytes):
        self._data[self._used : self._used + len(v)] = v
        self._used += len(v)

    def _put(self, offset: int, value: bytes):
        self._data[offset : offset + len(value)] = value

    def __init__(self):
        self._data = bytearray(b"\0" * 256)
        self._used = 10

    def construct_table(self, t: Type[TO]) -> TO:
        """Construct a table of the given type"""
        return t(self, True)

    def construct_int8_list(self, size: int) -> BasicListOut[int]:
        return BasicListOut[int](self, "b", 1, size)

    def construct_uint8_list(self, size: int) -> BasicListOut[int]:
        return BasicListOut[int](self, "B", 1, size)

    def construct_int16_list(self, size: int) -> BasicListOut[int]:
        return BasicListOut[int](self, "h", 2, size)

    def construct_uint16_list(self, size: int) -> BasicListOut[int]:
        return BasicListOut[int](self, "H", 2, size)

    def construct_int32_list(self, size: int) -> BasicListOut[int]:
        return BasicListOut[int](self, "i", 4, size)

    def construct_uint32_list(self, size: int) -> BasicListOut[int]:
        return BasicListOut[int](self, "I", 4, size)

    def construct_int64_list(self, size: int) -> BasicListOut[int]:
        return BasicListOut[int](self, "q", 8, size)

    def construct_uint64_list(self, size: int) -> BasicListOut[int]:
        return BasicListOut[int](self, "Q", 8, size)

    def construct_float32_list(self, size: int) -> BasicListOut[float]:
        return BasicListOut[float](self, "f", 4, size)

    def construct_float64_list(self, size: int) -> BasicListOut[float]:
        return BasicListOut[float](self, "d", 8, size)

    def construct_enum_list(self, e: Type[E], size: int) -> EnumListOut[E]:
        return EnumListOut[E](self, e, size)

    def construct_struct_list(self, s: Type[S], size: int) -> StructListOut[S]:
        return StructListOut[S](self, s, size)

    def construct_table_list(self, s: Type[TO], size: int) -> TableListOut[TO]:
        return TableListOut[S](self, s, size)

    def construct_direct_table_list(
        self, s: Type[TO], size: int
    ) -> DirectTableListOut[TO]:
        return DirectTableListOut[S](self, s, size)

    def construct_text_list(self, size: int) -> TextListOut:
        return TextListOut(self, size)

    def construct_bytes_list(self, size: int) -> BytesListOut:
        return BytesListOut(self, size)

    def construct_bool_list(self, size: int) -> BoolListOut:
        return BoolListOut(self, size)

    def construct_union_list(self, u: Type[UO], size: int) -> UnionListOut[UO]:
        return UnionListOut[UO](self, u, size)

    def construct_bytes(self, b: bytes) -> BytesOut:
        self._reserve(len(b) + 10)
        sizelow, sizehigh = split48_(len(b))
        self._write(struct.pack("<IIH", BYTES_MAGIC, sizelow, sizehigh))
        o = self._used
        self._write(b)
        return BytesOut(o)

    def construct_text(self, t: str) -> TextOut:
        tt = t.encode("utf-8")
        self._reserve(len(tt) + 11)
        sizelow, sizehigh = split48_(len(tt))
        self._write(struct.pack("<IIH", TEXT_MAGIC, sizelow, sizehigh))
        o = self._used
        self._write(tt)
        self._write(b"\0")
        return TextOut(o)

    def copy(self, t: Type[TO], i: TI) -> TO:
        res = t(self, True)
        res._copy(i)
        return res

    def finalize(self, root: TableOut) -> bytes:
        """Return finalized message given root object"""
        offsetlow, offsethigh = split48_(root._offset - 10)
        self._data[0:10] = struct.pack("<IIH", MESSAGE_MAGIC, offsetlow, offsethigh)
        return self._data[0 : self._used]
