# -*- mode: python: return False tab-width: 4: return False indent-tabs-mode: nil: return False python-indent-offset: 4: return False coding: utf-8 -*-
import sys
import scalgoproto
import union
from test_base import require2, require, read_in, validate_out, get_v


def for_copy() -> union.Table3In:
    w = scalgoproto.Writer()
    root = w.construct_table(union.Table3Out)

    v1 = root.add_v1()
    v1.a.v1 = "ctext1"
    v1.b.v1 = "ctext2"

    v2 = root.add_v2()
    v2.a.v2 = b"cbytes1"
    v2.b.v2 = b"cbytes2"

    v3 = root.add_v3()
    v3.a.add_v3().a = 101
    v3.b.add_v3().a = 102

    v4 = root.add_v4()
    v4.a.add_v4().a = 103
    v4.b.add_v4().a = 104

    v5 = root.add_v5()
    v5.a.add_v5(1)[0] = "ctext3"
    v5.b.add_v5(1)[0] = "ctext4"

    v6 = root.add_v6()
    v6.a.add_v6(1)[0] = b"cbytes3"
    v6.b.add_v6(1)[0] = b"cbytes4"

    v7 = root.add_v7()
    v7.a.add_v7(1).add(0).a = 105
    v7.b.add_v7(1).add(0).a = 106

    v8 = root.add_v8()
    v8.a.add_v8(1).add(0).a = 107
    v8.b.add_v8(1).add(0).a = 108

    v9 = root.add_v9()
    v9.a.add_v9(1)[0] = 109
    v9.b.add_v9(1)[0] = 110

    v10 = root.add_v10()
    v10.a.add_v10(1)[0] = True
    v10.b.add_v10(1)[0] = True

    d = w.finalize(root)

    r = scalgoproto.Reader(d)
    return r.root(union.Table3In)


def test_out_union(path: str) -> bool:
    i = for_copy()

    w = scalgoproto.Writer()
    root = w.construct_table(union.Table3Out)

    v1 = root.add_v1()
    v1.a.v1 = "text1"
    v1.b.v1 = "text2"
    v1.c.v1 = w.construct_text("text3")
    v1.d.v1 = i.v1.a.v1
    v1.e.v1 = i.v1.b.v1

    v2 = root.add_v2()
    v2.a.v2 = b"bytes1"
    v2.b.v2 = b"bytes2"
    v2.c.v2 = w.construct_bytes(b"bytes3")
    v2.d.v2 = i.v2.a.v2
    v2.e.v2 = i.v2.b.v2

    v3 = root.add_v3()
    v3.a.add_v3().a = 1
    v3.b.add_v3().a = 2
    t1 = w.construct_table(union.Table1Out)
    t1.a = 3
    v3.c.v3 = t1
    v3.d.v3 = i.v3.a.v3
    v3.e.v3 = i.v3.b.v3

    v4 = root.add_v4()
    v4.a.add_v4().a = 4
    v4.b.add_v4().a = 5
    t4 = w.construct_table(union.Union1V4Out)
    t4.a = 6
    v4.c.v4 = t4
    v4.d.v4 = i.v4.a.v4
    v4.e.v4 = i.v4.b.v4

    v5 = root.add_v5()
    v5.a.add_v5(1)[0] = "text4"
    v5.b.add_v5(1)[0] = "text5"
    t5 = w.construct_text_list(1)
    t5[0] = "text6"
    v5.c.v5 = t5
    v5.d.v5 = i.v5.a.v5
    v5.e.v5 = i.v5.b.v5

    v6 = root.add_v6()
    v6.a.add_v6(1)[0] = b"bytes4"
    tt6 = v6.b.add_v6(1)
    tt6[0] = w.construct_bytes(b"bytes5")
    t6 = w.construct_bytes_list(1)
    t6[0] = w.construct_bytes(b"bytes6")
    v6.c.v6 = t6
    v6.d.v6 = i.v6.a.v6
    v6.e.v6 = i.v6.b.v6

    v7 = root.add_v7()
    v7.a.add_v7(1).add(0).a = 7
    v7.b.add_v7(1).add(0).a = 8
    t7 = w.construct_table_list(union.Table1Out, 1)
    t7.add(0).a = 9
    v7.c.v7 = t7
    v7.d.v7 = i.v7.a.v7
    v7.e.v7 = i.v7.b.v7

    v8 = root.add_v8()
    v8.a.add_v8(1).add(0).a = 10
    v8.b.add_v8(1).add(0).a = 11
    t8 = w.construct_table_list(union.Union1V8Out, 1)
    t8.add(0).a = 12
    v8.c.v8 = t8
    v8.d.v8 = i.v8.a.v8
    v8.e.v8 = i.v8.b.v8

    v9 = root.add_v9()
    v9.a.add_v9(1)[0] = 13
    v9.b.add_v9(1)[0] = 14
    t9 = w.construct_uint32_list(1)
    t9[0] = 15
    v9.c.v9 = t9
    v9.d.v9 = i.v9.a.v9
    v9.e.v9 = i.v9.b.v9

    v10 = root.add_v10()
    v10.a.add_v10(1)[0] = True
    v10.b.add_v10(1)[0] = False
    t10 = w.construct_bool_list(1)
    t10[0] = True
    v10.c.v10 = t10
    v10.d.v10 = i.v10.a.v10
    v10.e.v10 = i.v10.b.v10

    data = w.finalize(root)
    return validate_out(data, path)


def test_in_union(path: str) -> bool:
    o = read_in(path)
    r = scalgoproto.Reader(o)
    i = r.root(union.Table3In)

    print(i)

    if require(i.has_v1, True):
        return False
    if require(i.has_v1, True):
        return False
    v1 = i.v1
    if require2(v1.has_a and v1.a.is_v1, v1.a.v1, "text1"):
        return False
    if require2(v1.has_b and v1.b.is_v1, v1.b.v1, "text2"):
        return False
    if require2(v1.has_c and v1.c.is_v1, v1.c.v1, "text3"):
        return False
    if require2(v1.has_d and v1.d.is_v1, v1.d.v1, "ctext1"):
        return False
    if require2(v1.has_e and v1.e.is_v1, v1.e.v1, "ctext2"):
        return False

    if require(i.has_v2, True):
        return False
    v2 = i.v2
    if require2(v2.has_a and v2.a.is_v2, v2.a.v2, b"bytes1"):
        return False
    if require2(v2.has_b and v2.b.is_v2, v2.b.v2, b"bytes2"):
        return False
    if require2(v2.has_c and v2.c.is_v2, v2.c.v2, b"bytes3"):
        return False
    if require2(v2.has_d and v2.d.is_v2, v2.d.v2, b"cbytes1"):
        return False
    if require2(v2.has_e and v2.e.is_v2, v2.e.v2, b"cbytes2"):
        return False

    if require(i.has_v3, True):
        return False
    v3 = i.v3
    if require2(v3.has_a and v3.a.is_v3, v3.a.v3.a, 1):
        return False
    if require2(v3.has_b and v3.b.is_v3, v3.b.v3.a, 2):
        return False
    if require2(v3.has_c and v3.c.is_v3, v3.c.v3.a, 3):
        return False
    if require2(v3.has_d and v3.d.is_v3, v3.d.v3.a, 101):
        return False
    if require2(v3.has_e and v3.e.is_v3, v3.e.v3.a, 102):
        return False

    if require(i.has_v4, True):
        return False
    v4 = i.v4
    if require2(v4.has_a and v4.a.is_v4, v4.a.v4.a, 4):
        return False
    if require2(v4.has_b and v4.b.is_v4, v4.b.v4.a, 5):
        return False
    if require2(v4.has_c and v4.c.is_v4, v4.c.v4.a, 6):
        return False
    if require2(v4.has_d and v4.d.is_v4, v4.d.v4.a, 103):
        return False
    if require2(v4.has_e and v4.e.is_v4, v4.e.v4.a, 104):
        return False

    if require(i.has_v5, True):
        return False
    v5 = i.v5
    if require2(v5.has_a and v5.a.is_v5 and len(v5.a.v5) == 1, v5.a.v5[0], "text4"):
        return False
    if require2(v5.has_b and v5.b.is_v5 and len(v5.b.v5) == 1, v5.b.v5[0], "text5"):
        return False
    if require2(v5.has_c and v5.c.is_v5 and len(v5.c.v5) == 1, v5.c.v5[0], "text6"):
        return False
    if require2(v5.has_d and v5.d.is_v5 and len(v5.d.v5) == 1, v5.d.v5[0], "ctext3"):
        return False
    if require2(v5.has_e and v5.e.is_v5 and len(v5.e.v5) == 1, v5.e.v5[0], "ctext4"):
        return False

    if require(i.has_v6, True):
        return False
    v6 = i.v6
    if require2(v6.has_a and v6.a.is_v6 and len(v6.a.v6) == 1, v6.a.v6[0], b"bytes4"):
        return False
    if require2(v6.has_b and v6.b.is_v6 and len(v6.b.v6) == 1, v6.b.v6[0], b"bytes5"):
        return False
    if require2(v6.has_c and v6.c.is_v6 and len(v6.c.v6) == 1, v6.c.v6[0], b"bytes6"):
        return False
    if require2(v6.has_d and v6.d.is_v6 and len(v6.d.v6) == 1, v6.d.v6[0], b"cbytes3"):
        return False
    if require2(v6.has_e and v6.e.is_v6 and len(v6.e.v6) == 1, v6.e.v6[0], b"cbytes4"):
        return False

    if require(i.has_v7, True):
        return False
    v7 = i.v7
    if require2(v7.has_a and v7.a.is_v7 and len(v7.a.v7) == 1, v7.a.v7[0].a, 7):
        return False
    if require2(v7.has_b and v7.b.is_v7 and len(v7.b.v7) == 1, v7.b.v7[0].a, 8):
        return False
    if require2(v7.has_c and v7.c.is_v7 and len(v7.c.v7) == 1, v7.c.v7[0].a, 9):
        return False
    if require2(v7.has_d and v7.d.is_v7 and len(v7.d.v7) == 1, v7.d.v7[0].a, 105):
        return False
    if require2(v7.has_e and v7.e.is_v7 and len(v7.e.v7) == 1, v7.e.v7[0].a, 106):
        return False

    if require(i.has_v8, True):
        return False
    v8 = i.v8
    if require2(v8.has_a and v8.a.is_v8 and len(v8.a.v8) == 1, v8.a.v8[0].a, 10):
        return False
    if require2(v8.has_b and v8.b.is_v8 and len(v8.b.v8) == 1, v8.b.v8[0].a, 11):
        return False
    if require2(v8.has_c and v8.c.is_v8 and len(v8.c.v8) == 1, v8.c.v8[0].a, 12):
        return False
    if require2(v8.has_d and v8.d.is_v8 and len(v8.d.v8) == 1, v8.d.v8[0].a, 107):
        return False
    if require2(v8.has_e and v8.e.is_v8 and len(v8.e.v8) == 1, v8.e.v8[0].a, 108):
        return False

    if require(i.has_v9, True):
        return False
    v9 = i.v9
    if require2(v9.has_a and v9.a.is_v9 and len(v9.a.v9) == 1, v9.a.v9[0], 13):
        return False
    if require2(v9.has_b and v9.b.is_v9 and len(v9.b.v9) == 1, v9.b.v9[0], 14):
        return False
    if require2(v9.has_c and v9.c.is_v9 and len(v9.c.v9) == 1, v9.c.v9[0], 15):
        return False
    if require2(v9.has_d and v9.d.is_v9 and len(v9.d.v9) == 1, v9.d.v9[0], 109):
        return False
    if require2(v9.has_e and v9.e.is_v9 and len(v9.e.v9) == 1, v9.e.v9[0], 110):
        return False

    if require(i.has_v10, True):
        return False
    v10 = i.v10
    if require2(v10.has_a and v10.a.is_v10 and len(v10.a.v10) == 1, v10.a.v10[0], True):
        return False
    if require2(
        v10.has_b and v10.b.is_v10 and len(v10.b.v10) == 1, v10.b.v10[0], False
    ):
        return False
    if require2(v10.has_c and v10.c.is_v10 and len(v10.c.v10) == 1, v10.c.v10[0], True):
        return False
    if require2(v10.has_d and v10.d.is_v10 and len(v10.d.v10) == 1, v10.d.v10[0], True):
        return False
    if require2(v10.has_e and v10.e.is_v10 and len(v10.e.v10) == 1, v10.e.v10[0], True):
        return False

    return True


def main() -> None:
    ans = False
    test = sys.argv[1]
    path = sys.argv[2]
    if test == "out_union":
        ans = test_out_union(path)
    elif test == "in_union":
        ans = test_in_union(path)
    if not ans:
        sys.exit(1)


if __name__ == "__main__":
    main()
