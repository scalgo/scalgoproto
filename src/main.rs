mod scalgo_proto;
mod simple;

macro_rules! require {
    ( $x:expr, $y:expr ) => {{
        let got = $x;
        let expected = $y;
        if got != expected {
            println!(
                "Error {} gave {:?} expected {:?} ({})",
                stringify!($x),
                got,
                expected,
                stringify!($y)
            );
            return Err(scalgo_proto::Error::InvalidPointer());
        }
    }};
}

macro_rules! require_none {
    ( $x:expr ) => {{
        if let Some(_) = $x {
            println!("Error {} should yield None", stringify!($x),);
            return Err(scalgo_proto::Error::InvalidPointer());
        }
    }};
}

macro_rules! require_some {
    ( $x:expr) => {{
        match $x {
            None => {
                println!("Error {} should yield Some", stringify!($x),);
                return Err(scalgo_proto::Error::InvalidPointer());
            }
            Some(v) => v,
        }
    }};
}

macro_rules! require_enum {
    ( $x:expr, $y:pat, $z:expr) => {{
        let x = $x;
        match x {
            $y => $z,
            _ => {
                println!("Error {} should yield {}", stringify!($x), stringify!($y));
                return Err(scalgo_proto::Error::InvalidPointer());
            }
        }
    }};
}

macro_rules! ce {
    ( $x: expr ) => {{
        match $x {
            Ok(v) => v,
            Err(e) => {
                println!("Error {} failed {:?}", stringify!($x), e);
                return Err(e);
            }
        }
    }};
}

fn validate_out(data: &[u8], path: &str) -> bool {
    let exp = std::fs::read(path).expect("Unable to read file");
    if exp == data {
        return true;
    }
    println!("Wrong output");
    for i in (0..usize::max(data.len(), exp.len())).step_by(16) {
        print!("{:08X} | ", i);
        for j in i..i + 16 {
            if exp.get(j) == data.get(j) {
                print!("\x1b[0m");
            } else {
                print!("\x1b[92m");
            }
            match exp.get(j) {
                Some(v) => print!("{:02X}", v),
                None => print!("  "),
            };
            if j % 4 == 3 {
                print!(" ")
            }
        }
        print!("\x1b[0m| ");
        for j in i..i + 16 {
            if exp.get(j) == data.get(j) {
                print!("\x1b[0m");
            } else {
                print!("\x1b[91m");
            }
            match data.get(j) {
                Some(v) => print!("{:02X}", v),
                None => print!("  "),
            };
            if j % 4 == 3 {
                print!(" ")
            }
        }
        print!("\x1b[0m| ");
        for j in i..i + 16 {
            if exp.get(j) == data.get(j) {
                print!("\x1b[0m");
            } else {
                print!("\x1b[92m");
            }
            match exp.get(j) {
                Some(v) if 32 <= *v && *v <= 126 => print!("{}", *v as char),
                Some(_) => print!("."),
                None => print!(" "),
            };
            if j % 4 == 3 {
                print!(" ")
            }
        }
        print!("\x1b[0m| ");
        for j in i..i + 16 {
            if exp.get(j) == data.get(j) {
                print!("\x1b[0m");
            } else {
                print!("\x1b[91m");
            }
            match data.get(j) {
                Some(v) if 32 <= *v && *v <= 126 => print!("{}", *v as char),
                Some(_) => print!("."),
                None => print!(" "),
            };
            if j % 4 == 3 {
                print!(" ")
            }
        }
        println!("\x1b[0m");
    }
    false
}

fn test_out_default(path: &str) -> bool {
    let mut writer = scalgo_proto::Writer::new(1024);
    let mut o = writer.add_table::<simple::Simple>();
    let data = writer.finalize(o);
    return validate_out(data, path);
}

fn test_in_default(path: &str) -> scalgo_proto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let s = scalgo_proto::read_message::<simple::Simple>(&data)?;
    require!(s.e(), None);
    require!(s.s().e(), Some(simple::MyEnum::A));
    require!(s.s().s().x(), 0);
    require!(s.s().s().x(), 0);
    require!(s.s().s().y(), 0.0);
    require!(s.s().s().z(), false);
    require!(s.s().b(), false);
    require!(s.s().u8(), 0);
    require!(s.s().u16(), 0);
    require!(s.s().u32(), 0);
    require!(s.s().u64(), 0);
    require!(s.s().i8(), 0);
    require!(s.s().i16(), 0);
    require!(s.s().i32(), 0);
    require!(s.s().i64(), 0);
    require!(s.s().f(), 0.0);
    require!(s.s().d(), 0.0);
    require!(s.b(), false);
    require!(s.u8(), 2);
    require!(s.u16(), 3);
    require!(s.u32(), 4);
    require!(s.u64(), 5);
    require!(s.i8(), 6);
    require!(s.i16(), 7);
    require!(s.i32(), 8);
    require!(s.i64(), 9);
    require!(s.f(), 10.0);
    require!(s.d(), 11.0);
    require_none!(s.os());
    require!(s.ob(), None);
    require!(s.ou8(), None);
    require!(s.ou16(), None);
    require!(s.ou32(), None);
    require!(s.ou64(), None);
    require!(s.oi8(), None);
    require!(s.oi16(), None);
    require!(s.oi32(), None);
    require!(s.oi64(), None);
    require!(s.of(), None);
    require!(s.od(), None);
    require!(s.ne(), None);
    require_none!(s.ns());
    require!(s.nb(), None);
    require!(s.nu8(), None);
    require!(s.nu16(), None);
    require!(s.nu32(), None);
    require!(s.nu64(), None);
    require!(s.ni8(), None);
    require!(s.ni16(), None);
    require!(s.ni32(), None);
    require!(s.ni64(), None);
    require!(s.nf(), None);
    require!(s.nd(), None);
    Ok(())
}

fn test_out(path: &str) -> bool {
    let mut writer = scalgo_proto::Writer::new(1024);
    let mut s = writer.add_table::<simple::Simple>();
    s.e(Some(simple::MyEnum::C));
    let mut ss = s.s();
    ss.e(Some(simple::MyEnum::D));
    let mut sss = ss.s();
    sss.x(42);
    sss.y(27.0);
    sss.z(true);
    ss.b(false);
    ss.u8(8);
    ss.u16(9);
    ss.u32(10);
    ss.u64(11);
    ss.i8(-8);
    ss.i16(-9);
    ss.i32(-10);
    ss.i64(-11);
    ss.f(27.0);
    ss.d(22.0);
    s.b(true);
    s.u8(242);
    s.u16(4024);
    s.u32(124474);
    s.u64(5465778);
    s.i8(-40);
    s.i16(4025);
    s.i32(124475);
    s.i64(5465779);
    s.f(2.0);
    s.d(3.0);
    let mut ss = s.os();
    ss.x(43);
    ss.y(28.0);
    ss.z(false);
    s.ob(Some(false));
    s.ou8(Some(252));
    s.ou16(Some(4034));
    s.ou32(Some(124464));
    s.ou64(Some(5465768));
    s.oi8(Some(-60));
    s.oi16(Some(4055));
    s.oi32(Some(124465));
    s.oi64(Some(5465729));
    s.of(Some(5.0));
    s.od(Some(6.4));
    let data = writer.finalize(s);
    return validate_out(data, path);
}

fn test_in(path: &str) -> scalgo_proto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let s = scalgo_proto::read_message::<simple::Simple>(&data)?;
    require!(s.e(), Some(simple::MyEnum::C));
    require!(s.s().e(), Some(simple::MyEnum::D));
    require!(s.s().s().x(), 42);
    require!(s.s().s().y(), 27.0);
    require!(s.s().s().z(), true);
    require!(s.s().b(), false);
    require!(s.s().u8(), 8);
    require!(s.s().u16(), 9);
    require!(s.s().u32(), 10);
    require!(s.s().u64(), 11);
    require!(s.s().i8(), -8);
    require!(s.s().i16(), -9);
    require!(s.s().i32(), -10);
    require!(s.s().i64(), -11);
    require!(s.s().f(), 27.0);
    require!(s.s().d(), 22.0);
    require!(s.b(), true);
    require!(s.u8(), 242);
    require!(s.u16(), 4024);
    require!(s.u32(), 124474);
    require!(s.u64(), 5465778);
    require!(s.i8(), -40);
    require!(s.i16(), 4025);
    require!(s.i32(), 124475);
    require!(s.i64(), 5465779);
    require!(s.f(), 2.0);
    require!(s.d(), 3.0);
    let v = require_some!(s.os());
    require!(v.x(), 43);
    require!(v.y(), 28.0);
    require!(v.z(), false);
    require!(s.ob(), Some(false));
    require!(s.ou8(), Some(252));
    require!(s.ou16(), Some(4034));
    require!(s.ou32(), Some(124464));
    require!(s.ou64(), Some(5465768));
    require!(s.oi8(), Some(-60));
    require!(s.oi16(), Some(4055));
    require!(s.oi32(), Some(124465));
    require!(s.oi64(), Some(5465729));
    require!(s.of(), Some(5.0));
    require!(s.od(), Some(6.4));
    require!(s.ne(), None);
    require_none!(s.ns());
    require!(s.nb(), None);
    require!(s.nu8(), None);
    require!(s.nu16(), None);
    require!(s.nu32(), None);
    require!(s.nu64(), None);
    require!(s.ni8(), None);
    require!(s.ni16(), None);
    require!(s.ni32(), None);
    require!(s.ni64(), None);
    require!(s.nf(), None);
    require!(s.nd(), None);
    Ok(())
}

fn test_out_complex(path: &str) -> bool {
    let mut writer = scalgo_proto::Writer::new(1024);

    let mut m = writer.add_table::<simple::Member>();
    m.id(42);

    let mut l = writer.add_i32_list(31);
    for i in 0..31 {
        l.set(i, 100 - 2 * (i) as i32);
    }

    let mut l2 = writer.add_enum_list::<simple::MyEnum>(2);
    l2.set(0, Some(simple::MyEnum::A));

    let mut l3 = writer.add_struct_list::<simple::MyStruct>(1);

    let b = writer.add_bytes(b"bytes");
    let t = writer.add_text("text");

    let mut l4 = writer.add_text_list(200);
    for i in (1..200).step_by(2) {
        l4.add(i, "HI THERE");
    }

    let mut l5 = writer.add_bytes_list(1);
    l5.set(0, Some(b));

    let mut l6 = writer.add_table_list::<simple::Member>(3);
    l6.set(0, Some(m));
    l6.set(2, Some(m));

    let mut l7 = writer.add_f32_list(2);
    l7.set(1, 98.0);

    let mut l8 = writer.add_f64_list(3);
    l8.set(2, 78.0);

    let mut l9 = writer.add_u8_list(2);
    l9.set(0, 4);

    let mut l10 = writer.add_bool_list(10);
    l10.set(0, true);
    l10.set(2, true);
    l10.set(8, true);

    let mut s = writer.add_table::<simple::Complex>();
    s.set_member(Some(m));
    s.set_text(Some(t));
    s.set_my_bytes(Some(b));
    s.set_int_list(Some(l));
    s.set_struct_list(Some(l3));
    s.set_enum_list(Some(l2));
    s.set_text_list(Some(l4));
    s.set_bytes_list(Some(l5));
    s.set_member_list(Some(l6));
    s.set_f32list(Some(l7));
    s.set_f64list(Some(l8));
    s.set_u8list(Some(l9));
    s.set_blist(Some(l10));
    let data = writer.finalize(s);
    return validate_out(data, path);
}

fn test_in_complex(path: &str) -> scalgo_proto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let s = scalgo_proto::read_message::<simple::Complex>(&data)?;
    require_none!(ce!(s.nmember()));
    require_none!(ce!(s.ntext()));
    require_none!(ce!(s.nbytes()));
    require!(ce!(s.text()), Some("text"));
    require!(ce!(s.my_bytes()), Some((b"bytes").as_ref()));
    let m = require_some!(ce!(s.member()));
    require!(m.id(), 42);
    require_none!(ce!(s.nint_list()));
    let l = require_some!(ce!(s.int_list()));
    require!(l.len(), 31);
    for (i, v) in l.iter().enumerate() {
        require!(v, (100 - 2 * i) as i32);
    }
    let l = require_some!(ce!(s.enum_list()));
    require!(l.len(), 2);
    require!(l.get(0), Some(simple::MyEnum::A));
    require!(l.get(1), None);
    let l = require_some!(ce!(s.struct_list()));
    require!(l.len(), 1);
    let l = require_some!(ce!(s.text_list()));
    require!(l.len(), 200);
    for (i, v) in l.iter().enumerate() {
        require!(ce!(v), if i % 2 == 0 { None } else { Some("HI THERE") });
    }
    let l = require_some!(ce!(s.bytes_list()));
    require!(l.len(), 1);
    require!(ce!(l.get(0)), Some((b"bytes").as_ref()));
    let l = require_some!(ce!(s.member_list()));
    require!(l.len(), 3);
    require!(require_some!(ce!(l.get(0))).id(), 42);
    require_none!(ce!(l.get(1)));
    require!(require_some!(ce!(l.get(2))).id(), 42);
    let l = require_some!(ce!(s.f32list()));
    require!(l.len(), 2);
    require!(l.get(0), 0.0);
    require!(l.get(1), 98.0);
    let l = require_some!(ce!(s.f64list()));
    require!(l.len(), 3);
    require!(l.get(0), 0.0);
    require!(l.get(1), 0.0);
    require!(l.get(2), 78.0);
    let l = require_some!(ce!(s.u8list()));
    require!(l.len(), 2);
    require!(l.get(0), 4);
    require!(l.get(1), 0);
    let l = require_some!(ce!(s.blist()));
    require!(l.len(), 10);
    for (v, e) in l.iter().zip(
        [
            true, false, true, false, false, false, false, false, true, false,
        ]
        .into_iter(),
    ) {
        require!(v, *e);
    }
    Ok(())
}

fn test_out_complex2(path: &str) -> bool {
    let mut writer = scalgo_proto::Writer::new(1024);
    let mut m = writer.add_table::<simple::Member>();
    m.id(42);
    let b = writer.add_bytes(b"bytes");
    let t = writer.add_text("text");
    /*
    l = w.construct_enum_list(base.NamedUnionEnumList, 2)
    l[0] = base.NamedUnionEnumList.x
    l[1] = base.NamedUnionEnumList.z

    l2 = w.construct_struct_list(complex2.Complex2L, 1)
    l2[0] = complex2.Complex2L(2, True)

    l3 = w.construct_union_list(base.NamedUnionOut, 2)
    l3[0].text = t
    l3[1].my_bytes = b

    r = w.construct_table(complex2.Complex2Out)
    r.u1.member = m
    r.u2.text = t
    r.u3.my_bytes = b
    r.u4.enum_list = l
    r.u5.add_a()

    m2 = r.add_hat()
    m2.id = 43

    r.l = l2
    r.s = complex2.Complex2S(complex2.Complex2SX.p, complex2.Complex2SY(8))
    r.l2 = l3
    data = w.finalize(r)*/

    false
}

fn test_in_complex2(path: &str) -> scalgo_proto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    /*let s = scalgo_proto::read_message::<simple::Complex2>(&data)?;
        let m = match s.u1() {

        };

        s = r.root(complex2.Complex2In)
        if require(s.u1.is_member, True):
            return False
        if require(s.u1.member.id, 42):
            return False
        if require(s.u2.is_text, True):
            return False
        if require(s.u2.text, "text"):
            return False
        if require(s.u3.is_my_bytes, True):
            return False
        if require(s.u3.my_bytes, b"bytes"):
            return False
        if require(s.u4.is_enum_list, True):
            return False
        l = s.u4.enum_list
        if require(len(l), 2):
            return False
        if require(l[0], base.NamedUnionEnumList.x):
            return False
        if require(l[1], base.NamedUnionEnumList.z):
            return False
        if require(s.u5.is_a, True):
            return False
        if require(s.has_hat, True):
            return False
        if require(s.hat.id, 43):
            return False
        if require(s.has_l, True):
            return False
        l2 = s.l
        if require(len(l2), 1):
            return False
        if require(l2[0].a, 2):
            return False
        if require(l2[0].b, True):
            return False
        if require(s.s.x, complex2.Complex2SX.p):
            return False
        if require(s.s.y.z, 8):
            return False
    */
    Ok(())
}

fn test_out_inplace(path: &str) -> bool {
    let mut writer = scalgo_proto::Writer::new(1024);

    let name = writer.add_text("nilson");
    let u = writer.add_table::<simple::InplaceUnion>();
    //     u.u.add_monkey().name = name

    let u2 = writer.add_table::<simple::InplaceUnion>();
    //     u2.u.add_text().t = "foobar"

    let t = writer.add_table::<simple::InplaceText>();
    t.id(45);
    t.add_t("cake");

    let b = writer.add_table::<simple::InplaceBytes>();
    b.id(46);
    b.add_b(b"hi");

    let l = writer.add_table::<simple::InplaceList>();
    l.id(47);
    //let ll = l.add_l(2);
    //ll[0] = 24
    //ll[1] = 99

    let mut root = writer.add_table::<simple::InplaceRoot>();
    root.set_u(Some(u));
    root.set_u2(Some(u2));
    root.set_t(Some(t));
    root.set_b(Some(b));
    root.set_l(Some(l));
    let data = writer.finalize(root);
    return validate_out(data, path);
}

fn test_in_inplace(path: &str) -> scalgo_proto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let s = scalgo_proto::read_message::<simple::InplaceRoot>(&data)?;

    let u = require_some!(ce!(s.u()));
    let v = require_enum!(ce!(u.u()), simple::InplaceUnionUIn::MONKEY(v), v);
    require!(ce!(v.name()), Some("nilson"));
    let u = require_some!(ce!(s.u2()));
    let v = require_enum!(ce!(u.u()), simple::InplaceUnionUIn::TEXT(v), v);
    require!(ce!(v.t()), Some("foobar"));
    let u = require_some!(ce!(s.t()));
    require!(ce!(u.t()), Some("cake"));
    let b = require_some!(ce!(s.b()));
    require!(b.id(), 46);
    require!(ce!(b.b()), Some(b"hi".as_ref()));
    let l = require_some!(ce!(s.l()));
    require!(l.id(), 47);
    let ll = require_some!(ce!(l.l()));
    require!(ll.len(), 2);
    require!(ll.get(0), 24);
    require!(ll.get(1), 99);
    Ok(())
}

fn test_out_extend1(path: &str) -> bool {
    let mut writer = scalgo_proto::Writer::new(1024);
    let mut o = writer.add_table::<simple::Gen1>();
    o.aa(77);
    let data = writer.finalize(o);
    return validate_out(data, path);
}

fn test_in_extend1(path: &str) -> scalgo_proto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let s = scalgo_proto::read_message::<simple::Gen2>(&data)?;
    require!(s.aa(), 77);
    require!(s.bb(), 42);
    require_enum!(ce!(s.u()), simple::Gen2UIn::NONE, ());
    Ok(())
}

fn test_out_extend2(path: &str) -> bool {
    let mut writer = scalgo_proto::Writer::new(1024);
    let mut o = writer.add_table::<simple::Gen2>();
    o.aa(80);
    o.bb(81);
    //     cake = root.u.add_cake()
    //     cake.v = 45
    let data = writer.finalize(o);
    return validate_out(data, path);
}

fn test_in_extend2(path: &str) -> scalgo_proto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let s = scalgo_proto::read_message::<simple::Gen3>(&data)?;
    require!(s.aa(), 80);
    require!(s.bb(), 81);
    require!(
        require_enum!(ce!(s.u()), simple::Gen3UIn::CAKE(cake), cake).v(),
        45
    );
    require!(s.e(), Some(simple::MyEnum::C));
    require!(s.s().x(), 0);
    require!(s.s().y(), 0.0);
    require!(s.s().z(), false);
    require!(s.b(), false);
    require!(s.u8(), 2);
    require!(s.u16(), 3);
    require!(s.u32(), 4);
    require!(s.u64(), 5);
    require!(s.i8(), 6);
    require!(s.i16(), 7);
    require!(s.i32(), 8);
    require!(s.i64(), 9);
    require!(s.f(), 10.0);
    require!(s.d(), 11.0);
    require_none!(s.os());
    require_none!(s.ob());
    require_none!(s.ou8());
    require_none!(s.ou16());
    require_none!(s.ou32());
    require_none!(s.ou64());
    require_none!(s.oi8());
    require_none!(s.oi16());
    require_none!(s.oi32());
    require_none!(s.oi64());
    require_none!(s.of());
    require_none!(s.od());
    require_none!(ce!(s.member()));
    require_none!(ce!(s.text()));
    require_none!(ce!(s.mbytes()));
    require_none!(ce!(s.int_list()));
    require_none!(ce!(s.enum_list()));
    require_none!(ce!(s.struct_list()));
    require_none!(ce!(s.text_list()));
    require_none!(ce!(s.bytes_list()));
    require_none!(ce!(s.member_list()));
    Ok(())
}

fn main() {
    if !test_out_default("test/simple_default.bin") {
        println!("test_out_default failed");
    }
    if let Err(_) = test_in_default("test/simple_default.bin") {
        println!("test_in_default failed");
    }

    if !test_out("test/simple.bin") {
        println!("test_out failed");
    }
    if let Err(_) = test_in("test/simple.bin") {
        println!("test_in_failed");
    }

    if !test_out_complex("test/complex.bin") {
        println!("test_out_complex failed");
    }
    if let Err(_) = test_in_complex("test/complex.bin") {
        println!("test_in_complex failed");
    }

    if !test_out_complex2("test/complex2.bin") {
        println!("test_out_complex2 failed");
    }
    if let Err(_) = test_in_complex2("test/complex2.bin") {
        println!("test_in_complex2 failed");
    }

    if !test_out_inplace("test/inplace.bin") {
        println!("test_out_inplace failed");
    }
    if let Err(_) = test_in_inplace("test/inplace.bin") {
        println!("test_in_inplace failed");
    }

    if !test_out_extend1("test/extend1.bin") {
        println!("test_out_extend1 failed");
    }
    if let Err(_) = test_in_extend1("test/extend1.bin") {
        println!("test_in_extend1 failed");
    }

    if !test_out_extend2("test/extend2.bin") {
        println!("test_out_extend2 failed");
    }
    if let Err(_) = test_in_extend2("test/extend2.bin") {
        println!("test_in_extend2 failed");
    }
    println!("Tests done")
}
