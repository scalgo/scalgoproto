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

### Performance notes

* Reads go through a `DataView`, which handles the unaligned data of the packed
  format at full speed in both V8 and SpiderMonkey.
* Generated classes have no base class and declare (rather than define) their fields,
  so the speed does not depend on the compilation target or `useDefineForClassFields`.
* Strings of up to 24 bytes are decoded in JavaScript, longer strings with
  `TextDecoder`, which has a fixed cost per call. The best threshold differs between
  engines (about 16 to 24 bytes in V8, 32 to 48 in SpiderMonkey); 24 is a compromise.
* Most of the speedup over the previous version is in list access. Reading fields of a
  table object you already have is only slightly faster than before, as it was already
  a direct read.
* `test/bench_read.ts` is a benchmark of the reader.

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
