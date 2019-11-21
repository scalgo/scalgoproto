mod scalgo_proto;
mod simple;

fn main() {
    let mut writer = scalgo_proto::Writer::new(1024 * 1024);

    let mut o = writer.add_table::<simple::Simple>();

    o.e(Some(simple::MyEnum::C));

    let mut x = o.s();
    x.e(None);
    x.s().x(22);

    let bytes: &[u8] = writer.finalize(o);

    let si = scalgo_proto::read_message::<simple::Simple>(bytes);

    println!("HI  {:?}", si);

    println!("Hello, world!");
}
