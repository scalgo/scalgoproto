#[repr(u8)]
#[derive(Copy, Clone, Debug)]
pub enum MyEnum {
    A = 0,
    B = 1,
    C = 2,
    D = 3,
}

#[repr(C, packed(1))]
#[derive(Copy, Clone, Debug)]
pub struct MyStruct {
    pub x: u32,
    pub y: f32,
    pub z: bool,
}

#[repr(C, packed(1))]
#[derive(Copy, Clone, Debug)]
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

pub type Result<T> = std::result::Result<T, ()>;

pub trait ScalgoprotoReader:Sized {
    fn slice(&self, offset: usize, size: usize) -> Result<&[u8]>;
    fn ptr(&self, offset: usize, target_size: usize) -> Result<Self>;

    fn get_u8(&self, offset: usize) -> Result<u8> {
        Ok(self.slice(offset, 1)?[0])
    }

    fn get_bit(&self, offset: usize, bit: usize) -> bool {
        (self.get_u8(offset).unwrap_or(0) >> bit) & 1 == 1
    }

    fn get_48(&self, offset: usize) -> Result<u64> {
        let s = self.slice(offset, 6)?;
        let mut target: u64 = 0;
        unsafe {
            std::ptr::copy_nonoverlapping(s.as_ptr(), &mut target as *mut u64 as *mut u8, 6);
        }
        Ok(target)
    }

    fn get_pod<T: Copy>(&self, offset: usize) -> Result<T> {
        let s = self.slice(offset, std::mem::size_of::<T>())?;
        unsafe {
            let mut target: T = std::mem::MaybeUninit::uninit().assume_init();
            std::ptr::copy_nonoverlapping(s.as_ptr(), &mut target as *mut T as *mut u8, std::mem::size_of::<T>());
            //TODO make validator that checks that enums are within range and that structs are valid
            //That is contained bools are 0 or 1, and contained enums are within range
            Ok(target)
        }
    }
}

pub trait ScalgoprotoTableIn {
    fn magic() -> u32;
}

pub struct SimpleIn<R: ScalgoprotoReader> {
    reader: R,
}

impl<R: ScalgoprotoReader> ScalgoprotoTableIn for SimpleIn<R> {
    fn magic() -> u32 {
        0xF0606B0B
    }
}

impl<R: ScalgoprotoReader>  SimpleIn<R> {
    fn has_e(&self) -> bool {
        self.reader.get_u8(0).unwrap_or(255) != 255
    }

    fn e(&self) -> Result<MyEnum> {
        self.reader.get_pod::<MyEnum>(0)
    }

    fn s(&self) -> Result<FullStruct> {
        self.reader.get_pod::<FullStruct>(1)
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

    fn f32_(&self) -> f32 {
        self.reader.get_pod::<f32>(85).unwrap_or(10.0f32)
    }

    fn f64_(&self) -> f64 {
        self.reader.get_pod::<f64>(89).unwrap_or(11.0f64)
    }

    fn has_os(&self) -> bool {
        self.reader.get_bit(54, 1)
    }

    fn os(&self) -> Result<MyStruct> {
        self.reader.get_pod::<MyStruct>(97)
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
        self.reader.get_pod::<u8>(106)
    }

    fn has_ou16(&self) -> bool {
        self.reader.get_bit(54, 5)
    }

    fn ou16(&self) -> Result<u16> {
        self.reader.get_pod::<u16>(107)
    }

    fn has_ou32(&self) -> bool {
        self.reader.get_bit(54, 6)
    }

    fn ou32(&self) -> Result<u32> {
        self.reader.get_pod::<u32>(109)
    }
}

struct LinearReader<'a> {
    full: &'a [u8],
    part: &'a [u8],
}

impl<'a> ScalgoprotoReader for LinearReader<'a> {
    fn slice(&self, offset: usize, size: usize) -> Result<&[u8]> {
        if offset + size > self.part.len() {
            Err(())
        } else {
            Ok(&self.part[offset..offset+size])
        }
    }

    fn ptr(&self, offset: usize, target_size: usize) -> Result<Self> {
        Err(())
    }
}



fn main() {

    let bytes : [u8; 1000] = [1; 1000];

    let reader = LinearReader {full: &bytes, part: &bytes};

    let si = SimpleIn { reader: reader };

    println!("HI  {:?} {:?}", si.e().unwrap(), si.s().unwrap());

    println!("Hello, world!");
}
