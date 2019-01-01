# -*- mode: python; tab-width: 4; indent-tabs-mode: nil; python-indent-offset: 4; coding: utf-8 -*-
import sys
import scalgoproto
import union
from test_base import require, read_in, validate_out, get_v

def for_copy() -> union.Table3In:
    w = scalgoproto.Writer()
    root = w.construct_table(union.Table3Out)

    v1 = root.add_v1()
    v1.a.v1 = "text1"
    v1.b.v1 = "text2"

    v2 = root.add_v2()
    #v2.a.v2 = b"bytes1"
    v2.b.v2 = b"bytes2"

    v3 = root.add_v3()
    v3.a.add_v3().a = 1
    v3.b.add_v3().a = 2

    v4 = root.add_v4()
    v4.a.add_v4().a = 3
    v4.b.add_v4().a = 4

    v5 = root.add_v5()
    v5.a.add_v5(1)[0] = "text3"
    #v5.b.add_v5(1)[0] = "text4"

    v6 = root.add_v6()
    # v6.a.add_v6(1)[0] = b"bytes3"
    # v6.b.add_v6(1)[0] = b"bytes4"

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
    # v2.a.v2 = b"bytes1"
    # v2.b.v2 = b"bytes2"
    # v2.c.v2 = w.construct_bytes(b"bytes3")
    # v2.d.v2 = i.v2.a.v2
    # v2.e.v2 = i.v2.b.v2
    
    v3 = root.add_v3()
    v3.a.add_v3().a = 1
    v3.b.add_v3().a = 2
    t1 = w.construct_table(union.Table1Out)
    t1.a = 3
    v3.c.v3 = t1 
    v3.d.v3 = i.v3.a.v3
    v3.e.v3 = i.v3.b.v3
    
    v4 = root.add_v4()
    v4.a.add_v4().a = 3
    v4.b.add_v4().a = 4
    t2 = w.construct_table(union.Union1V4Out)
    t2.a = 4
    v4.c.v4 = t2
    
    v5 = root.add_v5()
    v5.a.add_v5(1)[0] = "text4"
    #v5.b.add_v5(1)[0] = "text5"
    t3 = w.construct_text_list(1)
    t3[0] = "text6"
    v5.c.v5 = t3
    v5.d.v5 = i.v5.a.v5
    #v5.e.v5 = i.v5.b.v5
    
    v6 = root.add_v6()
    #v6.a.add_v6(1)[0] = b"bytes4"
    #v6.b.add_v6(1)[0] = w.construct_bytes(b"bytes5")
    t4 = w.construct_bytes_list(1)
    t4[0] = w.construct_bytes(b"bytes6")
    v6.c.v6 = t4
    #v6.d.v6 = i.v6.a.v6
    #v6.e.v6 = i.v6.b.v6
    
    data = w.finalize(root)
    return validate_out(data, path)


def test_in_union(path: str) -> bool:
    # o = read_in(path)
    # r = scalgoproto.Reader(o)
    # s = r.root(base.Gen3In)
    # if require(s.aa, 80):
    #     return False
    # if require(s.bb, 81):
    #     return False
    # if require(s.u.is_cake, True):
    #     return False
    # if require(s.u.cake.v, 45):
    #     return False
    # if require(s.e, base.MyEnum.c):
    #     return False
    # if require(s.s.x, 0):
    #     return False
    # if require(s.s.y, 0):
    #     return False
    # if require(s.s.z, 0):
    #     return False
    # if require(s.b, False):
    #     return False
    # if require(s.u8, 2):
    #     return False
    # if require(s.u16, 3):
    #     return False
    # if require(s.u32, 4):
    #     return False
    # if require(s.u64, 5):
    #     return False
    # if require(s.i8, 6):
    #     return False
    # if require(s.i16, 7):
    #     return False
    # if require(s.i32, 8):
    #     return False
    # if require(s.i64, 9):
    #     return False
    # if require(s.f, 10):
    #     return False
    # if require(s.d, 11):
    #     return False
    # if require(s.has_os, False):
    #     return False
    # if require(s.has_ob, False):
    #     return False
    # if require(s.has_ou8, False):
    #     return False
    # if require(s.has_ou16, False):
    #     return False
    # if require(s.has_ou32, False):
    #     return False
    # if require(s.has_ou64, False):
    #     return False
    # if require(s.has_oi8, False):
    #     return False
    # if require(s.has_oi16, False):
    #     return False
    # if require(s.has_oi32, False):
    #     return False
    # if require(s.has_oi64, False):
    #     return False
    # if require(s.has_of, False):
    #     return False
    # if require(s.has_od, False):
    #     return False
    # if require(s.has_member, False):
    #     return False
    # if require(s.has_text, False):
    #     return False
    # if require(s.has_mbytes, False):
    #     return False
    # if require(s.has_int_list, False):
    #     return False
    # if require(s.has_enum_list, False):
    #     return False
    # if require(s.has_struct_list, False):
    #     return False
    # if require(s.has_text_list, False):
    #     return False
    # if require(s.has_bytes_list, False):
    #     return False
    # if require(s.has_member_list, False):
    #     return False
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
