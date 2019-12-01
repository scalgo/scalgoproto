/* Trait used to describe the placment of lists, tabels and unions. There should only be two implementations: Normal and Inplace */
pub trait Placement: Copy {}

#[derive(Copy, Clone)]
pub struct Inplace {}
impl Placement for Inplace {}
#[derive(Copy, Clone)]
pub struct Normal {}
impl Placement for Normal {}

/* The meta types describes types of members */
pub trait MetaType: Clone {
    fn list_bytes(len: usize) -> usize;
    fn list_def() -> u8 {
        0
    }
}

#[derive(Copy, Clone)]
pub struct PodType<T: Copy + std::fmt::Debug> {
    p: std::marker::PhantomData<T>,
}
impl<T: Copy + std::fmt::Debug> MetaType for PodType<T> {
    fn list_bytes(len: usize) -> usize {
        len * std::mem::size_of::<T>()
    }
}

#[derive(Copy, Clone)]
pub struct BoolType {}
impl MetaType for BoolType {
    fn list_bytes(len: usize) -> usize {
        (len + 7) >> 3
    }
}

#[derive(Copy, Clone)]
pub struct EnumType<T: Enum> {
    p: std::marker::PhantomData<T>,
}
impl<T: Enum> MetaType for EnumType<T> {
    fn list_bytes(len: usize) -> usize {
        len
    }
    fn list_def() -> u8 {
        255
    }
}

#[derive(Copy, Clone)]
pub struct TextType {}
impl MetaType for TextType {
    fn list_bytes(len: usize) -> usize {
        len * 6
    }
}

#[derive(Copy, Clone)]
pub struct BytesType {}
impl MetaType for BytesType {
    fn list_bytes(len: usize) -> usize {
        len * 6
    }
}

#[derive(Copy, Clone)]
pub struct TableType<'a, F: TableFactory<'a>> {
    p: std::marker::PhantomData<&'a F>,
}
impl<'a, F: TableFactory<'a>> MetaType for TableType<'a, F> {
    fn list_bytes(len: usize) -> usize {
        len * 6
    }
}

#[derive(Copy, Clone)]
pub struct StructType<'a, F: StructFactory<'a>> {
    p: std::marker::PhantomData<&'a F>,
}
impl<'a, F: StructFactory<'a>> MetaType for StructType<'a, F> {
    fn list_bytes(len: usize) -> usize {
        len * F::size()
    }
}

pub trait Enum: Copy + std::fmt::Debug {
    fn max_value() -> u8;
}

#[derive(Debug)]
pub enum Error {
    Utf8(std::str::Utf8Error),
    InvalidPointer(),
    Overflow(),
    BadMagic(u32, u32),
}

impl From<std::str::Utf8Error> for Error {
    fn from(err: std::str::Utf8Error) -> Self {
        Self::Utf8(err)
    }
}

pub type Result<T> = std::result::Result<T, Error>;

pub trait StructFactory<'a>: Copy {
    type In: std::fmt::Debug;
    type Out;
    type B;
    fn size() -> usize;
    fn new_in(bytes: &'a Self::B) -> Self::In;
    fn new_out(arena: &'a Arena, offset: usize) -> Self::Out;
}
static ZERO: [u8; 1024 * 16] = [0; 1024 * 16];
const ROOTMAGIC: u32 = 0xB5C0C4B3;
const LISTMAGIC: u32 = 0x3400BB46;
const TEXTMAGIC: u32 = 0xD812C8F5;
const BYTESMAGIC: u32 = 0xDCDBBE10;

//This is safe to call if T is an enum with u8 storage specifier and every integer i
//such that 0 <= i < range, is a valid enum value
pub unsafe fn to_enum<T: Enum + Copy>(v: u8) -> Option<T> {
    if v >= T::max_value() {
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
pub unsafe fn to_struct<'a, F: StructFactory<'a> + 'a>(s: &[u8]) -> F::In {
    F::new_in(&*(s as *const [u8] as *const F::B))
}

pub fn to_bool(v: u8) -> bool {
    if v == 0 {
        false
    } else {
        true
    }
}

// This method is safe as long as v has length at least 6
pub unsafe fn to_u48(v: &[u8]) -> u64 {
    let mut out: u64 = 0;
    std::ptr::copy_nonoverlapping(v.as_ptr(), &mut out as *mut u64 as *mut u8, 6);
    out
}

pub unsafe fn to_u48_usize(v: &[u8]) -> Result<usize> {
    match std::convert::TryFrom::try_from(to_u48(v)) {
        Ok(v) => Ok(v),
        Err(_) => Err(Error::Overflow()),
    }
}

#[derive(Copy, Clone)]
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

    pub fn get_48_usize(&self, offset: usize) -> Result<Option<usize>> {
        let v = match self.get_48(offset) {
            Some(v) => v,
            None => return Ok(None),
        };
        match std::convert::TryFrom::try_from(v) {
            Ok(v) => Ok(Some(v)),
            Err(_) => Err(Error::Overflow()),
        }
    }

    pub fn get_struct<F: StructFactory<'a> + 'a>(&self, offset: usize) -> F::In {
        match self.slice(offset, F::size()) {
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

    pub fn get_enum<T: Enum>(&self, offset: usize, default: u8) -> Option<T> {
        match self.get_u8(offset) {
            Some(v) => unsafe { to_enum(v) },
            None => unsafe { to_enum(default) },
        }
    }

    pub fn get_ptr(&self, offset: usize) -> Result<Option<(usize, u32, usize)>> {
        let o = match self.get_48_usize(offset)? {
            Some(v) if v == 0 => return Ok(None),
            Some(v) => v,
            None => return Ok(None),
        };
        if self.full.len() < o + 10 {
            return Err(Error::InvalidPointer());
        }
        let magic: u32 = unsafe { to_pod(&self.full[o..o + 4]) };
        let size = unsafe { to_u48_usize(&self.full[o + 4..o + 10]) }?;
        return Ok(Some((o + 10, magic, size)));
    }

    pub fn get_ptr_inplace(&self, offset: usize) -> Result<Option<(usize, usize)>> {
        let size = match self.get_48_usize(offset)? {
            Some(v) => v,
            None => return Ok(None),
        };
        let o = self.part.as_ptr() as usize - self.full.as_ptr() as usize + self.part.len();
        return Ok(Some((o, size)));
    }

    pub fn get_table_union<F: TableFactory<'a> + 'a>(
        &self,
        magic: Option<u32>,
        offset: usize,
        size: usize,
    ) -> Result<F::In> {
        if let Some(m) = magic {
            if m != F::magic() {
                return Err(Error::BadMagic(m, F::magic()));
            }
        }
        if offset + size > self.full.len() {
            return Err(Error::InvalidPointer());
        }
        Ok(F::new_in(Reader {
            full: self.full,
            part: &self.full[offset..offset + size],
        }))
    }

    pub fn get_table<F: TableFactory<'a> + 'a>(&self, offset: usize) -> Result<Option<F::In>> {
        match self.get_ptr(offset) {
            Err(e) => Err(e),
            Ok(None) => Ok(None),
            Ok(Some((o, m, s))) => Ok(Some(self.get_table_union::<F>(Some(m), o, s)?)),
        }
    }
    pub fn get_table_inplace<F: TableFactory<'a> + 'a>(
        &self,
        offset: usize,
    ) -> Result<Option<F::In>> {
        match self.get_ptr_inplace(offset) {
            Err(e) => Err(e),
            Ok(None) => Ok(None),
            Ok(Some((o, s))) => Ok(Some(self.get_table_union::<F>(None, o, s)?)),
        }
    }

    pub fn get_text_union(
        &self,
        magic: Option<u32>,
        offset: usize,
        size: usize,
    ) -> Result<&'a str> {
        if let Some(m) = magic {
            if m != TEXTMAGIC {
                return Err(Error::BadMagic(m, TEXTMAGIC));
            }
        }
        if offset + size > self.full.len() {
            return Err(Error::InvalidPointer());
        }
        Ok(std::str::from_utf8(&self.full[offset..offset + size])?)
    }

    pub fn get_text(&self, offset: usize) -> Result<Option<&'a str>> {
        match self.get_ptr(offset) {
            Err(e) => Err(e),
            Ok(None) => Ok(None),
            Ok(Some((o, m, s))) => Ok(Some(self.get_text_union(Some(m), o, s)?)),
        }
    }

    pub fn get_text_inplace(&self, offset: usize) -> Result<Option<&'a str>> {
        match self.get_ptr_inplace(offset) {
            Err(e) => Err(e),
            Ok(None) => Ok(None),
            Ok(Some((o, s))) => Ok(Some(self.get_text_union(None, o, s)?)),
        }
    }

    pub fn get_bytes_union(
        &self,
        magic: Option<u32>,
        offset: usize,
        size: usize,
    ) -> Result<&'a [u8]> {
        if let Some(m) = magic {
            if m != BYTESMAGIC {
                return Err(Error::BadMagic(m, BYTESMAGIC));
            }
        }
        if offset + size > self.full.len() {
            return Err(Error::InvalidPointer());
        }
        Ok(&self.full[offset..offset + size])
    }

    pub fn get_bytes(&self, offset: usize) -> Result<Option<&'a [u8]>> {
        match self.get_ptr(offset) {
            Err(e) => Err(e),
            Ok(None) => Ok(None),
            Ok(Some((o, m, s))) => Ok(Some(self.get_bytes_union(Some(m), o, s)?)),
        }
    }

    pub fn get_bytes_inplace(&self, offset: usize) -> Result<Option<&'a [u8]>> {
        match self.get_ptr_inplace(offset) {
            Err(e) => Err(e),
            Ok(None) => Ok(None),
            Ok(Some((o, s))) => Ok(Some(self.get_bytes_union(None, o, s)?)),
        }
    }

    pub fn get_list_union<A: ListAccess<'a> + 'a>(
        &self,
        magic: Option<u32>,
        offset: usize,
        size: usize,
    ) -> Result<ListIn<'a, A>> {
        if let Some(m) = magic {
            if m != LISTMAGIC {
                return Err(Error::BadMagic(m, LISTMAGIC));
            }
        }
        let size_bytes = A::bytes(size);
        if offset + size_bytes > self.full.len() {
            return Err(Error::InvalidPointer());
        }
        Ok(ListIn {
            reader: Reader {
                full: self.full,
                part: &self.full[offset..offset + size_bytes],
            },
            _len: size,
            phantom: std::marker::PhantomData {},
        })
    }

    pub fn get_list<A: ListAccess<'a> + 'a>(&self, offset: usize) -> Result<Option<ListIn<'a, A>>> {
        match self.get_ptr(offset) {
            Err(e) => Err(e),
            Ok(None) => Ok(None),
            Ok(Some((o, m, s))) => Ok(Some(self.get_list_union::<A>(Some(m), o, s)?)),
        }
    }

    pub fn get_list_inplace<A: ListAccess<'a> + 'a>(
        &self,
        offset: usize,
    ) -> Result<Option<ListIn<'a, A>>> {
        match self.get_ptr_inplace(offset) {
            Err(e) => Err(e),
            Ok(None) => Ok(None),
            Ok(Some((o, s))) => Ok(Some(self.get_list_union::<A>(None, o, s)?)),
        }
    }

    pub fn get_union<F: UnionFactory<'a> + 'a>(&self, offset: usize) -> Result<F::In> {
        let t = self.get_pod::<u16>(offset).unwrap_or(0);
        match self.get_ptr(offset + 2)? {
            Some((o, magic, size)) => F::new_in(t, Some(magic), o, size, self),
            None => F::new_in(t, None, 0, 0, self),
        }
    }

    pub fn get_union_inplace<F: UnionFactory<'a> + 'a>(&self, offset: usize) -> Result<F::In> {
        let t = self.get_pod::<u16>(offset).unwrap_or(0);
        match self.get_ptr_inplace(offset + 2)? {
            Some((o, size)) => F::new_in(t, None, o, size, self),
            None => F::new_in(t, None, 0, 0, self),
        }
    }
}

pub trait ListAccess<'a> {
    type Output: std::fmt::Debug;
    fn bytes(size: usize) -> usize;
    unsafe fn get(reader: &Reader<'a>, idx: usize) -> Self::Output;
}

pub struct ListIn<'a, A: ListAccess<'a>> {
    reader: Reader<'a>,
    _len: usize,
    phantom: std::marker::PhantomData<A>,
}

impl<'a, A: ListAccess<'a>> ListIn<'a, A> {
    pub fn len(&self) -> usize {
        self._len
    }
    pub fn get(&self, idx: usize) -> A::Output {
        assert!(idx < self._len);
        unsafe { A::get(&self.reader, idx) }
    }
    pub fn iter(&self) -> ListIter<'a, A> {
        ListIter {
            reader: self.reader,
            _len: self._len,
            idx: 0,
            phantom: std::marker::PhantomData {},
        }
    }
}

pub struct ListIter<'a, A: ListAccess<'a>> {
    reader: Reader<'a>,
    _len: usize,
    idx: usize,
    phantom: std::marker::PhantomData<A>,
}

impl<'a, A: ListAccess<'a> + 'a> std::iter::Iterator for ListIter<'a, A> {
    type Item = A::Output;
    fn next(&mut self) -> Option<Self::Item> {
        if self.idx >= self._len {
            return None;
        }
        let ans = unsafe { A::get(&self.reader, self.idx) };
        self.idx += 1;
        Some(ans)
    }
    fn size_hint(&self) -> (usize, Option<usize>) {
        let s = self._len - self.idx;
        (s, Some(s))
    }
}

impl<'a, A: ListAccess<'a> + 'a> std::iter::IntoIterator for ListIn<'a, A> {
    type Item = A::Output;
    type IntoIter = ListIter<'a, A>;
    fn into_iter(self) -> Self::IntoIter {
        Self::IntoIter {
            reader: self.reader,
            _len: self._len,
            idx: 0,
            phantom: std::marker::PhantomData {},
        }
    }
}

impl<'a, A: ListAccess<'a>> std::fmt::Debug for ListIn<'a, A> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("[")?;
        // TODO(jakob)
        // let mut first = true;
        // for i in self {
        //     if first {
        //         first = false;
        //     } else {
        //         f.write_str(", ")?;
        //     }
        //     write!(f, "{:?}", i)?;
        // }
        f.write_str("]")?;
        Ok(())
    }
}

#[derive(Copy, Clone)]
pub struct ListOut<'a, T: MetaType, P: Placement> {
    arena: &'a Arena,
    offset: usize,
    _len: usize,
    p1: std::marker::PhantomData<T>,
    p2: std::marker::PhantomData<P>,
}
impl<'a, T: MetaType, P: Placement> ListOut<'a, T, P> {
    pub fn len(&self) -> usize {
        self._len
    }
}

impl<'a, T: Copy + std::fmt::Debug, P: Placement> ListOut<'a, PodType<T>, P> {
    pub fn set(&mut self, idx: usize, v: T) {
        assert!(idx < self._len);
        unsafe {
            self.arena
                .set_pod(self.offset + idx * std::mem::size_of::<T>(), &v)
        }
    }
}
impl<'a, P: Placement> ListOut<'a, BoolType, P> {
    pub fn set(&mut self, idx: usize, v: bool) {
        assert!(idx < self._len);
        unsafe { self.arena.set_bit(self.offset + (idx >> 3), idx & 7, v) }
    }
}
impl<'a, T: Enum, P: Placement> ListOut<'a, EnumType<T>, P> {
    pub fn set(&mut self, idx: usize, v: Option<T>) {
        assert!(idx < self._len);
        unsafe { self.arena.set_enum(self.offset + idx, v) }
    }
}
impl<'a, P: Placement> ListOut<'a, TextType, P> {
    pub fn set(&mut self, idx: usize, v: Option<TextOut<'a>>) {
        assert!(idx < self._len);
        unsafe { self.arena.set_text(self.offset + idx * 6, v) }
    }
    pub fn add(&mut self, idx: usize, v: &str) -> TextOut<'a> {
        assert!(idx < self._len);
        unsafe { self.arena.add_text(self.offset + idx * 6, v) }
    }
}
impl<'a, P: Placement> ListOut<'a, BytesType, P> {
    pub fn set(&mut self, idx: usize, v: Option<BytesOut<'a>>) {
        assert!(idx < self._len);
        unsafe { self.arena.set_bytes(self.offset + idx * 6, v) }
    }
    pub fn add(&mut self, idx: usize, v: &[u8]) -> BytesOut<'a> {
        assert!(idx < self._len);
        unsafe { self.arena.add_bytes(self.offset + idx * 6, v) }
    }
}
impl<'a, F: TableFactory<'a>, P: Placement> ListOut<'a, TableType<'a, F>, P> {
    pub fn set(&mut self, idx: usize, v: Option<F::Out>) {
        assert!(idx < self._len);
        unsafe { self.arena.set_table(self.offset + idx * 6, v) }
    }
    pub fn add(&mut self, idx: usize) -> F::Out {
        assert!(idx < self._len);
        unsafe { self.arena.add_table::<'a, F>(self.offset + idx * 6) }
    }
}
impl<'a, F: StructFactory<'a>, P: Placement> ListOut<'a, StructType<'a, F>, P> {
    pub fn get(&mut self, idx: usize) -> F::Out {
        assert!(idx < self._len);
        unsafe { F::new_out(self.arena, self.offset + idx * F::size()) }
    }
}

pub struct PodListAccess<'a, T: Copy + std::fmt::Debug> {
    p: std::marker::PhantomData<&'a T>,
}
impl<'a, T: Copy + std::fmt::Debug> ListAccess<'a> for PodListAccess<'a, T> {
    type Output = T;
    fn bytes(size: usize) -> usize {
        size * std::mem::size_of::<T>()
    }
    unsafe fn get(reader: &Reader<'a>, idx: usize) -> Self::Output {
        reader
            .get_pod::<T>(idx * std::mem::size_of::<T>())
            .expect("Index error")
    }
}

pub struct EnumListAccess<'a, T: Enum> {
    p: std::marker::PhantomData<&'a T>,
}
impl<'a, T: Enum> ListAccess<'a> for EnumListAccess<'a, T> {
    type Output = Option<T>;
    fn bytes(size: usize) -> usize {
        size
    }
    unsafe fn get(reader: &Reader<'a>, idx: usize) -> Self::Output {
        reader.get_enum::<T>(idx, 255)
    }
}

pub struct StructListAccess<'a, F: StructFactory<'a> + 'a> {
    p: std::marker::PhantomData<&'a F>,
}
impl<'a, F: StructFactory<'a> + 'a> ListAccess<'a> for StructListAccess<'a, F> {
    type Output = F::In;
    fn bytes(size: usize) -> usize {
        size * F::size()
    }
    unsafe fn get(reader: &Reader<'a>, idx: usize) -> Self::Output {
        reader.get_struct::<F>(idx * F::size())
    }
}

pub struct TextListAccess<'a> {
    p: std::marker::PhantomData<&'a u8>,
}
impl<'a> ListAccess<'a> for TextListAccess<'a> {
    type Output = Result<Option<&'a str>>;
    fn bytes(size: usize) -> usize {
        size * 6
    }
    unsafe fn get(reader: &Reader<'a>, idx: usize) -> Self::Output {
        reader.get_text(idx * 6)
    }
}

pub struct BytesListAccess<'a> {
    p: std::marker::PhantomData<&'a u8>,
}
impl<'a> ListAccess<'a> for BytesListAccess<'a> {
    type Output = Result<Option<&'a [u8]>>;
    fn bytes(size: usize) -> usize {
        size * 6
    }
    unsafe fn get(reader: &Reader<'a>, idx: usize) -> Self::Output {
        reader.get_bytes(idx * 6)
    }
}

pub struct TableListAccess<'a, F: TableFactory<'a> + 'a> {
    p: std::marker::PhantomData<&'a F>,
}
impl<'a, F: TableFactory<'a> + 'a> ListAccess<'a> for TableListAccess<'a, F> {
    type Output = Result<Option<F::In>>;
    fn bytes(size: usize) -> usize {
        size * 6
    }
    unsafe fn get(reader: &Reader<'a>, idx: usize) -> Self::Output {
        reader.get_table::<F>(idx * 6)
    }
}

pub struct BoolListAccess<'a> {
    p: std::marker::PhantomData<&'a bool>,
}
impl<'a> ListAccess<'a> for BoolListAccess<'a> {
    type Output = bool;
    fn bytes(size: usize) -> usize {
        (size + 7) >> 3
    }
    unsafe fn get(reader: &Reader<'a>, idx: usize) -> bool {
        reader.get_bit(idx >> 3, idx & 7)
    }
}

pub trait UnionFactory<'a> {
    type In: std::fmt::Debug;
    type Out;
    type InplaceOut;

    fn new_in(
        t: u16,
        magic: Option<u32>,
        offset: usize,
        size: usize,
        reader: &Reader<'a>,
    ) -> Result<Self::In>;

    fn new_out(arena: &'a Arena, offset: usize) -> Self::Out;

    fn new_inplace_out(arena: &'a Arena, offset: usize) -> Self::InplaceOut;
}

pub trait TableOut<P: Placement>: Copy {
    fn offset(&self) -> usize;
}

pub trait TableFactory<'a>: Copy {
    type In: std::fmt::Debug;
    type Out: TableOut<Normal>;
    type InplaceOut: TableOut<Inplace>;
    fn magic() -> u32;
    fn size() -> usize;
    fn default() -> &'static [u8];
    fn new_in(reader: Reader<'a>) -> Self::In;
    fn new_out(arena: &'a Arena, offset: usize) -> Self::Out;
    fn new_inplace_out(arena: &'a Arena, offset: usize) -> Self::InplaceOut;
}

pub fn read_message<'a, F: TableFactory<'a> + 'a>(data: &'a [u8]) -> Result<F::In> {
    if data.len() < 10 {
        return Err(Error::InvalidPointer());
    }
    let r = Reader {
        full: data,
        part: &data[0..10],
    };
    match r.get_table::<F>(4) {
        Err(e) => Err(e),
        Ok(Some(v)) => Ok(v),
        Ok(None) => Err(Error::InvalidPointer()),
    }
}

pub struct Arena {
    data: std::cell::UnsafeCell<Vec<u8>>,
}

impl Arena {
    pub unsafe fn set_pod<T: Copy + std::fmt::Debug>(&self, offset: usize, v: &T) {
        let size = std::mem::size_of::<T>();
        let data = &mut *self.data.get();
        assert!(offset + size <= data.len());
        std::ptr::copy_nonoverlapping(
            v as *const T as *const u8,
            data.as_mut_ptr().add(offset),
            size,
        );
    }

    pub unsafe fn set_bit(&self, offset: usize, bit: usize, value: bool) {
        let data = &mut *self.data.get();
        assert!(bit < 8);
        assert!(offset < data.len());
        if value {
            data[offset] = data[offset] | (1 << bit);
        } else {
            data[offset] = data[offset] & !(1 << bit);
        }
    }

    pub unsafe fn set_bool(&self, offset: usize, value: bool) {
        let data = &mut *self.data.get();
        assert!(offset < data.len());
        data[offset] = if value { 1 } else { 0 }
    }

    pub unsafe fn set_u48(&self, offset: usize, value: u64) {
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

    pub unsafe fn set_enum<T: Enum>(&self, offset: usize, v: Option<T>) {
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

    pub unsafe fn set_table<T: TableOut<Normal>>(&self, offset: usize, v: Option<T>) {
        let o = match v {
            Some(t) => t.offset(),
            None => 0,
        } - 10;
        self.set_u48(offset, o as u64);
    }

    pub unsafe fn set_list<'a, T: MetaType>(
        &'a self,
        offset: usize,
        v: Option<ListOut<'a, T, Normal>>,
    ) {
        let o = match v {
            Some(t) => t.offset,
            None => 0,
        } - 10;
        self.set_u48(offset, o as u64);
    }

    pub fn create_table<'a, F: TableFactory<'a>>(&'a self) -> F::Out {
        unsafe {
            let o = self.allocate_default(10, F::default());
            self.set_pod(o, &F::magic());
            self.set_u48(o + 4, F::size() as u64);
            F::new_out(&self, o + 10)
        }
    }

    pub unsafe fn add_table<'a, F: TableFactory<'a>>(&'a self, offset: usize) -> F::Out {
        let a = self.create_table::<F>();
        self.set_table(offset, Some(a));
        a
    }

    pub unsafe fn add_table_inplace<'a, F: TableFactory<'a>>(
        &'a self,
        offset: usize,
    ) -> F::InplaceOut {
        // TODO (jakob) check that we are in the right location
        unsafe {
            let o = self.allocate_default(0, F::default());
            self.set_u48(offset, F::size() as u64);
            F::new_inplace_out(&self, o)
        }
    }

    pub fn create_bytes<'a>(&'a self, v: &[u8]) -> BytesOut<'a> {
        let o = self.allocate(10 + v.len());
        unsafe {
            self.set_pod(o, &BYTESMAGIC);
            self.set_u48(o + 4, v.len() as u64);
            let data = &mut *self.data.get();
            std::ptr::copy_nonoverlapping(v.as_ptr(), data.as_mut_ptr().add(o + 10), v.len());
        };
        BytesOut {
            arena: self,
            offset: o,
        }
    }

    pub unsafe fn add_bytes<'a>(&'a self, offset: usize, v: &[u8]) -> BytesOut<'a> {
        let ans = self.create_bytes(v);
        self.set_u48(offset, ans.offset as u64);
        ans
    }

    pub unsafe fn add_bytes_inplace<'a>(&'a self, offset: usize, v: &[u8]) {
        let o = self.allocate(v.len());
        //TODO(jakobt) check that o is right after the table
        unsafe {
            self.set_u48(offset, v.len() as u64);
            let data = &mut *self.data.get();
            std::ptr::copy_nonoverlapping(v.as_ptr(), data.as_mut_ptr().add(o), v.len());
        };
    }

    pub unsafe fn set_bytes<'a>(&'a self, offset: usize, v: Option<BytesOut<'a>>) {
        let o = match v {
            Some(b) => {
                assert!(std::ptr::eq(self, b.arena));
                b.offset
            }
            None => 0,
        };
        self.set_u48(offset, o as u64);
    }

    pub fn create_text<'a>(&'a self, v: &str) -> TextOut<'a> {
        let o = self.allocate(11 + v.len());
        unsafe {
            self.set_pod(o, &TEXTMAGIC);
            self.set_u48(o + 4, v.len() as u64);
            let data = &mut *self.data.get();
            std::ptr::copy_nonoverlapping(
                v.as_bytes().as_ptr(),
                data.as_mut_ptr().add(o + 10),
                v.len(),
            );
        }
        TextOut {
            arena: self,
            offset: o,
        }
    }

    pub unsafe fn add_text<'a>(&'a self, offset: usize, v: &str) -> TextOut<'a> {
        let ans = self.create_text(v);
        self.set_u48(offset, ans.offset as u64);
        ans
    }

    pub unsafe fn add_text_inplace<'a>(&'a self, offset: usize, v: &str) {
        let o = self.allocate(1 + v.len());
        //TODO(jakobt) check that o is right after the table
        unsafe {
            self.set_u48(offset, v.len() as u64);
            let data = &mut *self.data.get();
            std::ptr::copy_nonoverlapping(v.as_bytes().as_ptr(), data.as_mut_ptr().add(o), v.len());
        };
    }

    pub unsafe fn set_text<'a>(&'a self, offset: usize, v: Option<TextOut<'a>>) {
        let o = match v {
            Some(b) => {
                assert!(std::ptr::eq(self, b.arena));
                b.offset
            }
            None => 0,
        };
        self.set_u48(offset, o as u64);
    }

    pub fn create_list<'a, T: MetaType>(&'a self, len: usize) -> ListOut<'a, T, Normal> {
        unsafe {
            let d = &mut *self.data.get();
            let ans = d.len();
            d.resize(ans + T::list_bytes(len) + 10, T::list_def());
            self.set_pod(ans, &LISTMAGIC);
            self.set_u48(ans + 4, len as u64);
            ListOut {
                offset: ans + 10,
                _len: len,
                arena: self,
                p1: std::marker::PhantomData {},
                p2: std::marker::PhantomData {},
            }
        }
    }

    pub fn add_list<'a, T: MetaType>(
        &'a self,
        offset: usize,
        len: usize,
    ) -> ListOut<'a, T, Normal> {
        unsafe {
            let ans = self.create_list::<T>(len);
            self.set_list(offset, Some(ans.clone()));
            ans
        }
    }

    pub fn add_list_inplace<'a, T: MetaType>(
        &'a self,
        offset: usize,
        len: usize,
    ) -> ListOut<'a, T, Inplace> {
        unsafe {
            //TODO (jakobt) check if we are in the right spot
            let d = &mut *self.data.get();
            let ans = d.len();
            d.resize(ans + T::list_bytes(len), T::list_def());
            self.set_u48(offset, len as u64);
            ListOut {
                offset: ans,
                _len: len,
                arena: self,
                p1: std::marker::PhantomData {},
                p2: std::marker::PhantomData {},
            }
        }
    }

    pub fn get_union<'a, F: UnionFactory<'a> + 'a>(&'a self, offset: usize) -> F::Out {
        F::new_out(self, offset)
    }

    pub fn get_union_inplace<'a, F: UnionFactory<'a> + 'a>(
        &'a self,
        offset: usize,
    ) -> F::InplaceOut {
        F::new_inplace_out(self, offset)
    }

    pub fn allocate(&self, size: usize) -> usize {
        unsafe {
            let d = &mut *self.data.get();
            let ans = d.len();
            d.resize(ans + size, 0);
            ans
        }
    }
    pub fn allocate_default(&self, head: usize, default: &[u8]) -> usize {
        unsafe {
            let d = &mut *self.data.get();
            let ans = d.len();
            d.reserve(head + default.len());
            d.resize(ans + head, 0);
            d.extend_from_slice(default);
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

    pub fn add_table<'a, F: TableFactory<'a> + 'a>(&'a self) -> F::Out {
        let offset = self.arena.allocate_default(10, F::default());
        unsafe {
            self.arena.set_pod(offset, &F::magic());
            self.arena.set_u48(offset + 4, F::size() as u64);
        }
        F::new_out(&self.arena, offset + 10)
    }

    pub fn add_text<'a>(&'a self, text: &str) -> TextOut<'a> {
        self.arena.create_text(text)
    }

    pub fn add_bytes<'a>(&'a self, bytes: &[u8]) -> BytesOut<'a> {
        self.arena.create_bytes(bytes)
    }

    pub fn add_u8_list<'a>(&'a self, size: usize) -> ListOut<'a, PodType<u8>, Normal> {
        self.arena.create_list::<PodType<u8>>(size)
    }
    pub fn add_u16_list<'a>(&'a self, size: usize) -> ListOut<'a, PodType<u16>, Normal> {
        self.arena.create_list::<PodType<u16>>(size)
    }
    pub fn add_u32_list<'a>(&'a self, size: usize) -> ListOut<'a, PodType<u32>, Normal> {
        self.arena.create_list::<PodType<u32>>(size)
    }
    pub fn add_u64_list<'a>(&'a self, size: usize) -> ListOut<'a, PodType<u64>, Normal> {
        self.arena.create_list::<PodType<u64>>(size)
    }
    pub fn add_i8_list<'a>(&'a self, size: usize) -> ListOut<'a, PodType<i8>, Normal> {
        self.arena.create_list::<PodType<i8>>(size)
    }
    pub fn add_i16_list<'a>(&'a self, size: usize) -> ListOut<'a, PodType<i16>, Normal> {
        self.arena.create_list::<PodType<i16>>(size)
    }
    pub fn add_i32_list<'a>(&'a self, size: usize) -> ListOut<'a, PodType<i32>, Normal> {
        self.arena.create_list::<PodType<i32>>(size)
    }
    pub fn add_i64_list<'a>(&'a self, size: usize) -> ListOut<'a, PodType<i64>, Normal> {
        self.arena.create_list::<PodType<i64>>(size)
    }
    pub fn add_f32_list<'a>(&'a self, size: usize) -> ListOut<'a, PodType<f32>, Normal> {
        self.arena.create_list::<PodType<f32>>(size)
    }
    pub fn add_f64_list<'a>(&'a self, size: usize) -> ListOut<'a, PodType<f64>, Normal> {
        self.arena.create_list::<PodType<f64>>(size)
    }
    pub fn add_enum_list<'a, T: Enum + 'a>(
        &'a self,
        size: usize,
    ) -> ListOut<'a, EnumType<T>, Normal> {
        self.arena.create_list::<EnumType<T>>(size)
    }
    pub fn add_table_list<'a, F: TableFactory<'a> + 'a>(
        &'a self,
        size: usize,
    ) -> ListOut<'a, TableType<F>, Normal> {
        self.arena.create_list::<TableType<F>>(size)
    }
    pub fn add_struct_list<'a, F: StructFactory<'a> + 'a>(
        &'a self,
        size: usize,
    ) -> ListOut<'a, StructType<F>, Normal> {
        self.arena.create_list::<StructType<F>>(size)
    }
    pub fn add_text_list<'a>(&'a self, size: usize) -> ListOut<'a, TextType, Normal> {
        self.arena.create_list::<TextType>(size)
    }
    pub fn add_bytes_list<'a>(&'a self, size: usize) -> ListOut<'a, BytesType, Normal> {
        self.arena.create_list::<BytesType>(size)
    }
    pub fn add_bool_list<'a>(&'a self, size: usize) -> ListOut<'a, BoolType, Normal> {
        self.arena.create_list::<BoolType>(size)
    }
    pub fn finalize<T: TableOut<Normal>>(&self, root: T) -> &[u8] {
        unsafe {
            self.arena.set_pod(0, &ROOTMAGIC);
            self.arena.set_u48(4, (root.offset() - 10) as u64);
            (&*self.arena.data.get()).as_slice()
        }
    }

    pub fn clear(&mut self) {
        unsafe { (&mut *self.arena.data.get()).resize(10, 0) }
    }
}

#[derive(Copy, Clone)]
pub struct TextOut<'a> {
    arena: &'a Arena,
    offset: usize,
}

#[derive(Copy, Clone)]
pub struct BytesOut<'a> {
    arena: &'a Arena,
    offset: usize,
}
