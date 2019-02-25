// -*- mode: python; tab-width: 4; indent-tabs-mode: t; coding: utf-8 -*-
import * as scalgoproto from 'scalgoproto'
import * as union from 'union'

import {readIn, require1, require2} from './test_base'

// def forCopy() -> union.Table3In:
//     w = scalgoproto.Writer()
//     root = w.construct_table(union.Table3Out)

//     v1 = root.addV1()
//     v1.a.v1 = "ctext1"
//     v1.b.v1 = "ctext2"

//     v2 = root.addV2()
//     v2.a.v2 = b"cbytes1"
//     v2.b.v2 = b"cbytes2"

//     v3 = root.addV3()
//     v3.a.addV3().a = 101
//     v3.b.addV3().a = 102

//     v4 = root.addV4()
//     v4.a.addV4().a = 103
//     v4.b.addV4().a = 104

//     v5 = root.addV5()
//     v5.a.addV5(1)[0] = "ctext3"
//     v5.b.addV5(1)[0] = "ctext4"

//     v6 = root.addV6()
//     v6.a.addV6(1)[0] = b"cbytes3"
//     v6.b.addV6(1)[0] = b"cbytes4"

//     v7 = root.addV7()
//     v7.a.addV7(1).add(0).a = 105
//     v7.b.addV7(1).add(0).a = 106

//     v8 = root.addV8()
//     v8.a.addV8(1).add(0).a = 107
//     v8.b.addV8(1).add(0).a = 108

//     v9 = root.addV9()
//     v9.a.addV9(1)[0] = 109
//     v9.b.addV9(1)[0] = 110

//     v10 = root.addV10()
//     v10.a.addV10(1)[0] = true
//     v10.b.addV10(1)[0] = true

//     d = w.finalize(root)

//     r = scalgoproto.Reader(d)
//     return r.root(union.Table3In)

function test_out_union(path: string): boolean {
	// i = forCopy()

	// w = scalgoproto.Writer()
	// root = w.construct_table(union.Table3Out)

	// v1 = root.addV1()
	// v1.a.v1 = "text1"
	// v1.b.v1 = "text2"
	// v1.c.v1 = w.construct_text("text3")
	// v1.d.v1 = i.v1.a.v1
	// v1.e.v1 = i.v1.b.v1

	// v2 = root.addV2()
	// v2.a.v2 = b"bytes1"
	// v2.b.v2 = b"bytes2"
	// v2.c.v2 = w.constructBytes(b"bytes3")
	// v2.d.v2 = i.v2.a.v2
	// v2.e.v2 = i.v2.b.v2

	// v3 = root.addV3()
	// v3.a.addV3().a = 1
	// v3.b.addV3().a = 2
	// t1 = w.construct_table(union.Table1Out)
	// t1.a = 3
	// v3.c.v3 = t1
	// v3.d.v3 = i.v3.a.v3
	// v3.e.v3 = i.v3.b.v3

	// v4 = root.addV4()
	// v4.a.addV4().a = 4
	// v4.b.addV4().a = 5
	// t4 = w.construct_table(union.Union1V4Out)
	// t4.a = 6
	// v4.c.v4 = t4
	// v4.d.v4 = i.v4.a.v4
	// v4.e.v4 = i.v4.b.v4

	// v5 = root.addV5()
	// v5.a.addV5(1)[0] = "text4"
	// v5.b.addV5(1)[0] = "text5"
	// t5 = w.construct_text_list(1)
	// t5[0] = "text6"
	// v5.c.v5 = t5
	// v5.d.v5 = i.v5.a.v5
	// v5.e.v5 = i.v5.b.v5

	// v6 = root.addV6()
	// v6.a.addV6(1)[0] = b"bytes4"
	// tt6 = v6.b.addV6(1)
	// tt6[0] = w.constructBytes(b"bytes5")
	// t6 = w.constructBytes_list(1)
	// t6[0] = w.constructBytes(b"bytes6")
	// v6.c.v6 = t6
	// v6.d.v6 = i.v6.a.v6
	// v6.e.v6 = i.v6.b.v6

	// v7 = root.addV7()
	// v7.a.addV7(1).add(0).a = 7
	// v7.b.addV7(1).add(0).a = 8
	// t7 = w.construct_table_list(union.Table1Out, 1)
	// t7.add(0).a = 9
	// v7.c.v7 = t7
	// v7.d.v7 = i.v7.a.v7
	// v7.e.v7 = i.v7.b.v7

	// v8 = root.addV8()
	// v8.a.addV8(1).add(0).a = 10
	// v8.b.addV8(1).add(0).a = 11
	// t8 = w.construct_table_list(union.Union1V8Out, 1)
	// t8.add(0).a = 12
	// v8.c.v8 = t8
	// v8.d.v8 = i.v8.a.v8
	// v8.e.v8 = i.v8.b.v8

	// v9 = root.addV9()
	// v9.a.addV9(1)[0] = 13
	// v9.b.addV9(1)[0] = 14
	// t9 = w.construct_uint32_list(1)
	// t9[0] = 15
	// v9.c.v9 = t9
	// v9.d.v9 = i.v9.a.v9
	// v9.e.v9 = i.v9.b.v9

	// v10 = root.addV10()
	// v10.a.addV10(1)[0] = true
	// v10.b.addV10(1)[0] = False
	// t10 = w.constructBool_list(1)
	// t10[0] = true
	// v10.c.v10 = t10
	// v10.d.v10 = i.v10.a.v10
	// v10.e.v10 = i.v10.b.v10

	// data = w.finalize(root)
	// return validate_out(data, path)
	return false;
}

function test_in_union(path: string): boolean {
	const o = readIn(path);
	const r = new scalgoproto.Reader(o);
	const i = r.root(union.Table3In);

	// print(i)

	if (require1(i.v1 !== null, true)) return false;
	if (require1(i.v1 !== null, true)) return false;
	const v1 = i.v1!;
	if (require2(v1.a.isV1, v1.a.v1, 'text1')) return false;
	if (require2(v1.b.isV1, v1.b.v1, 'text2')) return false;
	if (require2(v1.c.isV1, v1.c.v1, 'text3')) return false;
	if (require2(v1.d.isV1, v1.d.v1, 'ctext1')) return false;
	if (require2(v1.e.isV1, v1.e.v1, 'ctext2')) return false;

	if (require1(i.v2 !== null, true)) return false;
	if (!i.v2) throw Error('Require v2');
	const v2 = i.v2;
	// if (require2(v2.a.isV2, v2.a.v2, b"bytes1"))
	//     return false;
	// if (require2(v2.b.isV2, v2.b.v2, b"bytes2"))
	//     return false;
	// if (require2(v2.c.isV2, v2.c.v2, b"bytes3"))
	//     return false;
	// if (require2(v2.d.isV2, v2.d.v2, b"cbytes1"))
	//     return false;
	// if (require2(v2.e.isV2, v2.e.v2, b"cbytes2"))
	//     return false;

	if (require1(i.v3 !== null, true)) return false;
	const v3 = i.v3!;
	if (require2(v3.a.isV3, v3.a.v3!.a, 1)) return false;
	if (require2(v3.b.isV3, v3.b.v3!.a, 2)) return false;
	if (require2(v3.c.isV3, v3.c.v3!.a, 3)) return false;
	if (require2(v3.d.isV3, v3.d.v3!.a, 101)) return false;
	if (require2(v3.e.isV3, v3.e.v3!.a, 102)) return false;

	if (require1(i.v4 !== null, true)) return false;
	const v4 = i.v4!;
	if (require2(v4.a.isV4, v4.a.v4!.a, 4)) return false;
	if (require2(v4.b.isV4, v4.b.v4!.a, 5)) return false;
	if (require2(v4.c.isV4, v4.c.v4!.a, 6)) return false;
	if (require2(v4.d.isV4, v4.d.v4!.a, 103)) return false;
	if (require2(v4.e.isV4, v4.e.v4!.a, 104)) return false;

	if (require1(i.v5 !== null, true)) return false;
	const v5 = i.v5!;
	if (require2(v5.a.isV5 && v5.a.v5!.length == 1, v5.a.v5![0], 'text4')) return false;
	if (require2(v5.b.isV5 && v5.b.v5!.length == 1, v5.b.v5![0], 'text5')) return false;
	if (require2(v5.c.isV5 && v5.c.v5!.length == 1, v5.c.v5![0], 'text6')) return false;
	if (require2(v5.d.isV5 && v5.d.v5!.length == 1, v5.d.v5![0], 'ctext3')) return false;
	if (require2(v5.e.isV5 && v5.e.v5!.length == 1, v5.e.v5![0], 'ctext4')) return false;

	if (require1(i.v6 !== null, true)) return false;
	const v6 = i.v6!;
	// if (require2(v6.a.isV6 && v6.a.v6!.length == 1, v6.a.v6![0], b"bytes4"))
	//     return false;
	// if (require2(v6.b.isV6 && v6.b.v6!.length == 1, v6.b.v6![0], b"bytes5"))
	//     return false;
	// if (require2(v6.c.isV6 && v6.c.v6!.length == 1, v6.c.v6![0], b"bytes6"))
	//     return false;
	// if (require2(v6.d.isV6 && v6.d.v6!.length == 1, v6.d.v6![0], b"cbytes3"))
	//     return false;
	// if (require2(v6.e.isV6 && v6.e.v6!.length == 1, v6.e.v6![0], b"cbytes4"))
	//     return false;

	if (require1(i.v7 !== null, true)) return false;
	const v7 = i.v7!;
	if (require2(v7.a.isV7 && v7.a.v7!.length == 1, v7.a.v7![0]!.a, 7)) return false;
	if (require2(v7.b.isV7 && v7.b.v7!.length == 1, v7.b.v7![0]!.a, 8)) return false;
	if (require2(v7.c.isV7 && v7.c.v7!.length == 1, v7.c.v7![0]!.a, 9)) return false;
	if (require2(v7.d.isV7 && v7.d.v7!.length == 1, v7.d.v7![0]!.a, 105)) return false;
	if (require2(v7.e.isV7 && v7.e.v7!.length == 1, v7.e.v7![0]!.a, 106)) return false;

	if (require1(i.v8 !== null, true)) return false;
	const v8 = i.v8!;
	if (require2(v8.a.isV8 && v8.a.v8!.length == 1, v8.a.v8![0]!.a, 10)) return false;
	if (require2(v8.b.isV8 && v8.b.v8!.length == 1, v8.b.v8![0]!.a, 11)) return false;
	if (require2(v8.c.isV8 && v8.c.v8!.length == 1, v8.c.v8![0]!.a, 12)) return false;
	if (require2(v8.d.isV8 && v8.d.v8!.length == 1, v8.d.v8![0]!.a, 107)) return false;
	if (require2(v8.e.isV8 && v8.e.v8!.length == 1, v8.e.v8![0]!.a, 108)) return false;

	if (require1(i.v8 !== null, true)) return false;
	const v9 = i.v9!;
	if (require2(v9.a.isV9 && v9.a.v9!.length == 1, v9.a.v9![0], 13)) return false;
	if (require2(v9.b.isV9 && v9.b.v9!.length == 1, v9.b.v9![0], 14)) return false;
	if (require2(v9.c.isV9 && v9.c.v9!.length == 1, v9.c.v9![0], 15)) return false;
	if (require2(v9.d.isV9 && v9.d.v9!.length == 1, v9.d.v9![0], 109)) return false;
	if (require2(v9.e.isV9 && v9.e.v9!.length == 1, v9.e.v9![0], 110)) return false;

	if (require1(i.v10 !== null, true)) return false;
	const v10 = i.v10!;
	if (require2(v10.a.isV10 && v10.a.v10!.length == 1, v10.a.v10![0], true))
		return false;
	if (require2(v10.b.isV10 && v10.b.v10!.length == 1, v10.b.v10![0], false))
		return false;
	if (require2(v10.c.isV10 && v10.c.v10!.length == 1, v10.c.v10![0], true))
		return false;
	if (require2(v10.d.isV10 && v10.d.v10!.length == 1, v10.d.v10![0], true))
		return false;
	if (require2(v10.e.isV10 && v10.e.v10!.length == 1, v10.e.v10![0], true))
		return false;

	return true;
}

if (!module.parent) {
	let ans = false;
	const test = process.argv[2];
	const path = process.argv[3];
	if (test == 'out_union')
		ans = test_out_union(path);
	else if (test == 'in_union')
		ans = test_in_union(path)
		if (!ans) process.exit(1);
}