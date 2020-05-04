import typing as ty
from enum import Enum


class TokenType(Enum):
    BAD = 0
    BOOL = 1
    BYTES = 2
    COLON = 3
    COMMA = 4
    ENUM = 5
    EOF = 6
    EQUAL = 7
    FALSE = 8
    I16 = 9
    I32 = 10
    I64 = 11
    I8 = 12
    LBRACE = 13
    LIST = 14
    NUMBER = 15
    OPTIONAL = 17
    RBRACE = 18
    SEMICOLON = 20
    STRUCT = 22
    TABLE = 23
    TEXT = 24
    TRUE = 25
    U16 = 26
    UI32 = 27
    UI64 = 28
    U8 = 29
    UNION = 30
    IDENTIFIER = 31
    F32 = 32
    F64 = 64
    ID = 65
    NAMESPACE = 66
    COLONCOLON = 67
    DOCCOMMENT = 68
    INPLACE = 69
    IMPORT = 70
    DIRECT = 71
    REMOVED = 72


Token = ty.NamedTuple(
    "Token", [("type", TokenType), ("index", int), ("length", int), ("document", int)]
)


def tokenize(data: str, document: int) -> ty.Iterator[Token]:
    cur: int = 0
    end: int = 0
    ops: ty.Dict[str, TokenType] = {
        ":": TokenType.COLON,
        ";": TokenType.SEMICOLON,
        ",": TokenType.COMMA,
        "=": TokenType.EQUAL,
        "{": TokenType.LBRACE,
        "}": TokenType.RBRACE,
    }

    keywords: ty.Dict[str, TokenType] = {
        "Bool": TokenType.BOOL,
        "Bytes": TokenType.BYTES,
        "F32": TokenType.F32,
        "F64": TokenType.F64,
        "I16": TokenType.I16,
        "I32": TokenType.I32,
        "I64": TokenType.I64,
        "I8": TokenType.I8,
        "list": TokenType.LIST,
        "optional": TokenType.OPTIONAL,
        "Text": TokenType.TEXT,
        "U16": TokenType.U16,
        "U32": TokenType.UI32,
        "U64": TokenType.UI64,
        "U8": TokenType.U8,
        "enum": TokenType.ENUM,
        "false": TokenType.FALSE,
        "struct": TokenType.STRUCT,
        "table": TokenType.TABLE,
        "true": TokenType.TRUE,
        "union": TokenType.UNION,
        "namespace": TokenType.NAMESPACE,
        "inplace": TokenType.INPLACE,
        "import": TokenType.IMPORT,
        "direct": TokenType.DIRECT,
        "Removed": TokenType.REMOVED,
    }

    while cur < len(data):
        if data[cur] in " \t\n\r":
            cur += 1
            continue

        if data[cur : cur + 2] == "::":
            yield Token(TokenType.COLONCOLON, cur, 2, document)
            cur += 2
            continue

        if data[cur] in ops:
            yield Token(ops[data[cur]], cur, 1, document)
            cur += 1
            continue

        if data[cur : cur + 2] == "##" or data[cur : cur + 2] == "///":
            start = cur
            cur += 2
            while cur < len(data) and data[cur] != "\n":
                cur += 1
            while True:
                while cur < len(data) and data[cur] in " \t":
                    cur += 1
                if cur == len(data) or (
                    data[cur] != "#" and data[cur : cur + 2] != "//"
                ):
                    break
                cur += 1
                while cur < len(data) and data[cur] != "\n":
                    cur += 1
            yield Token(TokenType.DOCCOMMENT, start, cur - start, document)
            continue

        if data[cur : cur + 3] == "/**":
            start = cur
            cur += 2
            while cur < len(data) and data[cur : cur + 2] != "*/":
                cur += 1
            if data[cur : cur + 2] == "*/":
                cur += 2
                yield Token(TokenType.DOCCOMMENT, start, cur - start, document)
            else:
                yield Token(TokenType.BAD, start, cur - start, document)
            continue

        if data[cur] == "#" or data[cur : cur + 2] == "//":
            while cur < len(data) and data[cur] != "\n":
                cur += 1
            continue
        if data[cur : cur + 2] == "/*":
            cnt = 1
            cur += 2
            while cnt != 0 and cur < len(data):
                if data[cur : cur + 2] == "/*":
                    cnt += 1
                    cur += 2
                elif data[cur : cur + 2] == "*/":
                    cnt -= 1
                    cur += 2
                else:
                    cur += 1
            continue

        if data[cur].isalpha() or data[cur] == "_":
            end = cur + 1
            while end < len(data) and (data[end] == "_" or data[end].isalnum()):
                end += 1
            type: TokenType = TokenType.IDENTIFIER
            if data[cur:end] in keywords:
                type = keywords[data[cur:end]]
            yield Token(type, cur, end - cur, document)
            cur = end
            continue

        if data[cur] == "@":
            end = cur + 1
            while end < len(data) and data[end] in "0123456789ABCDEFG":
                end += 1
            yield Token(TokenType.ID, cur, end - cur, document)
            cur = end
            continue

        if data[cur] == "-" or data[cur] == "." or data[cur] in "0123456789":
            end = cur
            if end < len(data) and data[end] == "-":
                end += 1
            while end < len(data) and data[end] in "0123456789":
                end += 1
            if end < len(data) and data[end] == ".":
                end += 1
                while end < len(data) and data[end] in "0123456789":
                    end += 1
            if end < len(data) and data[end] in "eE":
                end += 1
                if end < len(data) and data[end] in "+-":
                    end += 1
                while end < len(data) and data[end] in "0123456789":
                    end += 1
            yield Token(TokenType.NUMBER, cur, end - cur, document)
            cur = end
            continue

        yield Token(TokenType.BAD, cur, 1, document)
        cur += 1
    yield Token(TokenType.EOF, cur, 0, document)
