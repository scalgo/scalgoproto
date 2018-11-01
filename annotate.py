# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Perform validation of the ast, and assign offsets and such
"""
from parser import TokenType, NodeType

class Annotater:
	def __init__(self, data):
		self.data = data
		self.errors = 0

	def value(self, t):
		return self.data[t.index: t.index + t.length]	
		
	def error(self, token, message):
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
		
	def annotate(self, ast):
		enums = set()
		structs = {}
		tabels = set()
		ids = set()
		for node in ast:
			if node.t == NodeType.STRUCT:
				name = self.value(node.identifier)
				self.context = "struct %s"%name
				if name in enums or name in structs or name in tabels:
					self.error(node.identifier, "Duplicate name")
					continue
				values = set()
				bytes = 0
				for v in node.values:					 
					if v.t in (NodeType.VLUNION, NodeType.VLLIST, NodeType.VLBYTES, NodeType.VLTEXT):
						self.error(v.token, "Not allowed in structs")
						continue
					elif v.t == NodeType.VALUE:
						if v.optional:
							self.error(v.optional, "Not allowed in structs")
						if v.list:
							self.error(v.list, "Not allowed in structs")

						if v.value:
							self.error(v.value, "Not allowed in structs")
							
						val = self.value(v.identifier)
						typeName = self.value(v.type)
						if val in values:
							self.error(v.identifier, "Duplicate name")
							continue
						if v.type.type in (TokenType.UINT8, TokenType.INT8, TokenType.BOOL):
							v.bytes = 1
							v.offset = bytes
						elif v.type.type in (TokenType.UINT16, TokenType.INT16):
							v.bytes = 2
							v.offset = bytes
						elif v.type.type in (TokenType.UINT32, TokenType.INT32, TokenType.FLOAT32):
							v.bytes = 4
							v.offset = bytes
						elif v.type.type in (TokenType.UINT64, TokenType.INT64, TokenType.FLOAT64):
							v.bytes = 8
							v.offset = bytes
						elif v.type.type != TokenType.IDENTIFIER:
							self.error(v.type, "Not allowed in structs")
							continue
						elif typeName in enums:
							v.bytes = 1
							v.offset = bytes
						elif typeName in structs:
							v.bytes = structs[typeName].bytes
							v.offset = bytes
						elif typeName in tabels:
							self.error(v.type, "Tabels not allowed in structs")
							continue
						else: 
							self.error(v.type, "Unknown identifier")
							continue
					else:
						assert(False)
					bytes += v.bytes
				values.add(v)
				structs[name] = node
				node.bytes = bytes
				print("struct %s of size %d"%(name, bytes))
			elif node.t == NodeType.ENUM:
				name = self.value(node.identifier)
				self.context = "enum %s"%name
				if name in enums or name in structs or name in tabels:
					self.error(node.identifier, "Duplicate name")
					continue
				values = {}
				index = 0
				for v in node.values:
					vv = self.value(v)
					if vv in values:
						self.error(v, "Duplicate name")
						continue
					values[vv] = index
					++index
				if len(values) > 254:
					self.error(node.identifier, "Too many enum values")
				node.annotatedValues = values
				enums.add(name)
				print("enum %s with %s members"%(name, len(values)))
			elif node.t == NodeType.TABLE:
				name = self.value(node.identifier)
				self.context = "tabel %s"%name
				if name in enums or name in structs or name in tabels:
					self.error(node.identifier, "Duplicate name")
					continue
				bytes = 0
				boolBit = 8
				boolOffset = 0
				values = set()
				for v in node.values:
					if v.t == NodeType.VALUE:
						val = self.value(v.identifier)
						if val in values:
							self.error(node.identifier, "Duplicate name")
							continue
						values.add(val)
						if v.optional and v.type in (
								TokenType.UINT8, TokenType.UINT16, TokenType.UINT32, TokenType.UINT64,
								TokenType.INT8, TokenType.INT16, TokenType.INT32, TokenType.INT64,
								TonkeType.BOOL):
							if boolBit == 8:
								boolBit = 0
								boolOffset = bytes
								bytes += 1
							v.hasOffset = boolOffset
							v.hasBit = boolBit
							boolBit += 1
						typeName = self.value(v.type)
						if v.type.type == TokenType.BOOL:
							if boolBit == 8:
								boolBit = 0
								boolOffset = bytes
								bytes += 1
							v.bytes = 0
							v.offset = boolOffset
							v.bit = boolBit
							boolBit += 1
						elif v.type.type in (TokenType.UINT8, TokenType.INT8):
							v.bytes = 1
							v.offset = bytes
						elif v.type.type in (TokenType.UINT16, TokenType.INT16):
							v.bytes = 2
							v.offset = bytes
						elif v.type.type in (TokenType.UINT32, TokenType.INT32, TokenType.FLOAT32, TokenType.TEXT, TokenType.BYTES):
							v.bytes = 4
							v.offset = bytes
						elif v.type.type in (TokenType.UINT64, TokenType.INT64, TokenType.FLOAT64):
							v.bytes = 8
							v.offset = bytes
						elif v.type.type != TokenType.IDENTIFIER:
							self.error(v.type, "Unknown type")
							continue
						elif typeName in enums:
							v.bytes = 1
							v.offset = bytes
						elif typeName in structs:
							v.bytes = structs[typeName].bytes 
							v.offset = bytes
						elif typeName in tabels:
							v.bytes = 4
							v.offset = bytes
						else:
							self.error(v.type, "Unknown type")
							continue
						bytes += v.bytes
				tabels.add(name)
				

def annotate(data, ast):
	a = Annotater(data)
	a.annotate(ast)
	return a.errors == 0
