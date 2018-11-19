# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
from typing import TypeVar, Type, Generic, Sequence, Callable, Tuple, ClassVar
import struct, enum, math
from abc import abstractmethod
_MESSAGE_MAGIC = 0xB5C0C4B3
_TEXT_MAGIC = 0xD812C8F5
_BYTES_MAGIC = 0xDCDBBE10
_LIST_MAGIC = 0x3400BB46

B = TypeVar('B')
class StructType(Generic[B]):
	_WIDTH: ClassVar[int] = 0

	@staticmethod
	@abstractmethod
	def _write(writer: 'Writer', offset: int, value: B) -> B:
		...

TO = TypeVar('TO', bound='TableOut')
E = TypeVar('E', bound=enum.IntEnum)
S = TypeVar('S', bound=StructType)

class TextOut:
	def __init__(self, offset:int) -> None:
		self._offset = offset

class BytesOut:
	def __init__(self, offset:int) -> None:
		self._offset = offset

class TableOut:
	_MAGIC: ClassVar[int] = 0

	def __init__(self, writer: 'Writer', withHeader: bool, default: bytes) -> None:
		"""Private constructor. Use factory methods on writer"""
		self._writer = writer
		self._writer._reserve(len(default) + 8)
		if withHeader: writer._write(struct.pack("<II", self._MAGIC, len(default)))
		self._offset = writer._used
		writer._write(default)

	def _setInt8(self, o:int, v:int) -> None: self._writer._data[self._offset+o:self._offset+o+1] = struct.pack("<b", v)
	def _setUInt8(self, o:int, v:int) -> None: self._writer._data[self._offset+o:self._offset+o+1] = struct.pack("<B", v)
	def _setInt16(self, o:int, v:int) -> None: self._writer._data[self._offset+o:self._offset+o+2] = struct.pack("<h", v)
	def _setUInt16(self, o:int, v:int) -> None: self._writer._data[self._offset+o:self._offset+o+2] = struct.pack("<H", v)
	def _setInt32(self, o:int, v:int) -> None: self._writer._data[self._offset+o:self._offset+o+4] = struct.pack("<i", v)
	def _setUInt32(self, o:int, v:int) -> None: self._writer._data[self._offset+o:self._offset+o+4] = struct.pack("<I", v)
	def _setInt64(self, o:int, v:int) -> None: self._writer._data[self._offset+o:self._offset+o+8] = struct.pack("<q", v)
	def _setUInt64(self, o:int, v:int) -> None: self._writer._data[self._offset+o:self._offset+o+8] = struct.pack("<Q", v)
	def _setFloat32(self, o:int, v:float) -> None: self._writer._data[self._offset+o:self._offset+o+4] = struct.pack("<f", v)
	def _setFloat64(self, o:int, v:float) -> None: self._writer._data[self._offset+o:self._offset+o+8] = struct.pack("<d", v)
	def _setBit(self, o:int, b:int) -> None: self._writer._data[self._offset+o] ^= (1 << b)
	def _unsetBit(self, o:int, b:int) -> None: self._writer._data[self._offset+o] &= ~(1 << b)
	def _setTable(self, o:int, v:TO) -> None: self._writer._data[self._offset+o:self._offset+o+4] = struct.pack("<I", v._offset-8)
	def _setText(self, o:int, v:TextOut) -> None: self._writer._data[self._offset+o:self._offset+o+4] = struct.pack("<I", v._offset-8)
	def _setBytes(self, o:int, v:BytesOut) -> None: self._writer._data[self._offset+o:self._offset+o+4] = struct.pack("<I", v._offset-8)
	def _setList(self, o:int, v:"OutList") -> None: self._writer._data[self._offset+o:self._offset+o+4] = struct.pack("<I", v._offset-8)
	def _getUInt16(self, o:int) -> int: return struct.unpack("<H", self._writer._data[self._offset+o:self._offset+o+2])[0]
	def _constructUnionMember(self, t:Type[TO])->TO:
		return t(self._writer, False)
	def _addVLText(self, o:int, t:str) -> None:
		tt = t.encode('utf-8')
		self._writer._data[self._offset+o:self._offset+o+4] = struct.pack("<I", len(tt))
		self._writer._reserve(len(tt)+1)
		self._writer._write(tt)
		self._writer._write(b"\0")
	def _addVLBytes(self, o:int, t:bytes) -> None:
		self._writer._data[self._offset+o:self._offset+o+4] = struct.pack("<I", len(t))
		self._writer._reserve(len(t))
		self._writer._write(t)
	def _setVLList(self, o:int, size:int) -> None:
		self._writer._data[self._offset+o:self._offset+o+4] = struct.pack("<I", size)
class OutList:
	_offset: int = 0
	def __init__(self, writer: 'Writer', d:bytes, size:int, withHeader:bool) -> None:
		"""Private constructor. Use factory methods on writer"""
		self._writer = writer
		self._w = len(d)
		writer._reserve(size*self._w + 8)
		if withHeader: writer._write(struct.pack("<II", _LIST_MAGIC, size))
		self._offset = writer._used
		writer._write(d*size)

class BasicListOut(OutList, Generic[B]):
	def __init__(self, writer: 'Writer', e:str, w:int, size:int, withHeader:bool = True) -> None:
		"""Private constructor. Use factory methods on writer"""
		super().__init__(writer, b'\0'*w, size, withHeader)
		self._e = "<"+e

	def add(self, index: int, value: B) -> None:
		"""Add value to list at index"""
		self._writer._data[self._offset + index*self._w: self._offset + (1+index)*self._w] = struct.pack(self._e, value)

class EnumListOut(OutList, Generic[E]):
	def __init__(self, writer: 'Writer', e:Type[E], size:int, withHeader:bool = True) -> None:
		"""Private constructor. Use factory methods on writer"""
		super().__init__(writer, b'\xff', size, withHeader)

	def add(self, index: int, value: E) -> None:
		"""Add value to list at index"""
		self._writer._data[self._offset + index: self._offset + index + 1] = struct.pack("B", int(value))

class StructListOut(OutList, Generic[S]):
	def __init__(self, writer: 'Writer', s:Type[S], size:int, withHeader:bool = True) -> None:
		"""Private constructor. Use factory methods on writer"""
		super().__init__(writer, b'\0'*s._WIDTH, size, withHeader)
		self._s = s

	def add(self, index: int, value: S) -> None:
		"""Add value to list at index"""
		self._s._write(self._writer, self._offset + index*self._s._WIDTH, value)

class ObjectListOut(OutList, Generic[B]):
	def __init__(self, writer: 'Writer', size:int, withHeader:bool = True) -> None:
		"""Private constructor. Use factory methods on writer"""
		super().__init__(writer, b'\0\0\0\0', size, withHeader)

	def add(self, index:int, value: B) -> None:
		"""Add value to list at index"""
		self._writer._data[self._offset + index*4: self._offset + index*4 + 1] = struct.pack("I", value._offset-8)

class Writer:
	_data: bytearray = None
	_used: int = 0

	def _reserve(self, s:int):
		while self._used + s > len(self._data):
			self._data += b"\0" * len(self._data)

	def _write(self, v: bytes):
		self._data[self._used: self._used+len(v)] = v
		self._used += len(v)

	def __init__(self):
		self._data = bytearray(b"\0"*256)
		self._used = 8

	def constructTable(self, t: Type[TO]) -> TO:
		"""Construct a table of the given type"""
		return t(self, True)

	def constructInt8List(self, size:int) -> BasicListOut[int]: return BasicListOut[int](self, "b", 1, size)
	def constructUInt8List(self, size:int) -> BasicListOut[int]: return BasicListOut[int](self, "B", 1, size)
	def constructInt16List(self, size:int) -> BasicListOut[int]: return BasicListOut[int](self, "h", 2, size)
	def constructUInt16List(self, size:int) -> BasicListOut[int]: return BasicListOut[int](self, "H", 2, size)
	def constructInt32List(self, size:int) -> BasicListOut[int]: return BasicListOut[int](self, "i", 4, size)
	def constructUInt32List(self, size:int) -> BasicListOut[int]: return BasicListOut[int](self, "I", 4, size)
	def constructInt64List(self, size:int) -> BasicListOut[int]: return BasicListOut[int](self, "q", 8, size)
	def constructUInt64List(self, size:int) -> BasicListOut[int]: return BasicListOut[int](self, "Q", 8, size)
	def constructFloat32List(self, size:int) -> BasicListOut[float]: return BasicListOut[float](self, "f", 4, size)
	def constructFloat64List(self, size:int) -> BasicListOut[float]: return BasicListOut[float](self, "d", 8, size)
	def constructEnumList(self, e:Type[E], size:int) -> EnumListOut[E]: return EnumListOut[E](self, e, size)
	def constructStructList(self, s:Type[S], size:int) -> StructListOut[S]: return StructListOut[S](self, s, size)
	def constructTableList(self, s:Type[TO], size:int) -> ObjectListOut[TO]: return ObjectListOut[S](self, size)
	def constructTextList(self, size:int) -> ObjectListOut[TextOut]: return ObjectListOut[TextOut](self, size)
	def constructBytesList(self, size:int) -> ObjectListOut[BytesOut]: return ObjectListOut[BytesOut](self, size)

	def constructBytes(self, b:bytes) -> BytesOut:
		self._reserve(len(b) + 8)
		self._write(struct.pack("<II", _BYTES_MAGIC, len(b)))
		o = self._used
		self._write(b)
		return BytesOut(o)

	def constructText(self, t:str) -> TextOut:
		tt = t.encode('utf-8')
		self._reserve(len(tt) + 9)
		self._write(struct.pack("<II", _TEXT_MAGIC, len(tt)))
		o = self._used
		self._write(tt)
		self._write(b"\0")
		return TextOut(o)

	def finalize(self, root: TableOut) -> bytes:
		"""Return finalized message given root object"""
		self._data[0:8] = struct.pack("<II", _MESSAGE_MAGIC, root._offset - 8)
		return self._data[0: self._used]
