#![allow(clippy::unreadable_literal)]
#![allow(clippy::float_cmp)]
#![allow(clippy::many_single_char_names)]

mod base;
mod complex2;
mod scalgoproto;
mod union;

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
            return Err(scalgoproto::Error::InvalidPointer());
        }
    }};
}

macro_rules! require_none {
    ( $x:expr ) => {{
        if $x.is_some() {
            println!("Error {} should yield None", stringify!($x),);
            return Err(scalgoproto::Error::InvalidPointer());
        }
    }};
}

macro_rules! require_some {
    ( $x:expr) => {{
        match $x {
            None => {
                println!("Error {} should yield Some", stringify!($x),);
                return Err(scalgoproto::Error::InvalidPointer());
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
                return Err(scalgoproto::Error::InvalidPointer());
            }
        }
    }};
}

macro_rules! require_one_list {
    ( $x:expr) => {{
        if $x.len() != 1 {
            println!("Error {} should have length 1", stringify!($x),);
            return Err(scalgoproto::Error::InvalidPointer());
        }
        $x.get(0)
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

fn validate_out(data: &[u8], path: &str) -> scalgoproto::Result<()> {
    let exp = std::fs::read(path).expect("Unable to read file");
    if exp == data {
        return Ok(());
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
    Err(scalgoproto::Error::InvalidPointer())
}

fn test_out_default(path: &str) -> scalgoproto::Result<()> {
    let arena = scalgoproto::Arena::new(vec![]);
    let mut writer = scalgoproto::Writer::new(&arena);
    writer.add_root::<base::Simple>();
    let data = arena.finalize();
    validate_out(&data, path)
}

fn test_in_default(path: &str) -> scalgoproto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let s = scalgoproto::read_message::<base::Simple>(&data)?;
    require!(s.e(), None);
    require!(s.s().e(), Some(base::MyEnum::A));
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

fn test_out(path: &str) -> scalgoproto::Result<()> {
    let arena = scalgoproto::Arena::new(vec![]);
    let mut writer = scalgoproto::Writer::new(&arena);
    let mut s = writer.add_root::<base::Simple>();
    s.e(Some(base::MyEnum::C));
    let mut ss = s.s();
    ss.e(Some(base::MyEnum::D));
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
    let data = arena.finalize();
    validate_out(&data, path)
}

fn test_in(path: &str) -> scalgoproto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let s = scalgoproto::read_message::<base::Simple>(&data)?;
    require!(s.e(), Some(base::MyEnum::C));
    require!(s.s().e(), Some(base::MyEnum::D));
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

fn test_out_complex(path: &str) -> scalgoproto::Result<()> {
    let arena = scalgoproto::Arena::new(vec![]);
    let mut writer = scalgoproto::Writer::new(&arena);

    let mut m = writer.add_table::<base::Member>();
    m.id(42);

    let mut l = writer.add_i32_list(31);
    for i in 0..31 {
        l.set(i, 100 - 2 * (i) as i32);
    }

    let mut l2 = writer.add_enum_list::<base::MyEnum>(2);
    l2.set(0, Some(base::MyEnum::A));

    let l3 = writer.add_struct_list::<base::MyStruct>(1);

    let b = writer.add_bytes(b"bytes");
    let t = writer.add_text("text");

    let mut l4 = writer.add_text_list(200);
    for i in (1..200).step_by(2) {
        l4.add(i, "HI THERE");
    }

    let mut l5 = writer.add_bytes_list(1);
    l5.set(0, Some(&b));

    let mut l6 = writer.add_table_list::<base::Member>(3);
    l6.set(0, Some(&m));
    l6.set(2, Some(&m));

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

    let mut s = writer.add_root::<base::Complex>();
    s.set_member(Some(&m));
    s.set_text(Some(&t));
    s.set_my_bytes(Some(&b));
    s.set_int_list(Some(&l));
    s.set_struct_list(Some(&l3));
    s.set_enum_list(Some(&l2));
    s.set_text_list(Some(&l4));
    s.set_bytes_list(Some(&l5));
    s.set_member_list(Some(&l6));
    s.set_f32list(Some(&l7));
    s.set_f64list(Some(&l8));
    s.set_u8list(Some(&l9));
    s.set_blist(Some(&l10));
    let data = arena.finalize();
    validate_out(&data, path)
}

fn test_in_complex(path: &str) -> scalgoproto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let s = scalgoproto::read_message::<base::Complex>(&data)?;
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
    require!(l.get(0), Some(base::MyEnum::A));
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
        .iter(),
    ) {
        require!(v, *e);
    }
    Ok(())
}

fn test_out_complex2(path: &str) -> scalgoproto::Result<()> {
    let arena = scalgoproto::Arena::new(vec![]);
    let mut writer = scalgoproto::Writer::new(&arena);

    let mut m = writer.add_table::<base::Member>();
    m.id(42);
    let b = writer.add_bytes(b"bytes");
    let t = writer.add_text("text");

    let mut l = writer.add_enum_list::<base::NamedUnionEnumList>(2);
    l.set(0, Some(base::NamedUnionEnumList::X));
    l.set(1, Some(base::NamedUnionEnumList::Z));

    let mut l2 = writer.add_struct_list::<complex2::Complex2L>(1);
    let mut c = l2.get(0);
    c.a(2);
    c.b(true);

    let mut l3 = writer.add_union_list::<base::NamedUnion>(2);
    l3.get(0).set_text(&t);
    l3.get(1).set_my_bytes(&b);

    let mut r = writer.add_root::<complex2::Complex2>();
    r.u1().set_member(&m);
    r.u2().set_text(&t);
    r.u3().set_my_bytes(&b);
    r.u4().set_enum_list(&l);
    r.u5().add_a();
    r.add_hat().id(43);
    r.set_l(Some(&l2));
    r.s().x(Some(complex2::Complex2SX::P));
    r.s().y().z(8);
    r.set_l2(Some(&l3));
    let data = arena.finalize();
    validate_out(&data, path)
}

fn test_in_complex2(path: &str) -> scalgoproto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let s = scalgoproto::read_message::<complex2::Complex2>(&data)?;
    require!(
        require_enum!(ce!(s.u1()), base::NamedUnionIn::Member(v), v).id(),
        42
    );
    require!(
        require_enum!(ce!(s.u2()), base::NamedUnionIn::Text(v), v),
        "text"
    );
    require!(
        require_enum!(ce!(s.u3()), base::NamedUnionIn::MyBytes(v), v),
        b"bytes"
    );
    let l = require_enum!(ce!(s.u4()), base::NamedUnionIn::EnumList(v), v);
    require!(l.len(), 2);
    require!(l.get(0), Some(base::NamedUnionEnumList::X));
    require!(l.get(1), Some(base::NamedUnionEnumList::Z));
    require_enum!(ce!(s.u5()), complex2::Complex2U5In::A(v), v);
    require!(require_some!(ce!(s.hat())).id(), 43);
    let i = require_one_list!(require_some!(ce!(s.l())));
    require!(i.a(), 2);
    require!(i.b(), true);
    require!(s.s().x(), Some(complex2::Complex2SX::P));
    require!(s.s().y().z(), 8);
    Ok(())
}

fn test_out_inplace(path: &str) -> scalgoproto::Result<()> {
    let arena = scalgoproto::Arena::new(vec![]);
    let mut writer = scalgoproto::Writer::new(&arena);

    let name = writer.add_text("nilson");
    let mut u = writer.add_table::<base::InplaceUnion>();
    u.u().add_monkey().set_name(Some(&name));

    let mut u2 = writer.add_table::<base::InplaceUnion>();
    u2.u().add_text().add_t("foobar");

    let mut t = writer.add_table::<base::InplaceText>();
    t.id(45);
    t.add_t("cake");

    let mut b = writer.add_table::<base::InplaceBytes>();
    b.id(46);
    b.add_b(b"hi");

    let mut l = writer.add_table::<base::InplaceList>();
    l.id(47);
    let mut ll = l.add_l(2);
    ll.set(0, 24);
    ll.set(1, 99);

    let mut root = writer.add_root::<base::InplaceRoot>();
    root.set_u(Some(&u));
    root.set_u2(Some(&u2));
    root.set_t(Some(&t));
    root.set_b(Some(&b));
    root.set_l(Some(&l));
    let data = arena.finalize();
    validate_out(&data, path)
}

fn test_in_inplace(path: &str) -> scalgoproto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let s = scalgoproto::read_message::<base::InplaceRoot>(&data)?;

    let u = require_some!(ce!(s.u()));
    let v = require_enum!(ce!(u.u()), base::InplaceUnionUIn::Monkey(v), v);
    require!(ce!(v.name()), Some("nilson"));
    let u = require_some!(ce!(s.u2()));
    let v = require_enum!(ce!(u.u()), base::InplaceUnionUIn::Text(v), v);
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

fn test_out_extend1(path: &str) -> scalgoproto::Result<()> {
    let arena = scalgoproto::Arena::new(vec![]);
    let mut writer = scalgoproto::Writer::new(&arena);
    let mut o = writer.add_root::<base::Gen1>();
    o.aa(77);
    let data = arena.finalize();
    validate_out(&data, path)
}

fn test_in_extend1(path: &str) -> scalgoproto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let s = scalgoproto::read_message::<base::Gen2>(&data)?;
    require!(s.aa(), 77);
    require!(s.bb(), 42);
    require_enum!(ce!(s.u()), base::Gen2UIn::NONE, ());
    Ok(())
}

fn test_out_extend2(path: &str) -> scalgoproto::Result<()> {
    let arena = scalgoproto::Arena::new(vec![]);
    let mut writer = scalgoproto::Writer::new(&arena);
    let mut o = writer.add_root::<base::Gen2>();
    o.aa(80);
    o.bb(81);
    let mut cake = o.u().add_cake();
    cake.v(45);
    let data = arena.finalize();
    validate_out(&data, path)
}

fn test_in_extend2(path: &str) -> scalgoproto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let s = scalgoproto::read_message::<base::Gen3>(&data)?;
    require!(s.aa(), 80);
    require!(s.bb(), 81);
    require!(
        require_enum!(ce!(s.u()), base::Gen3UIn::Cake(cake), cake).v(),
        45
    );
    require!(s.e(), Some(base::MyEnum::C));
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

fn test_out_union(path: &str) -> scalgoproto::Result<()> {
    let data = {
        let arena = scalgoproto::Arena::new(vec![]);
        let mut writer = scalgoproto::Writer::new(&arena);
        let mut root = writer.add_root::<union::Table3>();

        let mut v1 = root.add_v1();
        v1.a().add_v1("ctext1");
        v1.b().add_v1("ctext2");

        let mut v2 = root.add_v2();
        v2.a().add_v2(b"cbytes1");
        v2.b().add_v2(b"cbytes2");

        let mut v3 = root.add_v3();
        v3.a().add_v3().a(101);
        v3.b().add_v3().a(102);

        let mut v4 = root.add_v4();
        v4.a().add_v4().a(103);
        v4.b().add_v4().a(104);

        let mut v5 = root.add_v5();
        v5.a().add_v5(1).add(0, "ctext3");
        v5.b().add_v5(1).add(0, "ctext4");

        let mut v6 = root.add_v6();
        v6.a().add_v6(1).add(0, b"cbytes3");
        v6.b().add_v6(1).add(0, b"cbytes4");

        let mut v7 = root.add_v7();
        v7.a().add_v7(1).add(0).a(105);
        v7.b().add_v7(1).add(0).a(106);

        let mut v8 = root.add_v8();
        v8.a().add_v8(1).add(0).a(107);
        v8.b().add_v8(1).add(0).a(108);

        let mut v9 = root.add_v9();
        v9.a().add_v9(1).set(0, 109);
        v9.b().add_v9(1).set(0, 110);

        let mut v10 = root.add_v10();
        v10.a().add_v10(1).set(0, true);
        v10.b().add_v10(1).set(0, true);
        arena.finalize()
    };
    let s = scalgoproto::read_message::<union::Table3>(&data)?;

    let arena = scalgoproto::Arena::new(vec![]);
    let mut writer = scalgoproto::Writer::new(&arena);
    let mut root = writer.add_root::<union::Table3>();

    let mut v1 = root.add_v1();
    let iv1 = require_some!(ce!(s.v1()));
    v1.a().add_v1("text1");
    v1.b().add_v1("text2");
    v1.c().set_v1(&writer.add_text("text3"));
    v1.d()
        .add_v1(require_enum!(ce!(iv1.a()), union::Union1In::V1(v), v));
    v1.e()
        .add_v1(require_enum!(ce!(iv1.b()), union::Union1In::V1(v), v));

    let mut v2 = root.add_v2();
    let iv2 = require_some!(ce!(s.v2()));
    v2.a().add_v2(b"bytes1");
    v2.b().add_v2(b"bytes2");
    v2.c().set_v2(&writer.add_bytes(b"bytes3"));
    v2.d()
        .add_v2(require_enum!(ce!(iv2.a()), union::Union1In::V2(v), v));
    v2.e()
        .add_v2(require_enum!(ce!(iv2.b()), union::Union1In::V2(v), v));

    let mut v3 = root.add_v3();
    let iv3 = require_some!(ce!(s.v3()));
    v3.a().add_v3().a(1);
    v3.b().add_v3().a(2);
    let mut t3 = writer.add_table::<union::Table1>();
    t3.a(3);
    v3.c().set_v3(&t3);
    ce!(v3
        .d()
        .copy_v3(require_enum!(ce!(iv3.a()), union::Union1In::V3(v), v)));
    ce!(v3
        .e()
        .copy_v3(require_enum!(ce!(iv3.b()), union::Union1In::V3(v), v)));

    let mut v4 = root.add_v4();
    let iv4 = require_some!(ce!(s.v4()));
    v4.a().add_v4().a(4);
    v4.b().add_v4().a(5);
    let mut t4 = writer.add_table::<union::Union1V4>();
    t4.a(6);
    v4.c().set_v4(&t4);
    ce!(v4
        .d()
        .copy_v4(require_enum!(ce!(iv4.a()), union::Union1In::V4(v), v)));
    ce!(v4
        .e()
        .copy_v4(require_enum!(ce!(iv4.b()), union::Union1In::V4(v), v)));

    let mut v5 = root.add_v5();
    let iv5 = require_some!(ce!(s.v5()));
    v5.a().add_v5(1).add(0, "text4");
    v5.b().add_v5(1).add(0, "text5");
    let mut t5 = writer.add_text_list(1);
    t5.add(0, "text6");
    v5.c().set_v5(&t5);
    ce!(v5
        .d()
        .copy_v5(require_enum!(ce!(iv5.a()), union::Union1In::V5(v), v)));
    ce!(v5
        .e()
        .copy_v5(require_enum!(ce!(iv5.b()), union::Union1In::V5(v), v)));

    let mut v6 = root.add_v6();
    let iv6 = require_some!(ce!(s.v6()));
    v6.a().add_v6(1).add(0, b"bytes4");
    let mut tt6 = v6.b().add_v6(1);
    tt6.set(0, Some(&writer.add_bytes(b"bytes5")));
    let mut t6 = writer.add_bytes_list(1);
    t6.set(0, Some(&writer.add_bytes(b"bytes6")));
    v6.c().set_v6(&t6);
    ce!(v6
        .d()
        .copy_v6(require_enum!(ce!(iv6.a()), union::Union1In::V6(v), v)));
    ce!(v6
        .e()
        .copy_v6(require_enum!(ce!(iv6.b()), union::Union1In::V6(v), v)));

    let mut v7 = root.add_v7();
    let iv7 = require_some!(ce!(s.v7()));
    v7.a().add_v7(1).add(0).a(7);
    v7.b().add_v7(1).add(0).a(8);
    let mut t7 = writer.add_table_list::<union::Table1>(1);
    t7.add(0).a(9);
    v7.c().set_v7(&t7);
    ce!(v7
        .d()
        .copy_v7(require_enum!(ce!(iv7.a()), union::Union1In::V7(v), v)));
    ce!(v7
        .e()
        .copy_v7(require_enum!(ce!(iv7.b()), union::Union1In::V7(v), v)));

    let mut v8 = root.add_v8();
    let iv8 = require_some!(ce!(s.v8()));
    v8.a().add_v8(1).add(0).a(10);
    v8.b().add_v8(1).add(0).a(11);
    let mut t8 = writer.add_table_list::<union::Union1V8>(1);
    t8.add(0).a(12);
    v8.c().set_v8(&t8);
    ce!(v8
        .d()
        .copy_v8(require_enum!(ce!(iv8.a()), union::Union1In::V8(v), v)));
    ce!(v8
        .e()
        .copy_v8(require_enum!(ce!(iv8.b()), union::Union1In::V8(v), v)));

    let mut v9 = root.add_v9();
    let iv9 = require_some!(ce!(s.v9()));
    v9.a().add_v9(1).set(0, 13);
    v9.b().add_v9(1).set(0, 14);
    let mut t9 = writer.add_u32_list(1);
    t9.set(0, 15);
    v9.c().set_v9(&t9);
    ce!(v9
        .d()
        .copy_v9(require_enum!(ce!(iv9.a()), union::Union1In::V9(v), v)));
    ce!(v9
        .e()
        .copy_v9(require_enum!(ce!(iv9.b()), union::Union1In::V9(v), v)));

    let mut v10 = root.add_v10();
    let iv10 = require_some!(ce!(s.v10()));
    v10.a().add_v10(1).set(0, true);
    v10.b().add_v10(1).set(0, false);
    let mut t10 = writer.add_bool_list(1);
    t10.set(0, true);
    v10.c().set_v10(&t10);
    ce!(v10
        .d()
        .copy_v10(require_enum!(ce!(iv10.a()), union::Union1In::V10(v), v)));
    ce!(v10
        .e()
        .copy_v10(require_enum!(ce!(iv10.b()), union::Union1In::V10(v), v)));

    let data = arena.finalize();
    validate_out(&data, path)
}

fn test_in_union(path: &str) -> scalgoproto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let i = scalgoproto::read_message::<union::Table3>(&data)?;

    let v1 = require_some!(ce!(i.v1()));
    require!(
        require_enum!(ce!(v1.a()), union::Union1In::V1(s), s),
        "text1"
    );
    require!(
        require_enum!(ce!(v1.b()), union::Union1In::V1(s), s),
        "text2"
    );
    require!(
        require_enum!(ce!(v1.c()), union::Union1In::V1(s), s),
        "text3"
    );
    require!(
        require_enum!(ce!(v1.d()), union::Union1In::V1(s), s),
        "ctext1"
    );
    require!(
        require_enum!(ce!(v1.e()), union::Union1In::V1(s), s),
        "ctext2"
    );

    let v2 = require_some!(ce!(i.v2()));
    require!(
        require_enum!(ce!(v2.a()), union::Union1In::V2(b), b),
        b"bytes1"
    );
    require!(
        require_enum!(ce!(v2.b()), union::Union1In::V2(b), b),
        b"bytes2"
    );
    require!(
        require_enum!(ce!(v2.c()), union::Union1In::V2(b), b),
        b"bytes3"
    );
    require!(
        require_enum!(ce!(v2.d()), union::Union1In::V2(b), b),
        b"cbytes1"
    );
    require!(
        require_enum!(ce!(v2.e()), union::Union1In::V2(b), b),
        b"cbytes2"
    );

    let v3 = require_some!(ce!(i.v3()));
    require!(require_enum!(ce!(v3.a()), union::Union1In::V3(v), v).a(), 1);
    require!(require_enum!(ce!(v3.b()), union::Union1In::V3(v), v).a(), 2);
    require!(require_enum!(ce!(v3.c()), union::Union1In::V3(v), v).a(), 3);
    require!(
        require_enum!(ce!(v3.d()), union::Union1In::V3(v), v).a(),
        101
    );
    require!(
        require_enum!(ce!(v3.e()), union::Union1In::V3(v), v).a(),
        102
    );

    let v4 = require_some!(ce!(i.v4()));
    require!(require_enum!(ce!(v4.a()), union::Union1In::V4(v), v).a(), 4);
    require!(require_enum!(ce!(v4.b()), union::Union1In::V4(v), v).a(), 5);
    require!(require_enum!(ce!(v4.c()), union::Union1In::V4(v), v).a(), 6);
    require!(
        require_enum!(ce!(v4.d()), union::Union1In::V4(v), v).a(),
        103
    );
    require!(
        require_enum!(ce!(v4.e()), union::Union1In::V4(v), v).a(),
        104
    );

    let v5 = require_some!(ce!(i.v5()));
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v5.a()),
            union::Union1In::V5(v),
            v
        )))),
        "text4"
    );
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v5.b()),
            union::Union1In::V5(v),
            v
        )))),
        "text5"
    );
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v5.c()),
            union::Union1In::V5(v),
            v
        )))),
        "text6"
    );
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v5.d()),
            union::Union1In::V5(v),
            v
        )))),
        "ctext3"
    );
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v5.e()),
            union::Union1In::V5(v),
            v
        )))),
        "ctext4"
    );

    let v6 = require_some!(ce!(i.v6()));
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v6.a()),
            union::Union1In::V6(v),
            v
        )))),
        b"bytes4"
    );
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v6.b()),
            union::Union1In::V6(v),
            v
        )))),
        b"bytes5"
    );
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v6.c()),
            union::Union1In::V6(v),
            v
        )))),
        b"bytes6"
    );
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v6.d()),
            union::Union1In::V6(v),
            v
        )))),
        b"cbytes3"
    );
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v6.e()),
            union::Union1In::V6(v),
            v
        )))),
        b"cbytes4"
    );

    let v7 = require_some!(ce!(i.v7()));
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v7.a()),
            union::Union1In::V7(v),
            v
        ))))
        .a(),
        7
    );
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v7.b()),
            union::Union1In::V7(v),
            v
        ))))
        .a(),
        8
    );
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v7.c()),
            union::Union1In::V7(v),
            v
        ))))
        .a(),
        9
    );
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v7.d()),
            union::Union1In::V7(v),
            v
        ))))
        .a(),
        105
    );
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v7.e()),
            union::Union1In::V7(v),
            v
        ))))
        .a(),
        106
    );

    let v8 = require_some!(ce!(i.v8()));
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v8.a()),
            union::Union1In::V8(v),
            v
        ))))
        .a(),
        10
    );
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v8.b()),
            union::Union1In::V8(v),
            v
        ))))
        .a(),
        11
    );
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v8.c()),
            union::Union1In::V8(v),
            v
        ))))
        .a(),
        12
    );
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v8.d()),
            union::Union1In::V8(v),
            v
        ))))
        .a(),
        107
    );
    require!(
        require_some!(ce!(require_one_list!(require_enum!(
            ce!(v8.e()),
            union::Union1In::V8(v),
            v
        ))))
        .a(),
        108
    );

    let v9 = require_some!(ce!(i.v9()));
    require!(
        require_one_list!(require_enum!(ce!(v9.a()), union::Union1In::V9(v), v)),
        13
    );
    require!(
        require_one_list!(require_enum!(ce!(v9.b()), union::Union1In::V9(v), v)),
        14
    );
    require!(
        require_one_list!(require_enum!(ce!(v9.c()), union::Union1In::V9(v), v)),
        15
    );
    require!(
        require_one_list!(require_enum!(ce!(v9.d()), union::Union1In::V9(v), v)),
        109
    );
    require!(
        require_one_list!(require_enum!(ce!(v9.e()), union::Union1In::V9(v), v)),
        110
    );

    let v10 = require_some!(ce!(i.v10()));
    require!(
        require_one_list!(require_enum!(ce!(v10.a()), union::Union1In::V10(v), v)),
        true
    );
    require!(
        require_one_list!(require_enum!(ce!(v10.b()), union::Union1In::V10(v), v)),
        false
    );
    require!(
        require_one_list!(require_enum!(ce!(v10.c()), union::Union1In::V10(v), v)),
        true
    );
    require!(
        require_one_list!(require_enum!(ce!(v10.d()), union::Union1In::V10(v), v)),
        true
    );
    require!(
        require_one_list!(require_enum!(ce!(v10.e()), union::Union1In::V10(v), v)),
        true
    );

    Ok(())
}

fn main() {
    if test_out_default("test/simple_default.bin").is_err() {
        println!("test_out_default failed");
    }
    if test_in_default("test/simple_default.bin").is_err() {
        println!("test_in_default failed");
    }
    if test_out("test/simple.bin").is_err() {
        println!("test_out failed");
    }
    if test_in("test/simple.bin").is_err() {
        println!("test_in_failed");
    }

    if test_out_complex("test/complex.bin").is_err() {
        println!("test_out_complex failed");
    }
    if test_in_complex("test/complex.bin").is_err() {
        println!("test_in_complex failed");
    }

    if test_out_complex2("test/complex2.bin").is_err() {
        println!("test_out_complex2 failed");
    }
    if test_in_complex2("test/complex2.bin").is_err() {
        println!("test_in_complex2 failed");
    }

    if test_out_inplace("test/inplace.bin").is_err() {
        println!("test_out_inplace failed");
    }
    if test_in_inplace("test/inplace.bin").is_err() {
        println!("test_in_inplace failed");
    }

    if test_out_extend1("test/extend1.bin").is_err() {
        println!("test_out_extend1 failed");
    }
    if test_in_extend1("test/extend1.bin").is_err() {
        println!("test_in_extend1 failed");
    }

    if test_out_extend2("test/extend2.bin").is_err() {
        println!("test_out_extend2 failed");
    }
    if test_in_extend2("test/extend2.bin").is_err() {
        println!("test_in_extend2 failed");
    }

    if test_out_union("test/union.bin").is_err() {
        println!("test_out_union failed");
    }
    if test_in_union("test/union.bin").is_err() {
        println!("test_in_union failed");
    }

    println!("Tests done")
}
