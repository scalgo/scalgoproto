

## Gramma

An gramma for a schema is defined below:

    Document = (DocumentItem Split)*
    Split = (";" | ",")?
    DocumentItem = Namespace | Enum | Struct | Union | Table
    Namespace = "namespace" Identifier ("::" Identifier) * Split
    Identifier = UIdentifier | LIdentifier
    UIdentifier = "[A-Z][0-9a-zA-Z]*"
    LIdentifier = "[a-z][0-0a-zA-Z]*"
    Enum = "enum" UIdentifier "{" EnumItem * "}" Split
    EnumItem = LIdentifier Split
    Struct = "struct" UIdentifier "{" StructItem* "}" Split
    StructItem = LIdentifier ":" (BasicType | UIdentifier) Split
    BasicType = "U8" | "I8" | "U16" | "I16" | "U32" | "I32" | "U64" | "I64" | "F32" | "F64" | "Bool"
    Union = "union" UIdentifier UnionContent Split
    UnionContent = "{" UnionItem * "}" 
    UnionItem = LIdentifier (TableContent | UnionItemType) Split
    UnionItemType = ":" "list"? (BriefTable | BriefUnion | 
    UIdentifier | "Text" | "Bytes") 
    BriefUnion = "union" UnionContent
    Table = "table" UIdentifier TableId TableContent Split
    TableContent = "{" TableItem * "}"
    TableId = "@[0-9A-F]{8,8}"
    BriefTable = "table" TableId? TableContent
    TableItem = LIdentifier (TableContent | TableItemType) Split
    TableItemType = ":" ("list" | "optional" | "inplace") * (BasicType | "Text" | "Bytes" | UIdentifier | BriefUnion | BriefTable) ("=" Number)?
    Number = "-?[0-9]*(\.[0-9]*)?(e-?[0-9]+)?