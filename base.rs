#![allow(non_camel_case_types)]

#[repr(u8)]
pub enum MyEnum {
    a = 0,
    b = 1,
    c = 2,
    d = 3,
}

#[repr(C, packed(1))]
pub struct MyStruct {
    pub x: u32,
    pub y: f32,
    pub z: bool,
}

#[repr(C, packed(1))]
pub struct FullStruct {
    pub e: MyEnum,
    pub s: MyStruct,
    pub b: bool,
    pub u8_: u8,
    pub u16_: u16,
    pub u32_: u32,
    pub u64_: u64,
    pub i8_: i8,
    pub i16_: i16,
    pub i32_: i32,
    pub i64_: i64,
    pub f: f32,
    pub d: f64,
}

pub type Result<T> = std::Result<T, ()>;

pub trait ScalgoprotoReader {
    fn slice(&self, offset: usize, size: usize) -> Result<&[u8]>;
    fn ptr(&self, offset: usize, target_size: usize) -> Result<ScalgoprotoReader>;
}

impl<R: ScalgoprotoReader> R {
    fn get_u8(&self, offset: usize) -> Result<u8> {
        self.slice(offset, 1)?[0]
    }

    fn get_bit(&self, offset: usize, bit: usize) -> bool {
        (self.get_u8(offset).unwrap_or(0) >> bit) & 1 == 1
    }

    fn get_48(&self, offset: usize) -> Result<usize> {
        let data = self.slice(offset, 6)?;
        let target = &mut [0u64];
        unsafe {
            std::mem::transmute(target)[..6].clone_from_slice(data);
        }
        Ok(target[0] as usize)
    }
}

pub trait ScalgoprotoTableIn {
    fn magic() -> u32;
}

pub struct SimpleIn<R: ScalgoprotoReader> {
    reader: ScalgoprotoReader<'a>,
    start: usize,
}

impl ScalgoprotoTableIn for SimpleIn {
    fn magic() -> u32 {
        0xF0606B0B
    }
}

macro_rules! get_inner {
    ( $table:expr, $type:ty, $offset:expr ) => {
        $table.reader.slice($offset, std::mem::size_of::<$type>()).map(
            raw => {
                let typed: &[$type] = unsafe { std::mem::transmute(raw) };
                typed[0]
            }
        )
    }
}

impl SimpleIn {
    fn has_e(&self) -> bool {
        self.reader.get_u8(0).unwrap_or(255) != 255
    }

    fn e(&self) -> Result<MyEnum> {
        get_inner!(self, MyEnum, 0)
    }

    fn s(&self) -> Result<FullStruct> {
        get_inner!(self, FullStruct, 1)
    }

    fn b(&self) -> bool {
        self.reader.get_bit(54, 0)
    }

    fn u8_(&self) -> u8 {
        get_inner!(self, u8, 55).unwrap_or(2)
    }

    fn u16_(&self) -> u16 {
        get_inner!(self, u16, 56).unwrap_or(3)
    }

    fn u32_(&self) -> u32 {
        get_inner!(self, u32, 58).unwrap_or(4)
    }

    fn u64_(&self) -> u64 {
        get_inner!(self, u64, 62).unwrap_or(5)
    }

    fn i8_(&self) -> i8 {
        get_inner!(self, i8, 70).unwrap_or(6)
    }

    fn i16_(&self) -> i16 {
        get_inner!(self, i16, 71).unwrap_or(7)
    }

    fn i32_(&self) -> i32 {
        get_inner!(self, i32, 73).unwrap_or(8)
    }

    fn i64_(&self) -> i64 {
        get_inner!(self, i64, 77).unwrap_or(9)
    }

    fn f(&self) -> f32 {
        get_inner!(self, f32, 85).unwrap_or(10.0f32)
    }

    fn f(&self) -> f64 {
        get_inner!(self, f64, 89).unwrap_or(11.0f64)
    }

    fn has_os(&self) -> bool {
        self.reader.get_bit(54, 1)
    }

    fn os(&self) -> Result<MyStruct> {
        get_inner!(self, MyStruct, 97)
    }

    fn has_ob(&self) -> bool {
        self.reader.get_bit(54, 2)
    }

    fn ob(&self) -> bool {
        self.reader.get_bit(54, 3)
    }

    fn has_ou8(&self) -> bool {
        self.reader.get_bit(54, 4)
    }

    fn ou8(&self) -> Result<u8> {
        get_inner!(self, u8, 106)
    }

    fn has_ou16(&self) -> bool {
        self.reader.get_bit(54, 5)
    }

    fn ou16(&self) -> Result<u16> {
        get_inner!(self, u16, 107)
    }

    fn has_ou32(&self) -> bool {
        self.reader.get_bit(54, 6)
    }

    fn ou32(&self) -> Result<u32> {
        get_inner!(self, u32, 109)
    }
}
