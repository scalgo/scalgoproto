# scalgoproto
Flat array protocol buffers

### Upgrade compatibility
It is possible to make changes to a schema such that a new message can be read by an old schema, and an old message can be read with a new schema. In general it is safe to add new members to the bottom of tables, enums and unions, but not in structs. When making a breaking change to a schema it is advised to change its *magic* number. For a full description of exactly what may be done see [doc/compatibility.md](doc/compatibility.md).


### Binary coding
A message is coded in a packed binary format, such that any member in any object in the message can be accessed in constant time with a small constant. Structs and basic types are coded like they would be in c on an X64 with #pragma pack(1). Objects such as tables, lists, bytes, and texts, are encoded with a 32bit magic number followed by their size followed by the encoding of their content. For a full description of the encoding see [doc/binary_coding.md](doc/binary_coding.md).
