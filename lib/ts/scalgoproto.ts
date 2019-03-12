export const MESSAGE_MAGIC = 0xB5C0C4B3
export const TEXT_MAGIC = 0xD812C8F5
export const BYTES_MAGIC = 0xDCDBBE10
export const LIST_MAGIC = 0x3400BB46

export class StructType {
	static readonly _WIDTH: number = 0
}

export class ListIn<T> {
	[i: number]: T;
	get length(): number { return this.size; }
	constructor(public size: number,
				public offset: number,
				public acc: (start: number, index: number) => T) {}
};

const listInHandler = {
	get : <T>(obj: ListIn<T>, prop: string) : number | T => {
		if (prop === 'length') return obj.size;
		const index = +prop;
		if (!Number.isInteger(index) || index < 0 || index >= obj.size)
			throw Error('Index outside range');
		return obj.acc(obj.offset, index);
	}
};



export abstract class UnionIn {
	constructor(public _reader: Reader,
				public _type: number,
				public _offset: number,
				public _size: number|null = null) {}

	_getPtr(magic: number): [ number, number ] {
		if (this._size !== null) return [ this._offset, this._size ];
		return [ this._offset + 10, this._reader._readSize(this._offset, magic) ];
	}
}

export abstract class TableIn {
	static readonly _MAGIC: number = 0;

	/**
	 * Private constructor. Use the accessor methods on tables or the root method on
	 * Reader to get an instance
	 */
	constructor(public _reader: Reader, public _offset: number, public _size: number) {}

	_getUint48F(o: number): number { return this._reader._readUint48(o + this._offset); }

	_getInt8(o: number, d: number): number {
		if (o >= this._size) return d;
		return this._reader._data.getInt8(o + this._offset);
	}

	_getUint8(o: number, d: number): number {
		if (o >= this._size) return d;
		return this._reader._data.getUint8(o + this._offset);
	}

	_getInt16(o: number, d: number): number {
		if (o >= this._size) return d;
		return this._reader._data.getInt16(o + this._offset, true);
	}

	_getUint16(o: number, d: number): number {
		if (o >= this._size) return d;
		return this._reader._data.getUint16(o + this._offset, true);
	}

	_getInt32(o: number, d: number): number {
		if (o >= this._size) return d;
		return this._reader._data.getInt32(o + this._offset, true);
	}

	_getUint32(o: number, d: number): number {
		if (o >= this._size) return d;
		return this._reader._data.getUint32(o + this._offset, true);
	}

	_getUint48(o: number): number {
		if (o >= this._size) return 0;
		return this._reader._readUint48(o + this._offset);
	}

	_getInt64(o: number, d: number): number {
		if (o >= this._size) return d;
		return this._reader._readInt64(o + this._offset);
	}

	_getUint64(o: number, d: number): number {
		if (o >= this._size) return d;
		return this._reader._readUint64(o + this._offset);
	}

	_getFloat32(o: number, d: number): number {
		if (o >= this._size) return d;
		return this._reader._data.getFloat32(o + this._offset, true);
	}

	_getFloat64(o: number, d: number): number {
		if (o >= this._size) return d;
		return this._reader._data.getFloat64(o + this._offset, true);
	}

	_getBit(o: number, b: number, d: boolean): boolean {
		if (o >= this._size) return d;
		const v = this._reader._data.getUint8(o + this._offset);
		return (v & (1 << b)) != 0;
	}

	_getPtr(o: number, magic: number): [ number, number ] {
		const off = this._getUint48(o);
		if (off == 0) return [ 0, 0 ];
		const size = this._reader._readSize(off, magic);
		return [ off + 10, size ];
	}

	_getPtrInplace(o: number, magic: number): [ number, number ] {
		const size = this._getUint48(o);
		if (size == 0) return [ 0, 0 ];
		return [ this._offset + this._size, size ];
	}
};

// Responsible for reading a message
export class Reader {
	_data: DataView;

	constructor(data: ArrayBuffer) { this._data = new DataView(data); }

	_readUint48(o: number): number {
		// Note we cannot use shifts here as it would turn it into a 32bit instead of a
		// double
		return this._data.getUint32(o, true) +
			   this._data.getUint16(o + 4, true) * 2 ** 32;
	}

	_readInt64(o: number): number {
		return this._data.getUint32(o, true) + this._data.getInt32(o + 4, true) * 2 ** 32;
	}

	_readUint64(o: number): number {
		return this._data.getUint32(o, true) +
			   this._data.getUint32(o + 4, true) * 2 ** 32;
	}

	_readSize(o: number, magic: number): number {
		const m = this._data.getUint32(o, true);
		if (m != magic) throw Error('Bad magic');
		return this._readUint48(o + 4);
	}

	_readText(offset: number, len: number): string {
		let ans = '';
		const end = offset + len;
		while (offset < end) {
			const c = this._data.getUint8(offset++);
			switch (c >> 4) {
			case 0:
			case 1:
			case 2:
			case 3:
			case 4:
			case 5:
			case 6:
			case 7: ans += String.fromCharCode(c); break;
			case 12:
			case 13: {
				const char2 = this._data.getUint8(offset++);
				ans += String.fromCharCode(((c & 0x1F) << 6) | (char2 & 0x3F));
				break;
			}
			case 14: {
				const char2 = this._data.getUint8(offset++);
				const char3 = this._data.getUint8(offset++);
				ans += String.fromCharCode(((c & 0x0F) << 12) | ((char2 & 0x3F) << 6) |
										   ((char3 & 0x3F) << 0));
			} break;
			}
		}
		return ans;
	}

	_getInt8List(o: number, s: number): ListIn<number> {
		return new Proxy<ListIn<number>>(
		  new ListIn<number>(
			s, o, (s: number, i: number) => { return this._data.getInt8(s + i); }),
		  listInHandler);
	}

	_getInt16List(o: number, s: number): ListIn<number> {
		return new Proxy<ListIn<number>>(
		  new ListIn<number>(
			s,
			o,
			(s: number, i: number) => { return this._data.getInt16(s + i * 2, true); }),
		  listInHandler);
	}

	_getInt32List(o: number, s: number): ListIn<number> {
		return new Proxy<ListIn<number>>(
		  new ListIn<number>(
			s,
			o,
			(s: number, i: number) => { return this._data.getInt32(s + i * 4, true); }),
		  listInHandler);
	}

	_getInt64List(o: number, s: number): ListIn<number> {
		return new Proxy<ListIn<number>>(
		  new ListIn<number>(
			s, o, (s: number, i: number) => { return this._readInt64(s + i * 8); }),
		  listInHandler);
	}

	_getUint8List(o: number, s: number): ListIn<number> {
		return new Proxy<ListIn<number>>(
		  new ListIn<number>(
			s, o, (s: number, i: number) => { return this._data.getUint8(s + i); }),
		  listInHandler);
	}

	_getUint16List(o: number, s: number): ListIn<number> {
		return new Proxy<ListIn<number>>(
		  new ListIn<number>(
			s,
			o,
			(s: number, i: number) => { return this._data.getUint16(s + i * 2, true); }),
		  listInHandler);
	}

	_getUint32List(o: number, s: number): ListIn<number> {
		return new Proxy<ListIn<number>>(
		  new ListIn<number>(
			s,
			o,
			(s: number, i: number) => { return this._data.getUint32(s + i * 4, true); }),
		  listInHandler);
	}

	_getUint64List(o: number, s: number): ListIn<number> {
		return new Proxy<ListIn<number>>(
		  new ListIn<number>(
			s, o, (s: number, i: number) => { return this._readUint64(s + i * 8); }),
		  listInHandler);
	}

	_getFloat32List(o: number, s: number): ListIn<number> {
		return new Proxy<ListIn<number>>(
		  new ListIn<number>(
			s,
			o,
			(s: number, i: number) => { return this._data.getFloat32(s + i * 4, true); }),
		  listInHandler);
	}

	_getFloat64List(o: number, s: number): ListIn<number> {
		return new Proxy<ListIn<number>>(
		  new ListIn<number>(
			s,
			o,
			(s: number, i: number) => { return this._data.getFloat64(s + i * 8, true); }),
		  listInHandler);
	}

	_getBoolList(o: number, s: number): ListIn<boolean> {
		return new Proxy<ListIn<boolean>>(
		  new ListIn<boolean>(s, o, (s: number, i: number) => {
			  return ((this._data.getUint8(s + (i >> 3)) >> (i & 7)) & 1) != 0;
		  }), listInHandler);
	}

	_getStructList<S>(o: number,
					  s: number,
					  type: { _WIDTH: number, _read(reader: Reader, o: Number): S }):
	  ListIn<S> {
		return new Proxy<ListIn<S>>(new ListIn<S>(s, o, (s: number, i: number) => {
										return type._read(this, s + i * type._WIDTH);
									}), listInHandler);
	}

	_getEnumList<E>(o: number, s: number): ListIn<E|null> {
		return new Proxy<ListIn<E|null>>(
		  new ListIn<E|null>(s, o, (s: number, i: number) => {
			  const v = this._data.getUint8(s + i);
			  if (v === 255) return null;
			  return v as any as E;
		  }), listInHandler);
	}

	_getTextList(o: number, s: number): ListIn<string|null> {
		return new Proxy<ListIn<string|null>>(
		  new ListIn<string|null>(s, o, (s: number, i: number) => {
			  const off = this._readUint48(s + i * 6);
			  if (off == 0) return null;
			  const size = this._readSize(off, TEXT_MAGIC);
			  return this._readText(off + 10, size);
		  }), listInHandler);
	}

	_getBytesList(o: number, s: number): ListIn<ArrayBuffer|null> {
		return new Proxy<ListIn<ArrayBuffer|null>>(
		  new ListIn<ArrayBuffer|null>(s, o, (s: number, i: number) => {
			  const off = this._readUint48(s + i * 6);
			  if (off == 0) return null;
			  const size = this._readSize(off, BYTES_MAGIC);
			  const oo = off + 10 + (this._data.byteOffset || 0);
			  return this._data.buffer.slice(oo, oo + size);
		  }), listInHandler);
	}

	_getTableList<T extends TableIn>(o: number, s: number, type: {
		new(r: Reader, o: number, s: number): T; _MAGIC : number
	}): ListIn<T|null> {
		return new Proxy<ListIn<T|null>>(
		  new ListIn<T|null>(s, o, (s: number, i: number) => {
			  const off = this._readUint48(s + i * 6);
			  if (off == 0) return null;
			  const size = this._readSize(off, type._MAGIC);
			  return new type(this, off + 10, size);
		  }), listInHandler);
	}

	_getUnionList<T extends UnionIn>(o: number, s: number, type: {
		new(r: Reader, o: number, s: number): T;
	}): ListIn<T> {
		return new Proxy<ListIn<T>>(new ListIn<T>(s, o, (s: number, i: number) => {
										const t = this._data.getUint16(s + i * 8);
										const off = this._readUint48(s + i * 8 + 2);
										return new type(this, t, off);
									}), listInHandler);
	}

	/** Return root node of message, of type type */
	root<T extends TableIn>(type: {
		new(r: Reader, o: number, s: number): T; _MAGIC : number
	}): T {
		const magic = this._data.getUint32(0, true);
		const offset = this._readUint48(4);
		if (magic != MESSAGE_MAGIC) throw Error('Bad magic');
		const size = this._readSize(offset, type._MAGIC);
		return new type(this, offset + 10, size);
	}
}

export abstract class TableOut {
	static readonly _MAGIC: number = 0;
	static readonly _SIZE: number = 0;
	_offset: number = 0;

	constructor(public _writer: Writer,
				public withHeader: boolean,
				def: string,
				magic: number) {
		this._writer._reserve(def.length + (withHeader ? 10 : 0))
		if (withHeader) this._writer._data.setUint32(this._writer._size, magic, true);
		this._writer._writeUint48(this._writer._size + 4,
								  def.length) this._writer._size += 10 this._offset =
		  this._writer._size
		// writer._write(default)
	}
};

export class Writer {
	_buffer: ArrayBuffer;
	_data: DataView;
	_size: number;

	constructor(data: ArrayBuffer) {
		this._buffer = new ArrayBuffer(1024);
		this._data = new DataView(data);
		this._size = 10;
	}

	_reserve(o: number) {
		if (this._size + o <= this._buffer.byteLength) return;
		const nb = new ArrayBuffer(this._buffer.byteLength * 2);
		const nd = new Uint8Array(nb);
		nd.set(new Uint8Array(this._buffer));
		this._buffer = nb;
		this._data = new DataView(this._buffer);
	}

	_writeUint48(o: number, v: number) {
		const hi = v / 2 ** 32 | 0;
		const lo = (v - hi * 2 ** 32) | 0;
		this._data.setUint32(o, lo, true);
		this._data.setUint16(o + 4, hi, true);
	}

	_writeInt64(o: number, v: number) {
		let hi = v / 2 ** 32 | 0;
		if (v < 0) --hi;
		const lo = (v - hi * 2 ** 32) | 0;
		this._data.setUint32(o, lo, true);
		this._data.setInt32(o + 4, hi, true);
	}

	_writeUint64(o: number, v: number) {
		const hi = v / 2 ** 32 | 0;
		const lo = (v - hi * 2 ** 32) | 0;
		this._data.setUint32(o, lo, true);
		this._data.setUint32(o + 4, hi, true);
	}
}
