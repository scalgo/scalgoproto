pub trait StructInFactory<'a> {
    type T;
    type B;
    fn new(bytes: &'a Self::B) -> Self::T;
}

static ZERO: [u8; 1024 * 16] = [0; 1024 * 16];
const ROOTMAGIC: u32 = 0xB5C0C4B3;
const LISTMAGIC: u32 = 0x3400BB46;
const TEXTMAGIC: u32 = 0xD812C8F5;
const BYTESMAGIC: u32 = 0xDCDBBE10;

//This is safe to call if T is an enum with u8 storage specifier and every integer i
//such that 0 <= i < range, is a valid enum value
pub unsafe fn to_enum<T: Copy>(v: u8, range: u8) -> Option<T> {
    if v >= range {
        None
    } else {
        let mut target: T = std::mem::MaybeUninit::uninit().assume_init();
        std::ptr::copy_nonoverlapping(&v as *const u8, &mut target as *mut T as *mut u8, 1);
        Some(target)
    }
}

// This method is safe to call if the length of v is sizeof(T)
// and the bit pattern described by v is a valid state for T
pub unsafe fn to_pod<T: Copy>(v: &[u8]) -> T {
    let mut target: T = std::mem::MaybeUninit::uninit().assume_init();
    std::ptr::copy_nonoverlapping(
        v.as_ptr(),
        &mut target as *mut T as *mut u8,
        std::mem::size_of::<T>(),
    );
    target
}

// This method is safe to call if s has the right length for the struct
pub unsafe fn to_struct<'a, F: StructInFactory<'a> + 'a>(s: &[u8]) -> F::T {
    F::new(&*(s as *const [u8] as *const F::B))
}

pub fn to_bool(v: u8) -> bool {
    if v == 0 {
        true
    } else {
        false
    }
}

// This method is safe as long as v has length at leats 6
pub unsafe fn to_u48(v: &[u8]) -> u64 {
    let mut out: u64 = 0;
    unsafe {
        std::ptr::copy_nonoverlapping(v.as_ptr(), &mut out as *mut u64 as *mut u8, 6);
    };
    out
}

pub unsafe fn to_u48_usize(v: &[u8]) -> Result<usize, ()> {
    match std::convert::TryFrom::try_from(unsafe { to_u48(v) }) {
        Ok(v) => Ok(v),
        Err(_) => Err(()),
    }
}

pub struct Reader<'a> {
    full: &'a [u8],
    part: &'a [u8],
}

impl<'a> Reader<'a> {
    fn slice(&self, offset: usize, size: usize) -> Option<&'a [u8]> {
        if offset + size > self.part.len() {
            None
        } else {
            Some(&self.part[offset..offset + size])
        }
    }

    pub fn get_u8(&self, offset: usize) -> Option<u8> {
        match self.slice(offset, 1) {
            Some(v) => Some(v[0]),
            None => None,
        }
    }

    pub fn get_bit(&self, offset: usize, bit: usize) -> bool {
        (self.get_u8(offset).unwrap_or(0) >> bit) & 1 == 1
    }

    pub fn get_48(&self, offset: usize) -> Option<u64> {
        let s = match self.slice(offset, 6) {
            Some(v) => v,
            None => return None,
        };
        Some(unsafe { to_u48(s) })
    }

    pub fn get_struct<F: StructInFactory<'a> + 'a>(&self, offset: usize) -> F::T {
        match self.slice(offset, std::mem::size_of::<F::B>()) {
            Some(s) => unsafe { to_struct::<F>(s) },
            None => unsafe { to_struct::<F>(&ZERO) },
        }
    }

    pub fn get_pod<T: Copy>(&self, offset: usize) -> Option<T> {
        let s = match self.slice(offset, std::mem::size_of::<T>()) {
            Some(s) => s,
            None => return None,
        };
        unsafe { Some(to_pod(s)) }
    }

    pub fn get_enum<T: Copy>(&self, offset: usize, max_val: u8) -> Option<T> {
        match self.get_u8(offset) {
            Some(v) => unsafe { to_enum(v, max_val) },
            None => None,
        }
    }
}

pub trait TableOut {
    fn offset(&self) -> usize;
}

pub trait TableInFactory<'a> {
    type T;
    fn magic() -> u32;
    fn new(reader: Reader<'a>) -> Self::T;
}

pub trait TableOutFactory<'a> {
    type T;
    fn magic() -> u32;
    fn size() -> usize;
    fn new(Arena: &'a Arena, offset: usize) -> Self::T;
}

pub fn read_message<'a, F: TableInFactory<'a> + 'a>(
    data: &'a [u8],
) -> std::result::Result<F::T, ()> {
    if data.len() < 20 {
        return Err(());
    }
    let magic: u32 = unsafe { to_pod(&data[0..4]) };
    if magic != ROOTMAGIC {
        return Err(());
    }
    let offset = unsafe { to_u48_usize(&data[4..10]) }?;
    if data.len() < offset + 10 {
        return Err(());
    }
    let table_magic: u32 = unsafe { to_pod(&data[offset..offset + 4]) };
    if table_magic != F::magic() {
        return Err(());
    }
    let table_size = unsafe { to_u48_usize(&data[offset + 4..offset + 10]) }?;
    if offset + 10 + table_size > data.len() {
        return Err(());
    }
    Ok(F::new(Reader {
        full: data,
        part: &data[offset + 10..offset + 10 + table_size],
    }))
}

pub struct Arena {
    data: std::cell::UnsafeCell<Vec<u8>>,
}

impl Arena {
    pub fn set_pod<T: Copy>(&self, offset: usize, v: T) {
        unsafe {
            let size = std::mem::size_of::<T>();
            let data = &mut *self.data.get();
            assert!(offset + size <= data.len());
            std::ptr::copy_nonoverlapping(
                &v as *const T as *const u8,
                data.as_mut_ptr().add(offset),
                size,
            );
        }
    }

    pub fn set_bit(&self, offset: usize, bit: usize, value: bool) {
        unsafe {
            let data = &mut *self.data.get();
            assert!(bit < 8);
            assert!(offset < data.len());
            if value {
                data[offset] = data[offset] | (1 << bit);
            } else {
                data[offset] = data[offset] & !(1 << bit);
            }
        }
    }

    pub fn set_bool(&self, offset: usize, value: bool) {
        unsafe {
            let data = &mut *self.data.get();
            assert!(offset < data.len());
            data[offset] = if value { 0 } else { 1 }
        }
    }

    pub fn set_u48(&self, offset: usize, value: u64) {
        unsafe {
            let size = 6;
            let data = &mut *self.data.get();
            assert!(offset + size <= data.len());
            assert!(value < 1 << 42);
            std::ptr::copy_nonoverlapping(
                &value as *const u64 as *const u8,
                data.as_mut_ptr().add(offset),
                size,
            );
        }
    }

    pub fn set_enum<T: Copy>(&self, offset: usize, v: Option<T>) {
        unsafe {
            let data = &mut *self.data.get();
            assert!(offset < data.len());
            //TODO check size
            match v {
                Some(vv) => std::ptr::copy_nonoverlapping(
                    &vv as *const T as *const u8,
                    data.as_mut_ptr().add(offset),
                    1,
                ),
                None => data[offset] = 255,
            }
        }
    }

    pub fn allocate(&self, size: usize) -> usize {
        unsafe {
            let d = &mut *self.data.get();
            let ans = d.len();
            d.resize(ans + size, 0);
            ans
        }
    }
}

pub struct Writer {
    arena: Arena,
}

impl Writer {
    pub fn new(capacity: usize) -> Self {
        let writer = Writer {
            arena: Arena {
                data: std::cell::UnsafeCell::new(std::vec::Vec::with_capacity(capacity)),
            },
        };
        writer.arena.allocate(10); //Make room for the header
        writer
    }

    pub fn add_table<'a, F: TableOutFactory<'a> + 'a>(&'a self) -> F::T {
        let offset = self.arena.allocate(10 + F::size());
        self.arena.set_pod(offset, F::magic());
        self.arena.set_u48(offset + 4, F::size() as u64);
        F::new(&self.arena, offset + 10)
    }

    pub fn finalize<T: TableOut>(&self, root: T) -> &[u8] {
        self.arena.set_pod(0, ROOTMAGIC);
        self.arena.set_u48(4, (root.offset() - 10) as u64);
        unsafe { (&*self.arena.data.get()).as_slice() }
    }

    pub fn clear(&mut self) {
        unsafe { (&mut *self.arena.data.get()).resize(10, 0) }
    }
}
