//============================================================================================
//========================================> BASICS <==========================================
//============================================================================================
use std::marker::PhantomData;

pub trait Void: Copy {
    fn new() -> Self;
}

impl Void for () {
    fn new() {}
}
pub trait Pod: Copy + std::fmt::Debug {}
impl Pod for u8 {}
impl Pod for u16 {}
impl Pod for u32 {}
impl Pod for u64 {}
impl Pod for i8 {}
impl Pod for i16 {}
impl Pod for i32 {}
impl Pod for i64 {}
impl Pod for f32 {}
impl Pod for f64 {}

pub trait Enum: Copy + std::fmt::Debug {
    fn max_value() -> u8;
}

#[derive(Debug)]
pub enum Error {
    Utf8(std::str::Utf8Error),
    InvalidPointer(usize, usize),
    Overflow(),
    BadMagic(u32, u32),
}

impl From<std::str::Utf8Error> for Error {
    fn from(err: std::str::Utf8Error) -> Self {
        Self::Utf8(err)
    }
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::Utf8(e) => write!(f, "Scalgo proto error: utf8 {}", e),
            Error::InvalidPointer(offset, size) => write!(
                f,
                "Scalgo proto error: Invalid pointer at {} size is {}",
                offset, size
            ),
            Error::Overflow() => write!(f, "Scalgo proto error: Overflow"),
            Error::BadMagic(got, expected) => write!(
                f,
                "Scalgo proto error: Bad bagic got {} expected {}",
                got, expected
            ),
        }
    }
}

impl std::error::Error for Error {
    fn cause(&self) -> Option<&dyn std::error::Error> {
        match self {
            Error::Utf8(v) => Some(v),
            _ => None,
        }
    }
}

pub type Result<T> = std::result::Result<T, Error>;

static ZERO: [u8; 1024 * 16] = [0; 1024 * 16];
const ROOTMAGIC: u32 = 0xB5C0C4B3;
const LISTMAGIC: u32 = 0x3400BB46;
const DIRECTLISTMAGIC: u32 = 0xE2C6CC05;
const TEXTMAGIC: u32 = 0xD812C8F5;
const BYTESMAGIC: u32 = 0xDCDBBE10;

//============================================================================================
//========================================> READING <=========================================
//============================================================================================

pub trait StructIn<'a>: std::fmt::Debug + Clone + Copy {
    type B;
    fn size() -> usize;
    fn new(bytes: &'a Self::B) -> Self;
}

/// # Safety
///
/// This is safe to call if T is an enum with u8 storage specifier and every integer i
/// such that 0 <= i < range, is a valid enum value
pub unsafe fn to_enum<T: Enum>(v: u8) -> Option<T> {
    if v >= T::max_value() {
        None
    } else {
        let mut target: T = std::mem::MaybeUninit::uninit().assume_init();
        std::ptr::copy_nonoverlapping(&v as *const u8, &mut target as *mut T as *mut u8, 1);
        Some(target)
    }
}

/// # Safety
///
/// This method is safe to call if the length of v is sizeof(T)
/// and the bit pattern described by v is a valid state for T
pub unsafe fn to_pod<T: Pod>(v: &[u8]) -> T {
    let mut target: T = std::mem::MaybeUninit::uninit().assume_init();
    std::ptr::copy_nonoverlapping(
        v.as_ptr(),
        &mut target as *mut T as *mut u8,
        std::mem::size_of::<T>(),
    );
    target
}

/// # Safety
///
/// Should only be called if s is at least of size sizeof(S::B)
pub unsafe fn to_struct<'a, S: StructIn<'a> + 'a>(s: &[u8]) -> S {
    S::new(&*(s as *const [u8] as *const S::B))
}

pub fn to_bool(v: u8) -> bool {
    v != 0
}

/// # Safety
///
/// Should only be called when v.len() >= 6
pub unsafe fn to_u48(v: &[u8]) -> u64 {
    let mut out: u64 = 0;
    std::ptr::copy_nonoverlapping(v.as_ptr(), &mut out as *mut u64 as *mut u8, 6);
    out
}


/// # Safety
///
/// Should only be called when v.len() >= 6
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
        self.slice(offset, 1).map(|v| v[0])
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

    pub fn get_struct<S: StructIn<'a> + 'a>(&self, offset: usize) -> S {
        match self.slice(offset, S::size()) {
            Some(s) => unsafe { to_struct::<S>(s) },
            None => unsafe { to_struct::<S>(&ZERO) },
        }
    }

    pub fn get_pod<T: Pod>(&self, offset: usize) -> Option<T> {
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
            return Err(Error::InvalidPointer(o + 10, self.full.len()));
        }
        let magic: u32 = unsafe { to_pod(&self.full[o..o + 4]) };
        let size = unsafe { to_u48_usize(&self.full[o + 4..o + 10]) }?;
        Ok(Some((o + 10, magic, size)))
    }

    pub fn get_ptr_inplace(&self, offset: usize) -> Result<Option<(usize, usize)>> {
        let size = match self.get_48_usize(offset)? {
            Some(v) => v,
            None => return Ok(None),
        };
        let o = self.part.as_ptr() as usize - self.full.as_ptr() as usize + self.part.len();
        Ok(Some((o, size)))
    }

    pub fn get_table_union<T: TableIn<'a> + 'a>(
        &self,
        magic: Option<u32>,
        offset: usize,
        size: usize,
    ) -> Result<T> {
        if let Some(m) = magic {
            if m != T::magic() {
                return Err(Error::BadMagic(m, T::magic()));
            }
        }
        if offset + size > self.full.len() {
            return Err(Error::InvalidPointer(offset + size, self.full.len()));
        }
        Ok(T::new(Reader {
            full: self.full,
            part: &self.full[offset..offset + size],
        }))
    }

    pub fn get_direct_table<T: TableIn<'a> + 'a>(&self, offset: usize, size: usize) -> Result<T> {
        Ok(T::new(Reader {
            full: self.full,
            part: &self.part[offset..offset + size],
        }))
    }

    pub fn get_table<T: TableIn<'a> + 'a>(&self, offset: usize) -> Result<Option<T>> {
        match self.get_ptr(offset) {
            Err(e) => Err(e),
            Ok(None) => Ok(None),
            Ok(Some((o, m, s))) => Ok(Some(self.get_table_union::<T>(Some(m), o, s)?)),
        }
    }

    pub fn get_table_inplace<T: TableIn<'a> + 'a>(&self, offset: usize) -> Result<Option<T>> {
        match self.get_ptr_inplace(offset) {
            Err(e) => Err(e),
            Ok(None) => Ok(None),
            Ok(Some((o, s))) => Ok(Some(self.get_table_union::<T>(None, o, s)?)),
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
            return Err(Error::InvalidPointer(offset + size, self.full.len()));
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
            return Err(Error::InvalidPointer(offset + size, self.full.len()));
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

    pub fn get_list_union<A: ListRead<'a> + 'a>(
        &self,
        magic: Option<u32>,
        offset: usize,
        size: usize,
    ) -> Result<ListIn<'a, A>>
    where
        A::ItemSize: Void,
    {
        let item_size = Void::new();
        if let Some(m) = magic {
            if m != LISTMAGIC {
                return Err(Error::BadMagic(m, LISTMAGIC));
            }
        }
        let size_bytes = A::bytes(item_size, size);
        if offset + size_bytes > self.full.len() {
            return Err(Error::InvalidPointer(offset + size_bytes, self.full.len()));
        }
        Ok(ListIn {
            reader: Reader {
                full: self.full,
                part: &self.full[offset..offset + size_bytes],
            },
            _len: size,
            item_size,
            phantom: PhantomData,
        })
    }

    pub fn get_list<A: ListRead<'a> + 'a>(&self, offset: usize) -> Result<Option<ListIn<'a, A>>>
    where
        A::ItemSize: Void,
    {
        match self.get_ptr(offset) {
            Err(e) => Err(e),
            Ok(None) => Ok(None),
            Ok(Some((o, m, s))) => Ok(Some(self.get_list_union::<A>(Some(m), o, s)?)),
        }
    }

    pub fn get_direct_table_list<T: TableIn<'a> + 'a>(
        &self,
        offset: usize,
    ) -> Result<Option<ListIn<'a, DirectTableListRead<'a, T>>>> {
        let (o, m, size) = match self.get_ptr(offset) {
            Err(e) => return Err(e),
            Ok(None) => return Ok(None),
            Ok(Some(v)) => v,
        };
        if m != DIRECTLISTMAGIC {
            return Err(Error::BadMagic(m, DIRECTLISTMAGIC));
        }
        if self.full.len() < o + 8 {
            return Err(Error::InvalidPointer(o + 8, self.full.len()));
        }

        let table_magic: u32 = unsafe { to_pod(&self.full[o..o + 4]) };
        if table_magic != T::magic() {
            return Err(Error::BadMagic(table_magic, T::magic()));
        }
        let item_size: u32 = unsafe { to_pod(&self.full[o + 4..o + 8]) };
        let o = o + 8;
        let size_bytes = (item_size as usize) * size;
        if self.full.len() < o + size_bytes {
            return Err(Error::InvalidPointer(o + size_bytes, self.full.len()));
        }

        Ok(Some(ListIn {
            reader: Reader {
                full: self.full,
                part: &self.full[o..o + size_bytes],
            },
            _len: size,
            item_size,
            phantom: PhantomData,
        }))
    }

    pub fn get_list_inplace<A: ListRead<'a> + 'a>(
        &self,
        offset: usize,
    ) -> Result<Option<ListIn<'a, A>>>
    where
        A::ItemSize: Void,
    {
        match self.get_ptr_inplace(offset) {
            Err(e) => Err(e),
            Ok(None) => Ok(None),
            Ok(Some((o, s))) => Ok(Some(self.get_list_union::<A>(None, o, s)?)),
        }
    }

    pub fn get_union<U: UnionIn<'a> + 'a>(&self, offset: usize) -> Result<U> {
        let t = self.get_pod::<u16>(offset).unwrap_or(0);
        match self.get_ptr(offset + 2)? {
            Some((o, magic, size)) => U::new(t, Some(magic), o, size, self),
            None => U::new(t, None, 0, 0, self),
        }
    }

    pub fn get_union_inplace<U: UnionIn<'a> + 'a>(&self, offset: usize) -> Result<U> {
        let t = self.get_pod::<u16>(offset).unwrap_or(0);
        match self.get_ptr_inplace(offset + 2)? {
            Some((o, size)) => U::new(t, None, o, size, self),
            None => U::new(t, None, 0, 0, self),
        }
    }
}

pub trait ListRead<'a>: Clone + Copy {
    type Output: std::fmt::Debug;
    type ItemSize: Copy;
    fn bytes(item_size: Self::ItemSize, size: usize) -> usize;

    /// # Safety
    ///
    /// This is safe to call as long as the idx is less than the size of the list
    /// and every possibly bit pattern of size sizeof::<Output> is a valid representation
    /// of an output object
    unsafe fn get(item_size: Self::ItemSize, reader: &Reader<'a>, idx: usize) -> Self::Output;
}

#[derive(Clone, Copy)]
pub struct ListIn<'a, A: ListRead<'a>> {
    reader: Reader<'a>,
    _len: usize,
    item_size: A::ItemSize,
    phantom: PhantomData<A>,
}

impl<'a, A: ListRead<'a>> ListIn<'a, A> {
    pub fn len(&self) -> usize {
        self._len
    }

    pub fn is_empty(&self) -> bool {
        self._len == 0
    }

    pub fn get(&self, idx: usize) -> A::Output {
        assert!(idx < self._len);
        unsafe { A::get(self.item_size, &self.reader, idx) }
    }

    pub fn iter(&self) -> ListIter<'a, A> {
        ListIter {
            reader: self.reader,
            _len: self._len,
            idx: 0,
            item_size: self.item_size,
            phantom: PhantomData,
        }
    }
}

pub struct ListIter<'a, A: ListRead<'a>> {
    reader: Reader<'a>,
    _len: usize,
    idx: usize,
    item_size: A::ItemSize,
    phantom: PhantomData<A>,
}

impl<'a, A: ListRead<'a> + 'a> std::iter::Iterator for ListIter<'a, A> {
    type Item = A::Output;

    fn next(&mut self) -> Option<Self::Item> {
        if self.idx >= self._len {
            return None;
        }
        let ans = unsafe { A::get(self.item_size, &self.reader, self.idx) };
        self.idx += 1;
        Some(ans)
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        let s = self._len - self.idx;
        (s, Some(s))
    }
}

impl<'a, A: ListRead<'a> + 'a> std::iter::IntoIterator for ListIn<'a, A> {
    type Item = A::Output;
    type IntoIter = ListIter<'a, A>;

    fn into_iter(self) -> Self::IntoIter {
        Self::IntoIter {
            reader: self.reader,
            _len: self._len,
            idx: 0,
            item_size: self.item_size,
            phantom: PhantomData,
        }
    }
}

impl<'a, A: ListRead<'a>> std::fmt::Debug for ListIn<'a, A> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("[")?;
        let l = self.len();
        for i in 0..l {
            if i != 0 {
                f.write_str(", ")?;
            }
            write!(f, "{:?}", self.get(0))?;
        }
        f.write_str("]")?;
        Ok(())
    }
}

#[derive(Clone, Copy)]
pub struct PodListRead<'a, T: Pod> {
    p: PhantomData<&'a T>,
}

impl<'a, T: Pod> ListRead<'a> for PodListRead<'a, T> {
    type Output = T;
    type ItemSize = ();
    fn bytes(_: (), size: usize) -> usize {
        size * std::mem::size_of::<T>()
    }

    unsafe fn get(_: (), reader: &Reader<'a>, idx: usize) -> Self::Output {
        reader
            .get_pod::<T>(idx * std::mem::size_of::<T>())
            .expect("Index error")
    }
}

#[derive(Clone, Copy)]
pub struct EnumListRead<'a, T: Enum> {
    p: PhantomData<&'a T>,
}

impl<'a, T: Enum> ListRead<'a> for EnumListRead<'a, T> {
    type Output = Option<T>;
    type ItemSize = ();

    fn bytes(_: (), size: usize) -> usize {
        size
    }

    unsafe fn get(_: (), reader: &Reader<'a>, idx: usize) -> Self::Output {
        reader.get_enum::<T>(idx, 255)
    }
}

#[derive(Clone, Copy)]
pub struct StructListRead<'a, S: StructIn<'a> + 'a> {
    p: PhantomData<&'a S>,
}

impl<'a, S: StructIn<'a> + 'a> ListRead<'a> for StructListRead<'a, S> {
    type Output = S;
    type ItemSize = ();

    fn bytes(_: (), size: usize) -> usize {
        size * S::size()
    }

    unsafe fn get(_: (), reader: &Reader<'a>, idx: usize) -> S {
        reader.get_struct::<S>(idx * S::size())
    }
}

#[derive(Clone, Copy)]
pub struct TextListRead<'a> {
    p: PhantomData<&'a u8>,
}

impl<'a> ListRead<'a> for TextListRead<'a> {
    type Output = Result<Option<&'a str>>;
    type ItemSize = ();

    fn bytes(_: (), size: usize) -> usize {
        size * 6
    }

    unsafe fn get(_: (), reader: &Reader<'a>, idx: usize) -> Self::Output {
        reader.get_text(idx * 6)
    }
}

#[derive(Clone, Copy)]
pub struct BytesListRead<'a> {
    p: PhantomData<&'a u8>,
}

impl<'a> ListRead<'a> for BytesListRead<'a> {
    type Output = Result<Option<&'a [u8]>>;
    type ItemSize = ();

    fn bytes(_: (), size: usize) -> usize {
        size * 6
    }

    unsafe fn get(_: (), reader: &Reader<'a>, idx: usize) -> Self::Output {
        reader.get_bytes(idx * 6)
    }
}

#[derive(Clone, Copy)]
pub struct TableListRead<'a, T: TableIn<'a> + 'a> {
    p: PhantomData<&'a T>,
}

impl<'a, T: TableIn<'a> + 'a> ListRead<'a> for TableListRead<'a, T> {
    type Output = Result<Option<T>>;
    type ItemSize = ();

    fn bytes(_: (), size: usize) -> usize {
        size * 6
    }

    unsafe fn get(_: (), reader: &Reader<'a>, idx: usize) -> Self::Output {
        reader.get_table::<T>(idx * 6)
    }
}

#[derive(Clone, Copy)]
pub struct DirectTableListRead<'a, T: TableIn<'a> + 'a> {
    phantom: PhantomData<&'a T>,
}

impl<'a, T: TableIn<'a> + 'a> ListRead<'a> for DirectTableListRead<'a, T> {
    type Output = Result<T>;
    type ItemSize = u32;

    fn bytes(item_size: u32, size: usize) -> usize {
        item_size as usize * size
    }

    unsafe fn get(item_size: u32, reader: &Reader<'a>, idx: usize) -> Self::Output {
        reader.get_direct_table(item_size as usize * idx, item_size as usize)
    }
}

#[derive(Clone, Copy)]
pub struct BoolListRead<'a> {
    p: PhantomData<&'a bool>,
}

impl<'a> ListRead<'a> for BoolListRead<'a> {
    type Output = bool;
    type ItemSize = ();

    fn bytes(_: (), size: usize) -> usize {
        (size + 7) >> 3
    }

    unsafe fn get(_: (), reader: &Reader<'a>, idx: usize) -> bool {
        reader.get_bit(idx >> 3, idx & 7)
    }
}

#[derive(Clone, Copy)]
pub struct UnionListRead<'a, U: UnionIn<'a> + 'a> {
    p: PhantomData<&'a U>,
}

impl<'a, U: UnionIn<'a> + 'a> ListRead<'a> for UnionListRead<'a, U> {
    type Output = Result<U>;

    type ItemSize = ();

    fn bytes(_: (), size: usize) -> usize {
        size * 8
    }
    unsafe fn get(_: (), reader: &Reader<'a>, idx: usize) -> Self::Output {
        reader.get_union::<U>(idx * 8)
    }
}

pub trait UnionIn<'a>: std::fmt::Debug + std::marker::Sized + Clone + Copy {
    fn new(
        t: u16,
        magic: Option<u32>,
        offset: usize,
        size: usize,
        reader: &Reader<'a>,
    ) -> Result<Self>;
}

pub trait TableIn<'a>: std::fmt::Debug + Clone + Copy {
    fn magic() -> u32;
    fn new(reader: Reader<'a>) -> Self;
}

//============================================================================================
//========================================> WRITING <=========================================
//============================================================================================

/// Trait used to describe the placment of lists, tabels and unions.
/// There should only be two implementations: Normal and Inplace .
/// This is an internal trait, it should not be used or implemented in user code.
pub trait Placement {}

pub struct Inplace {}
impl Placement for Inplace {}

pub struct Normal {}
impl Placement for Normal {}

enum ArenaState {
    BeforeWriter,
    BeforeRoot,
    AfterRoot,
}

pub struct PArena {
    data: std::cell::UnsafeCell<Vec<u8>>,
    state: std::cell::UnsafeCell<ArenaState>,
}

/// Represents disjoint slice of the arena
/// Note that this is an internal struct, it should not be used from user code
pub struct ArenaSlice<'a> {
    pub arena: &'a PArena,
    offset: usize,
    length: usize,
}

pub struct TextOut<'a> {
    slice: ArenaSlice<'a>,
}

pub struct BytesOut<'a> {
    slice: ArenaSlice<'a>,
}

pub trait StructOut<'a> {
    fn size() -> usize;
    fn new(data: ArenaSlice<'a>) -> Self;
}

pub trait Union<'a> {
    type Out;
    type InplaceOut;
    fn new_out(slice: ArenaSlice<'a>) -> Self::Out;
    fn new_inplace_out(slice: ArenaSlice<'a>, container_end: usize) -> Self::InplaceOut;
}

pub trait Struct<'a> {
    type Out: StructOut<'a>;
}

pub trait TableOut<'a, P: Placement> {
    fn magic() -> u32;
    fn size() -> usize;
    fn default() -> &'static [u8];
    fn new(slice: ArenaSlice<'a>) -> Self;
    fn offset(&self) -> usize;
    fn arena(&self) -> usize;
}

/* The meta types describes types of members */
pub trait ListWrite {
    fn list_bytes(len: usize) -> usize;
    fn list_def() -> u8 {
        0
    }
    fn list_head_size() -> usize {
        10
    }
}

pub struct PodListWrite<T: Pod> {
    p: PhantomData<T>,
}
impl<T: Pod> ListWrite for PodListWrite<T> {
    fn list_bytes(len: usize) -> usize {
        len * std::mem::size_of::<T>()
    }
}

pub struct BoolListWrite {}
impl ListWrite for BoolListWrite {
    fn list_bytes(len: usize) -> usize {
        (len + 7) >> 3
    }
}

pub struct EnumListWrite<T: Enum> {
    p: PhantomData<T>,
}
impl<T: Enum> ListWrite for EnumListWrite<T> {
    fn list_bytes(len: usize) -> usize {
        len
    }

    fn list_def() -> u8 {
        255
    }
}

pub struct TextListWrite {}
impl ListWrite for TextListWrite {
    fn list_bytes(len: usize) -> usize {
        len * 6
    }
}

pub struct BytesListWrite {}
impl ListWrite for BytesListWrite {
    fn list_bytes(len: usize) -> usize {
        len * 6
    }
}

pub struct TableListWrite<'a, T> {
    p: PhantomData<&'a T>,
}
impl<'a, T> ListWrite for TableListWrite<'a, T> {
    fn list_bytes(len: usize) -> usize {
        len * 6
    }
}

pub struct DirectTableListWrite<'a, T: TableOut<'a, Normal> + 'a> {
    p: PhantomData<&'a T>,
}
impl<'a, T: TableOut<'a, Normal>> ListWrite for DirectTableListWrite<'a, T> {
    fn list_bytes(len: usize) -> usize {
        len * T::size()
    }
    fn list_head_size() -> usize {
        18
    }
}

pub struct StructListWrite<'a, S: StructOut<'a>> {
    p: PhantomData<&'a S>,
}
impl<'a, S: StructOut<'a>> ListWrite for StructListWrite<'a, S> {
    fn list_bytes(len: usize) -> usize {
        len * S::size()
    }
}

pub struct UnionListWrite<'a, F: Union<'a>> {
    p: PhantomData<&'a F>,
}
impl<'a, F: Union<'a>> ListWrite for UnionListWrite<'a, F> {
    fn list_bytes(len: usize) -> usize {
        len * 8
    }
}

pub struct ListOut<'a, T: ListWrite, P: Placement> {
    slice: ArenaSlice<'a>,
    _len: usize,
    p1: PhantomData<T>,
    p2: PhantomData<P>,
}
impl<'a, T: ListWrite, P: Placement> ListOut<'a, T, P> {
    pub fn len(&self) -> usize {
        self._len
    }
    pub fn is_empty(&self) -> bool {
        self._len == 0
    }
}

impl<'a, T: Pod, P: Placement> ListOut<'a, PodListWrite<T>, P> {
    pub fn set(&mut self, idx: usize, v: T) {
        assert!(idx < self._len);
        unsafe {
            self.slice
                .set_pod_unsafe(idx * std::mem::size_of::<T>(), &v)
        };
    }
}

impl<'a, P: Placement> ListOut<'a, BoolListWrite, P> {
    pub fn set(&mut self, idx: usize, v: bool) {
        assert!(idx < self._len);
        unsafe { self.slice.set_bit_unsafe(idx >> 3, idx & 7, v) }
    }
}

impl<'a, T: Enum, P: Placement> ListOut<'a, EnumListWrite<T>, P> {
    pub fn set(&mut self, idx: usize, v: Option<T>) {
        assert!(idx < self._len);
        unsafe { self.slice.set_enum_unsafe(idx, v) }
    }
}

impl<'a, P: Placement> ListOut<'a, TextListWrite, P> {
    pub fn set(&mut self, idx: usize, v: Option<&TextOut<'a>>) {
        assert!(idx < self._len);
        self.slice.set_text(idx * 6, v)
    }
    pub fn add(&mut self, idx: usize, v: &str) -> TextOut<'a> {
        assert!(idx < self._len);
        self.slice.add_text(idx * 6, v)
    }
}

impl<'a, P: Placement> ListOut<'a, BytesListWrite, P> {
    pub fn set(&mut self, idx: usize, v: Option<&BytesOut<'a>>) {
        assert!(idx < self._len);
        self.slice.set_bytes(idx * 6, v)
    }
    pub fn add(&mut self, idx: usize, v: &[u8]) -> BytesOut<'a> {
        assert!(idx < self._len);
        self.slice.add_bytes(idx * 6, v)
    }
}

impl<'a, T: TableOut<'a, Normal> + 'a, P: Placement> ListOut<'a, TableListWrite<'a, T>, P> {
    pub fn set(&mut self, idx: usize, v: Option<&T>) {
        assert!(idx < self._len);
        self.slice.set_table(idx * 6, v)
    }
    pub fn add(&mut self, idx: usize) -> T {
        assert!(idx < self._len);
        self.slice.add_table::<T>(idx * 6)
    }
}

impl<'a, T: TableOut<'a, Normal> + 'a, P: Placement> ListOut<'a, DirectTableListWrite<'a, T>, P> {
    pub fn get(&mut self, idx: usize) -> T {
        assert!(idx < self._len);
        T::new(self.slice.part(idx * T::size(), T::size()))
    }
}

impl<'a, S: StructOut<'a>, P: Placement> ListOut<'a, StructListWrite<'a, S>, P> {
    pub fn get(&mut self, idx: usize) -> S {
        assert!(idx < self._len);
        S::new(self.slice.part(idx * S::size(), S::size()))
    }
}

impl<'a, F: Union<'a>, P: Placement> ListOut<'a, UnionListWrite<'a, F>, P> {
    pub fn get(&mut self, idx: usize) -> F::Out {
        assert!(idx < self._len);
        F::new_out(self.slice.part(idx * 8, 8))
    }
}

impl PArena {
    fn allocate(&self, size: usize, fill: u8) -> ArenaSlice {
        let d = unsafe { &mut *self.data.get() };
        let offset = d.len();
        d.resize(offset + size, fill);
        ArenaSlice {
            arena: self,
            offset,
            length: size,
        }
    }

    fn allocate_default(&self, head: usize, default: &[u8]) -> ArenaSlice {
        let d = unsafe { &mut *self.data.get() };
        let offset = d.len();
        d.reserve(offset + head + default.len());
        d.resize(offset + head, 0);
        d.extend_from_slice(default);
        ArenaSlice {
            arena: self,
            offset,
            length: head + default.len(),
        }
    }

    pub fn create_table<'a, T: TableOut<'a, Normal>>(&'a self) -> T {
        let mut slice = self.allocate_default(10, T::default());
        unsafe {
            slice.set_pod_unsafe(0, &T::magic());
            slice.set_u48_unsafe(4, T::size() as u64);
            T::new(slice.cut(10, 0))
        }
    }

    pub fn create_bytes<'a>(&'a self, v: &[u8]) -> BytesOut<'a> {
        let mut slice = self.allocate(10 + v.len(), 0);
        unsafe {
            slice.set_pod_unsafe(0, &BYTESMAGIC);
            slice.set_u48_unsafe(4, v.len() as u64);
            std::ptr::copy_nonoverlapping(v.as_ptr(), slice.data(10), v.len());
            BytesOut { slice }
        }
    }

    pub fn create_text<'a>(&'a self, v: &str) -> TextOut<'a> {
        let mut slice = self.allocate(11 + v.len(), 0);
        unsafe {
            slice.set_pod_unsafe(0, &TEXTMAGIC);
            slice.set_u48_unsafe(4, v.len() as u64);
            std::ptr::copy_nonoverlapping(v.as_bytes().as_ptr(), slice.data(10), v.len());
            TextOut { slice }
        }
    }

    pub fn create_list<T: ListWrite>(&self, len: usize) -> ListOut<T, Normal> {
        let mut slice = self.allocate(T::list_bytes(len) + 10, T::list_def());
        unsafe {
            slice.set_pod_unsafe(0, &LISTMAGIC);
            slice.set_u48_unsafe(4, len as u64);
            ListOut {
                slice: slice.cut(10, 0),
                _len: len,
                p1: PhantomData,
                p2: PhantomData,
            }
        }
    }

    pub fn create_direct_table_list<'a, T: TableOut<'a, Normal> + 'a>(
        &self,
        len: usize,
    ) -> ListOut<DirectTableListWrite<'a, T>, Normal> {
        let mut slice = self.allocate(T::size() * len + 18, 0);
        unsafe {
            slice.set_pod_unsafe(0, &DIRECTLISTMAGIC);
            slice.set_u48_unsafe(4, len as u64);
            slice.set_pod_unsafe(10, &T::magic());
            slice.set_pod_unsafe(14, &(T::size() as u32));
            ListOut {
                slice: slice.cut(18, 0),
                _len: len,
                p1: PhantomData,
                p2: PhantomData,
            }
        }
    }
}

impl<'a> ArenaSlice<'a> {
    pub fn arena_id(&self) -> usize {
        self.arena as *const _ as usize
    }

    pub fn get_offset(&self) -> usize {
        self.offset
    }

    pub fn part(&mut self, offset: usize, length: usize) -> Self {
        assert!(offset + length <= self.length);
        ArenaSlice {
            arena: self.arena,
            offset: self.offset + offset,
            length,
        }
    }

    pub fn cut(self, start: usize, end: usize) -> Self {
        assert!(start + end <= self.length);
        ArenaSlice {
            arena: self.arena,
            offset: self.offset + start,
            length: self.length - end - start,
        }
    }

    /// # Safety
    ///
    /// This is safe as long as o is within the arena, the pointer
    /// will be valid util the arena, resizes or is dropped.
    unsafe fn data(&self, o: usize) -> *mut u8 {
        let data = &mut *self.arena.data.get();
        data.as_mut_ptr().add(self.offset + o)
    }

    fn check_offset(&self, o: usize, size: usize) {
        assert!(self.offset + o + size <= unsafe { (*self.arena.data.get()).len() });
    }

    fn check_inplace(&self, o: usize, container_end: Option<usize>) {
        let end = match container_end {
            Some(v) => v,
            _ => self.offset + self.length,
        };
        if end != o {
            panic!("Inplace members must be constructed directly after their container")
        }
    }

    /// # Safety
    ///
    /// This is safe if offset..offset+sizeof<T> is within the arena
    pub unsafe fn set_pod_unsafe<T: Copy + std::fmt::Debug>(&mut self, offset: usize, value: &T) {
        std::ptr::copy_nonoverlapping(
            value as *const T as *const u8,
            self.data(offset),
            std::mem::size_of::<T>(),
        );
    }

    pub fn set_pod<T: Copy + std::fmt::Debug>(&mut self, offset: usize, value: &T) {
        self.check_offset(offset, std::mem::size_of::<T>());
        unsafe { self.set_pod_unsafe(offset, value) }
    }

    /// # Safety
    ///
    /// This is safe if offset is within the arena and bit < 8
    pub unsafe fn set_bit_unsafe(&mut self, offset: usize, bit: usize, value: bool) {
        let d = self.data(offset);
        if value {
            *d |= 1 << bit;
        } else {
            *d &= !(1 << bit);
        }
    }

    pub fn set_bit(&mut self, offset: usize, bit: usize, value: bool) {
        self.check_offset(offset, 1);
        assert!(bit < 8);
        unsafe { self.set_bit_unsafe(offset, bit, value) }
    }

    /// # Safety
    ///
    /// This is safe if offset is within the arena
    pub unsafe fn set_bool_unsafe(&mut self, offset: usize, value: bool) {
        *self.data(offset) = if value { 1 } else { 0 }
    }

    pub fn set_bool(&mut self, offset: usize, value: bool) {
        self.check_offset(offset, 1);
        unsafe { self.set_bool_unsafe(offset, value) }
    }

    /// # Safety
    ///
    /// This is safe if offset,offset+6 is in the arena, and value is less than 1 << 42
    pub unsafe fn set_u48_unsafe(&mut self, offset: usize, value: u64) {
        std::ptr::copy_nonoverlapping(&value as *const u64 as *const u8, self.data(offset), 6);
    }

    pub fn set_u48(&mut self, offset: usize, value: u64) {
        self.check_offset(offset, 6);
        assert!(value < 1 << 42);
        unsafe { self.set_u48_unsafe(offset, value) }
    }

    /// # Safety
    ///
    /// This is safe if std::mem::size_of::<T>() == 1 and offset is within the arena
    pub unsafe fn set_enum_unsafe<T: Enum>(&mut self, offset: usize, value: Option<T>) {
        match value {
            Some(vv) => {
                std::ptr::copy_nonoverlapping(&vv as *const T as *const u8, self.data(offset), 1)
            }
            None => *self.data(offset) = 255,
        }
    }

    pub fn set_enum<T: Enum>(&mut self, offset: usize, value: Option<T>) {
        assert!(std::mem::size_of::<T>() == 1);
        self.check_offset(offset, 1);
        unsafe { self.set_enum_unsafe(offset, value) }
    }

    pub fn set_table<T: TableOut<'a, Normal>>(&mut self, offset: usize, value: Option<&T>) {
        let o = match value {
            Some(t) => {
                if t.arena() != self.arena_id() {
                    panic!("Table not allocated in the same arena")
                }
                t.offset()
            }
            None => 0,
        } - 10;
        self.set_u48(offset, o as u64);
    }

    pub fn add_table<T: TableOut<'a, Normal>>(&mut self, offset: usize) -> T {
        let a = self.arena.create_table::<T>();
        self.set_table(offset, Some(&a));
        a
    }

    pub fn add_table_inplace<T: TableOut<'a, Inplace>>(
        &mut self,
        offset: usize,
        container_end: Option<usize>,
    ) -> T {
        let slice = self.arena.allocate_default(0, T::default());
        self.check_inplace(slice.offset, container_end);
        self.set_u48(offset, T::size() as u64);
        T::new(slice)
    }

    pub fn set_bytes(&mut self, offset: usize, v: Option<&BytesOut<'a>>) {
        let o = match v {
            Some(b) => {
                if b.slice.arena_id() != self.arena_id() {
                    panic!("Bytes not allocated in the same arena")
                }
                b.slice.offset
            }
            None => 0,
        };
        self.set_u48(offset, o as u64);
    }

    pub fn add_bytes(&mut self, offset: usize, v: &[u8]) -> BytesOut<'a> {
        let ans = self.arena.create_bytes(v);
        self.set_bytes(offset, Some(&ans));
        ans
    }

    pub fn add_bytes_inplace(&mut self, offset: usize, v: &[u8], container_end: Option<usize>) {
        let slice = self.arena.allocate(v.len(), 0);
        self.check_inplace(slice.offset, container_end);
        self.set_u48(offset, v.len() as u64);
        unsafe {
            std::ptr::copy_nonoverlapping(v.as_ptr(), slice.data(0), v.len());
        };
    }

    pub fn set_text(&mut self, offset: usize, v: Option<&TextOut<'a>>) {
        let o = match v {
            Some(b) => {
                if b.slice.arena_id() != self.arena_id() {
                    panic!("Text not allocated in the same arena")
                }
                b.slice.offset
            }
            None => 0,
        };
        self.set_u48(offset, o as u64);
    }

    pub fn add_text(&mut self, offset: usize, v: &str) -> TextOut<'a> {
        let ans = self.arena.create_text(v);
        self.set_text(offset, Some(&ans));
        ans
    }

    pub fn add_text_inplace(&mut self, offset: usize, v: &str, container_end: Option<usize>) {
        let slice = self.arena.allocate(1 + v.len(), 0);
        self.check_inplace(slice.offset, container_end);
        self.set_u48(offset, v.len() as u64);
        unsafe {
            std::ptr::copy_nonoverlapping(v.as_bytes().as_ptr(), slice.data(0), v.len());
        };
    }

    pub fn set_list<T: ListWrite>(&mut self, offset: usize, v: Option<&ListOut<'a, T, Normal>>) {
        let o = match v {
            Some(t) => {
                if t.slice.arena_id() != self.arena_id() {
                    panic!("List not allocated in the same arena")
                };
                t.slice.offset
            }
            None => 0,
        } - T::list_head_size();
        self.set_u48(offset, o as u64);
    }

    pub fn add_list<T: ListWrite>(&mut self, offset: usize, len: usize) -> ListOut<'a, T, Normal> {
        let ans = self.arena.create_list::<T>(len);
        self.set_list(offset, Some(&ans));
        ans
    }

    pub fn add_direct_table_list<T: TableOut<'a, Normal> + 'a>(
        &mut self,
        offset: usize,
        len: usize,
    ) -> ListOut<'a, DirectTableListWrite<'a, T>, Normal> {
        let ans = self.arena.create_direct_table_list::<T>(len);
        self.set_list(offset, Some(&ans));
        ans
    }

    pub fn add_list_inplace<T: ListWrite>(
        &mut self,
        offset: usize,
        len: usize,
        container_end: Option<usize>,
    ) -> ListOut<'a, T, Inplace> {
        let slice = self.arena.allocate(T::list_bytes(len), T::list_def());
        self.check_inplace(slice.offset, container_end);
        self.set_u48(offset, len as u64);
        ListOut {
            slice,
            _len: len,
            p1: PhantomData,
            p2: PhantomData,
        }
    }

    pub fn get_struct<'b, F: Struct<'b>>(&'b mut self, offset: usize) -> F::Out
    where
        'a: 'b,
    {
        StructOut::new(self.part(offset, F::Out::size()))
    }

    pub fn set_data(&mut self, data: &[u8]) {
        assert!(self.length == data.len());
        unsafe {
            std::ptr::copy_nonoverlapping(data.as_ptr(), self.data(0), data.len());
        };
    }

    pub fn get_union<'b, F: Union<'b>>(&'b mut self, offset: usize) -> F::Out
    where
        'a: 'b,
    {
        F::new_out(self.part(offset, 8))
    }

    pub fn get_union_inplace<'b, F: Union<'b>>(&'b mut self, offset: usize) -> F::InplaceOut
    where
        'a: 'b,
    {
        let end = self.offset + self.length;
        F::new_inplace_out(self.part(offset, 8), end)
    }
}

//============================================================================================
//========================================> COPYIN <==========================================
//============================================================================================

/// Internal trait used for copying from intput to output
/// This should not be used or implemented in user code.
pub trait CopyIn<In> {
    fn copy_in(&mut self, i: In) -> Result<()>;
}

impl<'a, 'b, T: Pod + 'b, P: Placement> CopyIn<ListIn<'b, PodListRead<'b, T>>>
    for ListOut<'a, PodListWrite<T>, P>
{
    fn copy_in(&mut self, i: ListIn<'b, PodListRead<'b, T>>) -> Result<()> {
        assert!(i.len() == self.len());
        for n in 0..i.len() {
            self.set(n, i.get(n));
        }
        Ok(())
    }
}

impl<'a, 'b, P: Placement> CopyIn<ListIn<'b, BoolListRead<'b>>> for ListOut<'a, BoolListWrite, P> {
    fn copy_in(&mut self, i: ListIn<'b, BoolListRead<'b>>) -> Result<()> {
        assert!(i.len() == self.len());
        for n in 0..i.len() {
            self.set(n, i.get(n));
        }
        Ok(())
    }
}

impl<'a, 'b, T: Enum + 'b, P: Placement> CopyIn<ListIn<'b, EnumListRead<'b, T>>>
    for ListOut<'a, EnumListWrite<T>, P>
{
    fn copy_in(&mut self, i: ListIn<'b, EnumListRead<'b, T>>) -> Result<()> {
        assert!(i.len() == self.len());
        for n in 0..i.len() {
            self.set(n, i.get(n));
        }
        Ok(())
    }
}

impl<'a, 'b, P: Placement> CopyIn<ListIn<'b, TextListRead<'b>>> for ListOut<'a, TextListWrite, P> {
    fn copy_in(&mut self, i: ListIn<'b, TextListRead<'b>>) -> Result<()> {
        assert!(i.len() == self.len());
        for n in 0..i.len() {
            if let Some(v) = i.get(n)? {
                self.add(n, v);
            }
        }
        Ok(())
    }
}

impl<'a, 'b, P: Placement> CopyIn<ListIn<'b, BytesListRead<'b>>>
    for ListOut<'a, BytesListWrite, P>
{
    fn copy_in(&mut self, i: ListIn<'b, BytesListRead<'b>>) -> Result<()> {
        assert!(i.len() == self.len());
        for n in 0..i.len() {
            if let Some(v) = i.get(n)? {
                self.add(n, v);
            }
        }
        Ok(())
    }
}

impl<'a, 'b, Out: StructOut<'a> + 'a + CopyIn<In>, P: Placement, In: StructIn<'b> + 'b>
    CopyIn<ListIn<'b, StructListRead<'b, In>>> for ListOut<'a, StructListWrite<'a, Out>, P>
{
    fn copy_in(&mut self, i: ListIn<'b, StructListRead<'b, In>>) -> Result<()> {
        assert!(i.len() == self.len());
        for n in 0..i.len() {
            self.get(n).copy_in(i.get(n))?;
        }
        Ok(())
    }
}

impl<'a, 'b, Out: TableOut<'a, Normal> + 'a + CopyIn<In>, P: Placement, In: TableIn<'b> + 'b>
    CopyIn<ListIn<'b, TableListRead<'b, In>>> for ListOut<'a, TableListWrite<'a, Out>, P>
{
    fn copy_in(&mut self, i: ListIn<'b, TableListRead<'b, In>>) -> Result<()> {
        assert!(i.len() == self.len());
        for n in 0..i.len() {
            if let Some(v) = i.get(n)? {
                let mut t = self.add(n);
                t.copy_in(v)?;
            }
        }
        Ok(())
    }
}

impl<'a, 'b, Out: TableOut<'a, Normal> + 'a + CopyIn<In>, P: Placement, In: TableIn<'b> + 'b>
    CopyIn<ListIn<'b, DirectTableListRead<'b, In>>>
    for ListOut<'a, DirectTableListWrite<'a, Out>, P>
{
    fn copy_in(&mut self, i: ListIn<'b, DirectTableListRead<'b, In>>) -> Result<()> {
        assert!(i.len() == self.len());
        for n in 0..i.len() {
            self.get(n).copy_in(i.get(n)?)?;
        }
        Ok(())
    }
}

impl<'a, 'b, U: Union<'a> + 'a, P: Placement, In: UnionIn<'b> + 'b>
    CopyIn<ListIn<'b, UnionListRead<'b, In>>> for ListOut<'a, UnionListWrite<'a, U>, P>
where
    U::Out: CopyIn<In>,
{
    fn copy_in(&mut self, i: ListIn<'b, UnionListRead<'b, In>>) -> Result<()> {
        {
            assert!(i.len() == self.len());
            for n in 0..i.len() {
                {
                    self.get(n).copy_in(i.get(n)?)?;
                }
            }
            Ok(())
        }
    }
}

//============================================================================================
//============================> USER FACING READING AND WRITING <=============================
//============================================================================================

/// Trait implemented for every tabel, so we can talk about it without specfying In, Out or Placement
pub trait Table<'a> {
    type In: TableIn<'a>;
    type Out: TableOut<'a, Normal>;
}

/// Read a table from the given data
pub fn read_message<'a, F: Table<'a> + 'a>(data: &'a [u8]) -> Result<F::In> {
    if data.len() < 10 {
        return Err(Error::InvalidPointer(10, data.len()));
    }
    let r = Reader {
        full: data,
        part: &data[0..10],
    };
    match r.get_table::<F::In>(4) {
        Err(e) => Err(e),
        Ok(Some(v)) => Ok(v),
        Ok(None) => Err(Error::InvalidPointer(0, data.len())),
    }
}

/// Writer used to write message
pub struct Writer<'a> {
    slice: ArenaSlice<'a>,
}

/// Arena a message is written in
pub struct Arena {
    arena: PArena,
}

impl Arena {
    /// Construct an arena storing data in the given Vec
    /// the data currently in the Vec is discarded
    pub fn new(mut data: Vec<u8>) -> Self {
        data.clear();
        Self {
            arena: PArena {
                data: std::cell::UnsafeCell::new(data),
                state: std::cell::UnsafeCell::<ArenaState>::new(ArenaState::BeforeWriter),
            },
        }
    }

    /// Get finalized message, note that a writer must have been constructed
    /// for the arena and a root added before this method may be called.
    /// The Vec returned is the one given to new, but now with the constructed message
    pub fn finalize(self) -> Vec<u8> {
        unsafe {
            if let ArenaState::AfterRoot = *self.arena.state.get() {
            } else {
                panic!("A root should be set before finalize is called")
            }
        };
        self.arena.data.into_inner()
    }
}

impl<'a> Writer<'a> {
    /// Construct a new writer for the given arena
    /// Note that exactly one writer must be allocated for an arena
    pub fn new(arena: &'a Arena) -> Self {
        unsafe {
            if let ArenaState::BeforeWriter = *arena.arena.state.get() {
                *arena.arena.state.get() = ArenaState::BeforeRoot;
            } else {
                panic!("Only one writer can be constructed per arena")
            }
        }
        Self {
            slice: arena.arena.allocate(10, 0),
        }
    }

    /// Add a root table to the message
    /// Note that exactly one root must be added to a message
    pub fn add_root<F: Table<'a> + 'a>(&mut self) -> F::Out {
        unsafe {
            if let ArenaState::BeforeRoot = *self.slice.arena.state.get() {
                *self.slice.arena.state.get() = ArenaState::AfterRoot;
            } else {
                panic!("Only one root element can be set")
            }
            let root = self.slice.arena.create_table::<F::Out>();
            self.slice.set_pod(0, &ROOTMAGIC);
            self.slice.set_u48(4, (root.offset() - 10) as u64);
            root
        }
    }

    pub fn add_table<F: Table<'a> + 'a>(&mut self) -> F::Out {
        self.slice.arena.create_table::<F::Out>()
    }

    pub fn add_text(&mut self, text: &str) -> TextOut<'a> {
        self.slice.arena.create_text(text)
    }

    pub fn add_bytes(&mut self, bytes: &[u8]) -> BytesOut<'a> {
        self.slice.arena.create_bytes(bytes)
    }

    pub fn add_u8_list(&mut self, size: usize) -> ListOut<'a, PodListWrite<u8>, Normal> {
        self.slice.arena.create_list::<PodListWrite<u8>>(size)
    }

    pub fn add_u16_list(&mut self, size: usize) -> ListOut<'a, PodListWrite<u16>, Normal> {
        self.slice.arena.create_list::<PodListWrite<u16>>(size)
    }

    pub fn add_u32_list(&mut self, size: usize) -> ListOut<'a, PodListWrite<u32>, Normal> {
        self.slice.arena.create_list::<PodListWrite<u32>>(size)
    }

    pub fn add_u64_list(&mut self, size: usize) -> ListOut<'a, PodListWrite<u64>, Normal> {
        self.slice.arena.create_list::<PodListWrite<u64>>(size)
    }

    pub fn add_i8_list(&mut self, size: usize) -> ListOut<'a, PodListWrite<i8>, Normal> {
        self.slice.arena.create_list::<PodListWrite<i8>>(size)
    }

    pub fn add_i16_list(&mut self, size: usize) -> ListOut<'a, PodListWrite<i16>, Normal> {
        self.slice.arena.create_list::<PodListWrite<i16>>(size)
    }

    pub fn add_i32_list(&mut self, size: usize) -> ListOut<'a, PodListWrite<i32>, Normal> {
        self.slice.arena.create_list::<PodListWrite<i32>>(size)
    }

    pub fn add_i64_list(&mut self, size: usize) -> ListOut<'a, PodListWrite<i64>, Normal> {
        self.slice.arena.create_list::<PodListWrite<i64>>(size)
    }

    pub fn add_f32_list(&mut self, size: usize) -> ListOut<'a, PodListWrite<f32>, Normal> {
        self.slice.arena.create_list::<PodListWrite<f32>>(size)
    }

    pub fn add_f64_list(&mut self, size: usize) -> ListOut<'a, PodListWrite<f64>, Normal> {
        self.slice.arena.create_list::<PodListWrite<f64>>(size)
    }

    pub fn add_enum_list<T: Enum + 'a>(
        &mut self,
        size: usize,
    ) -> ListOut<'a, EnumListWrite<T>, Normal> {
        self.slice.arena.create_list::<EnumListWrite<T>>(size)
    }

    pub fn add_table_list<F: Table<'a> + 'a>(
        &mut self,
        size: usize,
    ) -> ListOut<'a, TableListWrite<'a, F::Out>, Normal> {
        self.slice
            .arena
            .create_list::<TableListWrite<'a, F::Out>>(size)
    }

    pub fn add_direct_table_list<F: Table<'a> + 'a>(
        &mut self,
        size: usize,
    ) -> ListOut<'a, DirectTableListWrite<'a, F::Out>, Normal> {
        self.slice.arena.create_direct_table_list::<F::Out>(size)
    }

    pub fn add_struct_list<F: Struct<'a> + 'a>(
        &mut self,
        size: usize,
    ) -> ListOut<'a, StructListWrite<'a, F::Out>, Normal> {
        self.slice
            .arena
            .create_list::<StructListWrite<F::Out>>(size)
    }

    pub fn add_union_list<F: Union<'a> + 'a>(
        &mut self,
        size: usize,
    ) -> ListOut<'a, UnionListWrite<'a, F>, Normal> {
        self.slice.arena.create_list::<UnionListWrite<F>>(size)
    }

    pub fn add_text_list(&mut self, size: usize) -> ListOut<'a, TextListWrite, Normal> {
        self.slice.arena.create_list::<TextListWrite>(size)
    }

    pub fn add_bytes_list(&mut self, size: usize) -> ListOut<'a, BytesListWrite, Normal> {
        self.slice.arena.create_list::<BytesListWrite>(size)
    }

    pub fn add_bool_list(&mut self, size: usize) -> ListOut<'a, BoolListWrite, Normal> {
        self.slice.arena.create_list::<BoolListWrite>(size)
    }
}
