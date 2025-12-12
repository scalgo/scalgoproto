# Schema language

A schema file describes the layout of a messages, and has the extension ".spr". It is described in the domain specific language described below. An the top level a file consists of a number of tabels, structs and enums as well as some import and namespace statements.

### Basic tyes

The following basic tyes are supported:

* U8 is an 8 bit unsigned integer supporting values in the range 0 to 255.
* I8 is a 8 bit signed integer supporting values in the range -128 to 127.
* U16 is an 16 bit unsigned integer supporting values in the range 0 to 65536.
* I16 is a 16 bit signed integer supporting values in the range -32768 to 32767.
* U32 is an 32 bit unsigned integer supporting values in the range 0 to 4294967296.
* I32 is a 32 bit signed integer supporting values in the range -2147483648 to 2147483647.
* U64 is an 64 bit unsigned integer supporting values in the range 0 to 18446744073709551616.
* I64 is a 64 bit signed integer supporting values in the range -9223372036854775808 to 9223372036854775807.
* F32 is a 32 bit IEEE floating point number.
* F64 is a 64 bit IEEE floating point number.
* Bool is a boolean value, either true or false.

### Enum 

An enum defines a set with a fixed number of values. An enum can either be named or brief as in the examples below:

    enum MyEnum {
        value1,
        value2,
        value3
    }

    table MyTable @76E01AA2 {
        kind : enum {
            kind1,
            kind2
        };
    }

Here the named enum MyEnum can have one of the values "value1", "value2", "value3". And the brief enum in the MyTable table, can have the values "kind1", "kind2". An enum may have atmost 255 different values. New values should be added to the end to ensure backwards compatability. Enum names must be in camel case starting with an uppercase letter, and enum member must be in camel case starting with a lowercase letter.

### Struct

A struct is a linearly layed out object, that can be composed of elements of basic types, struct types or Enum types. 

    struct MyStruct {
        a: U8;
        b: F32;
    }

    enum MyEnum {
        value1,
        value2,
        value3
    }

    struct MyOtherStruct {
        x: MyStruct;
        y: MyEnum;
        z: struct {
            p: I32;
        }
    }

In the example above we define a struct called MyStruct with an U8 named a, and a F32 named b. We define another struct called MyOtherStruct with a MyStruct named x, a MyEnum called named y, and another brief struct named z. This brief struct has a I32 member named p.

Structs can either be named or brief. The name of struct must be camel case and the first letter must be uppercase.

Structs may have any number of members the name of member must be in camel case and the first letter must be in lowercase.
The type of the members must be either a base type, a named struct, a named enum, a brief struct or a brief enum.

It is **not possible** to extend or modify a struct in a backwards compatible way, so in general tabels should be prefered instead of structs. The main advantage of structs over tabels are that tables are embedded as pointers (offsets) in tables or lists while structs are directly embedded. In that way an array of points will be much smaller and more efficint if the points are structs as opposed to tabels.

### Table

A table is an object that can be extended in the future and which can contain any number of table members.

    table MyTable @5D99E0AD {
        v1: Bool;
    }

In the example above a table named MyTable is defined the table has the magic number 5D99E0AD and a Bool member named v1. Table names must be in camel case where the first letter is uppercase. The names of the members must be in camel case where the first letter is lowercase. The magic number is used as an identifier when decoding tables to ensure against type confusion.
The magic numbers can be generated as below:

    $ ./scalgoprotoc.py magic
    @8A32786C
    @8B1A472D
    @3DCEBBE2
    @915EE509

The tabels can contain any number of members. The type of the members can be basic types, Texts, Bytes, named unions, brief unions, named structs, brief structs, named tabels and brief Tabels.

##### Basic types and enums
In the example below basic types are used, and the member myInt will have a default value of 42 and namedEnum vill have a default value of b.
Bools always has a default value of false, numeric types default to 0 unless something else is specifed, enums default to the first member unless otherwise specified. 

    enum MyEnum {
        a, b
    }
    
    table MyTable @5D99E0AD {
        myBool: Bool;
        myInt: I32 = 42;
        myFloat: F32;
        namedEnum: MyEnum = b;
        briefEnum: enum {x,y};
    }

##### Texts and Bytes
In the example below Texts and Bytes are used.

    table MyTable @5D99E0AD {
        myText: Text;
        myBytes: Bytes;
    }

Here MyTable contains pointers to a text and a bytes.
A text is a zero terminated UTF-8 string, and Bytes can contain any binary content.

##### Structs and Tabels

    struct MyStruct {
        v: U64;
    }

    struct MyTable @5D99E0AD {
        v: I32;
    }

    table MyOtherTable @5D99E0AE {
        namedTable: MyTable;
        briefTable: table @5D99E0AF {
            x: U8;
        }
        namedStruct: MyStruct;
        briefStruct: struct {
            y: Bool;
        }
    }

In the example above MyOtherTabels contains pointers to a MyTable and a brief table. It embeds a named struct and a brief struct.

##### Unions

    union MyUnion {
        t: Text;
        b: Bytes;
    } 

    table MyTable @5D99E0AD {
        namedUnion: MyUnion;
        briefUnion: union {
            x: Text;
        }
    } 

In the example above my table have has a named and an brief union member, unions are described below.

##### Optional

Basic types, structs and enums may be declared optional. Tabels, unions, lists, bytes and texts are always optional. The default state of an optional element is unset. In the example below several optional elements are declared:

    table MyTable @5D99E0AD {
        a: optional I32;
        b: optional enum {x,y,z};
        c: optional struct {v:Bool};
    }

##### Lists

Tabels elements an also be lists. In the example below several lists are declared:

    table MyTable @5D99E0AD {
        a: list I32;
        b: list enum {x,y,z};
        c: list struct {v:Bool};
        d: list table {x:U32, y:U32};
    }

##### Direct list table

It is possible to use direct list table. This is more efficient than regular list tables:

    table MyTable @5D99E0AD {
        d: direct list table {x:U32, y:U32};
    }


For regular list tabels. The list stores a pointer to a table. At the pointer location the magic
and size of the table is stored. With a direct list table the table content is stored directly
in the list. So the pointer indirection, magic and size is saved.

##### Inplace

Within a table atmost one table, union, text or bytes, member may be declared inplace. An inplace member in encoded directly after its table, and 8 bytes are saved. In the example below an inplace union is used;

    table MyTable @5D99E0AD
        id: U64;
        content: union {
            name: Text;
            names: list Text;
            numbers: list I64;
        }
    }

##### Backwards compatability

To maintain backwards compatability new members must be added to the bottom of a table. If a non backwards compatible change is made to a table, it is reccomended that the magic number be changed.

### Union

A union is an entety that can hold atmost one value. These values must be eithers tabels, lists, texts or bytes.

    table MyTable @5D99E0AD {
        id: U64;
    }

    union MyUnion {
        a {};
        b: Text;
        c: MyTable;
        d: table @5D99E0AE {
            x: Bool;
        };
        e: Bytes;
        f: {
            z: U32;
        };
    };

In the example above a value of the MyUnion type can be one of the following:

* Unassigned
* The empty table a
* A pointer to Text b
* A pointer to MyTable c
* A pointer to brief table d
* A pointer to Bytes e
* A pointer to brief table f

A union can have at most 65535 different members. To maintain backwards compatability new members must be added to the end.

### Namespace

When generating NEKO for c++ often you want the readers and writers to be generated in a specific namespace. To do this a namespace decleration can be used as in the example below:

    namespace my::ns;

    table Cat @779E3838 {
        name: Text;
    }

Here the readers and writers for the Cat table will be placed in the namespace "my::ns". In general any reader or writer will be generated in the namespace of the last namespace statement preceeding it.


### Import

Some times it is not desierable to have everything in a single self contained schema file. In this case a single file can be split into several files where one file can reference entities in the other using the inport statement. As in the example below:

base.spr

    table Cat @779E3838 {
        name: Text;
    }

derived.spr

    import base

    table Container @BE5F5E2F {
        cat : Cat;
    }

Here the entities in base.spr are imported in derived.spr. When NEKO is generated from derived.spr, the readers and writers for entities of base.spr are not generetad instead an include/import statement is generated.

### Comments

Comments may be added at any place in a schema. The example below shows basic comments.

    // I am an one line comment
    # I am also an one line comment

    /*
        I am a multiline comment
    */

    /*
        I am a multiline comment
        /* I can contain recursive content */
        I am not done yet
     */

Additionally docstring comments are also supported, these comments are propagated to the output as docstrings or doxygens comments.

    /**
     * This is a good struct
     */
    struct MyStruct {}

    ## This is my enum
    enum MyEnum {
        /// Some value
        a,
        /** Some other value */
        b,
    }

## Gramma

An gramma for a schema is defined below:

    Document = (DocumentItem Split)*
    Split = (";" | ",")?
    DocumentItem = Import | Namespace | Enum | Struct | Union | Table
    Import = "import" Identifier
    Namespace = "namespace" Identifier ("::" Identifier)* Split
    Identifier = UIdentifier | LIdentifier
    UIdentifier = "[A-Z][0-9a-zA-Z]*"
    LIdentifier = "[a-z][0-0a-zA-Z]*"
    Enum = "enum" UIdentifier EnumContent Split
    EnumContent = "{" EnumItem* "}"
    EnumItem = LIdentifier Split
    BriefEnum = "enum" EnumContent
    Struct = "struct" UIdentifier "{" StructItem* "}" Split
    StructItem = LIdentifier ":" (BasicType | UIdentifier) Split
    BasicType = "U8" | "I8" | "U16" | "I16" | "U32" | "I32" | "U64" | "I64" | "F32" | "F64" | "Bool"
    Union = "union" UIdentifier UnionContent Split
    UnionContent = "{" UnionItem* "}" 
    UnionItem = LIdentifier (TableContent | UnionItemDesc) Split
    UnionItemDesc = ":" "list"? (BriefTable | BriefUnion | 
    UIdentifier | "Text" | "Bytes") 
    BriefUnion = "union" UnionContent
    Table = "table" UIdentifier TableId TableContent Split
    TableContent = "{" TableItem* "}"
    TableId = "@[0-9A-F]{8,8}"
    BriefTable = "table" TableId? TableContent
    TableItem = LIdentifier (TableContent | TableItemDesc) Split
    TableItemDesc = ":" TableItemMod* TableItemType ("=" Number | LIdentifier)?
    TableItemMod = "list" | "optional" | "inplace"
    TableItemType = BasicType | "Text" | "Bytes" | UIdentifier | BriefUnion | BriefTable | BriefEnum
    Number = "-?[0-9]*(\.[0-9]*)?(e-?[0-9]+)?
