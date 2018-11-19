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

	def finalize(self, root: TableOut) -> bytes:
		"""Return finalized message given root object"""
		self._data[0:8] = struct.pack("<II", _MESSAGE_MAGIC, root._offset - 8)
		return self._data[0: self._used]
