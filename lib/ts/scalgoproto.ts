export const MESSAGE_MAGIC = 0xB5C0C4B3
export const TEXT_MAGIC = 0xD812C8F5
export const BYTES_MAGIC = 0xDCDBBE10
export const LIST_MAGIC = 0x3400BB46

export class StructType {
	static readonly _WIDTH: number = 0
}

interface StructTypeType<T> {
	new(): T;
	_WIDTH: number;
	_write: (writer: Writer, offset: number, ins: T) => void;
	_read: (reader: Reader, offset: number) => T;
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

export class TextOut {
	constructor(public _offset: number) {};
}

export class BytesOut {
	constructor(public _offset: number) {};
}

interface TableOutType<T> {
	new(w: Writer, withHeader: boolean): T;
	_MAGIC: number, _SIZE: number;
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
		if (withHeader) {
			this._writer._data.setUint32(this._writer._size, magic, true);
			this._writer._writeUint48(this._writer._size + 4, def.length);
			this._writer._size += 10;
		}
		const o = this._offset = this._writer._size;
		for (let i = 0; i < def.length; ++i)
			this._writer._data.setUint8(o + i, def.charCodeAt(i));
		this._writer._size += def.length;
	}

	_setInt8(o: number, v: number) { this._writer._data.setInt8(this._offset + o, v); }

	_setUint8(o: number, v: number) { this._writer._data.setUint8(this._offset + o, v); }

	_setInt16(o: number, v: number) {
		this._writer._data.setInt16(this._offset + o, v, true);
	}

	_setUint16(o: number, v: number) {
		this._writer._data.setUint16(this._offset + o, v, true);
	}

	_setInt32(o: number, v: number) {
		this._writer._data.setInt32(this._offset + o, v, true);
	}

	_setUint32(o: number, v: number) {
		this._writer._data.setUint32(this._offset + o, v, true);
	}

	_setUint48(o: number, v: number) { this._writer._writeUint48(this._offset + o, v); }

	_setInt64(o: number, v: number) { this._writer._writeInt64(this._offset + o, v); }

	_setUint64(o: number, v: number) { this._writer._writeUint64(this._offset + o, v); }

	_setFloat32(o: number, v: number) {
		this._writer._data.setFloat32(this._offset + o, v, true);
	}

	_setFloat64(o: number, v: number) {
		this._writer._data.setFloat64(this._offset + o, v, true);
	}

	_setBit(o: number, bit: number) {
		const b = this._writer._data.getUint8(this._offset + o);
		this._writer._data.setUint8(this._offset + o, b | (1 << bit));
	}

	_unsetBit(o: number, bit: number) {
		const b = this._writer._data.getUint8(this._offset + o);
		this._writer._data.setUint8(this._offset + o, b & ~(1 << bit));
	}

	_setTable<T extends TableOut>(o: number, v: T) {
		this._writer._writeUint48(this._offset + o, v._offset - 10);
	}

	_setText(o: number, v: TextOut|string) {
		if (!(v instanceof TextOut)) v = this._writer.constructText(v);
		this._writer._writeUint48(this._offset + o, v._offset - 10);
	}

	_setBytes(o: number, v: BytesOut|ArrayBuffer) {
		if (!(v instanceof BytesOut)) v = this._writer.constructBytes(v);
		this._writer._writeUint48(this._offset + o, v._offset - 10);
	}

	_setList<T, IT>(o: number, v: ListOut<T, IT>) {
		this._writer._writeUint48(this._offset + o, v._offset - 10)
	}

	_addInplaceText(o: number, t: string) {
		const s = this._writer._writeText(t);
		this._writer._writeUint48(this._offset + o, s);
	}

	_addInplaceBytes(o: number, t: ArrayBuffer) {
		this._writer._writeUint48(this._offset + o, t.byteLength);
		const tt = new Uint8Array(t);
		this._writer._reserve(t.byteLength);
		for (let i = 0; i < t.byteLength; ++i)
			this._writer._data.setUint8(this._writer._size++, tt[i]);
	}

	_setInplaceList(o: number, size: number): void {
		this._writer._writeUint48(this._offset + o, size);
	}
}

export abstract class UnionOut {
	constructor(public _writer: Writer,
				public _offset: number,
				public _end: number|null) {}

	_set(idx: number, offset: number): void {
		this._writer._data.setInt16(this._offset, idx, true);
		this._writer._writeUint48(this._offset + 2, offset);
	}

	_setText(idx: number, v: TextOut|string): void {
		if (!(v instanceof TextOut)) v = this._writer.constructText(v);
		this._set(idx, v._offset - 10);
	}

	_setBytes(idx: number, v: BytesOut|ArrayBuffer): void {
		if (!(v instanceof BytesOut)) v = this._writer.constructBytes(v);
		this._set(idx, v._offset - 10);
	}

	_addInplaceText(idx: number, v: string): void {
		console.assert(this._writer._size == this._end);
		const l = this._writer._writeText(v);
		this._set(idx, l);
	}

	_addInplaceBytes(idx: number, t: ArrayBuffer): void {
		console.assert(this._writer._size == this._end);
		this._set(idx, t.byteLength);
		const tt = new Uint8Array(t);
		this._writer._reserve(t.byteLength);
		for (let i = 0; i < t.byteLength; ++i)
			this._writer._data.setUint8(this._writer._size++, tt[i]);
	}
}

export class ListOut<T, IT = T> {
	_offset: number;

	[i: number]: T;
	get length(): number { return this.size; }

	add(idx: number): T {
		if (!this._add) throw Error('Cannot add on this list');
		return this._add(this._offset, idx);
	}

	get(idx: number): T {
		if (!this._get) throw Error('Cannot get on this list');
		return this._get(this._offset, idx);
	}

	_copy(inp: ListIn<IT>): void {
		console.assert(this.length == inp.length);
		for (let i = 0; i < this.length; ++i) this.set(this._offset, i, inp[i]);
	}

	constructor(public writer: Writer,
				public size: number,
				d: string,
				dCnt: number,
				withHeader: boolean,
				public set: (off: number, index: number, v: T|IT) => void,
				public _add?: ((off: number, index: number) => T),
				public _get?: ((off: number, index: number) => T)) {
		writer._reserve(d.length * dCnt + 10);
		if (withHeader) {
			writer._data.setUint32(writer._size, LIST_MAGIC, true);
			writer._writeUint48(writer._size + 4, size);
			writer._size += 10;
		}
		this._offset = writer._size;
		for (let i = 0; i < dCnt; ++i)
			for (let j = 0; j < d.length; ++j)
				writer._data.setUint8(writer._size++, d.charCodeAt(j));
	}
};

const listOutHandel = {
	get : <T, IT>(obj: ListOut<T, IT>, prop: string) : any => {
		if (prop === 'length') return obj.size;
		if (prop === '_offset') return obj._offset;
		if (prop === 'add') return (idx: number) => { return obj.add(idx); };
		if (prop === '_copy') return (i: ListIn<IT>) => { obj._copy(i); };
		const index = +prop;
		if (Number.isInteger(+index)) {
			if (index < 0 || index >= obj.size) throw Error('Index outside range');
			return obj.get(index);
		}
		throw Error('Only length can be accessed ' + prop);
	},
	set : <T, IT>(obj: ListOut<T, IT>, prop: string, value: T|IT) : boolean => {
		const index = +prop;
		if (!Number.isInteger(index) || index < 0 || index >= obj.size)
			throw Error('Index outside range');
		obj.set(obj._offset, index, value);
		return true;
	}
};

type CopyType<T> = T extends { _copy(i: infer IN) : void } ? IN : never;

export class Writer {
	_buffer: ArrayBuffer;
	_data: DataView;
	_size: number;

	constructor() {
		this._buffer = new ArrayBuffer(1024);
		this._data = new DataView(this._buffer);
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

	_writeText(t: string): number {
		// Write utf-8 encoded text and return the number of bytes not including the 0
		// termination
		const s0 = this._size;
		for (let i = 0; i < t.length; ++i) {
			this._reserve(5);
			const c = t.charCodeAt(i);
			if (c < 128) {
				this._data.setUint8(this._size++, c);
			} else if (c < 2048) {
				this._data.setUint8(this._size++, 192 + (c & 31));
				this._data.setUint8(this._size++, 128 + (c >> 5));
			} else if (c < 65536) {
				this._data.setUint8(this._size++, 224 + (c & 15));
				this._data.setUint8(this._size++, 128 + ((c >> 4) & 63));
				this._data.setUint8(this._size++, 128 + (c >> 10));
			} else {
				this._data.setUint8(this._size++, 240 + (c & 7));
				this._data.setUint8(this._size++, 128 + ((c >> 3) & 63));
				this._data.setUint8(this._size++, 128 + (c >> 9) & 63);
				this._data.setUint8(this._size++, 128 + c >> 15);
			}
		}
		this._data.setUint8(this._size++, 0);
		return this._size - s0 - 1;
	}

	constructTable<T extends TableOut>(type: {
		new(writer: Writer, header: boolean): T;
	}): T {
		return new type(this, true);
	}

	constructInt8List(size: number, _inplace: boolean = false): ListOut<number> {
		return new Proxy<ListOut<number>>(
		  new ListOut<number>(this,
							  size,
							  '\0',
							  size,
							  !_inplace,
							  (off: number, idx: number, v: number):
								void => { this._data.setInt8(off + idx, v); }),
		  listOutHandel);
	}

	constructUint8List(size: number, _inplace: boolean = false): ListOut<number> {
		return new Proxy<ListOut<number>>(
		  new ListOut<number>(this,
							  size,
							  '\0',
							  size,
							  !_inplace,
							  (off: number, idx: number, v: number):
								void => { this._data.setUint8(off + idx, v); }),
		  listOutHandel);
	}

	constructInt16List(size: number, _inplace: boolean = false): ListOut<number> {
		return new Proxy<ListOut<number>>(
		  new ListOut<number>(this,
							  size,
							  '\0\0',
							  size,
							  !_inplace,
							  (off: number, idx: number, v: number):
								void => { this._data.setInt16(off + 2 * idx, v, true); }),
		  listOutHandel);
	}

	constructUint16List(size: number, _inplace: boolean = false): ListOut<number> {
		return new Proxy<ListOut<number>>(
		  new ListOut<number>(
			this,
			size,
			'\0\0',
			size,
			!_inplace,
			(off: number, idx: number, v: number):
			  void => { this._data.setUint16(off + 2 * idx, v, true); }),
		  listOutHandel);
	}

	constructInt32List(size: number, _inplace: boolean = false): ListOut<number> {
		return new Proxy<ListOut<number>>(
		  new ListOut<number>(this,
							  size,
							  '\0\0\0\0',
							  size,
							  !_inplace,
							  (off: number, idx: number, v: number):
								void => { this._data.setInt32(off + 4 * idx, v, true); }),
		  listOutHandel);
	}

	constructUint32List(size: number, _inplace: boolean = false): ListOut<number> {
		return new Proxy<ListOut<number>>(
		  new ListOut<number>(
			this,
			size,
			'\0\0\0\0',
			size,
			!_inplace,
			(off: number, idx: number, v: number):
			  void => { this._data.setUint32(off + 4 * idx, v, true); }),
		  listOutHandel);
	}

	constructInt64List(size: number, _inplace: boolean = false): ListOut<number> {
		return new Proxy<ListOut<number>>(
		  new ListOut<number>(this,
							  size,
							  '\0\0\0\0\0\0\0\0',
							  size,
							  !_inplace,
							  (off: number, idx: number, v: number):
								void => { this._writeInt64(off + 8 * idx, v); }),
		  listOutHandel);
	}

	constructUint64List(size: number, _inplace: boolean = false): ListOut<number> {
		return new Proxy<ListOut<number>>(
		  new ListOut<number>(this,
							  size,
							  '\0\0\0\0\0\0\0\0',
							  size,
							  !_inplace,
							  (off: number, idx: number, v: number):
								void => { this._writeUint64(off + 8 * idx, v); }),
		  listOutHandel);
	}

	constructFloat32List(size: number, _inplace: boolean = false): ListOut<number> {
		return new Proxy<ListOut<number>>(
		  new ListOut<number>(
			this,
			size,
			'\0\0\0\0',
			size,
			!_inplace,
			(off: number, idx: number, v: number):
			  void => { this._data.setFloat32(off + 4 * idx, v, true); }),
		  listOutHandel);
	}

	constructFloat64List(size: number, _inplace: boolean = false): ListOut<number> {
		return new Proxy<ListOut<number>>(
		  new ListOut<number>(
			this,
			size,
			'\0\0\0\0\0\0\0\0',
			size,
			!_inplace,
			(off: number, idx: number, v: number):
			  void => { this._data.setFloat64(off + 8 * idx, v, true); }),
		  listOutHandel);
	}

	constructEnumList<T>(size: number, _inplace: boolean = false): ListOut<T, T|null> {
		return new Proxy<ListOut<T, T|null>>(
		  new ListOut<T, T|null>(this,
								 size,
								 '\xff',
								 size,
								 !_inplace,
								 (off: number, idx: number, v: T|null):
								   void => {
									   if (v !== null)
										   this._data.setUint8(off + idx,
															   v as any as number);
								   }),
		  listOutHandel);
	}

	constructStructList<T extends StructType>(type: StructTypeType<T>,
											  size: number,
											  _inplace: boolean = false): ListOut<T> {
		return new Proxy<ListOut<T>>(
		  new ListOut<T>(this,
						 size,
						 '\0',
						 size * type._WIDTH,
						 !_inplace,
						 (off: number, idx: number, v: T):
						   void => { type._write(this, off + idx * type._WIDTH, v); }),
		  listOutHandel);
	};

	constructTableList<T extends TableOut>(type: {
		new(writer: Writer, withHeader: boolean): T;
		_IN : { new(reader: Reader, offset: number, size: number) : CopyType<T>}
	},
										   size: number,
										   _inplace: boolean = false):
	  ListOut<T, CopyType<T>|null> {
		return new Proxy<ListOut<T, CopyType<T>|null>>(
		  new ListOut<T, CopyType<T>|null>(
			this,
			size,
			'\0\0\0\0\0\0',
			size,
			!_inplace,
			(off: number, idx: number, v: T|CopyType<T>|null) => {
				if (v === null) return;
				if (v instanceof type._IN) {
					const v2 = this.constructTable(type);
					(v2 as any)._copy(v); // TODO get rid of any here
					v = v2;
				}
				this._writeUint48(off + idx * 6, (v as T)._offset - 10);
			},
			(off: number, idx: number):
			  T => {
				  const v = this.constructTable(type);
				  this._writeUint48(off + idx * 6, v._offset - 10);
				  return v;
			  }),
		  listOutHandel);
	}

	constructTextList(size: number,
					  _inplace: boolean = false): ListOut<string|TextOut, string|null> {
		return new Proxy<ListOut<string|TextOut, string|null>>(
		  new ListOut<string|TextOut, string|null>(
			this,
			size,
			'\0\0\0\0\0\0',
			size,
			!_inplace,
			(off: number, idx: number, v: TextOut|string|null) => {
				if (v === null) return;
				if (!(v instanceof TextOut)) { v = this.constructText(v); }
				this._writeUint48(off + idx * 6, v._offset - 10);
			}),
		  listOutHandel);
	}

	constructBytesList(size: number, _inplace: boolean = false):
	  ListOut<ArrayBuffer|BytesOut, ArrayBuffer|null> {
		return new Proxy<ListOut<ArrayBuffer|BytesOut, ArrayBuffer|null>>(
		  new ListOut<ArrayBuffer|BytesOut, ArrayBuffer|null>(
			this,
			size,
			'\0\0\0\0\0\0',
			size,
			!_inplace,
			(off: number, idx: number, v: BytesOut|ArrayBuffer|null) => {
				if (v === null) return;
				let o;
				if (!(v instanceof BytesOut)) { v = this.constructBytes(v); }
				this._writeUint48(off + idx * 6, v._offset - 10);
			}),
		  listOutHandel);
	}

	constructBoolList(size: number, _inplace: boolean = false): ListOut<boolean> {
		return new Proxy<ListOut<boolean>>(
		  new ListOut<boolean>(this,
							   size,
							   '\0',
							   (size + 7) >> 3,
							   !_inplace,
							   (off: number, idx: number, v: boolean) => {
								   const o = idx >> 3;
								   const b = 1 << (idx & 7);
								   const vv = this._data.getUint8(off + o);
								   this._data.setUint8(off + o, v ? (vv | b) : (vv & ~b));
							   }),
		  listOutHandel);
	}

	constructUnionList<T extends UnionOut>(type: {
		new(writer: Writer, offset: number): T; _IN : {
			new(reader: Reader, type: number, offset: number, size: number|null) :
			  CopyType<T>;
		}
	},
										   size: number,
										   _inplace: boolean = false):
	  ListOut<T, CopyType<T>|null> {
		return new Proxy<ListOut<T, CopyType<T>|null>>(
		  new ListOut<T, CopyType<T>|null>(
			this,
			size,
			'\0\0\0\0\0\0\0\0',
			size,
			!_inplace,
			(off: number, idx: number, v: T|CopyType<T>|null) => {
				if (!(v instanceof type._IN)) throw Error('Ups');
				const vv = new type(this, off + idx * 8);
				(vv as any)._copy(v);
			},
			undefined,
			(off: number, idx: number): T => { return new type(this, off + idx * 8); }),
		  listOutHandel);
	}

	constructText(t: string): TextOut {
		this._reserve(10);
		const s = this._size;
		this._data.setUint32(s, TEXT_MAGIC, true);
		this._size += 10;
		const bytes = this._writeText(t);
		this._writeUint48(s + 4, bytes);
		return new TextOut(s + 10);
	}

	constructBytes(t: ArrayBuffer): BytesOut {
		this._reserve(t.byteLength + 10);
		this._data.setUint32(this._size, BYTES_MAGIC, true);
		this._writeUint48(this._size + 4, t.byteLength);
		this._size += 10;
		const o = this._size;
		const b = new Uint8Array(t);
		for (let i = 0; i < t.byteLength; ++i) this._data.setUint8(o + i, b[i]);
		this._size += t.byteLength;
		return new BytesOut(o);
	}

	finalize<T extends TableOut>(root: T): ArrayBuffer {
		this._data.setUint32(0, MESSAGE_MAGIC, true);
		this._writeUint48(4, root._offset - 10);
		return this._buffer.slice(0, this._size);
	}
}
