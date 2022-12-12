# -*- mode: python; tab-width: 4; indent-tabs-mode: nil; python-indent-offset: 4; coding: utf-8 -*-
"""
Parse a protocol description and generate an ast
"""
import enum
import typing as ty
from .error import error
from .sp_tokenize import Token, TokenType, tokenize
from .documents import Documents, Document


class AstNode(object):
    __slots__ = [
        "token",
        "doc_comment",
        "bytes",
        "offset",
        "docstring",
        "document",
        "uses",
        "namespace",
    ]
    token: ty.Optional[Token]
    doc_comment: ty.Optional[Token]
    bytes: int
    offset: int
    docstring: ty.Optional[ty.List[str]]
    document: int
    uses: ty.Set[ty.Union["Union", "Table", "Struct", "Enum"]]
    namespace: ty.Optional[str]

    def __init__(
        self,
        token: ty.Optional[Token],
        document: int,
        doc_comment: ty.Optional[Token] = None,
    ) -> None:
        self.token = token
        self.doc_comment = doc_comment
        self.bytes = 0
        self.offset = 0
        self.document = document
        self.docstring = None
        self.uses = set()
        self.namespace = ""


class Namespace(AstNode):
    __slots__ = ["namespace"]

    def __init__(self, token: Token, document: int, namespace: str) -> None:
        super().__init__(token, document)
        self.namespace = namespace


class Struct(AstNode):
    __slots__ = ["identifier", "members", "name"]
    identifier: ty.Optional[Token]
    members: ty.List["Value"]
    name: ty.Optional[str]

    def __init__(
        self,
        token: Token,
        document: int,
        identifier: ty.Optional[Token],
        members: ty.List["Value"],
        doc_comment: ty.Optional[Token],
    ) -> None:
        super().__init__(token, document, doc_comment)
        self.identifier = identifier
        self.members = members
        self.name = None


class Enum(AstNode):
    __slots__ = ["identifier", "members", "annotatedValues", "name", "removed"]
    identifier: ty.Optional[Token]
    members: ty.List["Value"]
    name: ty.Optional[str]
    annotatedValues: ty.Optional[ty.Dict[str, int]]
    removed: bool

    def __init__(
        self,
        token: Token,
        document: int,
        identifier: ty.Optional[Token],
        members: ty.Optional[ty.List["Value"]],
        doc_comment: ty.Optional[Token],
    ) -> None:
        super().__init__(token, document, doc_comment)
        self.identifier = identifier
        self.members = members if members is not None else []
        self.removed = members is None
        self.name = None
        self.annotatedValues = None


class Table(AstNode):
    __slots__ = ["identifier", "id_", "members", "default", "magic", "name", "empty"]
    identifier: ty.Optional[Token]
    id_: ty.Optional[Token]
    members: ty.List["Value"]
    default: ty.Optional[bytes]
    name: ty.Optional[str]
    magic: int
    empty: bool

    def __init__(
        self,
        token: Token,
        document: int,
        identifier: ty.Optional[Token],
        id_: ty.Optional[Token],
        members: ty.List["Value"],
        doc_comment: ty.Optional[Token],
    ) -> None:
        super().__init__(token, document, doc_comment)
        self.identifier = identifier
        self.id_ = id_
        self.members = members
        self.default = None
        self.magic: int = 0
        self.name = None
        self.empty = False


class Union(AstNode):
    __slots__ = ["members", "identifier", "name"]
    members: ty.List["Value"]
    identifier: ty.Optional[Token]
    name: ty.Optional[str]

    def __init__(
        self,
        token: Token,
        document: int,
        identifier: ty.Optional[Token],
        members: ty.List["Value"],
        doc_comment: ty.Optional[Token],
    ) -> None:
        super().__init__(token, document, doc_comment)
        self.members = members
        self.identifier = identifier
        self.name = None


class Value(AstNode):
    __slots__ = [
        "identifier",
        "value",
        "type_",
        "optional",
        "list_",
        "inplace",
        "direct",
        "direct_table",
        "direct_union",
        "has_offset",
        "has_bit",
        "bit",
        "table",
        "enum",
        "struct",
        "union",
        "parsed_value",
        "direct_enum",
        "direct_struct",
    ]
    identifier: Token
    value: ty.Optional[Token]
    type_: ty.Optional[Token]
    optional: ty.Optional[Token]
    list_: ty.Optional[Token]
    inplace: ty.Optional[Token]
    direct: ty.Optional[Token]
    direct_table: ty.Optional[Table]
    direct_union: ty.Optional[Union]
    direct_enum: ty.Optional[Enum]
    direct_struct: ty.Optional[Struct]
    has_offset: int
    has_bit: int
    bit: int
    table: ty.Optional[Table]
    enum: ty.Optional[Enum]
    struct: ty.Optional[Struct]
    union: ty.Optional[Union]
    parsed_value: ty.Union[int, float]

    def __init__(
        self,
        token: ty.Optional[Token],
        document: int,
        identifier: Token,
        value: ty.Optional[Token],
        type_: ty.Optional[Token],
        optional: ty.Optional[Token],
        list_: ty.Optional[Token],
        inplace: ty.Optional[Token],
        direct: ty.Optional[Token],
        direct_table: ty.Optional[Table],
        direct_union: ty.Optional[Union],
        direct_enum: ty.Optional[Enum],
        direct_struct: ty.Optional[Struct],
        doc_comment: ty.Optional[Token],
    ) -> None:
        super().__init__(token, document, doc_comment)
        self.identifier = identifier
        self.value = value
        self.type_ = type_
        self.optional = optional
        self.list_ = list_
        self.inplace = inplace
        self.direct = direct
        self.direct_table = direct_table
        self.direct_union = direct_union
        self.direct_enum = direct_enum
        self.direct_struct = direct_struct
        self.has_offset = 0
        self.has_bit = 0
        self.bit = 0
        self.table = None
        self.enum = None
        self.struct = None
        self.union = None
        self.parsed_value = 0


class ParseError(Exception):
    def __init__(self, token: Token, message: str, context: str) -> None:
        self.token = token
        self.message = message
        self.context = context

    def describe(self, documents: Documents) -> None:
        error(documents, self.context, self.token, self.message, "Parse error")


class ICE(Exception):
    def __init__(self):
        super().__init__("Internal compiler error")


class Parser:
    token: ty.Optional[Token] = None

    def __init__(self, documents: Documents) -> None:
        self.strict = False
        self.documents = documents
        self.document = self.documents.root
        self.tokenizer = tokenize(self.document.content, self.document.id)
        self.docstack = [(self.document, self.tokenizer)]
        self.token = None
        self.parked_token: ty.Optional[Token] = None
        self.next_token()
        self.context = ""

    def check_token(self, t: Token, types: ty.List[TokenType]) -> None:
        if not t.type in types:
            raise ParseError(
                t,
                "Expected one of %s got %s" % (", ".join(map(str, types)), t.type),
                self.context,
            )

    def consume_token(self, types: ty.List[TokenType]) -> Token:
        assert self.token is not None
        t = self.token
        self.check_token(t, types)
        self.next_token()
        return t

    def next_token(self) -> None:
        while True:
            if self.parked_token:
                self.token = self.parked_token
                self.parked_token = None
            else:
                self.token = next(self.tokenizer)
            if self.strict:
                break
            if self.token.type not in (
                TokenType.SPACE,
                TokenType.NEWLINE,
                TokenType.TABS,
                TokenType.COMMENT,
            ):
                break

    def parse_content(self, indent: int, is_union: bool) -> ty.List[Value]:
        self.consume_token([TokenType.LBRACE])
        if self.token and self.token.type == TokenType.RBRACE:
            self.next_token()
            return []
        self.handle_end_of_line(indent)
        members: ty.List[Value] = []
        doc_comment: ty.Optional[Token] = None
        while True:
            if self.strict:
                if not self.token or self.token.type != TokenType.RBRACE or indent != 1:
                    tabs = self.consume_token([TokenType.TABS])
                    l = (
                        indent - 1
                        if self.token and self.token.type == TokenType.RBRACE
                        else indent
                    )
                    if tabs.length != l:
                        raise ParseError(
                            tabs,
                            f"Wrong indentation level {tabs.length} expected {l}",
                            self.context,
                        )

            t = self.consume_token(
                [
                    TokenType.RBRACE,
                    TokenType.IDENTIFIER,
                    TokenType.DOCCOMMENT,
                    TokenType.REMOVED,
                ]
            )
            if t.type == TokenType.DOCCOMMENT:
                doc_comment = t
            elif t.type == TokenType.RBRACE:
                break
            elif t.type in (TokenType.IDENTIFIER, TokenType.REMOVED):
                assert self.token is not None
                self.check_token(
                    self.token, [TokenType.COLON, TokenType.LBRACE, TokenType.SPACE]
                )
                colon: ty.Optional[Token] = None
                if self.strict:
                    if not is_union:
                        colon = self.consume_token([TokenType.COLON])
                    elif self.token.type == TokenType.COLON:
                        colon = self.consume_token([TokenType.COLON])
                    self.consume_space()
                elif self.token.type == TokenType.COLON:
                    colon = self.consume_token([TokenType.COLON])
                optional: ty.Optional[Token] = None
                list_: ty.Optional[Token] = None
                inplace: ty.Optional[Token] = None
                direct: ty.Optional[Token] = None
                value: ty.Optional[Token] = None
                direct_table: ty.Optional[Table] = None
                direct_union: ty.Optional[Union] = None
                direct_enum: ty.Optional[Enum] = None
                direct_struct: ty.Optional[Struct] = None
                modifiers = [
                    TokenType.OPTIONAL,
                    TokenType.LIST,
                    TokenType.INPLACE,
                    TokenType.DIRECT,
                ]
                while self.token.type in modifiers:
                    if self.token.type == TokenType.OPTIONAL:
                        optional = self.consume_token([TokenType.OPTIONAL])
                        self.consume_space()
                    elif self.token.type == TokenType.LIST:
                        list_ = self.consume_token([TokenType.LIST])
                        self.consume_space()
                    elif self.token.type == TokenType.INPLACE:
                        inplace = self.consume_token([TokenType.INPLACE])
                        self.consume_space()
                    elif self.token.type == TokenType.DIRECT:
                        direct = self.consume_token([TokenType.DIRECT])
                        self.consume_space()
                type_ = self.token
                self.check_token(
                    self.token,
                    [
                        TokenType.BOOL,
                        TokenType.TEXT,
                        TokenType.IDENTIFIER,
                        TokenType.BYTES,
                        TokenType.I8,
                        TokenType.I16,
                        TokenType.I32,
                        TokenType.I64,
                        TokenType.U8,
                        TokenType.U16,
                        TokenType.UI32,
                        TokenType.UI64,
                        TokenType.F32,
                        TokenType.F64,
                        TokenType.UNION,
                        TokenType.TABLE,
                        TokenType.LBRACE,
                        TokenType.ENUM,
                        TokenType.STRUCT,
                    ],
                )
                if type_.type == TokenType.LBRACE:
                    direct_table = Table(
                        type_,
                        self.document.id,
                        None,
                        None,
                        self.parse_content(indent + 1, False),
                        doc_comment,
                    )
                else:
                    self.next_token()
                    if type_.type == TokenType.UNION:
                        self.consume_space()
                        direct_union = Union(
                            type_,
                            self.document.id,
                            None,
                            self.parse_content(indent + 1, True),
                            doc_comment,
                        )
                    elif type_.type == TokenType.TABLE:
                        id_: ty.Optional[Token] = None
                        self.consume_space()
                        if self.token.type == TokenType.ID:
                            id_ = self.consume_token([TokenType.ID])
                            self.consume_space()
                        direct_table = Table(
                            type_,
                            self.document.id,
                            None,
                            id_,
                            self.parse_content(indent + 1, False),
                            doc_comment,
                        )
                    elif type_.type == TokenType.ENUM:
                        self.consume_space()
                        direct_enum = Enum(
                            t,
                            self.document.id,
                            None,
                            self.parse_enum(indent + 1),
                            doc_comment,
                        )
                    elif type_.type == TokenType.STRUCT:
                        self.consume_space()
                        direct_struct = Struct(
                            type_,
                            self.document.id,
                            None,
                            self.parse_content(indent + 1, False),
                            doc_comment,
                        )
                    if self.token and self.token.type == TokenType.SPACE:
                        self.consume_space()
                        self.check_token(self.token, [TokenType.EQUAL])
                    if self.token.type == TokenType.EQUAL:
                        self.consume_token([TokenType.EQUAL])
                        self.consume_space()
                        value = self.consume_token(
                            [
                                TokenType.TRUE,
                                TokenType.FALSE,
                                TokenType.NUMBER,
                                TokenType.IDENTIFIER,
                            ]
                        )
                members.append(
                    Value(
                        colon,
                        self.document.id,
                        t,
                        value,
                        type_,
                        optional,
                        list_,
                        inplace,
                        direct,
                        direct_table,
                        direct_union,
                        direct_enum,
                        direct_struct,
                        doc_comment,
                    )
                )
                doc_comment = None
            else:
                raise ICE()
            assert self.token is not None
            if self.token.type in [TokenType.COMMA, TokenType.SEMICOLON]:
                self.next_token()
            self.handle_end_of_line(indent)
        return members

    def parse_enum(self, indent: int) -> ty.Optional[ty.List[Value]]:
        assert self.token is not None
        if self.token.type == TokenType.REMOVED:
            self.consume_token([TokenType.REMOVED])
            return None
        self.consume_token([TokenType.LBRACE])
        expect_indent = False
        expect_more = True
        if self.token and self.token.type == TokenType.IDENTIFIER:
            pass
        else:
            expect_indent = True
            self.handle_end_of_line(indent)
        values: ty.List[Value] = []
        doc_comment = None
        while True:
            if self.strict and expect_indent:
                if not self.token or self.token.type != TokenType.RBRACE or indent != 1:
                    tabs = self.consume_token([TokenType.TABS])
                    l = (
                        indent - 1
                        if self.token and self.token.type == TokenType.RBRACE
                        else indent
                    )
                    if tabs.length != l:
                        raise ParseError(
                            tabs,
                            f"Wrong indentation level {tabs.length} expected {l}",
                            self.context,
                        )
                expect_indent = False
            if expect_more:
                self.check_token(
                    self.token,
                    [TokenType.RBRACE, TokenType.IDENTIFIER, TokenType.DOCCOMMENT],
                )
                expect_more = False
            else:
                self.check_token(
                    self.token,
                    [TokenType.RBRACE],
                )
            if self.token.type == TokenType.RBRACE:
                break
            elif self.token.type == TokenType.DOCCOMMENT:
                doccomment2 = self.token
            elif self.token.type == TokenType.IDENTIFIER:
                ident = self.consume_token([TokenType.IDENTIFIER])
                values.append(
                    Value(
                        ident,
                        self.document.id,
                        ident,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        doc_comment,
                    )
                )
                doc_comment = None
                if self.token.type in [TokenType.COMMA, TokenType.SEMICOLON]:
                    expect_more = True
                    self.next_token()
                if self.token and self.token.type == TokenType.RBRACE:
                    pass
                elif self.token and self.token.type == TokenType.SPACE:
                    self.consume_space()
                else:
                    expect_indent = True
                    self.handle_end_of_line(indent)
        self.consume_token([TokenType.RBRACE])
        return values

    def value(self, t: Token) -> str:
        return self.documents.by_id[t.document].content[t.index : t.index + t.length]

    def skip_empty_lines(self, indent: int) -> None:
        while True:
            if self.token is None:
                break

            tabs = None
            tabs_len = 0
            if self.token.type == TokenType.TABS:
                tabs = self.token
                self.next_token()
                tabs_len = tabs.length

            if self.token.type == TokenType.NEWLINE and (
                tabs_len == indent or tabs_len == 0
            ):
                self.consume_token([TokenType.NEWLINE])
                continue
            elif self.token.type == TokenType.COMMENT and tabs_len == indent:
                self.consume_token([TokenType.COMMENT])
                self.consume_token([TokenType.NEWLINE])
                continue
            elif tabs is not None:
                self.parked_token = self.token
                self.token = tabs
            break

    def handle_end_of_line(self, indent: int) -> None:
        if not self.strict:
            return
        if self.token and self.token.type == TokenType.SPACE:
            self.consume_token([TokenType.SPACE])
            self.consume_token([TokenType.COMMENT])
        self.consume_token([TokenType.NEWLINE])
        self.skip_empty_lines(indent)

    def consume_space(self) -> None:
        if self.strict:
            self.consume_token([TokenType.SPACE])

    def parse_document(self, strict=False) -> ty.List[AstNode]:
        ans: ty.List[AstNode] = []
        doc_comment: ty.Optional[Token] = None
        assert self.token is not None
        self.strict = strict
        self.skip_empty_lines(0)
        while self.token.type != TokenType.EOF:
            self.context = "message"
            t = self.consume_token(
                [
                    TokenType.STRUCT,
                    TokenType.ENUM,
                    TokenType.TABLE,
                    TokenType.NAMESPACE,
                    TokenType.UNION,
                    TokenType.DOCCOMMENT,
                    TokenType.IMPORT,
                ]
            )
            if t.type == TokenType.IMPORT:
                self.consume_space()
                self.context = ""
                i = self.token
                self.check_token(i, [TokenType.IDENTIFIER])
                name = self.value(i)
                if not name in self.documents.by_name:
                    self.document = self.documents.read(name)
                    self.tokenizer = tokenize(self.document.content, self.document.id)
                    self.docstack.append((self.document, self.tokenizer))
                    self.next_token()
                    ans += self.parse_document(False)
                    self.strict = strict
                    self.docstack.pop()
                    self.document, self.tokenizer = self.docstack[-1]
                    self.content = ""
                self.next_token()
                if strict:
                    self.consume_token([TokenType.SEMICOLON])
                self.handle_end_of_line(0)
            elif t.type == TokenType.DOCCOMMENT:
                doc_comment = t
            elif t.type == TokenType.NAMESPACE:
                self.consume_space()
                namespace = ""
                while True:
                    i = self.consume_token([TokenType.IDENTIFIER])
                    namespace += self.documents.by_id[self.document.id].content[
                        i.index : i.index + i.length
                    ]
                    tt = self.consume_token([TokenType.COLONCOLON, TokenType.SEMICOLON])
                    if tt.type != TokenType.COLONCOLON:
                        break
                    namespace += "::"
                self.handle_end_of_line(0)
                ans.append(Namespace(t, self.document.id, namespace))
                doc_comment = None
            elif t.type == TokenType.STRUCT:
                self.consume_space()
                i = self.consume_token([TokenType.IDENTIFIER])
                self.consume_space()
                self.context = "struct %s" % self.value(i)
                ans.append(
                    Struct(
                        t,
                        self.document.id,
                        i,
                        self.parse_content(1, False),
                        doc_comment,
                    )
                )
                doc_comment = None
                self.handle_end_of_line(0)
            elif t.type == TokenType.TABLE:
                self.consume_space()
                i = self.consume_token([TokenType.IDENTIFIER])
                self.consume_space()
                self.context = "table %s" % self.value(i)
                id_ = (
                    self.consume_token([TokenType.ID])
                    if self.token.type == TokenType.ID
                    else None
                )
                if id_:
                    self.consume_space()
                ans.append(
                    Table(
                        t,
                        self.document.id,
                        i,
                        id_,
                        self.parse_content(1, False),
                        doc_comment,
                    )
                )
                doc_comment = None
                self.handle_end_of_line(0)
            elif t.type == TokenType.ENUM:
                self.consume_space()
                i = self.consume_token([TokenType.IDENTIFIER])
                self.consume_space()
                self.context = "enum %s" % self.value(i)
                ans.append(
                    Enum(t, self.document.id, i, self.parse_enum(1), doc_comment)
                )
                doc_comment = None
                self.handle_end_of_line(0)
            elif t.type == TokenType.UNION:
                self.consume_space()
                i = self.consume_token([TokenType.IDENTIFIER])
                self.consume_space()
                self.context = "union %s" % self.value(i)
                ans.append(
                    Union(
                        t, self.document.id, i, self.parse_content(1, True), doc_comment
                    )
                )
                doc_comment = None
                self.handle_end_of_line(0)
            else:
                raise ICE()
            if not strict and self.token.type in [TokenType.COMMA, TokenType.SEMICOLON]:
                self.next_token()
        return ans
