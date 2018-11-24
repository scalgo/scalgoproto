# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Perform validation of the ast, and assign offsets and such
"""
from parser import TokenType, Token, Struct, AstNode, Value, Enum, Table, Union, Namespace
from typing import Set, Dict, List
import sys, struct, enum
from keywords import keywords
from error import error
from util import ucamel

class ContentType(enum.Enum):
	TABLE = 0
	STRUCT = 1
	UNION = 2

class Annotater:
	enums: Dict[str, Enum]
	structs: Dict[str, Struct]
	tabels: Dict[str, Table]
	unions: Dict[str, Union]

	def __init__(self, data:str) -> None:
		self.data = data
		self.errors = 0

	def value(self, t:Token) -> str:
		return self.data[t.index: t.index + t.length]	
		
	def error(self, token: Token, message: str) -> None:
		self.errors += 1
		error(self.data, self.context, token, message)

	def validate_uname(self, t:Token) -> str:
		name = self.value(t)
		if not name[0].isupper() or name.count("_") or not name.isidentifier():
			self.error(t, "Name must be CamelCase")
		if name in keywords:
			self.error(t, "Illegal name")
		if name in self.enums or name in self.structs or name in self.tabels or name in self.unions:
			self.error(t, "Duplicate name")
		if name in self.enums:
			self.error(self.enums[name].identifier, "Previously defined here")
		if name in self.structs:
			self.error(self.structs[name].identifier, "Previously defined here")
		if name in self.tabels:
			self.error(self.tabels[name].identifier, "Previously defined here")
		if name in self.unions:
			self.error(self.unions[name].identifier, "Previously defined here")
		return name

	def validate_member_name(self, t:Token, name:str, seen: Dict[str, Token], has:bool=False, is_:bool=False, add:bool=False, get:bool=False) -> None:
		if name[0].isupper() or name.count("_") or not name.isidentifier():
			self.error(t, "Name must be CamelCase")
		if name in keywords:
			self.error(t, "Illegal name '%s'"%name)
		hasName = "has%s%s"%(name[0].upper(), name[1:]) if has else None
		isName = "is%s%s"%(name[0].upper(), name[1:]) if is_ else None
		getName = "get%s%s"%(name[0].upper(), name[1:]) if has else None
		addName = "add%s%s"%(name[0].upper(), name[1:]) if is_ else None

		for n in [name, hasName, isName, getName, addName]:
			if n and n in seen:
				self.error(t, "Name conflict")
				self.error(seen[name], "Conflicts with this")
			seen[n] = t

	def get_int(self, value:Token, min:int, max:int, d:int) -> int:
		if not value:
			return d
		try:
			v = int(self.value(value))
			if min <= v <= max:
				return v
			self.error(value, "Value %d outside allowed range %d to %d"%(v, min, max))
		except ValueError:
			self.error(value, "Must be an integer")
		return d

	def get_float(self, value:Token, d:float) -> float:
		if not value:
			return d
		try:
			return float(self.value(value))
		except ValueError:
			self.error(value, "Must be a float")
		return d

	def create_doc_string(self, node: AstNode) -> None:
		if not node.docccomment: return
		v = self.value(node.docccomment)
		node.docstring = []
		for line in v.split("\n"):
			line = line.strip()
			if line[0:3] in ("/**", '///'): line = line[3:]
			elif line[0:2] in ('##', '*/', '//'): line = line[2:]
			elif line[0:1] in ("#", "*"): line = line[1:]
			if line[0:1] == ' ': line = line[1:]
			if node.docstring or line: node.docstring.append(line)
		while node.docstring and not node.docstring[-1]:
			node.docstring.pop()
		if node.docstring and node.docstring[-1].endswith("*/"):
			node.docstring[-1] = node.docstring[-1][0:-2].strip()
		while node.docstring and not node.docstring[-1]:
			node.docstring.pop()

	
	def visit_content(self, name:str, values: List[Value], t:ContentType) -> bytes:
		content: Dict[str, Token] = {}
		bytes = 0
		default = []
		bool_bit = 8
		bool_offset = 0
		inplace: Value = None
		for v in values:
			self.create_doc_string(v)

			if v.value:
				if t == ContentType.STRUCT:
					self.error(v.value, "Not allowed in structs")
				elif t == ContentType.UNION:
					self.error(v.value, "Not allowed in unions")
				elif v.optional:
					self.error(v.value, "Not allowed for optionals")
				elif v.list_:
					self.error(v.value, "Not allowed for lists")
				elif v.value.type in (TokenType.TRUE, TokenType.FALSE):
					self.error(v.value, "Booleans cannot have default values")
				elif v.value.type == TokenType.NUMBER:
					if v.type_.type not in (TokenType.UINT8, TokenType.UINT16, TokenType.UINT32, TokenType.UINT64, TokenType.INT8, TokenType.INT16, TokenType.INT32, TokenType.INT64,  TokenType.FLOAT32,  TokenType.FLOAT64):
						self.error(v.value, "Only allowed for number types")
				elif v.value.type == TokenType.IDENTIFIER:
					if v.type_.type != TokenType.IDENTIFIER or self.value(v.type_) not in self.enums:
						self.error(v.value, "Only allowed for enumes")
					elif self.value(v.value) not in self.enums[self.value(v.type_)].annotatedValues:
						self.error(v.value, "Not member of enum")
						self.error(self.enums[self.value(v.type_)].token, "Enum declared here")
				else:
					self.error(v.value, "Unhandled value")

			val = self.value(v.identifier)
			self.validate_member_name(v.identifier, val, content, get=False, has=v.optional != None, add=v.list_ != None)

			type_name = self.value(v.type_)

			if t == ContentType.STRUCT and v.optional:
				self.error(v.optional, "Not allowed in structs")
			if t == ContentType.UNION and v.optional:
				self.error(v.optional, "Not allowed in unions")

			if t == ContentType.STRUCT and v.inplace:
				self.error(v.inplace, "Not allowed in structs")
			if t == ContentType.UNION and v.inplace:
				self.error(v.inplace, "Not allowed in unions")

			if v.inplace and inplace:
				self.error(v.inplace, "More than one inplace element defined")
				self.error(inplace.inplace, "Previously defined here")

			if v.inplace:
				inplace = v

			if v.optional and v.type_.type in (
							TokenType.UINT8, TokenType.UINT16, TokenType.UINT32, TokenType.UINT64,
							TokenType.INT8, TokenType.INT16, TokenType.INT32, TokenType.INT64,
							TokenType.BOOL):
				if bool_bit == 8:
					bool_bit = 0
					bool_offset = bytes
					default.append(b"\0")
					bytes += 1
				v.has_offset = bool_offset
				v.has_bit = bool_bit
				bool_bit += 1

			typeName = self.value(v.type_)
			if v.list_:
				if v.type_.type == TokenType.IDENTIFIER:
					typeName = self.value(v.type_)
					if typeName in self.enums:
						v.enum = self.enums[typeName]
					elif typeName in self.tabels:
						v.table = self.tabels[typeName]
					elif typeName in self.structs:
						v.struct = self.structs[typeName]
					elif typeName in self.unions:
						v.union = self.unions[typeName]
					else:
						self.error(v.type_, "Unknown type")
				if t == ContentType.STRUCT:
					self.error(v.list_, "Not allowed in structs")
				if v.optional:
					self.error(v.optional, "Lists are alwayes optional")
				#TODO recurse in direct unions or tabels
				default.append(b"\0\0\0\0")
				v.bytes = 4
				v.offset = bytes
			elif t == ContentType.UNION and v.type_.type in (
				TokenType.BOOL, TokenType.UINT8, TokenType.INT8, TokenType.UINT8, TokenType.INT8,
				TokenType.UINT32, TokenType.INT32, TokenType.FLOAT32,
				TokenType.UINT64, TokenType.INT64, TokenType.FLOAT64):
				self.error(v.type_, "Not allowed in unions")
				v.bytes = 0
				v.offset = bytes
			elif t == ContentType.TABLE and v.type_.type == TokenType.BOOL:
				if bool_bit == 8:
					bool_bit = 0
					bool_offset = bytes
					default.append(b"\0")
					bytes += 1
				v.offset = bool_offset
				v.bit = bool_bit
				bool_bit += 1
			elif v.type_.type in (TokenType.UINT8, TokenType.INT8, TokenType.BOOL):
				if v.inplace:
					self.error(v.inplace, "Basic types may not be implace")
				if v.type_.type == TokenType.UINT8:
					v.parsed_value = self.get_int(v.value, 0, 255, 0)
					default.append(struct.pack("<B", v.parsed_value))
				elif v.type_.type == TokenType.INT8:
					v.parsed_value = self.get_int(v.value, -128, 127, 0)
					default.append(struct.pack("<b", v.parsed_value))
				elif v.type_.type == TokenType.BOOL:
					default.append(b"\0")
				else:
					self.error(v.type_.type, "Internal error")
				v.bytes = 1
				v.offset = bytes
			elif v.type_.type in (TokenType.UINT16, TokenType.INT16):
				if v.inplace:
					self.error(v.inplace, "Basic types may not be implace")
				if v.type_.type == TokenType.UINT16:
					v.parsed_value = self.get_int(v.value, 0, 2**16-1, 0)
					default.append(struct.pack("<H", v.parsed_value))
				elif v.type_.type == TokenType.INT16:
					v.parsed_value = self.get_int(v.value, -2**15, 2**15-1, 0)
					default.append(struct.pack("<h", v.parsed_value))
				else:
					self.error(v.type_.type, "Internal error")
				v.bytes = 2
				v.offset = bytes
			elif v.type_.type in (TokenType.UINT32, TokenType.INT32, TokenType.FLOAT32):
				if v.inplace:
					self.error(v.inplace, "Basic types may not be implace")
				if v.type_.type == TokenType.UINT32:
					v.parsed_value = self.get_int(v.value, 0, 2**32-1, 0)
					default.append(struct.pack("<I", v.parsed_value))
				elif v.type_.type == TokenType.INT32:
					v.parsed_value = self.get_int(v.value, -2**31, 2**31-1, 0)
					default.append(struct.pack("<i", v.parsed_value))
				elif v.type_.type == TokenType.FLOAT32:
					v.parsed_value = self.get_float(v.value, float('nan') if v.optional else 0.0)
					default.append(struct.pack("<f", v.parsed_value))
				else:
					self.error(v.type_.type, "Internal error")
				v.bytes = 4
				v.offset = bytes
			elif v.type_.type in (TokenType.UINT64, TokenType.INT64, TokenType.FLOAT64):
				if v.inplace:
					self.error(v.inplace, "Basic types may not be implace")
				if v.type_.type == TokenType.UINT64:
					v.parsed_value = self.get_int(v.value, 0, 2**64-1, 0)
					default.append(struct.pack("<Q", v.parsed_value))
				elif v.type_.type == TokenType.INT64:
					v.parsed_value = self.get_int(v.value, -2**64, 2**64-1, 0)
					default.append(struct.pack("<q", v.parsed_value))
				elif v.type_.type == TokenType.FLOAT64:
					v.parsed_value = self.get_float(v.value, float('nan') if v.optional else 0.0)
					default.append(struct.pack("<d", v.parsed_value))
				else:
					self.error(v.type_.type, "Internal error")
				v.bytes = 8
				v.offset = bytes
			elif v.type_.type in (TokenType.BYTES, TokenType.TEXT):
				if v.optional:
					self.error(v.optional, "Are alwayes optional")
				if  t == ContentType.STRUCT:
					self.error(v.type_, "Not allowed in structs")
				default.append(b"\0\0\0\0")
				v.bytes = 4
				v.offset = bytes
			elif v.direct_table:
				if  t == ContentType.STRUCT:
					self.error(v.type_, "Not allowed in structs")
				if v.optional:
					self.error(v.optional, "Tabels are alwayes optional")
				v.bytes = 4
				v.offset = bytes
				default.append(b"\0\0\0\0")
				#TODO docstring
				v.direct_table.name = name + ucamel(val)
				v.direct_table.default = self.visit_content(v.direct_table.name, v.direct_table.members, ContentType.TABLE)
				v.table = v.direct_table
			elif v.direct_union:
				if  t == ContentType.STRUCT:
					self.error(v.type_, "Not allowed in structs")
				if v.optional:
					self.error(v.optional, "Unions are alwayes optional")
				v.bytes = 6
				v.offset = bytes
				default.append(b"\0\0\0\0\0\0")
				#TODO docstring
				v.direct_union.name = name + ucamel(val)
				self.visit_content(v.direct_union.name, v.direct_union.members, ContentType.UNION)
				v.union = v.direct_union
			elif v.type_.type != TokenType.IDENTIFIER:
				self.error(v.type_, "Unknown type")
				continue
			elif typeName in self.enums:
				if v.inplace:
					self.error(v.inplace, "Enums types may not be implace")
				if v.optional:
					self.error(v.optional, "Are alwayes optional")
				v.enum = self.enums[typeName]
				d = 255
				if v.value:
					dn = self.value(v.value)
					if not dn in v.enum.annotatedValues:
						self.error(v.value, "Not member of enum")
					d = v.enum.annotatedValues[dn]
				v.parsed_value = d
				default.append(struct.pack("<B", d))
				v.bytes = 1
				v.offset = bytes
			elif typeName in self.structs:
				if v.inplace:
					self.error(v.inplace, "Structs types may not be implace")
				if v.optional:
					if bool_bit == 8:
						bool_bit = 0
						bool_offset = bytes
						default.append(b"\0")
						bytes += 1
					v.has_offset = bool_offset
					v.has_bit = bool_bit
					bool_bit += 1
				v.bytes = self.structs[typeName].bytes
				default.append(b"\0" * v.bytes)
				v.offset = bytes
				v.struct = self.structs[typeName]
			elif typeName in self.tabels:
				if t == ContentType.STRUCT:
					self.error(v.type_, "Tabels not allowed in structs")
				if v.optional:
					self.error(v.optional, "Lists are alwayes optional")
				default.append(b"\0\0\0\0")
				v.bytes = 4
				v.offset = bytes
				v.table = self.tabels[typeName]
			elif typeName in self.unions:
				if t == ContentType.STRUCT:
					self.error(v.type_, "Unions not allowed in structs")
				if v.optional:
					self.error(v.optional, "Unions are alwayes optional")
				default.append(b"\0\0\0\0\0\0")
				v.bytes = 6
				v.offset = bytes
				v.unions = self.unions[typeName]
			else:
				self.error(v.type_, "Unknown identifier")
				continue
			bytes += v.bytes

		default2 = b"".join(default)
		assert(len(default2) == bytes)
		return default2
	
	def annotate(self, ast: List[AstNode]) -> None:
		self.enums = {}
		self.structs = {}
		self.tabels = {}
		self.unions = {}
		for node in ast:
			self.context = "outer"
			self.create_doc_string(node)
			if isinstance(node, Struct):
				self.context = "struct %s"%self.value(node.identifier)
				name = self.validate_uname(node.identifier)
				structValues: Set[str] = set()
				bytes = len(self.visit_content(name, node.members, ContentType.STRUCT))
				self.structs[name] = node
				node.bytes = bytes
				print("struct %s of size %d"%(name, bytes), file=sys.stderr)
			elif isinstance(node, Enum):
				self.context = "enum %s"%self.value(node.identifier)
				name = self.validate_uname(node.identifier)
				enumValues: Dict[str, int] = {}
				index = 0
				for ev in node.members:
					vv = self.value(ev.identifier)
					if vv in enumValues:
						self.error(ev.identifier, "Duplicate name")
						continue
					enumValues[vv] = index
					index += 1
				if len(enumValues) > 254:
					self.error(node.identifier, "Too many enum values")
				node.annotatedValues = enumValues
				self.enums[name] = node
				print("enum %s with %s members"%(name, len(enumValues)), file=sys.stderr)
			elif isinstance(node, Table):
				self.context = "tabel %s"%self.value(node.identifier)
				name = self.validate_uname(node.identifier)
				node.name = name
				node.magic = int(self.value(node.id_)[1:], 16)
				node.default = self.visit_content(name, node.members, ContentType.TABLE)
				self.tabels[name] = node
				print("table %s of size >= %d"%(name, len(node.default)+8), file=sys.stderr)
			elif isinstance(node, Union):
				self.context = "union %s"%self.value(node.identifier)
				name = self.validate_uname(node.identifier)
				node.name = name
				self.visit_content(name, node.members, ContentType.UNION)
				self.unions[name] = node
				print("union %s"%name, file=sys.stderr)
			elif isinstance(node, Namespace):
				#TODO handel namespace
				pass
			else:
				self.error(node.token, "Unknown thing")
				continue

def annotate(data: str, ast: List[AstNode]) -> bool:
	a = Annotater(data)
	a.annotate(ast)
	return a.errors == 0
