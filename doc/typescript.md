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

`Reader` accepts an `ArrayBuffer`, a `SharedArrayBuffer` or any typed array/`DataView`.
A typed array is read in place, also when it is a view into the middle of a larger
buffer. Nothing is decoded up front: every getter reads directly from the message.

For each table `T` the generated code contains:

* `TIn`: reader with a getter per member. Members that are absent (an older message
  with a shorter table) return their default value. Optional members, texts, bytes,
  tables and lists return `null` when not set. For 64 bit integers the getter returns a
  `number` (exact up to 2^53); a `xxx_bigint` getter returns the exact value (the
  underscore keeps it from colliding with member names, which cannot contain one).
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

A plain loop over `get(i)` is the fastest way to access elements. `forEach` and
`toArray()` are implemented separately for every kind of list, so they stay fast when
an application uses many kinds of lists, but the callback of `forEach` still costs
about a factor two. `for..of` is the slowest, especially in programs that iterate
many kinds of lists.
`get(i)` throws a `RangeError` unless `i` is an integer in `[0, length)`.
Lists cannot be indexed with `l[i]`.

Lists of numbers can be turned into typed arrays:

```ts
const idx: Uint32Array = mesh.indices!.toTypedArray();
const raw: Uint8Array = mesh.vertices!.bytes(); // e.g. for gl.bufferData
```

`toTypedArray()` returns a view of the message when the list data happens to be aligned
to the element size, and a copy otherwise (the format is packed, so lists are not
generally aligned). A typed array is not automatically faster than `get(i)`: a single
pass over a copied list costs about as much as a pass with `get(i)`. Use it when the
values are read several times, or must be passed on as a typed array (e.g. to WebGL).
Pass `true` to always get a copy, e.g. one that can be transferred to another thread
without transferring the whole message. `bytes()` is always a view.

When converting lists repeatedly, reuse the destination with `copyTo`:

```ts
const xs = new Float64Array(maxLength);
mesh.xs!.copyTo(xs);      // or copyTo(xs, offset) to place it at an element offset
```

Allocating a new large typed array is expensive (in a benchmark converting a 1M element
F64 list 20 times took 16 ms in V8 and 58 ms in SpiderMonkey with `toTypedArray()`,
versus 3 and 2 ms with a reused destination). `copyTo` throws if the destination is too
small.
I64/U64 lists return `BigInt64Array`/`BigUint64Array` and have `getBigInt(i)`.
`BoolListIn.toUint8Array()` unpacks the bits, and `EnumListIn.toTypedArray()` and
`copyTo()` return the raw values (255 means not set). Lists of structs and direct lists of tables also have
`bytes()`.

### Direct lists of tables

`get(i)` creates a small object per row. V8 usually optimizes this allocation away in
tight loops, so `get(i)` and a cursor are equally fast there. In SpiderMonkey, and when
the row escapes the loop, the cursor avoids an allocation per row:

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
  becomes columns `s_x` and `s_y`. The `_` cannot occur in schema names, so these never
  collide with members.
* Texts, bytes, lists, tables and unions in table rows become plain arrays of what the
  getters return.
* Rows written with an older version of the schema (with fewer members) get the default
  for the missing members.

`toColumns()` reads the list in a single pass and is as fast as the equivalent
hand-written loop with a cursor. The generated `T_Columns` interface describes the
result.

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
* **Fetch in the worker.** Given a URL, the worker fetches the message itself, so the
  bytes never pass through the main thread.
* **A worker only pays off with real work.** Sending a message to a worker and the
  result back costs a round trip. If the data is already in the form you need (e.g. F32
  vertices and U32 indices that go straight to `gl.bufferData(..., list.bytes(), ...)`),
  decoding on the main thread costs microseconds and a worker gains nothing. Use one
  when there is per element work: converting coordinates, triangulating, building
  render batches, decoding many strings, or many messages at once.

In a test in Firefox, fetching and decoding an 11 MB message with 200k rows into columns
took about 70 ms in a worker with the main thread staying responsive, while decoding it
on the main thread blocked it for 30-50 ms.

## Performance notes

* Reads go through a `DataView`, which handles the unaligned data of the packed
  format at full speed in both V8 and SpiderMonkey.
* Generated classes have no base class and declare (rather than define) their fields,
  so the speed does not depend on the compilation target or `useDefineForClassFields`.
* Strings of up to 24 bytes are decoded in JavaScript, longer strings with
  `TextDecoder`, which has a fixed cost per call. The best threshold differs between
  engines (about 16 to 24 bytes in V8, 32 to 48 in SpiderMonkey); 24 is a compromise.
* `test/bench_read.ts` is a benchmark of the reader.

## Testing

`python3 -m test` runs the tests of all languages. The TypeScript part needs node and
installs TypeScript and tsx in `test/` with pnpm (or npm) on first use. It:

* Generates code for `test/base.spr`, `complex2.spr`, `union.spr`, `read.spr` and
  `names.spr`, and type checks the runtime, the generated code and the tests with `tsc`.
* Runs the cross language tests in `test_base.ts` and `test_union.ts`: the writer must
  produce exactly the bytes of the `.bin` files shared with C++, Python and Rust, and
  the reader must read them. The reading tests are run a second time with the message
  placed at an odd byte offset in memory, to test unaligned reads.
* Runs `test_read.ts`, which tests the reader API at all 8 byte offsets: every list type,
  `get`, iteration, `forEach`, `toArray`, typed array views versus copies, `copyTo`,
  cursors, `toColumns` (compared column by column with the getters, including rows
  written with an older schema), invalid indices, text decoding edge cases (multi byte
  characters, byte order marks, texts cut off by the end of the message or of a
  character), bigints above 2^53, and the accepted input types.

`names.spr` contains names that would collide with generated accessors or shadow
built-in types (`struct DataView`, a member `amountBigInt` next to `amount: U64`); it
only has to compile.

To test the TypeScript part alone, in `test/` after one run of `python3 -m test`:

    ./node_modules/.bin/tsc -p .
    ./node_modules/.bin/tsx test_read.ts
    ./node_modules/.bin/tsx test_base.ts in test/simple.bin
    SP_SHIFT=3 ./node_modules/.bin/tsx test_base.ts in test/simple.bin

## Writing

```ts
const w = new scalgoproto.Writer();
const root = w.constructTable(MeshOut);
root.name = 'mesh';
const l = root.addIndices(3);
l[0] = 0; l[1] = 1; l[2] = 2;
const data: ArrayBuffer = w.finalize(root);
```

Note that the writer currently encodes non ASCII text incorrectly, and does not grow
its buffer enough for single writes larger than the current buffer.
