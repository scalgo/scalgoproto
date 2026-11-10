// Tests of the reader API beyond the cross language tests in test_base.ts:
// unaligned messages, all list types, typed arrays, cursors, text decoding and bigints.
import * as base from 'base'
import * as names from 'names'
import * as read from 'read'
import * as scalgoproto from 'scalgoproto'

import {readIn} from './test_base'

let failures = 0;

function check(cond: boolean, msg: string): void {
	if (cond) return;
	console.error('FAILED: ' + msg);
	failures++;
}

function eq(found: unknown, expected: unknown, msg: string): void {
	const ok = found === expected ||
			   (typeof found === 'number' && typeof expected === 'number' && isNaN(found) &&
				isNaN(expected));
	check(ok, msg + ': expected ' + String(expected) + ' found ' + String(found));
}

function throws(fn: () => unknown, msg: string): void {
	try {
		fn();
	} catch (e) {
		return;
	}
	check(false, msg + ': expected exception');
}

/** Place msg at byte offset shift in a new buffer */
function at(msg: Uint8Array, shift: number): Uint8Array {
	const ans = new Uint8Array(new ArrayBuffer(msg.length + shift + 8), shift, msg.length);
	ans.set(msg);
	return ans;
}

const N = 37;
const NW = 23;
const I8 = (i: number) => ((i * 53) & 0xFF) - 128;
const U8 = (i: number) => (i * 53) & 0xFF;
const I16 = (i: number) => ((i * 4099) & 0xFFFF) - 32768;
const U16 = (i: number) => (i * 4099) & 0xFFFF;
const U32 = (i: number) => (i * 2654435761) >>> 0;
const I32 = (i: number) => U32(i) - 2 ** 31;
const I64 = (i: number) => (i - 18) * 123456789012;
const U64 = (i: number) => i * 123456789012345;
const F32 = (i: number) => Math.fround(i * 1.25 - 7);
const F64 = (i: number) => i * Math.PI - 3;
const B = (i: number) => i % 3 == 0;
const E = (i: number) => i % 4 == 3 ? null : (i % 3) as read.Color;
const TEXT = (i: number) => i % 4 == 0 ? null : 'text' + i;
const NAME = (i: number) => i % 5 == 0 ? null : 'row æøå 😀 ' + i;

function build(): Uint8Array {
	const w = new scalgoproto.Writer();
	const root = w.constructTable(read.ListsOut);
	const i8 = root.addI8(N), u8 = root.addU8(N), i16 = root.addI16(N), u16 = root.addU16(N);
	const i32 = root.addI32(N), u32 = root.addU32(N), i64 = root.addI64(N),
		  u64 = root.addU64(N);
	const f32 = root.addF32(N), f64 = root.addF64(N), b = root.addB(N), e = root.addE(N);
	const v = root.addV(N), rows = root.addRows(N), texts = root.addTexts(N);
	const blobs = root.addBlobs(3);
	for (let i = 0; i < N; ++i) {
		i8.set(i, I8(i));
		u8.set(i, U8(i));
		i16.set(i, I16(i));
		u16.set(i, U16(i));
		i32.set(i, I32(i));
		u32.set(i, U32(i));
		i64.set(i, I64(i));
		u64.set(i, U64(i));
		f32.set(i, F32(i));
		f64.set(i, F64(i));
		b.set(i, B(i));
		const ev = E(i);
		if (ev !== null) e.set(i, ev);
		v.set(i, new read.Vertex(i * 1.5, -i * 2.5, Math.fround(i / 3)));
		const row = rows.get(i);
		row.x = i * 0.5;
		row.y = -i * 0.25;
		row.color = U32(i);
		row.id = U64(i);
		row.flag = i % 2 == 1;
		row.kind = (i % 3) as read.Color;
		const t = TEXT(i);
		if (t !== null) texts.set(i, t);
	}
	const wide = root.addWide(NW);
	for (let i = 0; i < NW; ++i) {
		const x = wide.get(i);
		x.a = i - 10;
		if (i % 3) x.b = i * 1000;
		if (i % 4) x.c = i % 8 == 1;
		x.d = i % 2 == 0;
		if (i % 5) x.e = (i % 3) as read.Color;
		if (i % 2) x.f = i / 4;
		x.g = (i - 11) * 1e10;
		if (i % 6) x.h = i * 3;
		x.s = new read.Outer(i * 7, new read.Vertex(i, -i, i / 2), (i % 3) as read.Color, i % 2 == 1);
		if (i % 4 == 0) x.os = new read.Vertex(i + 0.5, i - 0.5, i);
		if (i % 5) x.t = 'wide ' + i;
		if (i % 3 == 0) x.by = new Uint8Array([i, i + 1]);
		if (i % 2) {
			const l = x.addL(i % 4);
			for (let j = 0; j < i % 4; ++j) l.set(j, j + i);
		}
		if (i % 7 == 0) x.addM().x = i;
		if (i % 3 == 1) x.u.x = 'u' + i;
		else if (i % 3 == 2) x.u.addY(2).set(1, i);
	}
	const outer = root.addOuter(NW);
	for (let i = 0; i < NW; ++i)
		outer.set(i, new read.Outer(i - 5, new read.Vertex(i, -i, i / 2), (i % 3) as read.Color, i % 2 == 1));
	blobs.set(0, new Uint8Array([1, 2, 3]));
	blobs.set(2, new Uint8Array([]));
	return new Uint8Array(w.finalize(root));
}

/**
 * The TS writer does not encode non ascii text correctly, so patch utf-8 names into the
 * message: append text objects at the end and point the rows at them.
 */
function addNames(msg: Uint8Array): Uint8Array {
	const enc = new TextEncoder();
	const parts: Uint8Array[] = [msg];
	let size = msg.length;
	const offsets: number[] = [];
	for (let i = 0; i < N; ++i) {
		const name = NAME(i);
		if (name === null) {
			offsets.push(0);
			continue;
		}
		const t = enc.encode(name);
		const p = new Uint8Array(10 + t.length + 1);
		const dv = new DataView(p.buffer);
		dv.setUint32(0, scalgoproto.TEXT_MAGIC, true);
		dv.setUint32(4, t.length, true);
		p.set(t, 10);
		offsets.push(size);
		parts.push(p);
		size += p.length;
	}
	const ans = new Uint8Array(size);
	let o = 0;
	for (const p of parts) {
		ans.set(p, o);
		o += p.length;
	}
	const rows = new scalgoproto.Reader(ans).root(read.ListsIn).rows!;
	const dv = new DataView(ans.buffer);
	for (let i = 0; i < N; ++i) {
		const off = rows._off + i * rows._itemSize; // name is the first member
		dv.setUint32(off, offsets[i], true);
		dv.setUint16(off + 4, 0, true);
	}
	return ans;
}

function checkNumberList<A extends ArrayLike<number | bigint>>(
  name: string, l: scalgoproto.NumberListIn<A>| null, f: (i: number) => number,
  width: number, r: scalgoproto.Reader) {
	check(l !== null, name + ' present');
	if (l === null) return;
	eq(l.length, N, name + ' length');
	for (let i = 0; i < N; ++i) eq(l.get(i), f(i), name + ' get ' + i);
	const arr = l.toArray();
	for (let i = 0; i < N; ++i) eq(arr[i], f(i), name + ' toArray ' + i);
	let j = 0;
	for (const x of l) eq(x, f(j++), name + ' iterate ' + (j - 1));
	eq(j, N, name + ' iterate count');
	l.forEach((x, i) => eq(x, f(i), name + ' forEach ' + i));
	throws(() => l.get(N), name + ' get(N)');
	throws(() => l.get(-1), name + ' get(-1)');
	eq(l.bytes().length, N * width, name + ' bytes length');
	const ta = l.toTypedArray() as any;
	const aligned = (r.bytes.byteOffset + l._off) % width === 0;
	eq(ta.buffer === r.bytes.buffer, aligned, name + ' typed array is a view iff aligned');
	eq(ta.length, N, name + ' typed length');
	for (let i = 0; i < N; ++i) {
		const exp = typeof ta[i] === 'bigint' ? BigInt(f(i)) : f(i);
		eq(ta[i], exp, name + ' typed ' + i);
	}
	// copyTo into a reused destination, at an element offset
	const dst = new ta.constructor(N + 3);
	const zero = typeof ta[0] === 'bigint' ? 0n : 0;
	check(l.copyTo(dst, 2) === dst, name + ' copyTo returns dst');
	eq(dst[0], zero, name + ' copyTo before offset');
	eq(dst[1], zero, name + ' copyTo before offset');
	for (let i = 0; i < N; ++i) eq(dst[i + 2], ta[i], name + ' copyTo ' + i);
	eq(dst[N + 2], zero, name + ' copyTo after end');
	l.copyTo(dst);
	eq(dst[0], ta[0], name + ' copyTo default offset');
	throws(() => l.copyTo(dst, 4), name + ' copyTo too small');
	throws(() => l.copyTo(dst, 0.5), name + ' copyTo fractional offset');
	throws(() => l.copyTo(dst, -1), name + ' copyTo negative offset');
	throws(() => l.copyTo(new ta.constructor(N - 1)), name + ' copyTo short destination');
	const tc = l.toTypedArray(true) as any;
	check(tc.buffer !== r.bytes.buffer, name + ' copy is a copy');
	eq(tc.length, N, name + ' copy length');
}

function sameBytes(a: Uint8Array | null, b: Uint8Array | null): boolean {
	if (a === null || b === null) return a === b;
	return a.length === b.length && a.every((x, i) => x === b[i]);
}

function checkColumns(root: read.ListsIn, s: string): void {
	// Every column must agree with the getters of the rows
	const rows = root.rows!;
	const rc = rows.toColumns();
	for (let i = 0; i < N; ++i) {
		const row = rows.get(i);
		eq(rc.name[i], row.name, 'rows column name' + s);
		eq(rc.x[i], row.x, 'rows column x' + s);
		eq(rc.y[i], row.y, 'rows column y' + s);
		eq(rc.color[i], row.color, 'rows column color' + s);
		eq(rc.id[i], row.id, 'rows column id' + s);
		eq(rc.flag[i], row.flag ? 1 : 0, 'rows column flag' + s);
		eq(rc.kind[i], row.kind ?? 255, 'rows column kind' + s);
	}

	const wide = root.wide!;
	const wc = wide.toColumns();
	eq(wc.a.length, NW, 'wide columns length' + s);
	for (let i = 0; i < NW; ++i) {
		const w = wide.get(i);
		const m = 'wide column ';
		eq(wc.a[i], w.a, m + 'a' + s);
		eq(wc.b_has[i], w.b === null ? 0 : 1, m + 'b_has' + s);
		eq(wc.b[i], w.b ?? 0, m + 'b' + s);
		eq(wc.c_has[i], w.c === null ? 0 : 1, m + 'c_has' + s);
		eq(wc.c[i], w.c ? 1 : 0, m + 'c' + s);
		eq(wc.d[i], w.d ? 1 : 0, m + 'd' + s);
		eq(wc.e[i], w.e ?? 255, m + 'e' + s);
		eq(wc.f[i], w.f ?? NaN, m + 'f' + s);
		eq(wc.g[i], w.g, m + 'g' + s);
		eq(wc.h[i], w.h, m + 'h' + s);
		eq(wc.s_id[i], w.s.id, m + 's_id' + s);
		eq(wc.s_v_x[i], w.s.v.x, m + 's_v_x' + s);
		eq(wc.s_v_y[i], w.s.v.y, m + 's_v_y' + s);
		eq(wc.s_v_z[i], w.s.v.z, m + 's_v_z' + s);
		eq(wc.s_c[i], w.s.c, m + 's_c' + s);
		eq(wc.s_b[i], w.s.b ? 1 : 0, m + 's_b' + s);
		eq(wc.os_has[i], w.os === null ? 0 : 1, m + 'os_has' + s);
		eq(wc.os_x[i], w.os?.x ?? 0, m + 'os_x' + s);
		eq(wc.os_y[i], w.os?.y ?? 0, m + 'os_y' + s);
		eq(wc.os_z[i], w.os?.z ?? 0, m + 'os_z' + s);
		eq(wc.t[i], w.t, m + 't' + s);
		check(sameBytes(wc.by[i], w.by), m + 'by' + s);
		eq(wc.l[i]?.length ?? -1, w.l?.length ?? -1, m + 'l' + s);
		eq(wc.m[i]?.x ?? -1, w.m?.x ?? -1, m + 'm' + s);
		eq(wc.u[i].type, w.u.type, m + 'u' + s);
		eq(wc.u[i].x, w.u.x, m + 'u.x' + s);
	}
	// The values themselves, not only agreement with the getters
	eq(wc.b[4], 4000, 'wide b value' + s);
	eq(wc.b_has[3], 0, 'wide b unset' + s);
	eq(wc.e[5], read.Color.blue, 'wide e default' + s); // The writer stores the default
	eq(wc.h[6], 7, 'wide h default' + s);
	eq(wc.os_x[4], 4.5, 'wide os value' + s);

	const outer = root.outer!;
	const oc = outer.toColumns();
	for (let i = 0; i < NW; ++i) {
		const o = outer.get(i);
		eq(oc.id[i], o.id, 'outer id' + s);
		eq(oc.v_x[i], o.v.x, 'outer v_x' + s);
		eq(oc.v_y[i], o.v.y, 'outer v_y' + s);
		eq(oc.v_z[i], o.v.z, 'outer v_z' + s);
		eq(oc.c[i], o.c, 'outer c' + s);
		eq(oc.b[i], o.b ? 1 : 0, 'outer b' + s);
	}
	eq(root.v!.toColumns().z[3], Math.fround(1), 'vertex columns' + s);
}

function testLists(msg: Uint8Array, shift: number): void {
	const r = new scalgoproto.Reader(at(msg, shift));
	const root = r.root(read.ListsIn);
	const s = ' (shift ' + shift + ')';
	checkNumberList('i8' + s, root.i8, I8, 1, r);
	checkNumberList('u8' + s, root.u8, U8, 1, r);
	checkNumberList('i16' + s, root.i16, I16, 2, r);
	checkNumberList('u16' + s, root.u16, U16, 2, r);
	checkNumberList('i32' + s, root.i32, I32, 4, r);
	checkNumberList('u32' + s, root.u32, U32, 4, r);
	checkNumberList('i64' + s, root.i64, I64, 8, r);
	checkNumberList('u64' + s, root.u64, U64, 8, r);
	checkNumberList('f32' + s, root.f32, F32, 4, r);
	checkNumberList('f64' + s, root.f64, F64, 8, r);

	const i64 = root.i64!, u64 = root.u64!;
	for (let i = 0; i < N; ++i) {
		eq(i64.getBigInt(i), BigInt(I64(i)), 'i64 bigint' + s);
		eq(u64.getBigInt(i), BigInt(U64(i)), 'u64 bigint' + s);
	}

	const b = root.b!;
	eq(b.length, N, 'bool length' + s);
	eq(b.bytes().length, (N + 7) >> 3, 'bool bytes' + s);
	const bu = b.toUint8Array();
	for (let i = 0; i < N; ++i) {
		eq(b.get(i), B(i), 'bool get' + s);
		eq(bu[i], B(i) ? 1 : 0, 'bool toUint8Array' + s);
	}
	throws(() => b.get(N), 'bool get(N)');

	const e = root.e!;
	const et = e.toTypedArray();
	const ec = e.copyTo(new Uint8Array(N + 1), 1);
	for (let i = 0; i < N; ++i) eq(ec[i + 1], et[i], 'enum copyTo' + s);
	const ea = e.toArray();
	for (let i = 0; i < N; ++i) eq(ea[i], E(i), 'enum toArray' + s);
	for (let i = 0; i < N; ++i) {
		eq(e.get(i), E(i), 'enum get' + s);
		eq(et[i], E(i) === null ? 255 : E(i), 'enum raw' + s);
	}

	const v = root.v!;
	eq(v.length, N, 'struct length' + s);
	eq(v.bytes().length, N * read.Vertex._WIDTH, 'struct bytes' + s);
	for (let i = 0; i < N; ++i) {
		const x = v.get(i);
		eq(x.x, i * 1.5, 'struct x' + s);
		eq(x.y, -i * 2.5, 'struct y' + s);
		eq(x.z, Math.fround(i / 3), 'struct z' + s);
	}
	throws(() => v.get(N), 'struct get(N)');

	const rows = root.rows!;
	eq(rows.length, N, 'direct length' + s);
	const checkRow = (row: read.RowIn, i: number, what: string) => {
		eq(row.name, NAME(i), what + ' name' + s);
		eq(row.x, i * 0.5, what + ' x' + s);
		eq(row.y, -i * 0.25, what + ' y' + s);
		eq(row.color, U32(i), what + ' color' + s);
		eq(row.id, U64(i), what + ' id' + s);
		eq(row.id_bigint, BigInt(U64(i)), what + ' idBigInt' + s);
		eq(row.flag, i % 2 == 1, what + ' flag' + s);
		eq(row.kind, i % 3, what + ' kind' + s);
	};
	for (let i = 0; i < N; ++i) checkRow(rows.get(i), i, 'direct get');
	rows.forEach((row, i) => checkRow(row, i, 'direct forEach'));
	const ra = rows.toArray();
	eq(ra.length, N, 'direct toArray length');
	for (let i = 0; i < N; ++i) checkRow(ra[i], i, 'direct toArray');
	const va = v.toArray();
	for (let i = 0; i < N; ++i) eq(va[i].x, i * 1.5, 'struct toArray' + s);
	eq(b.toArray().filter(x => x).length, bu.reduce((a, x) => a + x, 0), 'bool toArray' + s);
	const c = rows.cursor();
	for (let i = 0; i < N; ++i) checkRow(rows.seek(c, i), i, 'direct cursor');
	let j = 0;
	for (const row of rows) checkRow(row, j++, 'direct iterate');
	throws(() => rows.get(N), 'direct get(N)');
	throws(() => rows.seek(c, N), 'direct seek(N)');
	eq(rows.bytes().length, N * rows._itemSize, 'direct bytes');

	checkColumns(root, s);

	const texts = root.texts!;
	texts.forEach((t, i) => eq(t, TEXT(i), 'text forEach' + s));
	for (let i = 0; i < N; ++i) eq(texts.get(i), TEXT(i), 'text list' + s);

	const blobs = root.blobs!;
	eq(blobs.length, 3, 'bytes list length' + s);
	const b0 = blobs.get(0)!;
	eq(b0.length, 3, 'bytes list 0 length' + s);
	eq(b0.buffer, r.bytes.buffer, 'bytes are a view' + s);
	eq(b0[0] + b0[1] * 10 + b0[2] * 100, 321, 'bytes list 0' + s);
	eq(blobs.get(1), null, 'bytes list 1' + s);
	eq(blobs.get(2)!.length, 0, 'bytes list 2' + s);
}

function testText(): void {
	const strings = [
		'',
		'a',
		'hello world',
		'æøå ÆØÅ',
		'€uro ∑',
		'😀 emoji 🌍',
		'x'.repeat(24), // At the boundary between the JS loop and TextDecoder
		'x'.repeat(25),
		'æ'.repeat(12), // 24 bytes
		'æøå'.repeat(4) + 'a', // 25 bytes
		'Vandløb og søer i Danmark 😀 '.repeat(5),
		'ascii only and long enough to use the TextDecoder path for sure',
		'\u0000\u007f\u0080\u07ff\u0800\uffff',
	];
	const enc = new TextEncoder();
	for (const str of strings) {
		const bytes = enc.encode(str);
		for (const shift of [0, 3]) {
			const buf = new Uint8Array(bytes.length + shift);
			buf.set(bytes, shift);
			const r = new scalgoproto.Reader(buf);
			eq(r._text(shift, bytes.length), str, 'text ' + JSON.stringify(str));
		}
	}
}

function testInputs(): void {
	const msg = new Uint8Array(readIn('test/simple.bin'));
	const inputs: [string, ArrayBuffer | ArrayBufferView][] = [
		['ArrayBuffer', msg.buffer],
		['Uint8Array', msg],
		['shifted Uint8Array', at(msg, 5)],
		['DataView', new DataView(at(msg, 3).buffer, 3, msg.length)],
		['Buffer', Buffer.from(at(msg, 1))],
	];
	for (const [name, data] of inputs) {
		const s = new scalgoproto.Reader(data).root(base.SimpleIn);
		eq(s.u64, 5465778, name + ' u64');
		eq(s.u64_bigint, 5465778n, name + ' u64BigInt');
		eq(s.i64_bigint, 5465779n, name + ' i64BigInt');
		eq(s.oi64_bigint, 5465729n, name + ' oi64BigInt');
		eq(s.ni64_bigint, null, name + ' ni64BigInt');
		eq(s.s.i64, -11, name + ' struct i64');
	}
	const d = new scalgoproto.Reader(readIn('test/simple_default.bin')).root(base.SimpleIn);
	eq(d.u64_bigint, 5n, 'default u64BigInt');
	eq(d.i64_bigint, 9n, 'default i64BigInt');
	eq(d.ou64_bigint, null, 'default ou64BigInt');
	throws(() => new scalgoproto.Reader(readIn('test/simple.bin')).root(base.ComplexIn),
		   'wrong root magic');
}

function testBigIntExact(): void {
	// Values above 2^53 are only exact as bigints
	const msg = build();
	const r = new scalgoproto.Reader(msg);
	const u64 = r.root(read.ListsIn).u64!;
	const big = 2n ** 63n + 12345n;
	new DataView(msg.buffer, msg.byteOffset).setBigUint64(u64._off + 8, big, true);
	eq(u64.getBigInt(1), big, 'u64 exact bigint');
	eq(u64.toTypedArray(true)[1], big, 'u64 exact typed');
}

function testOldItems(): void {
	{
		// Columns of members missing from the old items get the default
		const s = new scalgoproto.Reader(readIn('test/extend2.bin')).root(base.Gen3In);
		const c = s.directMemberList!.toColumns();
		eq(c.id.length, 4, 'old columns length');
		for (let i = 0; i < 4; ++i) {
			eq(c.id[i], 100 + i, 'old columns id');
			eq(c.cookie[i], 37, 'old columns default');
		}
		// Empty direct list
		const w = new scalgoproto.Writer();
		const root = w.constructTable(read.ListsOut);
		root.addRows(0);
		const e = new scalgoproto.Reader(w.finalize(root)).root(read.ListsIn).rows!.toColumns();
		eq(e.x.length, 0, 'empty columns');
		eq(e.name.length, 0, 'empty text columns');
	}
	// extend2.bin is written with Member items; read with the larger MemberV2
	const s = new scalgoproto.Reader(readIn('test/extend2.bin')).root(base.Gen3In);
	const l = s.directMemberList!;
	eq(l.length, 4, 'old direct list length');
	const c = l.cursor();
	for (let i = 0; i < 4; ++i) {
		eq(l.get(i).id, 100 + i, 'old direct id');
		eq(l.get(i).cookie, 37, 'old direct default');
		eq(l.seek(c, i).id, 100 + i, 'old direct cursor id');
		eq(c.cookie, 37, 'old direct cursor default');
	}
}

function testIndexChecks(): void {
	const r = new scalgoproto.Reader(build());
	const root = r.root(read.ListsIn);
	const lists: [string, {get(i: number): unknown, length: number}][] = [
		['u16', root.u16!], ['f64', root.f64!], ['bool', root.b!], ['enum', root.e!],
		['text', root.texts!], ['struct', root.v!], ['direct', root.rows!],
		['bytes', root.blobs!],
	];
	for (const [name, l] of lists) {
		for (const i of [0.5, 1.5, NaN, -1, -0.5, l.length, 2 ** 32, 2 ** 32 + 1, Infinity])
			throws(() => l.get(i), name + ' get(' + i + ')');
		l.get(0);
		l.get(l.length - 1);
	}
	const rows = root.rows!;
	const c = rows.cursor();
	for (const i of [0.5, NaN, -1, 2 ** 32]) throws(() => rows.seek(c, i), 'seek(' + i + ')');
	// A one element bool list must not accept 2^32
	const w = new scalgoproto.Writer();
	const lr = w.constructTable(read.ListsOut);
	lr.addB(1).set(0, true);
	const b = new scalgoproto.Reader(w.finalize(lr)).root(read.ListsIn).b!;
	eq(b.get(0), true, 'one bool');
	throws(() => b.get(2 ** 32), 'one bool get(2^32)');
}

function testTextEdgeCases(): void {
	const enc = new TextEncoder();
	// A leading byte order mark is part of the text, for short and long strings
	for (const str of ['\uFEFF', '\uFEFFa', '\uFEFF' + 'a'.repeat(30), '\uFEFF' + 'a'.repeat(100)]) {
		const bytes = enc.encode(str);
		eq(new scalgoproto.Reader(bytes)._text(0, bytes.length), str, 'BOM ' + str.length);
	}
	// Text extending past the end of the message is an error, for short and long strings
	for (const len of [5, 24, 25, 40]) {
		const bytes = enc.encode('x'.repeat(len));
		const r = new scalgoproto.Reader(bytes.subarray(0, len - 1));
		throws(() => r._text(0, len), 'truncated text ' + len);
	}
	// A multi byte sequence cut off by the end of the text is not completed with the
	// bytes after it
	const bytes = enc.encode('aæb€c😀');
	const r = new scalgoproto.Reader(bytes);
	eq(r._text(0, 2), 'a\uFFFD', 'cut 2 byte sequence');
	eq(r._text(3, 2), 'b\uFFFD', 'cut 3 byte sequence');
	eq(r._text(7, 3), 'c\uFFFD', 'cut 4 byte sequence');
}

function testNames(): void {
	// Accessors must not collide with members, and schema names must not shadow
	// built in types
	const w = new scalgoproto.Writer();
	const root = w.constructTable(names.NamesOut);
	root.amount = 2 ** 40 + 7;
	root.amountBigInt = 42;
	root.d = new names.DataView(7);
	root.b = new Uint8Array([4, 5]);
	const s = new scalgoproto.Reader(w.finalize(root)).root(names.NamesIn);
	eq(s.amount, 2 ** 40 + 7, 'names amount');
	eq(s.amount_bigint, 2n ** 40n + 7n, 'names amount_bigint');
	eq(s.amountBigInt, 42, 'names amountBigInt');
	eq(s.d.x, 7, 'names DataView struct');
	eq(s.b!.length, 2, 'names bytes');
	eq(s.o, null, 'names optional float');
}

function testMalformedText(): void {
	// Malformed utf-8 must decode exactly like TextDecoder, for short texts (decoded in
	// JS) and long ones
	const td = new TextDecoder('utf-8', {ignoreBOM: true});
	const cases = [
		[0xC3, 0x41], // Missing continuation byte
		[0xE2, 0x41, 0x42],
		[0xC0, 0x80], // Overlong
		[0xE0, 0x80, 0x80],
		[0xF0, 0x80, 0x80, 0x80],
		[0xF8, 0x80, 0x80, 0x80], // Invalid lead byte
		[0xFF],
		[0xF4, 0x90, 0x80, 0x80], // Above U+10FFFF
		[0xED, 0xA0, 0x80], // Surrogate
		[0x80], // Lone continuation byte
		[0xC3], // Cut off
		[0xE2, 0x82],
		[0xF0, 0x9F, 0x98],
	];
	for (const c of cases) {
		for (const pad of [0, 30]) {
			const bytes = new Uint8Array([...c, ...new Array(pad).fill(0x61)]);
			eq(new scalgoproto.Reader(bytes)._text(0, bytes.length), td.decode(bytes),
			   'malformed ' + c.map(x => x.toString(16)).join(' ') + ' padded ' + pad);
		}
	}
	// Random bytes, mostly malformed, at all lengths around the switch to TextDecoder
	let seed = 1;
	const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF) >> 16;
	const buf = new Uint8Array(64);
	const r = new scalgoproto.Reader(buf);
	let bad = 0;
	for (let k = 0; k < 100000; ++k) {
		const n = k % 40, o = k % 7;
		for (let i = 0; i < n; ++i) {
			const x = rnd() & 0xFF;
			buf[o + i] = k & 1 ? x | 0x80 : x; // Odd rounds: only non ascii bytes
		}
		if (r._text(o, n) !== td.decode(buf.subarray(o, o + n))) ++bad;
	}
	eq(bad, 0, 'random bytes decoded like TextDecoder');
}

function testShared(): void {
	// Messages in shared memory are not supported
	const sab = new SharedArrayBuffer(16);
	throws(() => new scalgoproto.Reader(sab as any), 'SharedArrayBuffer');
	throws(() => new scalgoproto.Reader(new Uint8Array(sab)), 'view on a SharedArrayBuffer');
}

const msg = addNames(build());
testIndexChecks();
testTextEdgeCases();
testNames();
for (let shift = 0; shift < 8; ++shift) testLists(msg, shift);
testText();
testMalformedText();
testShared();
testInputs();
testBigIntExact();
testOldItems();

if (failures) {
	console.error(failures + ' checks failed');
	process.exit(1);
}
