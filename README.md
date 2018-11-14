# scalgoproto
Flat array protocol buffers

# Binary encoding
The following section describes the binary encoding used by scalgo proto.

### Basic types
The integer types UInt8, UInt16, UInt32, UInt64, Int8, Int16, Int16 and Int64, are encoded in little endian, two's complement without padding (as they would be in a packed struct on X64).
The floating point types Float32 and Float64 are encoded using IEEE 754 in little endian without padding (as they would be in a packed struct on X64).

### Structs
Structs are encoded as the concatenation of each member in turn. Boolean members are encoded as a byte with the value 0 for false and 1 for true. Struct members are encoded recursivily.

### Texts
Texts are encoded as follows. First the magic UInt32 0xD812C8F5 is encoded. Then the length of the text in bytes is encoded as a UInt32. Then then the UTF8 bytes of the text are stored. Finally a terminal zero byte is stored.

### Bytes
Binary blobs are encoded as follows. First the magic UInt32 0xDCDBBE10 is encoded. Then the length of the blob is encoded as a UInt32. Then the bytes of the blob are stored.

### Lists
TODO

### Tabels
Tables are encoded as follows. First the magic UInt32 id of the table is encoded. Then the length of the non variable length part of the table is encoded as a UInt32. Next the members of the table are encoded in turn:

* Booleans: The next free bit (low to high) of the last bool byte is used to store the boolean value. If there are no free bits in the last bool byte.  A new bool byte is appended and the least significant bit of this byte is used.

* Integers and Struct: If marked as optional a boolean is encoded to represent if we have a value or not. Next the integer or struct is encoded.

* Floats: The float is encoded as a basic type. If it is marked optional NAN is used to signal that it has no value.

* Bytes, Texts, Lists and Tabels: Are encoded as a UInt32 offset to the object in the message.  A zero offset denotes that there is no value.

* VLList, VLBytes, VLText: TODO

* Union: TODO

### Message
Objects in a message can occur in arbitrary order.  A message starts with the magic UInt32 0xB5C0C4B3,  followed by a UInt32 containing the offset of the root table within the message.
