# TypeScript

Generate code for a schema with

    python3 -m scalgoprotoc ts schema.spr output_dir

The generated file imports the runtime as `scalgoproto`, so map that module name to
`lib/ts/scalgoproto.ts` (e.g. with `paths` in tsconfig.json or an alias in the bundler).
The generated code needs ES2020 or later (it uses `bigint`).

## Reading

```ts
import * as scalgoproto from 'scalgoproto'
import {MeshIn} from './mesh'

const r = new scalgoproto.Reader(await (await fetch(url)).arrayBuffer());
const mesh = r.root(MeshIn);
console.log(mesh.name, mesh.vertices?.length);
```

`Reader` accepts an `ArrayBuffer` or any typed array/`DataView`; shared memory
(`SharedArrayBuffer`) is not supported. A typed array is read in place, also when it is
a view into the middle of a larger buffer. Nothing is decoded up front: every getter
reads directly from the message.

For each table `T` the generated code contains:

* `TIn`: reader with a getter per member. Members that are absent (an older message
  with a shorter table) return their default value. Optional members, texts, bytes,
  tables and lists return `null` when not set. For 64 bit integers the getter returns a
  `number` (exact up to 2^53); a `xxx_bigint` getter returns the exact value.
* `T_ListIn` and `T_DirectListIn`: lists of the table.

Unions get `UIn` with `type`, `isX` and `x` getters, and structs a class with a static
`_read`.

Bytes are returned as `Uint8Array` views of the message, not copies.

### Lists

All lists have `length`, `get(i)`, `forEach`, `toArray()` and are iterable.

```ts
const l = mesh.indices!;            // scalgoproto.Uint32ListIn
for (let i = 0; i < l.length; ++i) use(l.get(i));
```

A plain loop over `get(i)` is fastest; `forEach` is about half as fast, and `for..of`
slower still. `get(i)` throws a `RangeError` unless `i` is an integer in `[0, length)`.

Lists of numbers can be turned into typed arrays:

```ts
const idx: Uint32Array = mesh.indices!.toTypedArray();
const raw: Uint8Array = mesh.vertices!.bytes(); // e.g. for gl.bufferData
```

`toTypedArray()` returns a view of the message when the list data happens to be aligned
to the element size, and a copy otherwise (the format is packed, so lists are not
generally aligned). A typed array is not automatically faster than `get(i)`; use it
when the values are read several times, or must be passed on as a typed array (e.g. to
WebGL). Pass `true` to always get a copy, e.g. one that can be transferred to another
thread without transferring the whole message. `bytes()` is always a view.

Allocating large typed arrays is expensive, so when converting lists repeatedly, reuse
the destination with `copyTo` (it throws if the destination is too small):

```ts
const xs = new Float64Array(maxLength);
mesh.xs!.copyTo(xs);      // or copyTo(xs, offset) to place it at an element offset
```

I64/U64 lists return `BigInt64Array`/`BigUint64Array` and have `getBigInt(i)`.
`BoolListIn.toUint8Array()` unpacks the bits, and `EnumListIn.toTypedArray()` and
`copyTo()` return the raw values (255 means not set). Lists of structs and direct lists
of tables also have `bytes()`.

### Direct lists of tables

`get(i)` creates a small object per row. To avoid that, for example when rows are
passed to other functions, use a cursor:

```ts
const rows = root.rows!;
const c = rows.cursor();
for (let i = 0; i < rows.length; ++i) {
	rows.seek(c, i);
	sum += c.x;
}
```

### Columns

Direct lists of tables and lists of structs can be read into one array per field with
`toColumns()`:

```ts
const c = root.points!.toColumns();   // Point_Columns
for (let i = 0; i < c.x.length; ++i) draw(c.x[i], c.y[i], c.name[i]);
```

* Number members become typed arrays of their type. I64 and U64 become `Float64Array`
  (exact up to 2^53, like the getters).
* Bools become a `Uint8Array` of 0 and 1, enums a `Uint8Array` of the raw values (255
  means not set).
* Optional members get an extra `x_has` column (`Uint8Array`) telling whether each row
  has a value. Optional floats use NaN, like the getters.
* Struct members are flattened: a member `s` of a struct type with members `x` and `y`
  becomes columns `s_x` and `s_y`.
* Texts, bytes, lists, tables and unions in table rows become plain arrays of what the
  getters return.
* Rows written with an older version of the schema (with fewer members) get the default
  for the missing members.

The generated `T_Columns` interface describes the result.

## Decoding in workers

The library has no worker code of its own, but is easy to use from a worker: decode in
the worker, turn the parts you need into plain data, and post them back with their
buffers transferred, so they are not copied.

```ts
// decode.worker.ts
import {Reader} from 'scalgoproto'
import {TileIn} from './generated/tile'

self.onmessage = async (e: MessageEvent<{id: number, url: string}>) => {
	const {id, url} = e.data;
	const buf = await (await fetch(url)).arrayBuffer();
	const tile = new Reader(buf).root(TileIn);
	const features = tile.features!.toColumns();       // typed arrays and plain arrays
	const indices = tile.indices!.toTypedArray(true);   // a copy, see below
	self.postMessage({id, features, indices},
					 [features.x.buffer, features.y.buffer, indices.buffer]);
};
```

```ts
// main thread
const worker = new Worker(new URL('./decode.worker.ts', import.meta.url), {type: 'module'});
worker.onmessage = (e) => { /* match e.data.id to the request and use the arrays */ };
worker.postMessage({id: 1, url: '/tiles/3/4/2'});
```

Things to keep in mind:

* **Return plain data.** Reader objects (`TIn`, lists, unions) hold the reader and its
  `DataView`; posting them copies the whole message and they arrive without their
  methods. Return the values, or arrays from `toColumns`, `toTypedArray(true)`,
  `copyTo` or `bytes()`.
* **Transfer only what you mean to.** `toTypedArray()` without `true` and `bytes()` may
  return views of the message buffer, so transferring their buffer transfers the whole
  message. That is fine if the message is not needed any more in the worker; otherwise
  use `toTypedArray(true)` or `copyTo` to get arrays of their own.
* **Fetch in the worker,** so the bytes never pass through the main thread.
* **A worker only pays off with real work.** If the data is already in the form you
  need (e.g. F32 vertices and U32 indices that go straight to
  `gl.bufferData(..., list.bytes(), ...)`), decoding on the main thread costs
  microseconds. Use a worker when there is per element work: converting coordinates,
  triangulating, building render batches, decoding many strings, or many messages at
  once.

## Writing

```ts
import * as scalgoproto from 'scalgoproto'
import {MeshOut, Vertex} from './mesh'

const w = new scalgoproto.Writer();
const mesh = w.constructTable(MeshOut);
mesh.name = 'mesh';
mesh.addIndices(new Uint32Array([0, 1, 2]));             // from values
const v = mesh.addVertices(3);                           // or by length
for (let i = 0; i < 3; ++i) v.set(i, new Vertex(i, 0, 0));
const message: Uint8Array = w.finalize(mesh);
```

A message is written into one buffer that grows as needed. Objects are written when
they are constructed, and members are stored in the table they belong to as you set
them.

For each table `T` the generated code contains `TOut`, with:

* A setter for each member. Optional members are set by setting them; members that are
  never set keep their default. 64 bit members also have a `xxx_bigint` setter for
  exact values. Enums can be set to `null` (no value).
* For texts and bytes, a setter taking a string (or bytes as a `Uint8Array` or
  `ArrayBuffer`), or a `TextOut`/`BytesOut` from `w.constructText`/`w.constructBytes`,
  which can then be stored in several places.
* For tables, `addX()` which constructs the table and returns its writer, and a setter
  taking a `TOut` constructed with `w.constructTable` (stored in several places), or a
  `TIn` read from another message, which is copied.
* For lists, `addX(lengthOrValues)` which constructs a list of the given length, or
  with the given values, and returns its writer, and a setter taking a list writer or a
  list read from another message, which is copied.
* For unions, a getter returning the union writer, with a setter or adder for each
  member like those of tables.
* `_copy(i: TIn)`, which copies a table read from another message. Texts are copied byte
  for byte.

Lists:

* All lists have `length`, `set(i, value)` and `setAll(values, offset = 0)`. For lists
  of texts, bytes, tables and enums, `null` means no value, also when replacing one.
* Number lists copy a typed array of their own element type (e.g. a `Float32Array`
  into an F32 list, or a `BigInt64Array` into an I64 list) in one go. Other arrays are
  converted element by element.
* Lists of tables have `add(i)`, which constructs a table, stores it at index i and
  returns its writer.
* Direct lists of tables and lists of unions have `get(i)`, which returns a writer for
  the i'th element. The tables of a direct list start out with their defaults.
  `set(i, value)` replaces the i'th element with a copy of a table or union read from
  another message.
* Lists can also be constructed on their own with `w.constructList(T_ListOut, n)` (or
  `w.constructInt32List(n)` etc. for basic types) and then stored in tables.

Tables, lists, texts and bytes can only be stored in the message of the writer that
constructed them; storing one from another writer throws.

Inplace members (texts, bytes, lists, tables and unions marked `inplace` in the schema)
are stored right after their table, so they must be added right after the table is
constructed, before anything else is written. The writer throws otherwise. Their
setters take a string, bytes, or a table or list read from another message, not a
`TextOut`, `BytesOut` or writer constructed separately.

`finalize(root)` writes the message header and returns the message as a `Uint8Array`
with a buffer of its own, of exactly the message's size. `finalizeView(root)` returns it
without copying, as a view of the writer's buffer; that buffer is larger than the
message, so use the view itself and not its `.buffer` (e.g. when transferring it to a
worker). The writer must not be used after either.

Writing is fastest when:

* Number lists are constructed from typed arrays of their element type, which are
  copied in one go.
* The writer starts with a capacity close to the size of the message,
  `new scalgoproto.Writer(expectedBytes)`, which avoids growing (allocating and copying)
  the buffer repeatedly.
* `finalizeView` is used instead of `finalize`, which copies the message (about 5 ms for
  an 8 MB message).

## Testing

`python3 -m test` runs the tests of all languages. The TypeScript part installs
TypeScript and tsx in `test/` with pnpm (or npm) on first use, generates code for the
test schemas, type checks everything with `tsc`, and runs:

* `test_base.ts` and `test_union.ts`: the cross language tests. The writer must produce
  exactly the bytes of the shared `.bin` files, and the reader must read them. They are
  also run with the message at an odd byte offset in memory, and with a writer starting
  with a 16 byte buffer.
* `test_read.ts`: the reader API.
* `test_write.ts`: the writer API.
* `names.spr` and `names2.spr` contain schema names that must not break the generated
  code; they only have to compile.

To run the TypeScript tests alone, in `test/` after one run of `python3 -m test`:

    ./node_modules/.bin/tsc -p .
    ./node_modules/.bin/tsx test_read.ts
    ./node_modules/.bin/tsx test_write.ts
    ./node_modules/.bin/tsx test_base.ts in test/simple.bin
    SP_SHIFT=3 ./node_modules/.bin/tsx test_base.ts in test/simple.bin
    SP_WRITER_CAPACITY=16 ./node_modules/.bin/tsx test_base.ts out test/simple.bin

`bench_read.ts` and `bench_write.ts` are benchmarks of the reader and writer:

    ./node_modules/.bin/tsx bench_read.ts
    ./node_modules/.bin/tsx bench_write.ts
