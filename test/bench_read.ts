// Benchmark of the TypeScript reader. Run from test/ after generating code for
// test/read.spr (python3 -m test does that):
//
//     ./node_modules/.bin/tsx bench_read.ts
import * as read from 'read'
import * as scalgoproto from 'scalgoproto'

const NL = 1_000_000, NV = 300_000, NR = 200_000, NT = 200_000;

function build(): ArrayBuffer {
	const w = new scalgoproto.Writer();
	// The writer only doubles its buffer once per reservation, so grow it up front
	while (w._buffer.byteLength < 64e6) w._reserve(w._buffer.byteLength);
	const root = w.constructTable(read.ListsOut);
	const rows = root.addRows(NR);
	for (let i = 0; i < NR; ++i) {
		const row = rows.add(i);
		row.x = 500000 + i * 0.5;
		row.y = 6000000 - i * 0.25;
		row.color = (i * 2654435761) >>> 0;
		row.id = i * 1000003;
		row.flag = (i & 1) == 1;
		row.kind = (i % 3) as read.Color;
		row.name = 'row ' + i;
	}
	const f64 = root.addF64(NL), u32 = root.addU32(NL);
	for (let i = 0; i < NL; ++i) {
		f64[i] = i * 0.5;
		u32[i] = i * 7;
	}
	const v = root.addV(NV);
	for (let i = 0; i < NV; ++i) v[i] = new read.Vertex(500000 + i, 6000000 + i, i / 3);
	const t = root.addTexts(NT);
	for (let i = 0; i < NT; ++i)
		t[i] = i % 10 == 0 ? 'a somewhat longer text that is more than 32 bytes ' + i : 'name' + i;
	return w.finalize(root);
}

function bench(name: string, fn: () => number, reps = 9) {
	for (let i = 0; i < 3; ++i) fn();
	const ts: number[] = [];
	let r = 0;
	for (let i = 0; i < reps; ++i) {
		const t = performance.now();
		r = fn();
		ts.push(performance.now() - t);
	}
	ts.sort((a, b) => a - b);
	console.log(name.padEnd(46) + ts[reps >> 1].toFixed(2).padStart(9) + ' ms   chk ' + r.toFixed(0));
}

const msg = build();
console.log('message ' + (msg.byteLength / 1e6).toFixed(1) + ' MB');
const root = new scalgoproto.Reader(msg).root(read.ListsIn);
bench('f64 list 1M: get(i) sum', () => {
	const l = root.f64!;
	let s = 0;
	for (let i = 0; i < l.length; ++i) s += l.get(i);
	return s;
});
bench('f64 list 1M: toTypedArray + sum', () => {
	const a = root.f64!.toTypedArray();
	let s = 0;
	for (let i = 0; i < a.length; ++i) s += a[i];
	return s;
});
bench('f64 list 1M: for..of sum', () => {
	let s = 0;
	for (const x of root.f64!) s += x;
	return s;
});
bench('u32 list 1M: get(i) sum', () => {
	const l = root.u32!;
	let s = 0;
	for (let i = 0; i < l.length; ++i) s += l.get(i);
	return s;
});
bench('u32 list 1M: toTypedArray + sum', () => {
	const a = root.u32!.toTypedArray();
	let s = 0;
	for (let i = 0; i < a.length; ++i) s += a[i];
	return s;
});
bench('struct list 300k: x+y+z', () => {
	const l = root.v!;
	let s = 0;
	for (let i = 0; i < l.length; ++i) {
		const v = l.get(i);
		s += v.x + v.y + v.z;
	}
	return s;
});
bench('direct rows 200k: get(i)', () => {
	const l = root.rows!;
	let s = 0;
	for (let i = 0; i < l.length; ++i) {
		const r = l.get(i);
		s += r.x + r.y + r.color + r.id + (r.flag ? 1 : 0) + (r.kind as number);
	}
	return s;
});
bench('direct rows 200k: cursor', () => {
	const l = root.rows!;
	const r = l.cursor();
	let s = 0;
	for (let i = 0; i < l.length; ++i) {
		l.seek(r, i);
		s += r.x + r.y + r.color + r.id + (r.flag ? 1 : 0) + (r.kind as number);
	}
	return s;
});
bench('direct rows 200k: same columns by hand', () => {
	const l = root.rows!, n = l.length, r = l.cursor();
	const x = new Float64Array(n), y = new Float64Array(n), color = new Uint32Array(n),
		  id = new Float64Array(n), flag = new Uint8Array(n), kind = new Uint8Array(n);
	const name = new Array<string | null>(n);
	for (let i = 0; i < n; ++i) {
		l.seek(r, i);
		x[i] = r.x;
		y[i] = r.y;
		color[i] = r.color;
		id[i] = r.id;
		flag[i] = r.flag ? 1 : 0;
		kind[i] = r.kind ?? 255;
		name[i] = r.name;
	}
	return x.length + name.length;
});
bench('direct rows 200k: toColumns', () => {
	const c = root.rows!.toColumns();
	return c.x.length + c.name.length;
});
bench('struct list 300k: toColumns', () => root.v!.toColumns().x.length);
bench('direct rows 200k: name', () => {
	const l = root.rows!;
	let s = 0;
	for (let i = 0; i < l.length; ++i) s += l.get(i).name!.length;
	return s;
});
bench('text list 200k', () => {
	const l = root.texts!;
	let s = 0;
	for (let i = 0; i < l.length; ++i) s += l.get(i)!.length;
	return s;
});

// Repeated conversion: a reused destination avoids allocating a large array each time
const dst = new Float64Array(NL);
bench('f64 list 1M: toTypedArray x20', () => {
	let s = 0;
	for (let k = 0; k < 20; ++k) s += root.f64!.toTypedArray()[k];
	return s;
});
bench('f64 list 1M: copyTo(reused) x20', () => {
	let s = 0;
	for (let k = 0; k < 20; ++k) s += root.f64!.copyTo(dst)[k];
	return s;
});

// Applications use many kinds of lists; let the shared code paths see them all
const lists: scalgoproto.ListIn<unknown>[] =
  [root.f64!, root.u32!, root.v!, root.rows!, root.texts!];
for (let k = 0; k < 3; ++k)
	for (const l of lists) {
		l.forEach(() => {});
		l.toArray();
		for (const _ of l) {
		}
	}
console.log('after iterating many kinds of lists:');
bench('f64 list 1M: get(i) sum', () => {
	const l = root.f64!;
	let s = 0;
	for (let i = 0; i < l.length; ++i) s += l.get(i);
	return s;
});
bench('f64 list 1M: forEach sum', () => {
	let s = 0;
	root.f64!.forEach(x => { s += x; });
	return s;
});
bench('f64 list 1M: for..of sum', () => {
	let s = 0;
	for (const x of root.f64!) s += x;
	return s;
});
bench('u32 list 1M: toArray', () => root.u32!.toArray().length);
