use crate::scalgo_proto;
use std::fmt;

#[repr(u8)]
#[derive(Copy, Clone, Debug)]
pub enum MyEnum {
    A = 0,
    B = 1,
    C = 2,
    D = 3,
}

pub struct MyStructIn<'a> {
    bytes: &'a [u8; 9],
}
impl<'a> MyStructIn<'a> {
    pub fn x(&self) -> u32 {
        unsafe { scalgo_proto::to_pod(&self.bytes[0..4]) }
    }

    pub fn y(&self) -> f32 {
        unsafe { scalgo_proto::to_pod(&self.bytes[4..8]) }
    }

    pub fn z(&self) -> bool {
        scalgo_proto::to_bool(self.bytes[8])
    }
}
impl<'a> fmt::Debug for MyStructIn<'a> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "MyStruct {{ x: {:?}, y: {:?}, z: {:?} }}",
            self.x(),
            self.y(),
            self.z()
        )
    }
}
struct MyStructInFactory;
impl<'a> scalgo_proto::StructInFactory<'a> for MyStructInFactory {
    type T = MyStructIn<'a>;
    type B = [u8; 9];
    fn new(bytes: &'a Self::B) -> Self::T {
        Self::T { bytes }
    }
}

pub struct MyStructOut<'a> {
    arena: &'a scalgo_proto::Arena,
    offset: usize,
}

impl<'a> MyStructOut<'a> {
    pub fn x(&mut self, v: u32) {
        self.arena.set_pod(self.offset + 0, &v);
    }

    pub fn y(&mut self, v: f32) {
        self.arena.set_pod(self.offset + 4, &v);
    }

    pub fn z(&mut self, v: bool) {
        self.arena.set_bool(self.offset + 8, v);
    }
}

pub struct FullStructIn<'a> {
    bytes: &'a [u8; 53],
}
impl<'a> FullStructIn<'a> {
    fn e(&self) -> Option<MyEnum> {
        unsafe { scalgo_proto::to_enum(self.bytes[0], 4) }
    }
    fn s(&self) -> MyStructIn<'a> {
        unsafe { scalgo_proto::to_struct::<MyStructInFactory>(&self.bytes[1..10]) }
    }
    fn b(&self) -> bool {
        scalgo_proto::to_bool(self.bytes[10])
    }
    fn u8_(&self) -> u8 {
        unsafe { scalgo_proto::to_pod(&self.bytes[11..12]) }
    }
    fn u16_(&self) -> u16 {
        unsafe { scalgo_proto::to_pod(&self.bytes[12..14]) }
    }
    fn u32_(&self) -> u32 {
        unsafe { scalgo_proto::to_pod(&self.bytes[14..18]) }
    }
    fn u64_(&self) -> u64 {
        unsafe { scalgo_proto::to_pod(&self.bytes[18..26]) }
    }
    fn i8_(&self) -> i8 {
        unsafe { scalgo_proto::to_pod(&self.bytes[26..27]) }
    }
    fn i16_(&self) -> i16 {
        unsafe { scalgo_proto::to_pod(&self.bytes[27..29]) }
    }
    fn i32_(&self) -> i32 {
        unsafe { scalgo_proto::to_pod(&self.bytes[29..33]) }
    }
    fn i64_(&self) -> i64 {
        unsafe { scalgo_proto::to_pod(&self.bytes[33..41]) }
    }
    fn f(&self) -> f32 {
        unsafe { scalgo_proto::to_pod(&self.bytes[41..45]) }
    }
    fn d(&self) -> f64 {
        unsafe { scalgo_proto::to_pod(&self.bytes[45..53]) }
    }
}
impl<'a> fmt::Debug for FullStructIn<'a> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "FullStruct {{ e: {:?}, s: {:?}, b: {:?}, u8: {:?}, u16: {:?}, u32: {:?}, u64: {:?}, i8: {:?}, i16: {:?}, i32: {:?}, i64: {:?}, f: {:?}, d: {:?} }}", self.e(), self.s(), self.b(), self.u8_(), self.u16_(), self.u32_(), self.u64_(), self.i8_(), self.i16_(), self.i32_(), self.i64_(), self.f(), self.d())
    }
}
struct FullStructInFactory;
impl<'a> scalgo_proto::StructInFactory<'a> for FullStructInFactory {
    type T = FullStructIn<'a>;
    type B = [u8; 53];
    fn new(bytes: &'a Self::B) -> Self::T {
        Self::T { bytes }
    }
}

pub struct FullStructOut<'a> {
    arena: &'a scalgo_proto::Arena,
    offset: usize,
}

impl<'a> FullStructOut<'a> {
    pub fn e(&mut self, val: Option<MyEnum>) {
        self.arena.set_enum(self.offset + 0, val);
    }
    pub fn s(&self) -> MyStructOut<'a> {
        //TODO this should go through the arena
        return MyStructOut {
            arena: self.arena,
            offset: self.offset + 1,
        };
    }
    pub fn b(&mut self, val: bool) {
        self.arena.set_bool(self.offset + 10, val);
    }
    //MORE CRAPPY FUNCTIONS
}

pub struct SimpleIn<'a> {
    reader: scalgo_proto::Reader<'a>,
}

impl<'a> SimpleIn<'a> {
    fn e(&self) -> Option<MyEnum> {
        self.reader.get_enum::<MyEnum>(0, 4)
    }

    fn s(&self) -> FullStructIn<'a> {
        self.reader.get_struct::<FullStructInFactory>(1)
    }

    fn b(&self) -> bool {
        self.reader.get_bit(54, 0)
    }

    fn u8_(&self) -> u8 {
        self.reader.get_pod::<u8>(55).unwrap_or(2)
    }

    fn u16_(&self) -> u16 {
        self.reader.get_pod::<u16>(56).unwrap_or(3)
    }

    fn u32_(&self) -> u32 {
        self.reader.get_pod::<u32>(58).unwrap_or(4)
    }

    fn u64_(&self) -> u64 {
        self.reader.get_pod::<u64>(62).unwrap_or(5)
    }

    fn i8_(&self) -> i8 {
        self.reader.get_pod::<i8>(70).unwrap_or(6)
    }

    fn i16_(&self) -> i16 {
        self.reader.get_pod::<i16>(71).unwrap_or(7)
    }

    fn i32_(&self) -> i32 {
        self.reader.get_pod::<i32>(73).unwrap_or(8)
    }

    fn i64_(&self) -> i64 {
        self.reader.get_pod::<i64>(77).unwrap_or(9)
    }

    fn f(&self) -> f32 {
        self.reader.get_pod::<f32>(85).unwrap_or(10.0f32)
    }

    fn d(&self) -> f64 {
        self.reader.get_pod::<f64>(89).unwrap_or(11.0f64)
    }

    fn os(&self) -> Option<MyStructIn<'a>> {
        if self.reader.get_bit(54, 1) {
            Some(self.reader.get_struct::<MyStructInFactory>(97))
        } else {
            None
        }
    }

    fn ob(&self) -> Option<bool> {
        if self.reader.get_bit(54, 2) {
            Some(self.reader.get_bit(54, 3))
        } else {
            None
        }
    }

    fn ou8(&self) -> Option<u8> {
        if self.reader.get_bit(54, 4) {
            Some(self.reader.get_pod::<u8>(106).unwrap_or(0))
        } else {
            None
        }
    }

    fn ou16(&self) -> Option<u16> {
        if self.reader.get_bit(54, 5) {
            Some(self.reader.get_pod::<u16>(107).unwrap_or(0))
        } else {
            None
        }
    }

    fn ou32(&self) -> Option<u32> {
        if self.reader.get_bit(54, 6) {
            Some(self.reader.get_pod::<u32>(109).unwrap_or(0))
        } else {
            None
        }
    }
}
impl<'a> fmt::Debug for SimpleIn<'a> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Simple {{ e: {:?}, s: {:?}, b: {:?}, u8: {:?}, u16: {:?}, u32: {:?}, u64: {:?}, i8: {:?}, i16: {:?}, i32: {:?}, i64: {:?}, f: {:?}, d: {:?}, os: {:?}, ob: {:?}, ou8: {:?}, ou16: {:?}, ou32: {:?} }}", 
        self.e(), self.s(), self.b(), self.u8_(), self.u16_(), self.u32_(), self.u64_(), self.i8_(), self.i16_(), self.i32_(), self.i64_(), self.f(), self.d(),
        self.os(), self.ob(), self.ou8(), self.ou16(), self.ou32())
    }
}

pub struct SimpleOut<'a> {
    arena: &'a scalgo_proto::Arena,
    offset: usize,
}
impl<'a> SimpleOut<'a> {
    pub fn e(&mut self, v: Option<MyEnum>) {
        self.arena.set_enum(self.offset + 0, v);
    }

    pub fn s(&self) -> FullStructOut<'a> {
        FullStructOut {
            arena: self.arena,
            offset: self.offset + 1,
        }
    }
}
impl<'a> scalgo_proto::TableOut for SimpleOut<'a> {
    fn offset(&self) -> usize {
        self.offset
    }
}
pub struct Simple {}
impl<'a> scalgo_proto::TableInFactory<'a> for Simple {
    type T = SimpleIn<'a>;
    fn magic() -> u32 {
        0xF0606B0B
    }
    fn new(reader: scalgo_proto::Reader<'a>) -> Self::T {
        Self::T { reader }
    }
}

impl<'a> scalgo_proto::TableOutFactory<'a> for Simple {
    type T = SimpleOut<'a>;
    fn magic() -> u32 {
        0xF0606B0B
    }
    fn size() -> usize {
        444
    }
    fn new(arena: &'a scalgo_proto::Arena, offset: usize) -> Self::T {
        Self::T { arena, offset }
    }
}
