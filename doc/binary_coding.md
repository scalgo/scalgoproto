# Binary coding
The following describes the binary encoding used by scalgoproto.

### Basic types
The integer types U8, U16, U32, U64, I8, I16, I16 and I64, are encoded in little endian, two's complement without padding (as they would be in a packed struct on X64).
The floating point types F32 and F64 are encoded using IEEE 754 in little endian without padding (as they would be in a packed struct on X64).

### Structs
Structs are encoded as the concatenation of each member in turn. Boolean members are encoded as a byte with the value 0 for false and 1 for true. Struct members are encoded recursively.

### Texts
Texts are encoded as follows. First the magic U32 0xD812C8F5 is encoded. Then the length of the text in bytes is encoded as a U48. Then then the UTF8 bytes of the text are stored. Finally a terminal zero byte is stored.

### Bytes
Binary blobs are encoded as follows. First the magic U32 0xDCDBBE10 is encoded. Then the length of the blob is encoded as a U48. Then the bytes of the blob are stored.

### Lists
Lists are encoded as follows. First the magic U32 0x3400BB46 is encoded. Then the number of elements in the list is encoded as a U48. Next the individual elements are encoded in order.

* I8, U16, U32, U64, I8, I16, I16, Int6, F32 and F64 are encoded as basic types. For the floating point types NAN specifies that we do not have a value. For the integer types we always have a value.
* Texts, Bytes, Lists and tables are encoded as the U48 offset of their magic word in the message. The special offset zero indicates that we do not have a value.
* Bools are packed into bytes. Such that the value of the i'th bool can be found as (bytes[i>>3] >> (i & 7)) & 1.
* Enum values are encoded as U8. The special value 255 indicates that we do not have a value.
* Unions are encoded are encoded as a U16 type followed by a U48 offset.

### Tables
Tables are encoded as follows. First the magic U32 id of the table is encoded. Then the length of the non variable length part of the table is encoded as a U48. Next the members of the table are encoded in turn:

* Booleans: The next free bit (low to high) of the last bool byte is used to store the boolean value. If there are no free bits in the last bool byte.  A new bool byte is appended and the least significant bit of this byte is used.
* Bools and Struct: If marked as optional a boolean is encoded to represent if we have a value or not. Next the integer or struct is encoded.
* Floats: The float is encoded as a basic type. If it is marked optional NAN is used to signal that it has no value.
* Bytes, Texts, list and tables: Are encoded as a U48 offset of the magic of object in the message.  A zero offset denotes that there is no value. If the Bytes, Texts, list or table is marked as inplace, instead of the offset, the length of the object is encoded, the object is then encoded without its magic and length immediatly after the table. That is at the location table.offset+table.length+8.
* Union: The choice of union member is encoded as a U16. Where zero indicates no member and other members are numbered as they appear in the specification from 1. Next the offset of the object is encoded as a U48. If the union is marked as inplace instead of the offset the length of the object is encoded and the content of the object is encoded without the magic and length immediatly after the table. That is at the location table.offset+table.length+8.


### Direct lists
Direct list are used to store lists of tabels. First the magic U32 0xE2C6CC05 is encoded. Then the number of elements
in the list are encoded as a U48. Then the magic of the stored tables are encoded as a U32. Then the size of each table is encoded as a U32.

Finally the individual table elements are encoded in order. This is done as described in the Tables section except that the MAGIC and size are skipped. They would be the same for each element, so they are encode once in the header.

### Message
Objects in a message can occur in arbitrary order.  A message starts with the magic U32 0xB5C0C4B3, followed by a U48 containing the offset of the root table within the message.
