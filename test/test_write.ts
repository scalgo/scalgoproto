// Tests of the writer API beyond the cross language tests in test_base.ts: text encoding,
// large messages, bulk list construction, bigints, copying, defaults and misuse.
import * as base from 'base'
import * as names from 'names'
import * as read from 'read'
import * as scalgoproto from 'scalgoproto'
import * as union from 'union'

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

function throws(fn: () => unknown, msg: string, pattern?: RegExp): void {
	try {
		fn();
	} catch (e: any) {
		if (pattern) check(pattern.test(String(e?.message)), msg + ': wrong error ' + e);
		return;
	}
	check(false, msg + ': expected exception');
}

function sameBytes(a: ArrayLike<number>, b: ArrayLike<number>): boolean {
	if (a.length !== b.length) return false;
	for (let i = 0; i < a.length; ++i)
		if (a[i] !== b[i]) return false;
	return true;
}

/** Writers with different initial capacities, to exercise buffer growth */
const capacities = [16, 1024, 1 << 20];

function testText(): void {
	const strings = [
		'',
		'ascii',
		'Vandløb ved Århus å, øst for søen',
		'€uro ∑ ∆',
		'😀 emoji 🌍 and more 😀😀😀',
		'\u0000\u007f\u0080\u07ff\u0800\uffff',
		'x'.repeat(1000) + 'æ',
		'æ' + 'x'.repeat(1000),
		'mixed ' + 'æøå😀'.repeat(300),
		// Around the switch from the JS encoder to TextEncoder (48 code units)
		'æ'.repeat(47),
		'æ'.repeat(48),
		'æ'.repeat(49),
		'a' + '😀'.repeat(24),
		'😀'.repeat(24) + 'æ',
		// Lone surrogates in both encoders
		'æ\ud800x',
		'æ\udc00',
		'æ' + '\ud83d'.repeat(60),
	];
	const enc = new TextEncoder();
	for (const cap of capacities) {
		for (const str of strings) {
			const w = new scalgoproto.Writer(cap);
			const root = w.constructTable(base.ComplexOut);
			root.text = str;
			const tl = root.addTextList(2);
			tl.set(1, str);
			const msg = w.finalize(root);
			const r = new scalgoproto.Reader(msg).root(base.ComplexIn);
			const what = ' ' + JSON.stringify(str.slice(0, 20)) + ' capacity ' + cap;
			// Lone surrogates can not be encoded and become U+FFFD
			const expected = new TextDecoder().decode(enc.encode(str));
			eq(r.text, expected, 'text round trip' + what);
			eq(r.textList!.get(1), expected, 'text list round trip' + what);
			eq(r.textList!.get(0), null, 'text list unset' + what);
			// The bytes must be exactly utf-8 followed by a zero byte
			const p = new DataView(msg.buffer, msg.byteOffset).getUint32(root._off + 12, true);
			const bytes = enc.encode(str);
			eq(new DataView(msg.buffer, msg.byteOffset).getUint32(p, true),
			   scalgoproto.TEXT_MAGIC, 'text magic' + what);
			eq(new DataView(msg.buffer, msg.byteOffset).getUint32(p + 4, true), bytes.length,
			   'text length' + what);
			check(sameBytes(msg.subarray(p + 10, p + 10 + bytes.length), bytes),
				  'text is utf-8' + what);
			eq(msg[p + 10 + bytes.length], 0, 'text is zero terminated' + what);
		}
	}
	// A lone surrogate is not valid utf-16; it is written as U+FFFD (as by TextEncoder,
	// which the byte comparison above checks against)
	const w = new scalgoproto.Writer();
	const root = w.constructTable(base.ComplexOut);
	root.text = 'a\ud800b';
	eq(new scalgoproto.Reader(w.finalize(root)).root(base.ComplexIn).text, 'a\ufffdb',
	   'lone surrogate');
	// Inplace text
	for (const cap of capacities) {
		const w2 = new scalgoproto.Writer(cap);
		const t = w2.constructTable(base.InplaceTextOut);
		t.t = 'inplace æøå 😀';
		t.id = 7;
		const ti = new scalgoproto.Reader(w2.finalize(t)).root(base.InplaceTextIn);
		eq(ti.t, 'inplace æøå 😀', 'inplace text capacity ' + cap);
		eq(ti.id, 7, 'inplace text id');
	}
}

function testLarge(): void {
	// Single writes much larger than the buffer
	const n = 1_000_000;
	const xs = new Float64Array(n);
	for (let i = 0; i < n; ++i) xs[i] = i * 0.25;
	const big = 'x'.repeat(3_000_000) + 'ø';
	for (const cap of capacities) {
		const w = new scalgoproto.Writer(cap);
		const root = w.constructTable(read.ListsOut);
		root.addF64(xs);
		root.addU8(3); // makes the following lists unaligned
		root.addF32(xs);
		root.addTexts([big]);
		root.addBlobs([new Uint8Array(2_000_000).fill(7)]);
		const r = new scalgoproto.Reader(w.finalize(root)).root(read.ListsIn);
		eq(r.f64!.length, n, 'large f64 length capacity ' + cap);
		eq(r.f64!.get(n - 1), (n - 1) * 0.25, 'large f64 value');
		eq(r.f32!.get(n - 1), Math.fround((n - 1) * 0.25), 'large f32 value');
		eq(r.texts!.get(0)!.length, big.length, 'large text');
		eq(r.texts!.get(0)!.slice(-1), 'ø', 'large text end');
		eq(r.blobs!.get(0)!.length, 2_000_000, 'large bytes');
		eq(r.blobs!.get(0)![1_999_999], 7, 'large bytes value');
	}
}

function testLists(): void {
	const w = new scalgoproto.Writer(16);
	const root = w.constructTable(read.ListsOut);
	// From plain arrays, typed arrays of the element type (copied in one go) and others
	root.addI8([-1, 2, -3]);
	root.addU8(new Uint8Array([1, 2, 255]));
	root.addI16(new Int16Array([-300, 0, 300]));
	root.addU16([1, 65535]);
	root.addI32(new Float64Array([-5, 6])); // Not the element type: converted one by one
	root.addU32(new Uint32Array([0, 4294967295]));
	root.addI64(new BigInt64Array([-(2n ** 62n), 2n ** 62n + 1n]));
	root.addU64([2 ** 52, 3]);
	const f32 = new Float32Array(10).map((_, i) => i / 3);
	root.addF32(f32.subarray(3)); // A view at an offset in its buffer
	root.addF64([Math.PI, -0, Infinity, NaN]);
	root.addB([true, false, true, true, false, false, false, false, true]);
	root.addE([read.Color.green, null, read.Color.blue]);
	root.addV([new read.Vertex(1, 2, 3), {x: 4, y: 5, z: 6}]);
	root.addTexts(['a', null, w.constructText('c')]);
	root.addBlobs([new Uint8Array([1]), null, new Uint8Array([2, 3]).buffer]);
	const outer = root.addOuter(2);
	outer.set(0, new read.Outer(1, new read.Vertex(1, 1, 1), read.Color.blue, true));
	const wide = root.addWide(3);
	wide.get(0).a = 5;
	const l = scalgoproto;
	void l;
	const r = new scalgoproto.Reader(w.finalize(root)).root(read.ListsIn);
	eq(r.i8!.toArray().join(), '-1,2,-3', 'i8 list');
	eq(r.u8!.toArray().join(), '1,2,255', 'u8 list');
	eq(r.i16!.toArray().join(), '-300,0,300', 'i16 list');
	eq(r.u16!.toArray().join(), '1,65535', 'u16 list');
	eq(r.i32!.toArray().join(), '-5,6', 'i32 list from other typed array');
	eq(r.u32!.toArray().join(), '0,4294967295', 'u32 list');
	eq(r.i64!.getBigInt(0), -(2n ** 62n), 'i64 list bigint');
	eq(r.i64!.getBigInt(1), 2n ** 62n + 1n, 'i64 list bigint exact');
	eq(r.u64!.get(0), 2 ** 52, 'u64 list');
	eq(r.f32!.length, 7, 'f32 list from view');
	eq(r.f32!.get(0), f32[3], 'f32 list from view value');
	eq(r.f64!.get(0), Math.PI, 'f64 list');
	check(Object.is(r.f64!.get(1), -0), 'f64 negative zero');
	eq(r.f64!.get(2), Infinity, 'f64 infinity');
	eq(r.f64!.get(3), NaN, 'f64 NaN');
	eq(r.b!.toArray().join(), 'true,false,true,true,false,false,false,false,true', 'bool list');
	eq(r.e!.toArray().join(), '1,,2', 'enum list with null');
	eq(r.v!.get(1).z, 6, 'struct list from plain objects');
	eq(r.texts!.toArray().join('|'), 'a||c', 'text list');
	eq(r.blobs!.get(1), null, 'bytes list null');
	eq(r.blobs!.get(2)!.length, 2, 'bytes list from ArrayBuffer');
	eq(r.outer!.get(0).v.x, 1, 'struct list set');
	eq(r.outer!.get(1).id, 0, 'struct list unset');

	// Direct list items that are not touched have the table defaults
	const wr = r.wide!;
	eq(wr.get(0).a, 5, 'direct list item');
	eq(wr.get(1).a, -3, 'direct list default a');
	eq(wr.get(1).e, read.Color.blue, 'direct list default e');
	eq(wr.get(2).h, 7, 'direct list default h');

	// setAll at an offset, and bounds
	const w2 = new scalgoproto.Writer();
	const r2 = w2.constructTable(read.ListsOut);
	const f = r2.addF64(5);
	f.setAll(new Float64Array([1, 2]), 3);
	f.setAll([7], 0);
	throws(() => f.setAll([1, 2], 4), 'setAll past the end');
	throws(() => f.setAll(new Float64Array(2), 4), 'typed setAll past the end');
	throws(() => f.setAll([1], -1), 'setAll negative offset');
	throws(() => f.set(5, 1), 'set past the end');
	throws(() => f.set(0.5, 1), 'set fractional index');
	throws(() => f.set(NaN, 1), 'set NaN index');
	throws(() => r2.addF64(-1), 'negative length');
	throws(() => r2.addF64(1.5), 'fractional length');
	const t = r2.addRows(2);
	throws(() => t.get(2), 'direct get past the end');
	const fr = new scalgoproto.Reader(w2.finalize(r2)).root(read.ListsIn).f64!;
	eq(fr.toArray().join(), '7,0,0,1,2', 'setAll at offset');
}

function testScalars(): void {
	const w = new scalgoproto.Writer();
	const s = w.constructTable(base.SimpleOut);
	s.i64 = -(2 ** 53) + 1;
	s.u64_bigint = 2n ** 64n - 1n;
	s.oi64_bigint = -(2n ** 63n);
	s.e = null;
	s.ne = base.MyEnum.b;
	const r = new scalgoproto.Reader(w.finalize(s)).root(base.SimpleIn);
	eq(r.i64, -(2 ** 53) + 1, 'large negative i64 number');
	eq(r.u64_bigint, 2n ** 64n - 1n, 'u64 bigint setter');
	eq(r.oi64_bigint, -(2n ** 63n), 'optional i64 bigint setter');
	check(r.oi64 !== null, 'bigint setter sets has bit');
	eq(r.e, null, 'enum set to null');
	eq(r.ne, base.MyEnum.b, 'enum');
	eq(r.ou64, null, 'unset optional');

	// Name collisions: amount_bigint next to a member called amountBigInt
	const w2 = new scalgoproto.Writer();
	const n = w2.constructTable(names.NamesOut);
	n.amount_bigint = 2n ** 60n + 1n;
	n.amountBigInt = 5;
	const nr = new scalgoproto.Reader(w2.finalize(n)).root(names.NamesIn);
	eq(nr.amount_bigint, 2n ** 60n + 1n, 'names bigint');
	eq(nr.amountBigInt, 5, 'names member');
}

function testCopy(): void {
	// Copy every kind of member and list from a message into a new one, at all
	// capacities, and compare what is read back
	const src = new scalgoproto.Writer();
	const root = src.constructTable(read.ListsOut);
	root.addI8([1, -2]);
	root.addU16([3]);
	root.addI64(new BigInt64Array([2n ** 60n + 3n]));
	root.addU64(new BigUint64Array([2n ** 63n + 5n]));
	root.addF32([1.5]);
	root.addB([true, false, true]);
	root.addE([read.Color.red, null]);
	root.addV([new read.Vertex(1, 2, 3)]);
	root.addTexts(['æ', null]);
	root.addBlobs([new Uint8Array([9, 8]), null]);
	root.addOuter([new read.Outer(1, new read.Vertex(4, 5, 6), read.Color.green, true)]);
	const rows = root.addRows(2);
	rows.get(1).name = 'row 1';
	rows.get(1).id = 2 ** 53 - 1;
	const wide = root.addWide(2);
	const x = wide.get(0);
	x.b = 7;
	x.g = -12;
	x.h_bigint = 2n ** 64n - 1n;
	x.os = new read.Vertex(1, 2, 3);
	x.t = 'text';
	x.by = new Uint8Array([1, 2, 3]);
	x.addL([4, 5]);
	x.addM().x = 3.5;
	x.u.addY([1, 2, 3]);
	wide.get(1).u.x = 'union text';
	const input = new scalgoproto.Reader(src.finalize(root)).root(read.ListsIn);

	for (const cap of capacities) {
		const w = new scalgoproto.Writer(cap);
		const copy = w.constructTable(read.ListsOut);
		copy._copy(input);
		const c = new scalgoproto.Reader(w.finalize(copy)).root(read.ListsIn);
		const what = ' capacity ' + cap;
		eq(c.i8!.toArray().join(), '1,-2', 'copy i8' + what);
		eq(c.u16!.get(0), 3, 'copy u16' + what);
		eq(c.i64!.getBigInt(0), 2n ** 60n + 3n, 'copy i64 exact' + what);
		eq(c.u64!.getBigInt(0), 2n ** 63n + 5n, 'copy u64 exact' + what);
		eq(c.f32!.get(0), 1.5, 'copy f32' + what);
		eq(c.b!.toArray().join(), 'true,false,true', 'copy bool' + what);
		eq(c.e!.toArray().join(), '0,', 'copy enum' + what);
		eq(c.v!.get(0).z, 3, 'copy struct list' + what);
		eq(c.texts!.toArray().join('|'), 'æ|', 'copy texts' + what);
		eq(c.blobs!.get(0)![1], 8, 'copy bytes list' + what);
		eq(c.blobs!.get(1), null, 'copy bytes list null' + what);
		eq(c.outer!.get(0).v.z, 6, 'copy outer' + what);
		eq(c.rows!.get(1).name, 'row 1', 'copy direct row text' + what);
		eq(c.rows!.get(1).id, 2 ** 53 - 1, 'copy direct row id' + what);
		eq(c.rows!.get(0).name, null, 'copy direct row null' + what);
		const cw = c.wide!.get(0);
		eq(cw.a, -3, 'copy default' + what);
		eq(cw.b, 7, 'copy optional' + what);
		eq(cw.c, null, 'copy unset optional' + what);
		eq(cw.g, -12, 'copy i64' + what);
		eq(cw.h_bigint, 2n ** 64n - 1n, 'copy u64 exact' + what);
		eq(cw.os!.y, 2, 'copy optional struct' + what);
		eq(cw.t, 'text', 'copy text' + what);
		eq(cw.by!.length, 3, 'copy bytes' + what);
		eq(cw.l!.toArray().join(), '4,5', 'copy list' + what);
		eq(cw.m!.x, 3.5, 'copy table' + what);
		eq(cw.u.y!.toArray().join(), '1,2,3', 'copy union list' + what);
		eq(c.wide!.get(1).u.x, 'union text', 'copy union text' + what);
	}

	// Inplace members and unions, from the cross language test message
	const inplace = new scalgoproto.Reader(readIn('test/inplace.bin')).root(base.InplaceRootIn);
	const w = new scalgoproto.Writer(16);
	const copy = w.constructTable(base.InplaceRootOut);
	copy._copy(inplace);
	const c = new scalgoproto.Reader(w.finalize(copy)).root(base.InplaceRootIn);
	eq(c.u!.u.monkey!.name, 'nilson', 'copy inplace union');
	eq(c.u2!.u.isEmpty, true, 'copy inplace empty union member');
	eq(c.t!.t, 'cake', 'copy inplace text');
	eq(c.b!.b![1], 'i'.charCodeAt(0), 'copy inplace bytes');
	eq(c.l!.l!.toArray().join(), '24,99', 'copy inplace list');

	// Copying a list of another type is refused
	const w2 = new scalgoproto.Writer();
	const r2 = w2.constructTable(read.ListsOut);
	throws(() => r2.addI32(1)._copy(input.u16 as any), 'copy list of another type',
		   /different type/);
	throws(() => r2.addI32(5)._copy(input.i8 as any), 'copy list of another length',
		   /length/);
}

function testReplace(): void {
	// Replacing a populated direct list row with an unset one restores the defaults
	const src = new scalgoproto.Writer();
	const sroot = src.constructTable(read.ListsOut);
	sroot.addWide(1);
	const unsetRow = new scalgoproto.Reader(src.finalize(sroot)).root(read.ListsIn).wide!.get(0);

	const w = new scalgoproto.Writer();
	const root = w.constructTable(read.ListsOut);
	const wide = root.addWide(1);
	const x = wide.get(0);
	x.a = 1;
	x.b = 7;
	x.c = true;
	x.e = read.Color.red;
	x.f = 2;
	x.h = 1;
	x.os = new read.Vertex(1, 2, 3);
	x.t = 'stale';
	x.by = new Uint8Array([1]);
	x.addL([1]);
	x.addM();
	x.u.x = 'stale';
	wide.set(0, unsetRow);
	const r = new scalgoproto.Reader(w.finalize(root)).root(read.ListsIn).wide!.get(0);
	eq(r.a, -3, 'replaced row default');
	eq(r.b, null, 'replaced row optional');
	eq(r.c, null, 'replaced row optional bool');
	eq(r.e, read.Color.blue, 'replaced row enum default');
	eq(r.f, null, 'replaced row optional float');
	eq(r.h, 7, 'replaced row u64 default');
	eq(r.os, null, 'replaced row optional struct');
	eq(r.t, null, 'replaced row text');
	eq(r.by, null, 'replaced row bytes');
	eq(r.l, null, 'replaced row list');
	eq(r.m, null, 'replaced row table');
	eq(r.u.type, 0, 'replaced row union');

	// Replacing a set union with an unset one clears it, in lists and tables
	const src2 = new scalgoproto.Writer();
	const s2 = src2.constructTable(names.NamesOut);
	s2.addUl(1);
	const unset = new scalgoproto.Reader(src2.finalize(s2)).root(names.NamesIn);
	const w2 = new scalgoproto.Writer();
	const n = w2.constructTable(names.NamesOut);
	const ul = n.addUl(1);
	ul.get(0).a = 'stale';
	ul.set(0, unset.ul!.get(0));
	n.ch.a = 'stale';
	n.ch._copy(unset.ch);
	const nr = new scalgoproto.Reader(w2.finalize(n)).root(names.NamesIn);
	eq(nr.ul!.get(0).type, 0, 'replaced union list element');
	eq(nr.ch.type, 0, 'replaced union member');

	// Setting null clears populated list entries
	const w3 = new scalgoproto.Writer();
	const r3 = w3.constructTable(read.ListsOut);
	const texts = r3.addTexts(['stale', 'keep']);
	texts.setAll([null]);
	const blobs = r3.addBlobs([new Uint8Array([9]), new Uint8Array([8])]);
	blobs.set(0, null);
	const lr = new scalgoproto.Reader(w3.finalize(r3)).root(read.ListsIn);
	eq(lr.texts!.get(0), null, 'text set to null');
	eq(lr.texts!.get(1), 'keep', 'text not set to null');
	eq(lr.blobs!.get(0), null, 'bytes set to null');
	eq(lr.blobs!.get(1)![0], 8, 'bytes not set to null');
	const w4 = new scalgoproto.Writer();
	const c4 = w4.constructTable(base.ComplexOut);
	const m4 = c4.addMemberList(2);
	m4.add(0).id = 1;
	m4.add(1).id = 2;
	m4.set(0, null);
	const cr = new scalgoproto.Reader(w4.finalize(c4)).root(base.ComplexIn).memberList!;
	eq(cr.get(0), null, 'table set to null');
	eq(cr.get(1)!.id, 2, 'table not set to null');
}

function testMisuse(): void {
	// Inplace members must be added right after their table
	const w = new scalgoproto.Writer();
	const t = w.constructTable(base.InplaceTextOut);
	w.constructText('something else');
	throws(() => { t.t = 'late'; }, 'late inplace text', /Inplace/);
	const w2 = new scalgoproto.Writer();
	const l = w2.constructTable(base.InplaceListOut);
	w2.constructText('x');
	throws(() => l.addL(2), 'late inplace list', /Inplace/);
	const w3 = new scalgoproto.Writer();
	const u = w3.constructTable(base.InplaceUnionOut);
	w3.constructText('x');
	throws(() => u.u.addMonkey(), 'late inplace union table', /Inplace/);
}

function testFinalize(): void {
	const w = new scalgoproto.Writer();
	const s = w.constructTable(base.MemberOut);
	s.id = 3;
	const msg = w.finalize(s);
	check(msg instanceof Uint8Array, 'finalize returns a Uint8Array');
	eq(msg.buffer.byteLength, msg.length, 'finalize returns a buffer of exactly the message');
	check(msg.buffer !== w._buffer, 'finalize returns a copy');
	eq(new scalgoproto.Reader(msg.buffer as ArrayBuffer).root(base.MemberIn).id, 3,
	   'finalized message');
	const w2 = new scalgoproto.Writer();
	const s2 = w2.constructTable(base.MemberOut);
	s2.id = 4;
	const view = w2.finalizeView(s2);
	check(view.buffer === w2._buffer, 'finalizeView returns a view');
	eq(new scalgoproto.Reader(view).root(base.MemberIn).id, 4, 'finalized view');
	throws(() => w.finalize(s2), 'finalize with a root from another writer', /another writer/);
}

function testOwnership(): void {
	// Objects from another writer can not be stored
	const a = new scalgoproto.Writer(), b = new scalgoproto.Writer();
	const ca = a.constructTable(base.ComplexOut);
	const member = b.constructTable(base.MemberOut);
	const text = b.constructText('x'), bytes = b.constructBytes(new Uint8Array([1]));
	const list = b.constructInt32List(2);
	throws(() => { ca.member = member; }, 'table from another writer', /another writer/);
	throws(() => ca.addMemberList(1).set(0, member), 'table list from another writer',
		   /another writer/);
	throws(() => { ca.text = text; }, 'text from another writer', /another writer/);
	throws(() => { ca.myBytes = bytes; }, 'bytes from another writer', /another writer/);
	throws(() => ca.addTextList(1).set(0, text), 'text list from another writer',
		   /another writer/);
	throws(() => { ca.intList = list; }, 'list from another writer', /another writer/);
	// The same objects from the right writer are fine
	const cb = b.constructTable(base.ComplexOut);
	cb.member = member;
	cb.text = text;
	cb.myBytes = bytes;
	cb.intList = list;
	const r = new scalgoproto.Reader(b.finalize(cb)).root(base.ComplexIn);
	eq(r.text, 'x', 'own text');
	eq(r.intList!.length, 2, 'own list');
}

function testCopyEdgeCases(): void {
	// A union with its type set but no value is copied as such
	const w = new scalgoproto.Writer();
	const n = w.constructTable(names.NamesOut);
	n.ch._set(1, 0);
	const src = new scalgoproto.Reader(w.finalize(n)).root(names.NamesIn);
	eq(src.ch.type, 1, 'union type set without value');
	eq(src.ch.a, null, 'union without value');
	const w2 = new scalgoproto.Writer();
	const c = w2.constructTable(names.NamesOut);
	c._copy(src);
	const cr = new scalgoproto.Reader(w2.finalize(c)).root(names.NamesIn);
	eq(cr.ch.type, 1, 'copied union type');
	eq(cr.ch.a, null, 'copied union without value');

	// Texts are copied byte for byte, also when they are not valid utf-8
	const w3 = new scalgoproto.Writer();
	const t = w3.constructTable(base.ComplexOut);
	t.text = 'Ab';
	t.addTextList(['Cd', null]);
	const msg = w3.finalize(t);
	// Make the texts invalid utf-8 of the same length
	for (const s of ['Ab', 'Cd']) {
		const at = msg.findIndex((_, i) => msg[i] === s.charCodeAt(0) && msg[i + 1] === s.charCodeAt(1));
		msg[at] = 0xC3;
	}
	const ti = new scalgoproto.Reader(msg).root(base.ComplexIn);
	const w4 = new scalgoproto.Writer();
	const tc = w4.constructTable(base.ComplexOut);
	tc._copy(ti);
	const copied = w4.finalize(tc);
	const tr = new scalgoproto.Reader(copied).root(base.ComplexIn);
	eq(tr.text, ti.text, 'copied malformed text');
	eq(tr.textList!.get(0), ti.textList!.get(0), 'copied malformed text list');
	eq(tr.textList!.get(1), null, 'copied text list null');
	let found = 0;
	for (let i = 0; i + 1 < copied.length; ++i)
		if (copied[i] === 0xC3 && (copied[i + 1] === 0x62 || copied[i + 1] === 0x64)) ++found;
	eq(found, 2, 'malformed bytes copied as they are');

	// Texts in unions (inplace or not) and inplace texts are also copied byte for byte
	const w6 = new scalgoproto.Writer();
	const t2 = w6.constructTable(union.Table2Out);
	t2.a.v1 = 'Ef'; // inplace union
	t2.b.v1 = 'Gh';
	const t6 = w6.finalize(t2);
	const w7 = new scalgoproto.Writer();
	const it = w7.constructTable(base.InplaceTextOut);
	it.t = 'Ij';
	const i7 = w7.finalize(it);
	const breakText = (m: Uint8Array, s: string) => {
		const at = m.findIndex((_, i) => m[i] === s.charCodeAt(0) && m[i + 1] === s.charCodeAt(1));
		m[at] = 0xC3;
	};
	breakText(t6, 'Ef');
	breakText(t6, 'Gh');
	breakText(i7, 'Ij');
	const countBroken = (m: Uint8Array, second: string) => {
		let n = 0;
		for (let i = 0; i + 1 < m.length; ++i)
			if (m[i] === 0xC3 && m[i + 1] === second.charCodeAt(0)) ++n;
		return n;
	};
	const u2 = new scalgoproto.Reader(t6).root(union.Table2In);
	const w8 = new scalgoproto.Writer();
	const c8 = w8.constructTable(union.Table2Out);
	c8._copy(u2);
	const m8 = w8.finalize(c8);
	const r8 = new scalgoproto.Reader(m8).root(union.Table2In);
	eq(r8.a.v1, u2.a.v1, 'copied malformed inplace union text');
	eq(r8.b.v1, u2.b.v1, 'copied malformed union text');
	eq(countBroken(m8, 'f') + countBroken(m8, 'h'), 2, 'union texts copied as they are');
	const iti = new scalgoproto.Reader(i7).root(base.InplaceTextIn);
	const w9 = new scalgoproto.Writer();
	const c9 = w9.constructTable(base.InplaceTextOut);
	c9._copy(iti);
	const m9 = w9.finalize(c9);
	eq(new scalgoproto.Reader(m9).root(base.InplaceTextIn).t, iti.t, 'copied malformed inplace text');
	eq(countBroken(m9, 'j'), 1, 'inplace text copied as it is');

	// An optional 64 bit member with its has bit in the table but its value outside it (a
	// malformed message) reads as the default, and must be copied as such
	const w10 = new scalgoproto.Writer();
	const s10 = w10.constructTable(base.SimpleOut);
	s10.ou64 = 5465768;
	const m10 = w10.finalize(s10);
	const dv10 = new DataView(m10.buffer);
	const full = dv10.getUint32(s10._off - 6, true);
	let size = 1;
	for (; size < full; ++size) {
		dv10.setUint32(s10._off - 6, size, true);
		if (new scalgoproto.Reader(m10).root(base.SimpleIn).ou64 === 0) break;
	}
	check(size < full, 'found a size with the has bit but not the value');
	const src10 = new scalgoproto.Reader(m10).root(base.SimpleIn);
	const w11 = new scalgoproto.Writer();
	const c11 = w11.constructTable(base.SimpleOut);
	c11._copy(src10);
	const r11 = new scalgoproto.Reader(w11.finalize(c11)).root(base.SimpleIn);
	eq(r11.ou64, 0, 'copied optional value outside the table');

	// The defaults of direct list rows, for many lengths (they are filled by doubling)
	for (const len of [0, 1, 2, 3, 5, 8, 33, 100]) {
		const w5 = new scalgoproto.Writer(16);
		const l = w5.constructTable(read.ListsOut);
		const wide = l.addWide(len);
		if (len > 1) wide.get(len - 2).a = 1;
		const wr = new scalgoproto.Reader(w5.finalize(l)).root(read.ListsIn).wide!;
		eq(wr.length, len, 'direct list length ' + len);
		// Every row that was not touched has exactly the default bytes
		const def = read.WideOut._DEFAULT, raw = wr.bytes();
		let differ = 0;
		for (let i = 0; i < len; ++i)
			if (i !== len - 2 && !sameBytes(raw.subarray(i * def.length, (i + 1) * def.length), def))
				++differ;
		eq(differ, 0, 'direct list default bytes ' + len);
		for (let i = 0; i < len; ++i) {
			eq(wr.get(i).a, i === len - 2 ? 1 : -3, 'direct list default a ' + len + ' ' + i);
			eq(wr.get(i).e, read.Color.blue, 'direct list default e ' + len + ' ' + i);
			eq(wr.get(i).h, 7, 'direct list default h ' + len + ' ' + i);
		}
	}
}

function testOtherRealm(): void {
	// Typed arrays from another realm (iframe, vm) are copied correctly
	const vm = require('vm');
	const xs = vm.runInNewContext('new Float64Array([1.5, 2.5, 3.5])');
	check(!(xs instanceof Float64Array), 'array is from another realm');
	const w = new scalgoproto.Writer();
	const root = w.constructTable(read.ListsOut);
	root.addF64(xs);
	root.addI64(vm.runInNewContext('new BigInt64Array([-5n])'));
	const r = new scalgoproto.Reader(w.finalize(root)).root(read.ListsIn);
	eq(r.f64!.toArray().join(), '1.5,2.5,3.5', 'other realm f64');
	eq(r.i64!.getBigInt(0), -5n, 'other realm i64');
}

testText();
testLarge();
testLists();
testScalars();
testCopy();
testReplace();
testMisuse();
testFinalize();
testOwnership();
testCopyEdgeCases();
testOtherRealm();

if (failures) {
	console.error(failures + ' checks failed');
	process.exit(1);
}
