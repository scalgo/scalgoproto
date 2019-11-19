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

/// get_inner(self, T, i): Use self.reader (a ref to a ScalgoprotoReader)
/// to read size_of<T>() bytes at i and transmute to a Result<&T>.
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
