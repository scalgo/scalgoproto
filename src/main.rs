mod scalgo_proto;
mod simple;

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
                Some(v) => print!("."),
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
                Some(v) => print!("."),
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
    match s.os() {
        Some(v) => return Err(scalgo_proto::Error::InvalidPointer()),
        None => (),
    };
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
    match s.ns() {
        Some(v) => return Err(scalgo_proto::Error::InvalidPointer()),
        None => (),
    };
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
    match s.os() {
        Some(v) => {
            require!(v.x(), 43);
            require!(v.y(), 28.0);
            require!(v.z(), false);
        }
        None => return Err(scalgo_proto::Error::InvalidPointer()),
    };
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
    match s.ns() {
        Some(v) => return Err(scalgo_proto::Error::InvalidPointer()),
        None => (),
    };
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

fn main() {
    if !test_out_default("test/simple_default.bin") {
        println!("test_out_default failed");
    };
    if let Err(_) = test_in_default("test/simple_default.bin") {
        println!("test_in_default failed");
    };

    if !test_out("test/simple.bin") {
        println!("test_out failed");
    };
    if let Err(_) = test_in("test/simple.bin") {
        println!("test_in_failed");
    };
    println!("Tests done")
}
