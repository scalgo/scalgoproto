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

#[derive(Copy, Clone)]
pub struct UnionType<'a, F: UnionFactory<'a>> {
    p: std::marker::PhantomData<&'a F>,
}
impl<'a, F: UnionFactory<'a>> MetaType for UnionType<'a, F> {
    fn list_bytes(len: usize) -> usize {
        len * 8
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

pub trait StructOut<'a> {
    fn new(data: ArenaSlice<'a>) -> Self;
}

pub trait StructFactory<'a>: Copy {
    type In: std::fmt::Debug;
    type Out: StructOut<'a>;
    type B;
    fn size() -> usize;
    fn new_in(bytes: &'a Self::B) -> Self::In;
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

pub struct ListOut<'a, T: MetaType, P: Placement> {
    slice: ArenaSlice<'a>,
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
            self.slice
                .set_pod_unsafe(idx * std::mem::size_of::<T>(), &v)
        };
    }
}
impl<'a, P: Placement> ListOut<'a, BoolType, P> {
    pub fn set(&mut self, idx: usize, v: bool) {
        assert!(idx < self._len);
        unsafe { self.slice.set_bit_unsafe(idx >> 3, idx & 7, v) }
    }
}
impl<'a, T: Enum, P: Placement> ListOut<'a, EnumType<T>, P> {
    pub fn set(&mut self, idx: usize, v: Option<T>) {
        assert!(idx < self._len);
        unsafe { self.slice.set_enum_unsafe(idx, v) }
    }
}
impl<'a, P: Placement> ListOut<'a, TextType, P> {
    pub fn set(&mut self, idx: usize, v: Option<&TextOut<'a>>) {
        assert!(idx < self._len);
        self.slice.set_text(idx * 6, v)
    }
    pub fn add(&mut self, idx: usize, v: &str) -> TextOut<'a> {
        assert!(idx < self._len);
        self.slice.add_text(idx * 6, v)
    }
}
impl<'a, P: Placement> ListOut<'a, BytesType, P> {
    pub fn set(&mut self, idx: usize, v: Option<&BytesOut<'a>>) {
        assert!(idx < self._len);
        self.slice.set_bytes(idx * 6, v)
    }
    pub fn add(&mut self, idx: usize, v: &[u8]) -> BytesOut<'a> {
        assert!(idx < self._len);
        self.slice.add_bytes(idx * 6, v)
    }
}
impl<'a, F: TableFactory<'a>, P: Placement> ListOut<'a, TableType<'a, F>, P> {
    pub fn set(&mut self, idx: usize, v: Option<&F::Out>) {
        assert!(idx < self._len);
        self.slice.set_table(idx * 6, v)
    }
    pub fn add(&mut self, idx: usize) -> F::Out {
        assert!(idx < self._len);
        self.slice.add_table::<F>(idx * 6)
    }
}
impl<'a, F, P: Placement> ListOut<'a, StructType<'a, F>, P>
where
    F: for<'b> StructFactory<'b>,
{
    pub fn get<'b>(&'b mut self, idx: usize) -> <F as StructFactory<'b>>::Out {
        assert!(idx < self._len);
        StructOut::new(self.slice.part(idx * F::size(), F::size()))
    }
}

impl<'a, F, P: Placement> ListOut<'a, UnionType<'a, F>, P>
where
    F: for<'b> UnionFactory<'b>,
{
    pub fn get<'b>(&'b mut self, idx: usize) -> <F as UnionFactory<'b>>::Out {
        assert!(idx < self._len);
        F::new_out(self.slice.part(idx * 8, 8))
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

pub struct UnionListAccess<'a, F: UnionFactory<'a> + 'a> {
    p: std::marker::PhantomData<&'a F>,
}
impl<'a, F: UnionFactory<'a> + 'a> ListAccess<'a> for UnionListAccess<'a, F> {
    type Output = Result<F::In>;
    fn bytes(size: usize) -> usize {
        size * 8
    }
    unsafe fn get(reader: &Reader<'a>, idx: usize) -> Self::Output {
        reader.get_union::<F>(idx * 8)
    }
}

pub trait UnionFactory<'a>: Copy {
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

    fn new_out(slice: ArenaSlice<'a>) -> Self::Out;

    fn new_inplace_out(slice: ArenaSlice<'a>, container_end: usize) -> Self::InplaceOut;
}

pub trait TableOut<P: Placement> {
    fn offset(&self) -> usize;
    fn arena(&self) -> usize;
}

pub trait TableFactory<'a>: Copy {
    type In: std::fmt::Debug;
    type Out: TableOut<Normal>;
    type InplaceOut: TableOut<Inplace>;
    fn magic() -> u32;
    fn size() -> usize;
    fn default() -> &'static [u8];
    fn new_in(reader: Reader<'a>) -> Self::In;
    fn new_out(slice: ArenaSlice<'a>) -> Self::Out;
    fn new_inplace_out(slice: ArenaSlice<'a>) -> Self::InplaceOut;
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

enum ArenaState {
    BeforeWriter,
    BeforeRoot,
    AfterRoot,
}

pub struct PArena {
    data: std::cell::UnsafeCell<Vec<u8>>,
    state: std::cell::UnsafeCell<ArenaState>,
}

impl PArena {
    fn allocate<'a>(&'a self, size: usize, fill: u8) -> ArenaSlice<'a> {
        let d = unsafe { &mut *self.data.get() };
        let offset = d.len();
        d.resize(offset + size, fill);
        ArenaSlice {
            arena: self,
            offset: offset,
            length: size,
        }
    }

    fn allocate_default<'a>(&'a self, head: usize, default: &[u8]) -> ArenaSlice<'a> {
        let d = unsafe { &mut *self.data.get() };
        let offset = d.len();
        d.reserve(offset + head + default.len());
        d.resize(offset + head, 0);
        d.extend_from_slice(default);
        ArenaSlice {
            arena: self,
            offset: offset,
            length: head + default.len(),
        }
    }

    pub fn create_table<'a, F: TableFactory<'a>>(&'a self) -> F::Out {
        let mut slice = self.allocate_default(10, F::default());
        unsafe {
            slice.set_pod_unsafe(0, &F::magic());
            slice.set_u48_unsafe(4, F::size() as u64);
            F::new_out(slice.cut(10, 0))
        }
    }

    pub fn create_bytes<'a>(&'a self, v: &[u8]) -> BytesOut<'a> {
        let mut slice = self.allocate(10 + v.len(), 0);
        unsafe {
            slice.set_pod_unsafe(0, &BYTESMAGIC);
            slice.set_u48_unsafe(4, v.len() as u64);
            std::ptr::copy_nonoverlapping(v.as_ptr(), slice.data(10), v.len());
            BytesOut { slice: slice }
        }
    }

    pub fn create_text<'a>(&'a self, v: &str) -> TextOut<'a> {
        let mut slice = self.allocate(11 + v.len(), 0);
        unsafe {
            slice.set_pod_unsafe(0, &TEXTMAGIC);
            slice.set_u48_unsafe(4, v.len() as u64);
            let data = &mut *self.data.get();
            std::ptr::copy_nonoverlapping(v.as_bytes().as_ptr(), slice.data(10), v.len());
            TextOut { slice: slice }
        }
    }

    pub fn create_list<'a, T: MetaType>(&'a self, len: usize) -> ListOut<'a, T, Normal> {
        let mut slice = self.allocate(T::list_bytes(len) + 10, T::list_def());
        unsafe {
            slice.set_pod_unsafe(0, &LISTMAGIC);
            slice.set_u48_unsafe(4, len as u64);
            ListOut {
                slice: slice.cut(10, 0),
                _len: len,
                p1: std::marker::PhantomData {},
                p2: std::marker::PhantomData {},
            }
        }
    }
}

/**
 * Represents disjoint slice of the arena
 */
pub struct ArenaSlice<'a> {
    pub arena: &'a PArena,
    offset: usize,
    length: usize,
}

impl<'a> ArenaSlice<'a> {
    pub fn arena_id(&self) -> usize {
        self.arena as * const _ as usize
    }

    pub fn get_offset(&self) -> usize {
        self.offset
    }

    pub fn part(&mut self, offset: usize, length: usize) -> ArenaSlice {
        assert!(offset + length <= self.length);
        ArenaSlice {
            arena: self.arena,
            offset: self.offset + offset,
            length: length,
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

    pub unsafe fn set_bit_unsafe(&mut self, offset: usize, bit: usize, value: bool) {
        let d = self.data(offset);
        if value {
            *d = *d | (1 << bit);
        } else {
            *d = *d & !(1 << bit);
        }
    }

    pub fn set_bit(&mut self, offset: usize, bit: usize, value: bool) {
        self.check_offset(offset, 1);
        assert!(bit < 8);
        unsafe { self.set_bit_unsafe(offset, bit, value) }
    }

    pub unsafe fn set_bool_unsafe(&mut self, offset: usize, value: bool) {
        *self.data(offset) = if value { 1 } else { 0 }
    }

    pub fn set_bool(&mut self, offset: usize, value: bool) {
        self.check_offset(offset, 1);
        unsafe { self.set_bool_unsafe(offset, value) }
    }

    pub unsafe fn set_u48_unsafe(&mut self, offset: usize, value: u64) {
        std::ptr::copy_nonoverlapping(&value as *const u64 as *const u8, self.data(offset), 6);
    }

    pub fn set_u48(&mut self, offset: usize, value: u64) {
        self.check_offset(offset, 6);
        assert!(value < 1 << 42);
        unsafe { self.set_u48_unsafe(offset, value) }
    }

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

    pub fn set_table<T: TableOut<Normal>>(&mut self, offset: usize, value: Option<&T>) {
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

    pub fn add_table<F: TableFactory<'a>>(&mut self, offset: usize) -> F::Out {
        let a = self.arena.create_table::<F>();
        self.set_table(offset, Some(&a));
        a
    }

    pub fn add_table_inplace<F: TableFactory<'a>>(
        &mut self,
        offset: usize,
        container_end: Option<usize>,
    ) -> F::InplaceOut {
        let slice = self.arena.allocate_default(0, F::default());
        self.check_inplace(slice.offset, container_end);
        self.set_u48(offset, F::size() as u64);
        F::new_inplace_out(slice)
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

    pub fn set_list<T: MetaType>(&mut self, offset: usize, v: Option<&ListOut<'a, T, Normal>>) {
        let o = match v {
            Some(t) => {
                if t.slice.arena_id() != self.arena_id() {
                    panic!("List not allocated in the same arena")
                };
                t.slice.offset
            },
            None => 0,
        } - 10;
        self.set_u48(offset, o as u64);
    }

    pub fn add_list<T: MetaType>(&mut self, offset: usize, len: usize) -> ListOut<'a, T, Normal> {
        let ans = self.arena.create_list::<T>(len);
        self.set_list(offset, Some(&ans));
        ans
    }

    pub fn add_list_inplace<T: MetaType>(
        &mut self,
        offset: usize,
        len: usize,
        container_end: Option<usize>,
    ) -> ListOut<'a, T, Inplace> {
        let slice = self.arena.allocate(T::list_bytes(len), T::list_def());
        self.check_inplace(slice.offset, container_end);
        self.set_u48(offset, len as u64);
        ListOut {
            slice: slice,
            _len: len,
            p1: std::marker::PhantomData {},
            p2: std::marker::PhantomData {},
        }
    }

    pub fn get_struct<'b, F: StructFactory<'b>>(&'b mut self, offset: usize) -> F::Out
    where
        'a: 'b,
    {
        StructOut::new(self.part(offset, F::size()))
    }

    pub fn get_union<'b, F: UnionFactory<'b>>(&'b mut self, offset: usize) -> F::Out
    where
        'a: 'b,
    {
        F::new_out(self.part(offset, 8))
    }

    pub fn get_union_inplace<'b, F: UnionFactory<'b>>(&'b mut self, offset: usize) -> F::InplaceOut
    where
        'a: 'b,
    {
        let end = self.offset + self.length;
        F::new_inplace_out(self.part(offset, 8), end)
    }
}

pub struct Arena {
    arena: PArena,
}

impl Arena {
    pub fn new(data: Vec<u8>) -> Self {
        Self {
            arena: PArena {
                data: std::cell::UnsafeCell::new(data),
                state: std::cell::UnsafeCell::<ArenaState>::new(ArenaState::BeforeWriter),
            },
        }
    }
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

pub struct Writer<'a> {
    slice: ArenaSlice<'a>,
}

impl<'a> Writer<'a> {
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

    pub fn add_root<F: TableFactory<'a> + 'a>(&mut self) -> F::Out {
        unsafe {
            if let ArenaState::BeforeRoot = *self.slice.arena.state.get() {
                *self.slice.arena.state.get() = ArenaState::AfterRoot;
            } else {
                panic!("Only one root element can be set")
            }
            let root = self.slice.arena.create_table::<F>();
            self.slice.set_pod(0, &ROOTMAGIC);
            self.slice.set_u48(4, (root.offset() - 10) as u64);
            root
        }
    }

    pub fn add_table<F: TableFactory<'a> + 'a>(&mut self) -> F::Out {
        self.slice.arena.create_table::<F>()
    }

    pub fn add_text(&mut self, text: &str) -> TextOut<'a> {
        self.slice.arena.create_text(text)
    }

    pub fn add_bytes(&mut self, bytes: &[u8]) -> BytesOut<'a> {
        self.slice.arena.create_bytes(bytes)
    }

    pub fn add_u8_list(&mut self, size: usize) -> ListOut<'a, PodType<u8>, Normal> {
        self.slice.arena.create_list::<PodType<u8>>(size)
    }
    pub fn add_u16_list(&mut self, size: usize) -> ListOut<'a, PodType<u16>, Normal> {
        self.slice.arena.create_list::<PodType<u16>>(size)
    }
    pub fn add_u32_list(&mut self, size: usize) -> ListOut<'a, PodType<u32>, Normal> {
        self.slice.arena.create_list::<PodType<u32>>(size)
    }
    pub fn add_u64_list(&mut self, size: usize) -> ListOut<'a, PodType<u64>, Normal> {
        self.slice.arena.create_list::<PodType<u64>>(size)
    }
    pub fn add_i8_list(&mut self, size: usize) -> ListOut<'a, PodType<i8>, Normal> {
        self.slice.arena.create_list::<PodType<i8>>(size)
    }
    pub fn add_i16_list(&mut self, size: usize) -> ListOut<'a, PodType<i16>, Normal> {
        self.slice.arena.create_list::<PodType<i16>>(size)
    }
    pub fn add_i32_list(&mut self, size: usize) -> ListOut<'a, PodType<i32>, Normal> {
        self.slice.arena.create_list::<PodType<i32>>(size)
    }
    pub fn add_i64_list(&mut self, size: usize) -> ListOut<'a, PodType<i64>, Normal> {
        self.slice.arena.create_list::<PodType<i64>>(size)
    }
    pub fn add_f32_list(&mut self, size: usize) -> ListOut<'a, PodType<f32>, Normal> {
        self.slice.arena.create_list::<PodType<f32>>(size)
    }
    pub fn add_f64_list(&mut self, size: usize) -> ListOut<'a, PodType<f64>, Normal> {
        self.slice.arena.create_list::<PodType<f64>>(size)
    }
    pub fn add_enum_list<T: Enum + 'a>(&mut self, size: usize) -> ListOut<'a, EnumType<T>, Normal> {
        self.slice.arena.create_list::<EnumType<T>>(size)
    }
    pub fn add_table_list<F: TableFactory<'a> + 'a>(
        &mut self,
        size: usize,
    ) -> ListOut<'a, TableType<'a, F>, Normal> {
        self.slice.arena.create_list::<TableType<'a, F>>(size)
    }
    pub fn add_struct_list<F: StructFactory<'a> + 'a>(
        &mut self,
        size: usize,
    ) -> ListOut<'a, StructType<'a, F>, Normal> {
        self.slice.arena.create_list::<StructType<F>>(size)
    }
    pub fn add_union_list<F: UnionFactory<'a> + 'a>(
        &mut self,
        size: usize,
    ) -> ListOut<'a, UnionType<'a, F>, Normal> {
        self.slice.arena.create_list::<UnionType<F>>(size)
    }
    pub fn add_text_list(&mut self, size: usize) -> ListOut<'a, TextType, Normal> {
        self.slice.arena.create_list::<TextType>(size)
    }
    pub fn add_bytes_list(&mut self, size: usize) -> ListOut<'a, BytesType, Normal> {
        self.slice.arena.create_list::<BytesType>(size)
    }
    pub fn add_bool_list(&mut self, size: usize) -> ListOut<'a, BoolType, Normal> {
        self.slice.arena.create_list::<BoolType>(size)
    }
}

pub struct TextOut<'a> {
    slice: ArenaSlice<'a>,
}

pub struct BytesOut<'a> {
    slice: ArenaSlice<'a>,
}
