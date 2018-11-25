The following describes the binary encoding used by scalgoproto.

### Basic types
The integer types UInt8, UInt16, UInt32, UInt64, Int8, Int16, Int16 and Int64, are encoded in little endian, two's complement without padding (as they would be in a packed struct on X64).
The floating point types Float32 and Float64 are encoded using IEEE 754 in little endian without padding (as they would be in a packed struct on X64).

### Structs
Structs are encoded as the concatenation of each member in turn. Boolean members are encoded as a byte with the value 0 for false and 1 for true. Struct members are encoded recursively.

### Texts
Texts are encoded as follows. First the magic UInt32 0xD812C8F5 is encoded. Then the length of the text in bytes is encoded as a UInt32. Then then the UTF8 bytes of the text are stored. Finally a terminal zero byte is stored.

### Bytes
Binary blobs are encoded as follows. First the magic UInt32 0xDCDBBE10 is encoded. Then the length of the blob is encoded as a UInt32. Then the bytes of the blob are stored.

### Lists
Lists are encoded as follows. First the magic UInt32 0x3400BB46 is encoded. Then the number of elements in the list is encoded as a UInt32. Next the individual elements are encoded in order.

* Int8, UInt16, UInt32, UInt64, Int8, Int16, Int16, Int6, Float32 and Float64 are encoded as basic types. For the floating point types NAN specifies that we do not have a value. For the integer types we always have a value.
* Texts, Bytes, Lists and tables are encoded as the UInt32 offset of their magic word in the message. The special offset zero indicates that we do not have a value.
* Bools are packed into bytes. Such that the value of the i'th bool can be found as (bytes[i>>3] >> (i & 7) & 1.
* Enum values are encoded as UInt8. The special value 255 indicates that we do not have a value.

### tables
Tables are encoded as follows. First the magic UInt32 id of the table is encoded. Then the length of the non variable length part of the table is encoded as a UInt32. Next the members of the table are encoded in turn:

* Booleans: The next free bit (low to high) of the last bool byte is used to store the boolean value. If there are no free bits in the last bool byte.  A new bool byte is appended and the least significant bit of this byte is used.
* Bools and Struct: If marked as optional a boolean is encoded to represent if we have a value or not. Next the integer or struct is encoded.
* Floats: The float is encoded as a basic type. If it is marked optional NAN is used to signal that it has no value.
* Bytes, Texts, Lists and tables: Are encoded as a UInt32 offset of the magic of object in the message.  A zero offset denotes that there is no value.
* VLList, VLBytes, VLText: The length of the list, bytes or text is encoded as a UInt32, the special length 0 indicates that we have no value. The content is encoded as Lists, Bytes and Text but without magic and length immediately after the table. That is at the location table.offset+table.length+8.
* Union: The choice of union member is encoded as a UInt16. Where zero indicates no member and other members are numbered as they appear in the specification from 1. Next the length of the member is encoded as a UInt32. The content of the member is encoded as a Table, List, Bytes or Text but without the magic and length immediately after the table. That is at the location table.offset+table.length+8.

### Message
Objects in a message can occur in arbitrary order.  A message starts with the magic UInt32 0xB5C0C4B3, followed by a UInt32 containing the offset of the root table within the message.
