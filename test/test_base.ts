// -*- mode: python; tab-width: 4; indent-tabs-mode: t; coding: utf-8 -*-
import * as base from 'base'
import * as complex2 from 'complex2'
import * as fs from 'fs';
import * as process from 'process';
import * as scalgoproto from 'scalgoproto'

export function bc(data: string): ArrayBuffer {
	const b = new ArrayBuffer(data.length);
	const b2 = new Uint8Array(b);
	for (let i = 0; i < data.length; ++i) b2[i] = data.charCodeAt(i);
	return b;
}

export function cb(l: ArrayBuffer, r: ArrayBuffer): boolean {
	const lb = new Uint8Array(l);
	const rb = new Uint8Array(r);
	if (lb.length != rb.length) return false;
	for (let i = 0; i < lb.length; ++i)
		if (lb[i] != rb[i]) return false;
	return true;
}

export function validateOut(data_: ArrayBuffer, path: string): boolean {
	const exp = new Uint8Array(readIn(path));
	const data = new Uint8Array(data_);

	if (data.length == exp.length) {
		let ok = true;
		for (let i = 0; i < data.length; ++i) ok = ok && data[i] == exp[i];
		if (ok) return true;
	}

	let hex = (num: number, length: number): string => {
		if (num === null || num == undefined) return 'xx';
		let v = num.toString(16);
		while (v.length != length) v = '0' + v;
		return v;
	};

	console.log('Wrong output')
	for (let i = 0; i < Math.max(data.length, exp.length); i += 16) {
		let line = hex(i, 8) + ' | ';
		for (let j = i; j < i + 16; ++j) {
			if (data[j] === exp[j])
				line += '\x1b[0m';
			else
				line += '\x1b[92m';
			if (j < exp.length)
				line += hex(exp[j], 2);
			else
				line += '  ';
			if (j % 4 == 3) line += ' ';
		}
		line += '| '
		for (let j = i; j < i + 16; ++j) {
			if (data[j] === exp[j])
				line += '\x1b[0m';
			else
				line += '\x1b[91m';
			if (j < data.length)
				line += hex(data[j], 2);
			else
				line += '  ';
			if (j % 4 == 3) line += ' ';
		}
		line += '\x1b[0m| ';
		for (let j = i; j < i + 16; ++j) {
			if (data[j] === exp[j])
				line += '\x1b[0m';
			else
				line += '\x1b[92m';
			if (j < exp.length && 32 <= exp[j] && exp[j] <= 126)
				line += String.fromCharCode(exp[j]);
			else if (j < exp.length)
				line += '.'
				else line += ' ';
			if (j % 4 == 3) line += ' ';
		}
		line += '| ';
		for (let j = i; j < i + 16; ++j) {
			if (data[j] === exp[j])
				line += '\x1b[0m';
			else
				line += '\x1b[91m';
			if (j < data.length && 32 <= data[j] && data[j] <= 126)
				line += String.fromCharCode(data[j]);
			else if (j < data.length)
				line += '.'
				else line += ' ';
			if (j % 4 == 3) line += ' ';
		}
		console.log(line);
	}
	return false;
}

export function readIn(path: string): ArrayBuffer {
	const b = fs.readFileSync('../' + path);
	return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
}

export function require1<T>(v: T, e: T): boolean {
	if (v instanceof ArrayBuffer) {
		if (e instanceof ArrayBuffer && cb(v, e)) return false;
	} else {
		if (e === v) return false;
	}
	console.error('Error expected \'%s\' found \'%s\'', e, v);
	return true;
}

export function require2<T>(b: boolean, v: T, e: T): boolean {
	if (!b) {
		console.error('Precondition not met');
		return true
	}
	if (v instanceof ArrayBuffer) {
		if (e instanceof ArrayBuffer && cb(v, e)) return false;
	} else {
		if (e === v) return false;
	}

	console.error('Error expected \'%s\' found \'%s\'', e, v);
	return true;
}

function testOutDefault(path: string): boolean {
	const w = new scalgoproto.Writer();
	const s = w.constructTable(base.SimpleOut)
	const data = w.finalize(s);
	return validateOut(data, path)
}

function testOut(path: string): boolean {
	const w = new scalgoproto.Writer();
	const s = w.constructTable(base.SimpleOut)
	s.e = base.MyEnum.c
	s.s = new base.FullStruct(
	  base.MyEnum.d,
	  new base.MyStruct(42, 27.0, true),
	  false,
	  8,
	  9,
	  10,
	  11,
	  -8,
	  -9,
	  -10,
	  -11,
	  27.0,
	  22.0,
	);
	s.b = true;
	s.u8 = 242;
	s.u16 = 4024;
	s.u32 = 124474;
	s.u64 = 5465778;
	s.i8 = -40;
	s.i16 = 4025;
	s.i32 = 124475;
	s.i64 = 5465779;
	s.f = 2.0;
	s.d = 3.0;
	s.os = new base.MyStruct(43, 28.0, false);
	s.ob = false;
	s.ou8 = 252;
	s.ou16 = 4034;
	s.ou32 = 124464;
	s.ou64 = 5465768;
	s.oi8 = -60;
	s.oi16 = 4055;
	s.oi32 = 124465;
	s.oi64 = 5465729;
	s.of = 5.0;
	s.od = 6.4;
	const data = w.finalize(s);
	return validateOut(data, path);
}

function testIn(path: string): boolean {
	const r = new scalgoproto.Reader(readIn(path))
	const s = r.root(base.SimpleIn)
	if (require1(s.e !== null, true)) return false;
	if (require1(s.e, base.MyEnum.c)) return false;
	if (require1(s.s.e, base.MyEnum.d)) return false;
	if (require1(s.s.s.x, 42)) return false;
	if (require1(s.s.s.y, 27.0)) return false;
	if (require1(s.s.s.z, true)) return false;
	if (require1(s.s.b, false)) return false;
	if (require1(s.s.u8, 8)) return false;
	if (require1(s.s.u16, 9)) return false;
	if (require1(s.s.u32, 10)) return false;
	if (require1(s.s.u64, 11)) return false;
	if (require1(s.s.i8, -8)) return false;
	if (require1(s.s.i16, -9)) return false;
	if (require1(s.s.i32, -10)) return false;
	if (require1(s.s.i64, -11)) return false;
	if (require1(s.s.f, 27.0)) return false;
	if (require1(s.s.d, 22.0)) return false;
	if (require1(s.b, true)) return false;
	if (require1(s.u8, 242)) return false;
	if (require1(s.u16, 4024)) return false;
	if (require1(s.u32, 124474)) return false;
	if (require1(s.u64, 5465778)) return false;
	if (require1(s.i8, -40)) return false;
	if (require1(s.i16, 4025)) return false;
	if (require1(s.i32, 124475)) return false;
	if (require1(s.i64, 5465779)) return false;
	if (require1(s.f, 2.0)) return false;
	if (require1(s.d, 3.0)) return false;
	if (require1(s.os !== null, true)) return false;
	if (require1(s.ob !== null, true)) return false;
	if (require1(s.ou8 !== null, true)) return false;
	if (require1(s.ou16 !== null, true)) return false;
	if (require1(s.ou32 !== null, true)) return false;
	if (require1(s.ou64 !== null, true)) return false;
	if (require1(s.oi8 !== null, true)) return false;
	if (require1(s.oi16 !== null, true)) return false;
	if (require1(s.oi32 !== null, true)) return false;
	if (require1(s.oi64 !== null, true)) return false;
	if (require1(s.of !== null, true)) return false;
	if (require1(s.od !== null, true)) return false;
	if (require1(s.os!.x, 43)) return false;
	if (require1(s.os!.y, 28.0)) return false;
	if (require1(s.os!.z, false)) return false;
	if (require1(s.ob, false)) return false;
	if (require1(s.ou8, 252)) return false;
	if (require1(s.ou16, 4034)) return false;
	if (require1(s.ou32, 124464)) return false;
	if (require1(s.ou64, 5465768)) return false;
	if (require1(s.oi8, -60)) return false;
	if (require1(s.oi16, 4055)) return false;
	if (require1(s.oi32, 124465)) return false;
	if (require1(s.oi64, 5465729)) return false;
	if (require1(s.of, 5.0)) return false;
	if (require1(s.od, 6.4)) return false;
	if (require1(s.ne, null)) return false;
	if (require1(s.ns, null)) return false;
	if (require1(s.nb, null)) return false;
	if (require1(s.nu8, null)) return false;
	if (require1(s.nu16, null)) return false;
	if (require1(s.nu32, null)) return false;
	if (require1(s.nu64, null)) return false;
	if (require1(s.ni8, null)) return false;
	if (require1(s.ni16, null)) return false;
	if (require1(s.ni32, null)) return false;
	if (require1(s.ni64, null)) return false;
	if (require1(s.nf, null)) return false;
	if (require1(s.nd, null)) return false;
	return true;
}

function testInDefault(path: string): boolean {
	const r = new scalgoproto.Reader(readIn(path))
	const s = r.root(base.SimpleIn)
	if (require1(s.e, null)) return false;
	if (require1(s.s.e, base.MyEnum.a)) return false;
	if (require1(s.s.s.x, 0)) return false;
	if (require1(s.s.s.y, 0.0)) return false;
	if (require1(s.s.s.z, false)) return false;
	if (require1(s.s.b, false)) return false;
	if (require1(s.s.u8, 0)) return false;
	if (require1(s.s.u16, 0)) return false;
	if (require1(s.s.u32, 0)) return false;
	if (require1(s.s.u64, 0)) return false;
	if (require1(s.s.i8, 0)) return false;
	if (require1(s.s.i16, 0)) return false;
	if (require1(s.s.i32, 0)) return false;
	if (require1(s.s.i64, 0)) return false;
	if (require1(s.s.f, 0)) return false;
	if (require1(s.s.d, 0)) return false;
	if (require1(s.b, false)) return false;
	if (require1(s.u8, 2)) return false;
	if (require1(s.u16, 3)) return false;
	if (require1(s.u32, 4)) return false;
	if (require1(s.u64, 5)) return false;
	if (require1(s.i8, 6)) return false;
	if (require1(s.i16, 7)) return false;
	if (require1(s.i32, 8)) return false;
	if (require1(s.i64, 9)) return false;
	if (require1(s.f, 10.0)) return false;
	if (require1(s.d, 11.0)) return false;
	if (require1(s.os, null)) return false;
	if (require1(s.ob, null)) return false;
	if (require1(s.ou8, null)) return false;
	if (require1(s.ou16, null)) return false;
	if (require1(s.ou32, null)) return false;
	if (require1(s.ou64, null)) return false;
	if (require1(s.oi8, null)) return false;
	if (require1(s.oi16, null)) return false;
	if (require1(s.oi32, null)) return false;
	if (require1(s.oi64, null)) return false;
	if (require1(s.of, null)) return false;
	if (require1(s.od, null)) return false;
	if (require1(s.ns, null)) return false;
	if (require1(s.nb, null)) return false;
	if (require1(s.nu8, null)) return false;
	if (require1(s.nu16, null)) return false;
	if (require1(s.nu32, null)) return false;
	if (require1(s.nu64, null)) return false;
	if (require1(s.ni8, null)) return false;
	if (require1(s.ni16, null)) return false;
	if (require1(s.ni32, null)) return false;
	if (require1(s.ni64, null)) return false;
	if (require1(s.nf, null)) return false;
	if (require1(s.nd, null)) return false;
	return true;
}

function testOutComplex(path: string): boolean {
	const w = new scalgoproto.Writer();

	const m = w.constructTable(base.MemberOut);
	m.id = 42;

	const l = w.constructInt32List(31);
	for (let i = 0; i < 31; ++i) l[i] = 100 - 2 * i;

	const l2 = w.constructEnumList<base.MyEnum>(2);
	l2[0] = base.MyEnum.a;

	const l3 = w.constructStructList(base.MyStruct, 1);

	const b = w.constructBytes(bc('bytes'));
	const t = w.constructText('text');

	const l4 = w.constructTextList(200);
	for (let i = 1; i < l4.length; i += 2) l4[i] = 'HI THERE';
	const l5 = w.constructBytesList(1);
	l5[0] = b;

	const l6 = w.constructTableList(base.MemberOut, 3);
	l6[0] = m;
	l6[2] = m;

	const l7 = w.constructFloat32List(2);
	l7[1] = 98.0;

	const l8 = w.constructFloat64List(3);
	l8[2] = 78.0;

	const l9 = w.constructUint8List(2);
	l9[0] = 4;

	const l10 = w.constructBoolList(10);
	l10[0] = true;
	l10[2] = true;
	l10[8] = true;

	const s = w.constructTable(base.ComplexOut);
	s.member = m;
	s.text = t;
	s.myBytes = b;
	s.intList = l;
	s.structList = l3;
	s.enumList = l2;
	s.textList = l4;
	s.bytesList = l5;
	s.memberList = l6;
	s.f32list = l7;
	s.f64list = l8;
	s.u8list = l9;
	s.blist = l10;

	const data = w.finalize(s);
	return validateOut(data, path);
}

function testInComplex(path: string): boolean {
	const r = new scalgoproto.Reader(readIn(path))
	const s = r.root(base.ComplexIn)
	if (require1(s.nmember, null)) return false;
	if (require1(s.ntext, null)) return false;
	if (require1(s.nbytes, null)) return false;
	if (require1(s.text !== null, true)) return false;
	if (require1(s.myBytes !== null, true)) return false;
	if (require1(s.text, 'text')) return false;
	if (require1(s.myBytes, bc('bytes'))) return false;
	if (require1(s.member !== null, true)) return false;
	const m = s.member!;
	if (require1(m.id, 42)) return false;

	if (require1(s.intList !== null, true)) return false;
	if (require1(s.nintList, null)) return false;
	const l = s.intList!;

	if (require1(l.length, 31)) return false;

	for (let i = 0; i < 31; ++i)
		if (require1(l[i], 100 - 2 * i)) return false;

	if (require1(s.enumList !== null, true)) return false;
	const l2 = s.enumList!;
	if (require1(l2[0] !== null, true)) return false;
	if (require1(l2[1] !== null, false)) return false;
	if (require1(l2[0], base.MyEnum.a)) return false;
	if (require1(l2.length, 2)) return false;

	if (require1(s.structList !== null, true)) return false;
	const l3 = s.structList!;
	if (require1(l3.length, 1)) return false;

	if (require1(s.textList !== null, true)) return false;
	const l4 = s.textList!;
	if (require1(l4.length, 200)) return false;
	for (let i = 0; i < l4.length; ++i) {
		if (i % 2 == 0) {
			if (require1(l4[i] !== null, false)) return false;
		} else {
			if (require1(l4[i] !== null, true)) return false;
			if (require1(l4[i], 'HI THERE')) return false;
		}
	}

	if (require1(s.bytesList !== null, true)) return false;
	const l5 = s.bytesList!;
	if (require1(l5.length, 1)) return false;
	if (require1(l5[0] !== null, true)) return false;
	if (require1(l5[0], bc('bytes'))) return false;
	if (require1(s.memberList !== null, true)) return false;
	const l6 = s.memberList!;
	if (require1(l6.length, 3)) return false;
	if (require1(l6[0] !== null, true)) return false;
	if (require1(l6[1] !== null, false)) return false;
	if (require1(l6[2] !== null, true)) return false;
	if (require1(l6[0]!.id, 42)) return false;
	if (require1(l6[2]!.id, 42)) return false;

	if (require1(s.f32list !== null, true)) return false;
	const l7 = s.f32list!;
	if (require1(l7.length, 2)) return false;
	if (require1(l7[0], 0.0)) return false;
	if (require1(l7[1], 98.0)) return false;

	if (require1(s.f64list !== null, true)) return false;
	const l8 = s.f64list!;
	if (require1(l8.length, 3)) return false;
	if (require1(l8[0], 0.0)) return false;
	if (require1(l8[1], 0.0)) return false;
	if (require1(l8[2], 78.0)) return false;

	if (require1(s.u8list !== null, true)) return false;
	const l9 = s.u8list!;
	if (require1(l9.length, 2)) return false;
	if (require1(l9[0], 4)) return false;
	if (require1(l9[1], 0)) return false;

	if (require1(s.blist !== null, true)) return false;
	const l10 = s.blist!;
	if (require1(l10.length, 10)) return false;
	if (require1(l10[0], true)) return false;
	if (require1(l10[1], false)) return false;
	if (require1(l10[2], true)) return false;
	if (require1(l10[3], false)) return false;
	if (require1(l10[4], false)) return false;
	if (require1(l10[5], false)) return false;
	if (require1(l10[6], false)) return false;
	if (require1(l10[7], false)) return false;
	if (require1(l10[8], true)) return false;
	if (require1(l10[9], false)) return false;
	return true;
}

function testOutComplex2(path: string): boolean {
	const w = new scalgoproto.Writer();

	const m = w.constructTable(base.MemberOut);
	m.id = 42;

	const b = w.constructBytes(bc('bytes'));
	const t = w.constructText('text');

	const l = w.constructEnumList<base.NamedUnionEnumList>(2);
	l[0] = base.NamedUnionEnumList.x;
	l[1] = base.NamedUnionEnumList.z;

	const l2 = w.constructStructList(complex2.Complex2L, 1);
	l2[0] = new complex2.Complex2L(2, true);

	const l3 = w.constructUnionList(base.NamedUnionOut, 2);
	l3[0].text = t;
	l3[1].myBytes = b;

	const r = w.constructTable(complex2.Complex2Out);
	r.u1.member = m;
	r.u2.text = t;
	r.u3.myBytes = b;
	r.u4.enumList = l;
	r.u5.addA();

	const m2 = r.addHat();
	m2.id = 43;

	r.l = l2;
	r.s = new complex2.Complex2S(complex2.Complex2SX.p, new complex2.Complex2SY(8));
	r.l2 = l3
	const data = w.finalize(r);
	return validateOut(data, path);
}

function testInComplex2(path: string): boolean {
	const r = new scalgoproto.Reader(readIn(path))
	const s = r.root(complex2.Complex2In)
	if (require1(s.u1.isMember, true)) return false;
	if (require1(s.u1.member!.id, 42)) return false;
	if (require1(s.u2.isText, true)) return false;
	if (require1(s.u2.text, 'text')) return false;
	if (require1(s.u3.isMyBytes, true)) return false;
	if (require1(s.u3.myBytes, bc('bytes'))) return false;
	if (require1(s.u4.isEnumList, true)) return false;
	const l = s.u4.enumList!;
	if (require1(l.length, 2)) return false;
	if (require1(l[0], base.NamedUnionEnumList.x)) return false;
	if (require1(l[1], base.NamedUnionEnumList.z)) return false;
	if (require1(s.u5.isA, true)) return false;
	if (require1(s.hat !== null, true)) return false;
	if (require1(s.hat!.id, 43)) return false;
	if (require1(s !== null, true)) return false;
	const l2 = s.l!;
	if (require1(l2.length, 1)) return false;
	if (require1(l2[0].a, 2)) return false;
	if (require1(l2[0].b, true)) return false;
	if (require1(s.s.x, complex2.Complex2SX.p)) return false;
	if (require1(s.s.y.z, 8)) return false;
	return true;
}

function testOutInplace(path: string): boolean {
	const w = new scalgoproto.Writer();
	const name = w.constructText('nilson');
	const u = w.constructTable(base.InplaceUnionOut);
	u.u.addMonkey().name = name;

	const u2 = w.constructTable(base.InplaceUnionOut);
	u2.u.addText().t = 'foobar';

	const t = w.constructTable(base.InplaceTextOut);
	t.id = 45;
	t.t = 'cake';

	const b = w.constructTable(base.InplaceBytesOut);
	b.id = 46;
	b.b = bc('hi');

	const l = w.constructTable(base.InplaceListOut);
	l.id = 47;
	const ll = l.addL(2);
	ll[0] = 24;
	ll[1] = 99;

	const root = w.constructTable(base.InplaceRootOut);
	root.u = u;
	root.u2 = u2;
	root.t = t;
	root.b = b;
	root.l = l;
	const data = w.finalize(root);
	return validateOut(data, path);
}

function testInInplace(path: string): boolean {
	const o = readIn(path)
	const r = new scalgoproto.Reader(o)
	const s = r.root(base.InplaceRootIn)

	if (require1(s.u !== null, true)) return false;
	const u = s.u!;
	if (require1(u.u.monkey !== null, true)) return false;
	const monkey = u.u.monkey!;
	if (require1(monkey.name !== null, true)) return false;
	if (require1(monkey.name, 'nilson')) return false;

	const u2 = s.u2;

	if (require1(s.t !== null, true)) return false;
	const t = s.t!;
	if (require1(t.id, 45)) return false;
	if (require1(t.t !== null, true)) return false;
	if (require1(t.t, 'cake')) return false;

	if (require1(s.b !== null, true)) return false;
	const b = s.b!;
	if (require1(b.id, 46)) return false;
	if (require1(b.b !== null, true)) return false;
	if (require1(b.b, bc('hi'))) return false;
	if (require1(s.l !== null, true)) return false;
	const l = s.l!;
	if (require1(l.id, 47)) return false;
	if (require1(l.l !== null, true)) return false;
	const ll = l.l!;
	if (require1(ll.length, 2)) return false;
	if (require1(ll[0], 24)) return false;
	if (require1(ll[1], 99)) return false;
	return true
}

function testOutExtend1(path: string): boolean {
	const w = new scalgoproto.Writer();
	const root = w.constructTable(base.Gen1Out)
	root.aa = 77;
	const data = w.finalize(root);
	return validateOut(data, path);
}

function testInExtend1(path: string): boolean {
	const data = readIn(path)
	const r = new scalgoproto.Reader(data)
	const s = r.root(base.Gen2In)
	if (require1(s.aa, 77)) return false;
	if (require1(s.bb, 42)) return false;
	if (require1(s.u.type, base.Gen2UType.NONE)) return false;
	return true
}

function testOutExtend2(path: string): boolean {
	const w = new scalgoproto.Writer();
	const root = w.constructTable(base.Gen2Out);
	root.aa = 80;
	root.bb = 81;
	const cake = root.u.addCake();
	cake.v = 45;
	const data = w.finalize(root);
	return validateOut(data, path);
}

function testInExtend2(path: string): boolean {
	const o = readIn(path)
	const r = new scalgoproto.Reader(o)
	const s = r.root(base.Gen3In)
	if (require1(s.aa, 80)) return false;
	if (require1(s.bb, 81)) return false;
	if (require1(s.u.cake !== null, true)) return false;
	if (require1(s.u.cake!.v, 45)) return false;
	if (require1(s.e, base.MyEnum.c)) return false;
	if (require1(s.s.x, 0)) return false;
	if (require1(s.s.y, 0)) return false;
	if (require1(s.s.z, false)) return false;
	if (require1(s.b, false)) return false;
	if (require1(s.u8, 2)) return false;
	if (require1(s.u16, 3)) return false;
	if (require1(s.u32, 4)) return false;
	if (require1(s.u64, 5)) return false;
	if (require1(s.i8, 6)) return false;
	if (require1(s.i16, 7)) return false;
	if (require1(s.i32, 8)) return false;
	if (require1(s.i64, 9)) return false;
	if (require1(s.f, 10)) return false;
	if (require1(s.d, 11)) return false;
	if (require1(s.os, null)) return false;
	if (require1(s.ob, null)) return false;
	if (require1(s.ou8, null)) return false;
	if (require1(s.ou16, null)) return false;
	if (require1(s.ou32, null)) return false;
	if (require1(s.ou64, null)) return false;
	if (require1(s.oi8, null)) return false;
	if (require1(s.oi16, null)) return false;
	if (require1(s.oi32, null)) return false;
	if (require1(s.oi64, null)) return false;
	if (require1(s.of, null)) return false;
	if (require1(s.od, null)) return false;
	if (require1(s.member, null)) return false;
	if (require1(s.text, null)) return false;
	if (require1(s.mbytes, null)) return false;
	if (require1(s.intList, null)) return false;
	if (require1(s.enumList, null)) return false;
	if (require1(s.structList, null)) return false;
	if (require1(s.textList, null)) return false;
	if (require1(s.bytesList, null)) return false;
	if (require1(s.memberList, null)) return false;
	return true;
}

if (!module.parent) {
	let ans = false
	const test = process.argv[2];
	const path = process.argv[3];
	if (test == 'out_default')
		ans = testOutDefault(path);
	else if (test == 'out')
		ans = testOut(path);
	else if (test == 'in')
		ans = testIn(path);
	else if (test == 'in_default')
		ans = testInDefault(path);
	else if (test == 'out_complex')
		ans = testOutComplex(path);
	else if (test == 'in_complex')
		ans = testInComplex(path);
	else if (test == 'out_complex2')
		ans = testOutComplex2(path);
	else if (test == 'in_complex2')
		ans = testInComplex2(path);
	else if (test == 'out_inplace')
		ans = testOutInplace(path);
	else if (test == 'in_inplace')
		ans = testInInplace(path);
	else if (test == 'out_extend1')
		ans = testOutExtend1(path);
	else if (test == 'in_extend1')
		ans = testInExtend1(path);
	else if (test == 'out_extend2')
		ans = testOutExtend2(path);
	else if (test == 'in_extend2')
		ans = testInExtend2(path);
	if (!ans) process.exit(1);
}
