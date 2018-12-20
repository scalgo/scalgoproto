# -*- mode: python; tab-width: 4; indent-tabs-mode: nil; python-indent-offset: 4; coding: utf-8 -*-
import enum
import math
import struct
from abc import abstractmethod
from typing import Callable, ClassVar, Generic, Sequence, Tuple, Type, TypeVar, Union

MESSAGE_MAGIC = 0xB5C0C4B3
TEXT_MAGIC = 0xD812C8F5
BYTES_MAGIC = 0xDCDBBE10
LIST_MAGIC = 0x3400BB46

B = TypeVar("B")


class StructType(Generic[B]):
    _WIDTH: ClassVar[int] = 0

    @staticmethod
    @abstractmethod
    def _write(writer: "Writer", offset: int, value: B) -> B:
        ...


TI = TypeVar("TI", bound="TableIn")
TO = TypeVar("TO", bound="TableOut")
UO = TypeVar("UO", bound="UnionOut")
E = TypeVar("E", bound=enum.IntEnum)
S = TypeVar("S", bound=StructType)

TT = TypeVar("TT")


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
    ) -> None:
        """Private constructor. Use the accessor methods on tables to get an instance"""
        self._reader = reader
        self._offset = offset
        self._size = size
        self._getter = getter
        self._haser = haser

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
        return self._getter(self._reader, self._offset, idx)


class UnionIn(object):
    __slots__ = ["_reader", "_type", "_offset", "_size"]

    def __init__(self, reader: "Reader", type: int, offset: int, size: int = None):
        """Private constructor. Use the accessor methods on tables or the root method on Reader to get an instance"""
        self._reader = reader
        self._type = type
        self._offset = offset
        self._size = size

    def _get_ptr(self, magic: int) -> Tuple[int, int]:
        if self._size:
            return (self._offset, self._size)
        return (self._offset + 8, self._reader._read_size(self._offset, magic))


class TableIn(object):
    """Base class for reading a table"""

    __slots__ = ["_reader", "_offset", "_size"]
    _MAGIC: int = 0

    def __init__(self, reader: "Reader", offset: int, size: int) -> None:
        """Private constructor. Use the accessor methods on tables or the root method on Reader to get an instance"""
        self._reader = reader
        self._offset = offset
        self._size = size

    def _get_uint32_f(self, o: int) -> int:
        return struct.unpack(
            "<I", self._reader._data[self._offset + o : self._offset + o + 4]
        )[0]

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
        off = self._get_uint32_f(o)
        size = self._reader._read_size(off, magic)
        return (off + 8, size)

    def _get_ptr_inplace(self, o: int, magic: int) -> Tuple[int, int]:
        size = self._get_uint32_f(o)
        return (self._offset + self._size, size)


class Reader(object):
    """Responsible for reading a message"""

    def __init__(self, data: bytes) -> None:
        """data is the message to read from"""
        self._data = data

    def _read_size(self, offset: int, magic: int):
        m, size = struct.unpack("<II", self._data[offset : offset + 8])
        if m != magic:
            raise Exception("Bad magic")
        return size

    def _get_table_list(self, t: Type[TI], off: int, size: int) -> ListIn[TI]:
        def getter(r: "Reader", s: int, i: int) -> TI:
            ooo = struct.unpack("<I", r._data[s + 4 * i : s + 4 * i + 4])[0]
            sss = r._read_size(ooo, t._MAGIC)
            return t(r, ooo + 8, sss)

        return ListIn[TI](
            self,
            size,
            off,
            getter,
            lambda r, s, i: struct.unpack("<I", r._data[s + 4 * i : s + 4 * i + 4])[0]
            != 0,
        )

    def _get_bool_list(self, off: int, size: int) -> ListIn[bool]:
        return ListIn[bool](
            self,
            size,
            off,
            lambda r, s, i: (r._data[s + (i >> 3)] >> (i & 7)) & 1 != 0,
            lambda r, s, i: True,
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
        )

    def _get_struct_list(self, t: Type[S], off: int, size: int) -> ListIn[S]:
        return ListIn[S](
            self,
            size,
            off,
            lambda r, s, i: t._read(r, s + i * t._WIDTH),
            lambda r, s, i: True,
        )

    def _get_enum_list(self, t: Type[E], off: int, size: int) -> ListIn[E]:
        return ListIn[E](
            self,
            size,
            off,
            lambda r, s, i: t(r._data[s + i]),
            lambda r, s, i: r._data[s + i] != 255,
        )

    def _get_text_list(self, off: int, size: int) -> ListIn[str]:
        def getter(r: "Reader", s: int, i: int) -> str:
            ooo = struct.unpack("<I", r._data[s + 4 * i : s + 4 * i + 4])[0]
            sss = r._read_size(ooo, TEXT_MAGIC)
            return r._data[ooo + 8 : ooo + 8 + sss].decode("utf-8")

        return ListIn[str](
            self,
            size,
            off,
            getter,
            lambda r, s, i: struct.unpack("<I", r._data[s + 4 * i : s + 4 * i + 4])[0]
            != 0,
        )

    def _get_bytes_list(self, off: int, size: int) -> ListIn[bytes]:
        def getter(r: "Reader", s: int, i: int) -> bytes:
            ooo = struct.unpack("<I", r._data[s + 4 * i : s + 4 * i + 4])[0]
            sss = r._read_size(ooo, BYTES_MAGIC)
            return r._data[ooo + 8 : ooo + 8 + sss]

        return ListIn[bytes](
            self,
            size,
            off,
            getter,
            lambda r, s, i: struct.unpack("<I", r._data[s + 4 * i : s + 4 * i + 4])[0]
            != 0,
        )

    def root(self, type: Type[TI]) -> TI:
        """Return root node of message, of type type"""
        magic, offset = struct.unpack("<II", self._data[0:8])
        if magic != MESSAGE_MAGIC:
            raise Exception("Bad magic")
        size = self._read_size(offset, type._MAGIC)
        return type(self, offset + 8, size)


class TextOut(object):
    def __init__(self, offset: int) -> None:
        self._offset = offset


class BytesOut(object):
    def __init__(self, offset: int) -> None:
        self._offset = offset


class TableOut(object):
    __slots__ = ["_writer", "_offset"]
    _MAGIC: ClassVar[int] = 0

    def __init__(self, writer: "Writer", with_weader: bool, default: bytes) -> None:
        """Private constructor. Use factory methods on writer"""
        self._writer = writer
        self._writer._reserve(len(default) + 8)
        if with_weader:
            writer._write(struct.pack("<II", self._MAGIC, len(default)))
        self._offset = writer._used
        writer._write(default)

    def _set_int8(self, o: int, v: int) -> None:
        self._writer._data[self._offset + o : self._offset + o + 1] = struct.pack(
            "<b", v
        )

    def _set_uint8(self, o: int, v: int) -> None:
        self._writer._data[self._offset + o : self._offset + o + 1] = struct.pack(
            "<B", v
        )

    def _set_int16(self, o: int, v: int) -> None:
        self._writer._data[self._offset + o : self._offset + o + 2] = struct.pack(
            "<h", v
        )

    def _set_uint16(self, o: int, v: int) -> None:
        self._writer._data[self._offset + o : self._offset + o + 2] = struct.pack(
            "<H", v
        )

    def _set_int32(self, o: int, v: int) -> None:
        self._writer._data[self._offset + o : self._offset + o + 4] = struct.pack(
            "<i", v
        )

    def _set_uint32(self, o: int, v: int) -> None:
        self._writer._data[self._offset + o : self._offset + o + 4] = struct.pack(
            "<I", v
        )

    def _set_int64(self, o: int, v: int) -> None:
        self._writer._data[self._offset + o : self._offset + o + 8] = struct.pack(
            "<q", v
        )

    def _set_uint64(self, o: int, v: int) -> None:
        self._writer._data[self._offset + o : self._offset + o + 8] = struct.pack(
            "<Q", v
        )

    def _set_float32(self, o: int, v: float) -> None:
        self._writer._data[self._offset + o : self._offset + o + 4] = struct.pack(
            "<f", v
        )

    def _set_float64(self, o: int, v: float) -> None:
        self._writer._data[self._offset + o : self._offset + o + 8] = struct.pack(
            "<d", v
        )

    def _set_bit(self, o: int, b: int) -> None:
        self._writer._data[self._offset + o] ^= 1 << b

    def _unset_bit(self, o: int, b: int) -> None:
        self._writer._data[self._offset + o] &= ~(1 << b)

    def _set_table(self, o: int, v: TO) -> None:
        self._writer._data[self._offset + o : self._offset + o + 4] = struct.pack(
            "<I", v._offset - 8
        )

    def _set_text(self, o: int, v: Union[TextOut, str]) -> None:
        if not isinstance(v, TextOut):
            v = self._writer.construct_text(v)
        self._writer._data[self._offset + o : self._offset + o + 4] = struct.pack(
            "<I", v._offset - 8
        )

    def _set_bytes(self, o: int, v: Union[BytesOut, bytes]) -> None:
        if not isinstance(v, BytesOut):
            v = self._writer.construct_bytes(v)
        self._writer._data[self._offset + o : self._offset + o + 4] = struct.pack(
            "<I", v._offset - 8
        )

    def _set_list(self, o: int, v: "OutList") -> None:
        self._writer._data[self._offset + o : self._offset + o + 4] = struct.pack(
            "<I", v._offset - 8
        )

    def _get_uint16(self, o: int) -> int:
        return struct.unpack(
            "<H", self._writer._data[self._offset + o : self._offset + o + 2]
        )[0]

    def _add_inplace_text(self, o: int, t: str) -> None:
        tt = t.encode("utf-8")
        self._writer._data[self._offset + o : self._offset + o + 4] = struct.pack(
            "<I", len(tt)
        )
        self._writer._reserve(len(tt) + 1)
        self._writer._write(tt)
        self._writer._write(b"\0")

    def _add_inplace_bytes(self, o: int, t: bytes) -> None:
        self._writer._data[self._offset + o : self._offset + o + 4] = struct.pack(
            "<I", len(t)
        )
        self._writer._reserve(len(t))
        self._writer._write(t)

    def _set_inplace_list(self, o: int, size: int) -> None:
        self._writer._data[self._offset + o : self._offset + o + 4] = struct.pack(
            "<I", size
        )


class UnionOut(object):
    __slots__ = ["_writer", "_offset", "_end"]

    def __init__(self, writer: "Writer", offset: int, end: int) -> None:
        self._writer = writer
        self._offset = offset
        self._end = end

    def _set(self, idx: int, offset: int) -> None:
        self._writer._data[self._offset : self._offset + 6] = struct.pack(
            "<HI", idx, offset
        )

    def _set_text(self, idx: int, v: Union[TextOut, str]) -> None:
        if not isinstance(v, TextOut):
            v = self._writer.construct_text(v)
        self._set(idx, v._offset - 8)

    def _set_bytes(self, idx: int, v: Union[BytesOut, bytes]) -> None:
        if not isinstance(v, BytesOut):
            v = self._writer.construct_bytes(v)
        self._set(idx, v._offset - 8)


class OutList:
    _offset: int = 0
    _size: int = 0

    def __init__(
        self, writer: "Writer", d: bytes, size: int, with_weader: bool
    ) -> None:
        """Private constructor. Use factory methods on writer"""
        self._writer = writer
        writer._reserve(len(d) + 8)
        if with_weader:
            writer._write(struct.pack("<II", LIST_MAGIC, size))
        self._offset = writer._used
        self._size = size
        writer._write(d)

    def __len__(self):
        return self._size


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
        self._writer._data[
            self._offset + index * self._w : self._offset + (1 + index) * self._w
        ] = struct.pack(self._e, value)


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
        self._writer._data[
            self._offset + index : self._offset + index + 1
        ] = struct.pack("B", int(value))


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
        super().__init__(writer, b"\0\0\0\0" * size, size, with_header)
        self.table = t

    def __setitem__(self, index: int, value: TO) -> None:
        """Add value to list at index"""
        assert 0 <= index < self._size
        assert isinstance(value, self.table)
        self._writer._data[
            self._offset + index * 4 : self._offset + index * 4 + 1
        ] = struct.pack("I", value._offset - 8)

    def add(self, index: int) -> TO:
        assert 0 <= index < self._size
        res = self._writer.construct_table(self.table)
        self[index] = res
        return res


class TextListOut(OutList):
    def __init__(self, writer: "Writer", size: int, with_header: bool = True) -> None:
        """Private constructor. Use factory methods on writer"""
        super().__init__(writer, b"\0\0\0\0" * size, size, with_header)

    def __setitem__(self, index: int, value: Union[TextOut, str]) -> None:
        """Add value to list at index"""
        assert 0 <= index < self._size
        if not isinstance(value, TextOut):
            value = self._writer.construct_text(value)
        self._writer._data[
            self._offset + index * 4 : self._offset + index * 4 + 1
        ] = struct.pack("I", value._offset - 8)


class BytesListOut(OutList, Generic[TO]):
    def __init__(
        self, writer: "Writer", t: Type[TO], size: int, with_header: bool = True
    ) -> None:
        """Private constructor. Use factory methods on writer"""
        super().__init__(writer, b"\0\0\0\0" * size, size, with_header)
        self.table = t

    def __setitem__(self, index: int, value: TO) -> None:
        """Add value to list at index"""
        assert 0 <= index < self._size
        assert isinstance(value, BytesOut)
        self._writer._data[
            self._offset + index * 4 : self._offset + index * 4 + 1
        ] = struct.pack("I", value._offset - 8)


class UnionListOut(OutList, Generic[UO]):
    def __init__(
        self, writer: "Writer", u: Type[UO], size: int, with_header: bool = True
    ) -> None:
        """Private constructor. Use factory methods on writer"""
        super().__init__(writer, b"\0\0\0\0\0\0" * size, size, with_header)
        self._u = u

    def __getitem__(self, index: int) -> B:
        return self._u(self._writer, self._offset + index * 6)


class Writer:
    _data: bytearray = None
    _used: int = 0

    def _reserve(self, s: int):
        while self._used + s > len(self._data):
            self._data += b"\0" * len(self._data)

    def _write(self, v: bytes):
        self._data[self._used : self._used + len(v)] = v
        self._used += len(v)

    def __init__(self):
        self._data = bytearray(b"\0" * 256)
        self._used = 8

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

    def construct_text_list(self, size: int) -> TextListOut:
        return TextListOut(self, size)

    def construct_bytes_list(self, size: int) -> BytesListOut:
        return BytesListOut(self, size)

    def construct_bool_list(self, size: int) -> BoolListOut:
        return BoolListOut(self, size)

    def construct_union_list(self, u: Type[UO], size: int) -> UnionListOut[UO]:
        return UnionListOut[UO](self, u, size)

    def construct_bytes(self, b: bytes) -> BytesOut:
        self._reserve(len(b) + 8)
        self._write(struct.pack("<II", BYTES_MAGIC, len(b)))
        o = self._used
        self._write(b)
        return BytesOut(o)

    def construct_text(self, t: str) -> TextOut:
        tt = t.encode("utf-8")
        self._reserve(len(tt) + 9)
        self._write(struct.pack("<II", TEXT_MAGIC, len(tt)))
        o = self._used
        self._write(tt)
        self._write(b"\0")
        return TextOut(o)

    def finalize(self, root: TableOut) -> bytes:
        """Return finalized message given root object"""
        self._data[0:8] = struct.pack("<II", MESSAGE_MAGIC, root._offset - 8)
        return self._data[0 : self._used]
