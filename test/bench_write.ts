// Benchmark of the TypeScript writer. Run from test/ after generating code for
// test/read.spr and test/base.spr (python3 -m test does that):
//
//     ./node_modules/.bin/tsx bench_write.ts
import * as base from 'base'
import * as read from 'read'
import * as scalgoproto from 'scalgoproto'

const N = 1_000_000, NR = 200_000, NV = 300_000, NT = 200_000;

function bench(name: string, fn: () => number, reps = 7) {
	for (let i = 0; i < 2; ++i) fn();
	const ts: number[] = [];
	let r = 0;
	for (let i = 0; i < reps; ++i) {
		const t = performance.now();
		r = fn();
		ts.push(performance.now() - t);
	}
	ts.sort((a, b) => a - b);
	console.log(name.padEnd(44) + ts[reps >> 1].toFixed(2).padStart(9) + ' ms   size ' + r);
}

const xs = new Float64Array(N).map((_, i) => i * 0.5);

bench('f64 list 1M, element by element', () => {
	const w = new scalgoproto.Writer();
	const r = w.constructTable(read.ListsOut);
	const l = r.addF64(N);
	for (let i = 0; i < N; ++i) l.set(i, xs[i]);
	return w.finalize(r).length;
});
bench('f64 list 1M, from a Float64Array', () => {
	const w = new scalgoproto.Writer();
	const r = w.constructTable(read.ListsOut);
	r.addF64(xs);
	return w.finalize(r).length;
});
bench('f64 list 1M, from a Float64Array, finalizeView', () => {
	const w = new scalgoproto.Writer();
	const r = w.constructTable(read.ListsOut);
	r.addF64(xs);
	return w.finalizeView(r).length;
});
bench('struct list 300k', () => {
	const w = new scalgoproto.Writer();
	const r = w.constructTable(read.ListsOut);
	const l = r.addV(NV);
	for (let i = 0; i < NV; ++i) l.set(i, new read.Vertex(i, -i, i / 2));
	return w.finalize(r).length;
});
bench('direct rows 200k, 6 fields', () => {
	const w = new scalgoproto.Writer();
	const r = w.constructTable(read.ListsOut);
	const l = r.addRows(NR);
	for (let i = 0; i < NR; ++i) {
		const x = l.get(i);
		x.x = i;
		x.y = -i;
		x.color = i;
		x.id = i;
		x.flag = (i & 1) == 1;
		x.kind = read.Color.green;
	}
	return w.finalize(r).length;
});
bench('text list 200k short ascii', () => {
	const w = new scalgoproto.Writer();
	const r = w.constructTable(read.ListsOut);
	const l = r.addTexts(NT);
	for (let i = 0; i < NT; ++i) l.set(i, 'name ' + i);
	return w.finalize(r).length;
});
bench('text list 200k short danish', () => {
	const w = new scalgoproto.Writer();
	const r = w.constructTable(read.ListsOut);
	const l = r.addTexts(NT);
	for (let i = 0; i < NT; ++i) l.set(i, 'sø ' + i);
	return w.finalize(r).length;
});
bench('table list 200k small tables', () => {
	const w = new scalgoproto.Writer();
	const r = w.constructTable(base.ComplexOut);
	const l = r.addMemberList(NR);
	for (let i = 0; i < NR; ++i) l.add(i).id = i & 0x7fff;
	return w.finalize(r).length;
});
