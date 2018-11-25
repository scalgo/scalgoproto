# Cross compatibility

It is possible to make modifications to a schema such that messages written with the new schema can be read using the old schema and vise versa.
This is supported if and only if the modifications are in the list below:

* Add a new member to a table

    You are allowed to add a new member to the bottom an existing table. 
    Reading a new message with the old schema will ignore the member. 
    Reading an old message with a new schema will give the member its default value. 
    For optional members the "has" property will be false.

* Add a new member to a union

    You are allowed to add a new member to the bottom of an existing union.
    Reading a new message with the old schema the "has" property of the union will be false if the new member is used, and the "isUnknown" property will be true.
    Reading an old message with a new schema will give the same result as before.

* Add a new member to an enum

    You are allowed to add a new member to the bottom of an existing enum.
    Reading a new message with the old schema the "has" property of the enum will be false if the new member is used, and the "isUnknown" property will be true.
    Reading an old message with a new schema will give the same result as before.

* Change any name

    You may change any name. Names are not used in the binary coding, only the position and type of the members

* Reorder top level elements

    You may reorder structs, tabels, enums and unions in the top level of a schema. The order is not used in the binary coding.

* Add new table, struct, enum or union

    You are allowed to add a new table, struct, enum or union to a schema. This does not affect the encoding of existing items.

* Toggle the optional flag on Float32 and Float64

    For float 32 and float 64 you may add or remove the optional flag. For Float32 and Float64 is optional is encoded as NaN. 
    So removing an optional flag on a float will case a unset float to be read as NaN.
    Adding an optional flag on a float will case it to be read as unset if it happened to have the value NaN.

Any other change to a schema **will break** cross compatibly. In paticular the following:
* Do **not** and a new member to a struct, not even at the bottom.
* Do **not** add a new member in the middle of a table, union or enum.
* Do **not** reorder members in structs, enums, tabels or unions.
* Do **not** change the type of any member in structs, enums, tabels or unions.
* Do **not** toggle the flag *optional* on any none float member.
* Do **not** toggle the flag *inplace* on any member.
* Do **not** change the *magic* on a table.

When making a breaking change to a table it is advised to change its *magic* number to error out early with a reasonable exception, when reading a new message with an old schema or vice versa.
