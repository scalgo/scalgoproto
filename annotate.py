# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Perform validation of the ast, and assign offsets and such
"""
from parser import TokenType, NodeType, Token, Struct, AstNode, Value, Enum, Table, VLUnion, VLList
from typing import Set, Dict, List
import sys, struct

class Annotater:
	enums: Dict[str, Enum]
	structs: Dict[str, Struct]
	tabels: Dict[str, Table]

	def __init__(self, data:str) -> None:
		self.data = data
		self.errors = 0

	def value(self, t:Token) -> str:
		return self.data[t.index: t.index + t.length]	
		
	def error(self, token: Token, message: str) -> None:
		self.errors += 1
		cnt = 1
		idx = 0
		start = 0
		t = 0
		while idx < token.index:
			if self.data[idx] == '\n':
				cnt += 1
				start = idx + 1
				t = 0
			if self.data[idx] == '\t':
				t += 1
			idx += 1
		print("Error in %s on line %d: %s"%(self.context, cnt, message))
		end = start
		while end < len(self.data) and self.data[end] != '\n':
			end += 1
		print(self.data[start:end])
		print("%s%s%s"%('\t'*t, ' '*(token.index - start -t), '^'*(token.length)))
	

	def getInt(self, value:Token, min:int, max:int, d:int) -> int:
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

	def getFloat(self, value:Token, d:float) -> float:
		if not value:
			return d
		try:
			return float(self.value(value))
		except ValueError:
			self.error(value, "Must be a float")
		return d

	def visitContent(self, tableName: str, values: List[AstNode], isStruct: bool) -> bytes:
		content: Set[str] = set()
		bytes = 0
		default = []
		boolBit = 8
		boolOffset = 0
		tableValues: Set[str] = set()
		vl:AstNode = None
		for v in values:					 
			if v.t == NodeType.VALUE:
				assert isinstance(v, Value)
				if v.value:
					if isStruct:
						self.error(v.value, "Not allowed in structs")
					elif v.optional:
						self.error(v.value, "Not allowed for optionals")
					elif v.list:
						self.error(v.value, "Not allowed for lists")
					elif v.value.type in (TokenType.TRUE, TokenType.FALSE):
						self.error(v.value, "Booleans cannot have default values")
					elif v.value.type == TokenType.NUMBER:
						if v.type.type not in (TokenType.UINT8, TokenType.UINT16, TokenType.UINT32, TokenType.UINT64, TokenType.INT8, TokenType.INT16, TokenType.INT32, TokenType.INT64,  TokenType.FLOAT32,  TokenType.FLOAT64):
							self.error(v.value, "Only allowed for number types")
					elif v.value.type == TokenType.IDENTIFIER:
						if v.type.type != TokenType.IDENTIFIER or self.value(v.type) not in self.enums:
							self.error(v.value, "Only allowed for enumes")
						elif self.value(v.value) not in self.enums[self.value(v.type)].annotatedValues:
							self.error(v.value, "Not member of enum")
							self.error(self.enums[self.value(v.type)].token, "Enum declared here")
					else:
						self.error(v.value, "Unhandled value")

				val = self.value(v.identifier)
				typeName = self.value(v.type)
				if val in content:
					self.error(v.identifier, "Duplicate name")
					continue

				if isStruct and v.optional:
					self.error(v.optional, "Not allowed in structs")
				if v.optional and v.type.type in (
								TokenType.UINT8, TokenType.UINT16, TokenType.UINT32, TokenType.UINT64,
								TokenType.INT8, TokenType.INT16, TokenType.INT32, TokenType.INT64,
								TokenType.BOOL):
					if boolBit == 8:
						boolBit = 0
						boolOffset = bytes
						default.append(b"\0")
						bytes += 1
					v.hasOffset = boolOffset
					v.hasBit = boolBit
					boolBit += 1
				if v.list:
					if v.type.type == TokenType.IDENTIFIER:
						typeName = self.value(v.type)
						if typeName not in self.enums and typeName not in self.structs and typeName not in self.tabels:
							self.error(v.type, "Unknown type")
					if isStruct:
						self.error(v.list, "Not allowed in structs")
					if v.optional:
						self.error(v.optional, "Lists are alwayes optional")
					default.append(b"\0\0\0\0")
					v.bytes = 4
					v.offset = bytes
				elif not isStruct and v.type.type == TokenType.BOOL:
					if boolBit == 8:
						boolBit = 0
						boolOffset = bytes
						default.append(b"\0")
						bytes += 1
					v.offset = boolOffset
					v.bit = boolBit
					boolBit += 1
				elif v.type.type in (TokenType.UINT8, TokenType.INT8, TokenType.BOOL):
					if v.type.type == TokenType.UINT8:
						default.append(struct.pack("<B", self.getInt(v.value, 0, 255, 0)))
					elif v.type.type == TokenType.INT8:
						default.append(struct.pack("<b", self.getInt(v.value, -128, 127, 0)))
					elif v.type.type == TokenType.BOOL:
						default.append(b"\0")
					else:
						self.error(v.type.type, "Internal error")
					v.bytes = 1
					v.offset = bytes
				elif v.type.type in (TokenType.UINT16, TokenType.INT16):
					if v.type.type == TokenType.UINT16:
						default.append(struct.pack("<H", self.getInt(v.value, 0, 2**16-1, 0)))
					elif v.type.type == TokenType.INT16:
						default.append(struct.pack("<h", self.getInt(v.value, -2**15, 2**15-1, 0)))
					else:
						self.error(v.type.type, "Internal error")
					v.bytes = 2
					v.offset = bytes
				elif v.type.type in (TokenType.UINT32, TokenType.INT32, TokenType.FLOAT32):
					if v.type.type == TokenType.UINT32:
						default.append(struct.pack("<I", self.getInt(v.value, 0, 2**32-1, 0)))
					elif v.type.type == TokenType.INT32:
						default.append(struct.pack("<i", self.getInt(v.value, -2**31, 2**31-1, 0)))
					elif v.type.type == TokenType.FLOAT32:
						default.append(struct.pack("<f", self.getFloat(v.value, float('nan') if v.optional else 0.0)))
					else:
						self.error(v.type.type, "Internal error")
					v.bytes = 4
					v.offset = bytes
				elif v.type.type in (TokenType.UINT64, TokenType.INT64, TokenType.FLOAT64):
					if v.type.type == TokenType.UINT64:
						default.append(struct.pack("<Q", self.getInt(v.value, 0, 2**64-1, 0)))
					elif v.type.type == TokenType.INT64:
						default.append(struct.pack("<q", self.getInt(v.value, -2**64, 2**64-1, 0)))
					elif v.type.type == TokenType.FLOAT64:
						default.append(struct.pack("<d", self.getFloat(v.value, float('nan') if v.optional else 0.0)))
					else:
						self.error(v.type.type, "Internal error")
					v.bytes = 8
					v.offset = bytes
				elif v.type.type in (TokenType.BYTES, TokenType.TEXT):
					if v.optional:
						self.error(v.optional, "Are alwayes optional")
					if isStruct:
						self.error(v.type, "Not allowed in structs")
					default.append(b"\0\0\0\0")
					v.bytes = 4
					v.offset = bytes
				elif v.type.type != TokenType.IDENTIFIER:
					self.error(v.type, "Unknown type")
					continue
				elif typeName in self.enums:
					if v.optional:
						self.error(v.optional, "Are alwayes optional")
					default.append(b"\xff")
					v.bytes = 1
					v.offset = bytes
					v.enum = self.enums[typeName]
				elif typeName in self.structs:
					if v.optional:
						if boolBit == 8:
							boolBit = 0
							boolOffset = bytes
							default.append(b"\0")
							bytes += 1
						v.hasOffset = boolOffset
						v.hasBit = boolBit
						boolBit += 1
					v.bytes = self.structs[typeName].bytes
					default.append(b"\0" * v.bytes)
					v.offset = bytes
					v.struct = self.structs[typeName]
				elif typeName in self.tabels:
					if isStruct:
						self.error(v.type, "Tabels not allowed in structs")
					if v.optional:
						self.error(v.optional, "Lists are alwayes optional")
					default.append(b"\0\0\0\0")
					v.bytes = 4
					v.offset = bytes
					v.table = self.tabels[typeName]
				else: 
					self.error(v.type, "Unknown identifier")
					continue
			elif v.t in (NodeType.VLUNION, NodeType.VLBYTES, NodeType.VLTEXT, NodeType.VLLIST):
				if isStruct:
					self.error(v.token, "Variable length members not allowed in structs")
				elif vl:
					self.error(v.token, "Cannot add more than one variable length member")
					self.error(vl.token, "We already have this variable length")
				else:
					vl = v
				v.offset = bytes
				if v.t == NodeType.VLUNION:
					v.bytes = 6
					default.append(b"\0\0\0\0\0\0")									
					assert isinstance(v, VLUnion)
					members: Dict[str, Token] = {}
					for member in v.members:
						if member.t == NodeType.VALUE:
							assert isinstance(member, Value)
							if member.type.type != TokenType.IDENTIFIER or self.value(member.type) not in self.tabels:
								self.error(member.type, "Must be a table")
							else:
								member.table = self.tabels[self.value(member.type)]
							name = self.value(member.identifier)
							if name in members:
								self.error(member.identifier, "Duplicate union member")
								self.error(members[name], "Allready declare here")
							else:
								members[name] = member.identifier
						elif member.t == NodeType.TABLE:
							assert isinstance(member, Table)
							name = self.value(member.identifier)
							if name in members:
								self.error(member.identifier, "Duplicate union member")
								self.error(members[name], "Allready declare here")
							else:
								members[name] = member.identifier
							member.name = "%s_%s"%(tableName, name)
							member.default = self.visitContent(member.name, member.values, False)
							
						else:
							self.error(member.token, "Unknown member type")
				elif v.t == NodeType.VLLIST:
					v.bytes = 4
					default.append(b"\0\0\0\0")
					assert isinstance(v, VLList)
					if v.type.type == TokenType.IDENTIFIER:
						typeName = self.value(v.type)
						if typeName not in self.enums and typeName not in self.structs and typeName not in self.tabels:
							self.error(v.type, "Unknown type")
				else:
					v.bytes = 4
					default.append(b"\0\0\0\0")
			else:
				assert(False)
			bytes += v.bytes

		default2 = b"".join(default)
		assert(len(default2) == bytes)
		return default2
	
	def annotate(self, ast: List[AstNode]) -> None:
		self.enums = {}
		self.structs = {}
		self.tabels = {}
		ids: Set[str] = set()
		for node in ast:
			if node.t == NodeType.STRUCT:
				assert isinstance(node, Struct)
				name = self.value(node.identifier)
				self.context = "struct %s"%name
				if name in self.enums or name in self.structs or name in self.tabels:
					self.error(node.identifier, "Duplicate name")
					continue
				structValues: Set[str] = set()
				bytes = len(self.visitContent(name, node.values, True))
				self.structs[name] = node
				node.bytes = bytes
				print("struct %s of size %d"%(name, bytes), file=sys.stderr)
			elif node.t == NodeType.ENUM:
				assert isinstance(node, Enum)
				name = self.value(node.identifier)
				self.context = "enum %s"%name
				if name in self.enums or name in self.structs or name in self.tabels:
					self.error(node.identifier, "Duplicate name")
					continue
				enumValues: Dict[str, int] = {}
				index = 0
				for ev in node.values:
					vv = self.value(ev)
					if vv in enumValues:
						self.error(ev, "Duplicate name")
						continue
					enumValues[vv] = index
					index += 1
				if len(enumValues) > 254:
					self.error(node.identifier, "Too many enum values")
				node.annotatedValues = enumValues
				self.enums[name] = node
				print("enum %s with %s members"%(name, len(enumValues)), file=sys.stderr)
			elif node.t == NodeType.TABLE:
				assert isinstance(node, Table)
				name = self.value(node.identifier)
				node.name = name
				node.magic = int(self.value(node.id)[1:], 16)
				self.context = "tabel %s"%name
				if name in self.enums or name in self.structs or name in self.tabels:
					self.error(node.identifier, "Duplicate name")
					continue
				node.default = self.visitContent(name, node.values, False)
				self.tabels[name] = node
				print("table %s of size >= %d"%(name, len(node.default)+8), file=sys.stderr)

				

def annotate(data: str, ast: List[AstNode]) -> bool:
	a = Annotater(data)
	a.annotate(ast)
	return a.errors == 0
