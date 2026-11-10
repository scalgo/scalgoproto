// -*- mode: typescript; tab-width: 4; indent-tabs-mode: t; coding: utf-8 -*-
//
// scalgoproto TypeScript runtime.
//
// The reader is designed for decoding speed:
// * All reads go through a single DataView, which handles the packed (unaligned)
//   layout of the format at full speed.
// * Generated table classes are standalone (no base class) and inline their field
//   offsets, so the JIT can keep them monomorphic.
// * Lists are plain classes with a get(i) method (no Proxy). Numeric lists can be
//   returned as typed arrays, which are views on the message when the data happens to
//   be aligned, and copies otherwise.

export const MESSAGE_MAGIC = 0xB5C0C4B3
export const TEXT_MAGIC = 0xD812C8F5
export const BYTES_MAGIC = 0xDCDBBE10
export const LIST_MAGIC = 0x3400BB46
export const DIRECT_LIST_MAGIC = 0xE2C6CC05

const TWO32 = 4294967296;
const LITTLE_ENDIAN = new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;

/**
 * Strings of at most this many bytes are decoded with a plain JS loop, longer strings
 * with TextDecoder, which has a fixed cost per call. Measured crossover points: V8
 * 16 bytes (ASCII) to 24 bytes (Danish text), SpiderMonkey 32 to 48 bytes. 24 keeps
 * both within about 40% of the faster method.
 */
const TEXT_DECODER_THRESHOLD = 24;
let textDecoder: TextDecoder | null = null;

/** Binary input accepted by the writer */
export type BytesLike = ArrayBuffer | Uint8Array;

export class StructType {
	static readonly _WIDTH: number = 0
}

interface StructTypeType<T> {
	new(): T;
	_WIDTH: number;
	_write: (writer: Writer, offset: number, ins: T) => void;
	_read: (reader: Reader, offset: number) => T;
}

/** Constructor type of generated table readers */
export interface TableInType<T> {
	new(reader: Reader, offset: number, size: number): T;
	readonly _MAGIC: number;
}

/** Throw an error for an invalid list index. Used by generated code */
export function _indexError(i: number, length: number): never {
	throw new RangeError('Index ' + i + ' outside list of length ' + length);
}

function magicError(o: number, magic: number, found: number): never {
	throw new Error('Bad magic at offset ' + o + ': expected 0x' + magic.toString(16) +
					' found 0x' + found.toString(16));
}

/** Responsible for reading a message */
export class Reader {
	// Fields are declared, not defined, so their initialization does not depend on
	// useDefineForClassFields and the compilation target
	/** View of the message */
	declare readonly _dv: DataView;
	/** Bytes of the message */
	declare readonly _u8: Uint8Array;

	/**
	 * Construct a reader for a message.
	 *
	 * Typed arrays (e.g. a subarray of a larger buffer) are read in place without copying.
	 * Shared memory (SharedArrayBuffer) is not supported.
	 */
	constructor(data: ArrayBuffer | ArrayBufferView) {
		const buffer = ArrayBuffer.isView(data) ? data.buffer : data;
		if (Object.prototype.toString.call(buffer) === '[object SharedArrayBuffer]')
			throw new TypeError('scalgoproto: messages in a SharedArrayBuffer are not supported');
		if (ArrayBuffer.isView(data))
			this._u8 = new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
		else
			this._u8 = new Uint8Array(data);
		this._dv = new DataView(this._u8.buffer, this._u8.byteOffset, this._u8.byteLength);
	}

	/** Return root node of message, of type type */
	root<T>(type: TableInType<T>): T {
		const magic = this._dv.getUint32(0, true);
		if (magic !== MESSAGE_MAGIC) magicError(0, MESSAGE_MAGIC, magic);
		const offset = this._u48(4);
		const size = this._size(offset, type._MAGIC);
		return new type(this, offset + 10, size);
	}

	/** The bytes of the message */
	get bytes(): Uint8Array { return this._u8; }

	_u48(o: number): number {
		// Note we cannot use shifts here as it would turn it into a 32bit int
		const dv = this._dv;
		return dv.getUint32(o, true) + dv.getUint16(o + 4, true) * TWO32;
	}

	_i64(o: number): number {
		const dv = this._dv;
		return dv.getUint32(o, true) + dv.getInt32(o + 4, true) * TWO32;
	}

	_u64(o: number): number {
		const dv = this._dv;
		return dv.getUint32(o, true) + dv.getUint32(o + 4, true) * TWO32;
	}

	/** Check the magic at o and return the size stored after it */
	_size(o: number, magic: number): number {
		const m = this._dv.getUint32(o, true);
		if (m !== magic) magicError(o, magic, m);
		return this._u48(o + 4);
	}

	/** Decode len bytes of utf-8 starting at o */
	_text(o: number, len: number): string {
		const u8 = this._u8;
		const start = o;
		const end = o + len;
		if (end > u8.length) throw new RangeError('Text outside message');
		if (len <= TEXT_DECODER_THRESHOLD) {
			// Decode well formed utf-8 in JS; anything malformed is left to TextDecoder so
			// the result does not depend on the length of the text
			let ans = '';
			for (;;) {
				if (o === end) return ans;
				const c = u8[o];
				if (c < 0x80) {
					ans += String.fromCharCode(c);
					o += 1;
				} else if (c >= 0xC2 && c <= 0xDF) {
					if (o + 1 >= end) break;
					const c1 = u8[o + 1];
					if ((c1 & 0xC0) !== 0x80) break;
					ans += String.fromCharCode(((c & 0x1F) << 6) | (c1 & 0x3F));
					o += 2;
				} else if (c >= 0xE0 && c <= 0xEF) {
					if (o + 2 >= end) break;
					const c1 = u8[o + 1], c2 = u8[o + 2];
					// No overlong forms (E0) and no surrogates (ED)
					if (c1 < (c === 0xE0 ? 0xA0 : 0x80) || c1 > (c === 0xED ? 0x9F : 0xBF) ||
						(c2 & 0xC0) !== 0x80)
						break;
					ans += String.fromCharCode(((c & 0x0F) << 12) | ((c1 & 0x3F) << 6) | (c2 & 0x3F));
					o += 3;
				} else if (c >= 0xF0 && c <= 0xF4) {
					if (o + 3 >= end) break;
					const c1 = u8[o + 1], c2 = u8[o + 2], c3 = u8[o + 3];
					// No overlong forms (F0) and nothing above U+10FFFF (F4)
					if (c1 < (c === 0xF0 ? 0x90 : 0x80) || c1 > (c === 0xF4 ? 0x8F : 0xBF) ||
						(c2 & 0xC0) !== 0x80 || (c3 & 0xC0) !== 0x80)
						break;
					const cp = (((c & 0x07) << 18) | ((c1 & 0x3F) << 12) | ((c2 & 0x3F) << 6) |
								(c3 & 0x3F)) -
							   0x10000;
					ans += String.fromCharCode(0xD800 + (cp >> 10), 0xDC00 + (cp & 0x3FF));
					o += 4;
				} else {
					break;
				}
			}
		}
		// ignoreBOM: keep a leading U+FEFF like the JS loop does
		if (textDecoder === null) textDecoder = new TextDecoder('utf-8', {ignoreBOM: true});
		return textDecoder.decode(u8.subarray(start, end));
	}

	/** Return a view of len bytes starting at o */
	_bytes(o: number, len: number): Uint8Array {
		if (o + len > this._u8.length) throw new RangeError('Bytes outside message');
		return this._u8.subarray(o, o + len);
	}
}

//////////////////////////////////////////////////////////////////////////////////////
// Lists
//////////////////////////////////////////////////////////////////////////////////////

/**
 * Base class of all read only lists.
 *
 * Use get(i) in performance critical loops; iteration and toArray() are convenient
 * but slightly slower.
 */
export abstract class ListIn<T> implements Iterable<T> {
	declare readonly _r: Reader;
	declare readonly _dv: DataView;
	/** Offset of the first element in the message */
	declare readonly _off: number;
	/** Number of elements in the list */
	declare readonly length: number;

	constructor(reader: Reader, offset: number, length: number) {
		this._r = reader;
		this._dv = reader._dv;
		this._off = offset;
		this.length = length;
	}

	/** Return the i'th element of the list */
	abstract get(i: number): T;

	[Symbol.iterator](): Iterator<T> { return new ListIterator<T>(this); }

	// forEach and toArray are repeated in each concrete list class (also the generated
	// ones) on purpose: every copy gets its own type feedback, which keeps them fast when
	// an application uses many kinds of lists. These are fallbacks.

	/** Return the elements of the list as an array */
	toArray(): Array<T> {
		const n = this.length;
		const ans = new Array<T>(n);
		for (let i = 0; i < n; ++i) ans[i] = this.get(i);
		return ans;
	}

	forEach(fn: (value: T, index: number) => void): void {
		const n = this.length;
		for (let i = 0; i < n; ++i) fn(this.get(i), i);
	}
}

/** Iterator over a list. Faster than a generator function */
class ListIterator<T> implements Iterator<T> {
	declare _list: ListIn<T>;
	declare _i: number;

	constructor(list: ListIn<T>) {
		this._list = list;
		this._i = 0;
	}

	next(): IteratorResult<T> {
		const i = this._i;
		if (i < this._list.length) {
			this._i = i + 1;
			return {value: this._list.get(i), done: false};
		}
		return {value: undefined, done: true};
	}

	[Symbol.iterator](): Iterator<T> { return this; }
}

type TypedArrayCtor<A> = {
	new(buffer: ArrayBufferLike, byteOffset: number, length: number): A;
	readonly BYTES_PER_ELEMENT: number;
};

function typedArray<A>(list: ListIn<unknown>, ctor: TypedArrayCtor<A>, copy: boolean): A {
	if (!LITTLE_ENDIAN) throw new Error('toTypedArray requires a little endian host');
	const u8 = list._r._u8;
	const w = ctor.BYTES_PER_ELEMENT;
	const n = list.length;
	const start = u8.byteOffset + list._off;
	if (list._off + n * w > u8.length) throw new RangeError('List outside message');
	if (!copy && start % w === 0) return new ctor(u8.buffer, start, n);
	return new ctor(u8.buffer.slice(start, start + n * w), 0, n);
}

function copyTyped<A extends ArrayBufferView>(list: ListIn<unknown>, dst: A, offset: number,
											  w: number): A {
	if (!LITTLE_ENDIAN) throw new Error('copyTo requires a little endian host');
	const u8 = list._r._u8;
	const bytes = list.length * w;
	if (!((offset >>> 0) === offset && offset * w + bytes <= dst.byteLength))
		throw new RangeError('List does not fit in destination at offset ' + offset);
	if (list._off + bytes > u8.length) throw new RangeError('List outside message');
	new Uint8Array(dst.buffer, dst.byteOffset + offset * w, bytes)
	  .set(u8.subarray(list._off, list._off + bytes));
	return dst;
}

/** Base class of lists of fixed width elements */
export abstract class FixedListIn<T> extends ListIn<T> {
	/** Number of bytes taken by the elements of the list */
	abstract get byteLength(): number;

	/** Return a view of the raw bytes of the elements of the list */
	bytes(): Uint8Array { return this._r._bytes(this._off, this.byteLength); }
}

/** Base class of lists of numbers */
export abstract class NumberListIn<A> extends FixedListIn<number> {
	/**
	 * Return the list as a typed array.
	 *
	 * If the data in the message is suitably aligned (and copy is false) the returned
	 * array is a view of the message buffer, otherwise it is a copy.
	 */
	abstract toTypedArray(copy?: boolean): A;

	/**
	 * Copy the list into the typed array dst starting at element offset, and return dst.
	 *
	 * Reusing dst for repeated conversions avoids allocating a new array each time, which
	 * is much faster than toTypedArray() when the list is not aligned.
	 */
	abstract copyTo(dst: A, offset?: number): A;
}

export class Int8ListIn extends NumberListIn<Int8Array> {
	forEach(fn: (value: number, index: number) => void): void {
		const dv = this._dv, o = this._off, n = this.length;
		for (let i = 0; i < n; ++i) fn(dv.getInt8(o + i), i);
	}
	toArray(): Array<number> {
		const dv = this._dv, o = this._off, n = this.length;
		const ans = new Array<number>(n);
		for (let i = 0; i < n; ++i) ans[i] = dv.getInt8(o + i);
		return ans;
	}
	copyTo(dst: Int8Array, offset: number = 0): Int8Array {
		return copyTyped(this, dst, offset, 1);
	}
	get byteLength(): number { return this.length; }
	get(i: number): number {
		if (!((i >>> 0) === i && i < this.length)) _indexError(i, this.length);
		return this._dv.getInt8(this._off + i);
	}
	toTypedArray(copy: boolean = false): Int8Array { return typedArray(this, Int8Array, copy); }
}

export class Uint8ListIn extends NumberListIn<Uint8Array> {
	forEach(fn: (value: number, index: number) => void): void {
		const dv = this._dv, o = this._off, n = this.length;
		for (let i = 0; i < n; ++i) fn(dv.getUint8(o + i), i);
	}
	toArray(): Array<number> {
		const dv = this._dv, o = this._off, n = this.length;
		const ans = new Array<number>(n);
		for (let i = 0; i < n; ++i) ans[i] = dv.getUint8(o + i);
		return ans;
	}
	copyTo(dst: Uint8Array, offset: number = 0): Uint8Array {
		return copyTyped(this, dst, offset, 1);
	}
	get byteLength(): number { return this.length; }
	get(i: number): number {
		if (!((i >>> 0) === i && i < this.length)) _indexError(i, this.length);
		return this._dv.getUint8(this._off + i);
	}
	toTypedArray(copy: boolean = false): Uint8Array { return typedArray(this, Uint8Array, copy); }
}

export class Int16ListIn extends NumberListIn<Int16Array> {
	forEach(fn: (value: number, index: number) => void): void {
		const dv = this._dv, o = this._off, n = this.length;
		for (let i = 0; i < n; ++i) fn(dv.getInt16(o + i * 2, true), i);
	}
	toArray(): Array<number> {
		const dv = this._dv, o = this._off, n = this.length;
		const ans = new Array<number>(n);
		for (let i = 0; i < n; ++i) ans[i] = dv.getInt16(o + i * 2, true);
		return ans;
	}
	copyTo(dst: Int16Array, offset: number = 0): Int16Array {
		return copyTyped(this, dst, offset, 2);
	}
	get byteLength(): number { return this.length * 2; }
	get(i: number): number {
		if (!((i >>> 0) === i && i < this.length)) _indexError(i, this.length);
		return this._dv.getInt16(this._off + i * 2, true);
	}
	toTypedArray(copy: boolean = false): Int16Array { return typedArray(this, Int16Array, copy); }
}

export class Uint16ListIn extends NumberListIn<Uint16Array> {
	forEach(fn: (value: number, index: number) => void): void {
		const dv = this._dv, o = this._off, n = this.length;
		for (let i = 0; i < n; ++i) fn(dv.getUint16(o + i * 2, true), i);
	}
	toArray(): Array<number> {
		const dv = this._dv, o = this._off, n = this.length;
		const ans = new Array<number>(n);
		for (let i = 0; i < n; ++i) ans[i] = dv.getUint16(o + i * 2, true);
		return ans;
	}
	copyTo(dst: Uint16Array, offset: number = 0): Uint16Array {
		return copyTyped(this, dst, offset, 2);
	}
	get byteLength(): number { return this.length * 2; }
	get(i: number): number {
		if (!((i >>> 0) === i && i < this.length)) _indexError(i, this.length);
		return this._dv.getUint16(this._off + i * 2, true);
	}
	toTypedArray(copy: boolean = false): Uint16Array {
		return typedArray(this, Uint16Array, copy);
	}
}

export class Int32ListIn extends NumberListIn<Int32Array> {
	forEach(fn: (value: number, index: number) => void): void {
		const dv = this._dv, o = this._off, n = this.length;
		for (let i = 0; i < n; ++i) fn(dv.getInt32(o + i * 4, true), i);
	}
	toArray(): Array<number> {
		const dv = this._dv, o = this._off, n = this.length;
		const ans = new Array<number>(n);
		for (let i = 0; i < n; ++i) ans[i] = dv.getInt32(o + i * 4, true);
		return ans;
	}
	copyTo(dst: Int32Array, offset: number = 0): Int32Array {
		return copyTyped(this, dst, offset, 4);
	}
	get byteLength(): number { return this.length * 4; }
	get(i: number): number {
		if (!((i >>> 0) === i && i < this.length)) _indexError(i, this.length);
		return this._dv.getInt32(this._off + i * 4, true);
	}
	toTypedArray(copy: boolean = false): Int32Array { return typedArray(this, Int32Array, copy); }
}

export class Uint32ListIn extends NumberListIn<Uint32Array> {
	forEach(fn: (value: number, index: number) => void): void {
		const dv = this._dv, o = this._off, n = this.length;
		for (let i = 0; i < n; ++i) fn(dv.getUint32(o + i * 4, true), i);
	}
	toArray(): Array<number> {
		const dv = this._dv, o = this._off, n = this.length;
		const ans = new Array<number>(n);
		for (let i = 0; i < n; ++i) ans[i] = dv.getUint32(o + i * 4, true);
		return ans;
	}
	copyTo(dst: Uint32Array, offset: number = 0): Uint32Array {
		return copyTyped(this, dst, offset, 4);
	}
	get byteLength(): number { return this.length * 4; }
	get(i: number): number {
		if (!((i >>> 0) === i && i < this.length)) _indexError(i, this.length);
		return this._dv.getUint32(this._off + i * 4, true);
	}
	toTypedArray(copy: boolean = false): Uint32Array {
		return typedArray(this, Uint32Array, copy);
	}
}

/**
 * List of I64. get returns a number, which is exact up to 2^53, use getBigInt or
 * toTypedArray for exact values.
 */
export class Int64ListIn extends NumberListIn<BigInt64Array> {
	forEach(fn: (value: number, index: number) => void): void {
		const r = this._r, o = this._off, n = this.length;
		for (let i = 0; i < n; ++i) fn(r._i64(o + i * 8), i);
	}
	toArray(): Array<number> {
		const r = this._r, o = this._off, n = this.length;
		const ans = new Array<number>(n);
		for (let i = 0; i < n; ++i) ans[i] = r._i64(o + i * 8);
		return ans;
	}
	copyTo(dst: BigInt64Array, offset: number = 0): BigInt64Array {
		return copyTyped(this, dst, offset, 8);
	}
	get byteLength(): number { return this.length * 8; }
	get(i: number): number {
		if (!((i >>> 0) === i && i < this.length)) _indexError(i, this.length);
		return this._r._i64(this._off + i * 8);
	}
	getBigInt(i: number): bigint {
		if (!((i >>> 0) === i && i < this.length)) _indexError(i, this.length);
		return this._dv.getBigInt64(this._off + i * 8, true);
	}
	toTypedArray(copy: boolean = false): BigInt64Array {
		return typedArray(this, BigInt64Array, copy);
	}
}

/**
 * List of U64. get returns a number, which is exact up to 2^53, use getBigInt or
 * toTypedArray for exact values.
 */
export class Uint64ListIn extends NumberListIn<BigUint64Array> {
	forEach(fn: (value: number, index: number) => void): void {
		const r = this._r, o = this._off, n = this.length;
		for (let i = 0; i < n; ++i) fn(r._u64(o + i * 8), i);
	}
	toArray(): Array<number> {
		const r = this._r, o = this._off, n = this.length;
		const ans = new Array<number>(n);
		for (let i = 0; i < n; ++i) ans[i] = r._u64(o + i * 8);
		return ans;
	}
	copyTo(dst: BigUint64Array, offset: number = 0): BigUint64Array {
		return copyTyped(this, dst, offset, 8);
	}
	get byteLength(): number { return this.length * 8; }
	get(i: number): number {
		if (!((i >>> 0) === i && i < this.length)) _indexError(i, this.length);
		return this._r._u64(this._off + i * 8);
	}
	getBigInt(i: number): bigint {
		if (!((i >>> 0) === i && i < this.length)) _indexError(i, this.length);
		return this._dv.getBigUint64(this._off + i * 8, true);
	}
	toTypedArray(copy: boolean = false): BigUint64Array {
		return typedArray(this, BigUint64Array, copy);
	}
}

export class Float32ListIn extends NumberListIn<Float32Array> {
	forEach(fn: (value: number, index: number) => void): void {
		const dv = this._dv, o = this._off, n = this.length;
		for (let i = 0; i < n; ++i) fn(dv.getFloat32(o + i * 4, true), i);
	}
	toArray(): Array<number> {
		const dv = this._dv, o = this._off, n = this.length;
		const ans = new Array<number>(n);
		for (let i = 0; i < n; ++i) ans[i] = dv.getFloat32(o + i * 4, true);
		return ans;
	}
	copyTo(dst: Float32Array, offset: number = 0): Float32Array {
		return copyTyped(this, dst, offset, 4);
	}
	get byteLength(): number { return this.length * 4; }
	get(i: number): number {
		if (!((i >>> 0) === i && i < this.length)) _indexError(i, this.length);
		return this._dv.getFloat32(this._off + i * 4, true);
	}
	toTypedArray(copy: boolean = false): Float32Array {
		return typedArray(this, Float32Array, copy);
	}
}

export class Float64ListIn extends NumberListIn<Float64Array> {
	forEach(fn: (value: number, index: number) => void): void {
		const dv = this._dv, o = this._off, n = this.length;
		for (let i = 0; i < n; ++i) fn(dv.getFloat64(o + i * 8, true), i);
	}
	toArray(): Array<number> {
		const dv = this._dv, o = this._off, n = this.length;
		const ans = new Array<number>(n);
		for (let i = 0; i < n; ++i) ans[i] = dv.getFloat64(o + i * 8, true);
		return ans;
	}
	copyTo(dst: Float64Array, offset: number = 0): Float64Array {
		return copyTyped(this, dst, offset, 8);
	}
	get byteLength(): number { return this.length * 8; }
	get(i: number): number {
		if (!((i >>> 0) === i && i < this.length)) _indexError(i, this.length);
		return this._dv.getFloat64(this._off + i * 8, true);
	}
	toTypedArray(copy: boolean = false): Float64Array {
		return typedArray(this, Float64Array, copy);
	}
}

/** List of bools, packed 8 to a byte */
export class BoolListIn extends FixedListIn<boolean> {
	forEach(fn: (value: boolean, index: number) => void): void {
		const dv = this._dv, o = this._off, n = this.length;
		for (let i = 0; i < n; ++i) fn(((dv.getUint8(o + (i >> 3)) >> (i & 7)) & 1) !== 0, i);
	}
	toArray(): Array<boolean> {
		const dv = this._dv, o = this._off, n = this.length;
		const ans = new Array<boolean>(n);
		for (let i = 0; i < n; ++i) ans[i] = ((dv.getUint8(o + (i >> 3)) >> (i & 7)) & 1) !== 0;
		return ans;
	}
	get byteLength(): number { return (this.length + 7) >> 3; }
	get(i: number): boolean {
		if (!((i >>> 0) === i && i < this.length)) _indexError(i, this.length);
		return ((this._dv.getUint8(this._off + (i >> 3)) >> (i & 7)) & 1) !== 0;
	}
	/** Return the list unpacked as one byte (0 or 1) per element */
	toUint8Array(): Uint8Array {
		const n = this.length;
		const ans = new Uint8Array(n);
		const b = this.bytes();
		for (let i = 0; i < n; ++i) ans[i] = (b[i >> 3] >> (i & 7)) & 1;
		return ans;
	}
}

/** List of enums. Missing values are returned as null */
export class EnumListIn<E> extends FixedListIn<E | null> {
	forEach(fn: (value: E | null, index: number) => void): void {
		const dv = this._dv, o = this._off, n = this.length;
		for (let i = 0; i < n; ++i) {
			const v = dv.getUint8(o + i);
			fn(v === 255 ? null : v as any as E, i);
		}
	}
	toArray(): Array<E | null> {
		const dv = this._dv, o = this._off, n = this.length;
		const ans = new Array<E | null>(n);
		for (let i = 0; i < n; ++i) {
			const v = dv.getUint8(o + i);
			ans[i] = v === 255 ? null : v as any as E;
		}
		return ans;
	}
	/** Copy the raw enum values (255 means not set) into dst starting at offset */
	copyTo(dst: Uint8Array, offset: number = 0): Uint8Array {
		return copyTyped(this, dst, offset, 1);
	}
	get byteLength(): number { return this.length; }
	get(i: number): E | null {
		if (!((i >>> 0) === i && i < this.length)) _indexError(i, this.length);
		const v = this._dv.getUint8(this._off + i);
		return v === 255 ? null : v as any as E;
	}
	/** Return the raw enum values, where 255 denotes a missing value */
	toTypedArray(copy: boolean = false): Uint8Array { return typedArray(this, Uint8Array, copy); }
}

export class TextListIn extends ListIn<string | null> {
	forEach(fn: (value: string | null, index: number) => void): void {
		const n = this.length;
		for (let i = 0; i < n; ++i) fn(this.get(i), i);
	}
	toArray(): Array<string | null> {
		const n = this.length;
		const ans = new Array<string | null>(n);
		for (let i = 0; i < n; ++i) ans[i] = this.get(i);
		return ans;
	}
	get(i: number): string | null {
		if (!((i >>> 0) === i && i < this.length)) _indexError(i, this.length);
		const r = this._r;
		const p = r._u48(this._off + i * 6);
		if (p === 0) return null;
		return r._text(p + 10, r._size(p, TEXT_MAGIC));
	}
}

/** List of bytes. Elements are returned as views of the message */
export class BytesListIn extends ListIn<Uint8Array | null> {
	forEach(fn: (value: Uint8Array | null, index: number) => void): void {
		const n = this.length;
		for (let i = 0; i < n; ++i) fn(this.get(i), i);
	}
	toArray(): Array<Uint8Array | null> {
		const n = this.length;
		const ans = new Array<Uint8Array | null>(n);
		for (let i = 0; i < n; ++i) ans[i] = this.get(i);
		return ans;
	}
	get(i: number): Uint8Array | null {
		if (!((i >>> 0) === i && i < this.length)) _indexError(i, this.length);
		const r = this._r;
		const p = r._u48(this._off + i * 6);
		if (p === 0) return null;
		return r._bytes(p + 10, r._size(p, BYTES_MAGIC));
	}
}

/** Base class of generated lists of structs */
export abstract class StructListIn<S> extends FixedListIn<S> {
	/** Width of a struct in bytes */
	abstract get _width(): number;
	get byteLength(): number { return this.length * this._width; }
}

/** Base class of generated lists of tables */
export abstract class TableListIn<T> extends ListIn<T | null> {}

/** Base class of generated lists of unions */
export abstract class UnionListIn<U> extends ListIn<U> {}

/**
 * Base class of generated direct lists of tables. The tables are stored inline
 * with a fixed size.
 *
 * For fast iteration without allocating an object per row, use cursor and seek:
 *
 *     const c = list.cursor();
 *     for (let i = 0; i < list.length; ++i) {
 *         list.seek(c, i);
 *         ... c.x ...
 *     }
 */
export abstract class DirectTableListIn<T> extends FixedListIn<T> {
	/** Size of each table in the list */
	declare readonly _itemSize: number;

	constructor(reader: Reader, offset: number, length: number, magic: number) {
		let itemSize = 0;
		if (length !== 0) {
			const m = reader._dv.getUint32(offset, true);
			if (m !== magic) magicError(offset, magic, m);
			itemSize = reader._dv.getUint32(offset + 4, true);
		}
		super(reader, offset + 8, length);
		this._itemSize = itemSize;
	}

	get byteLength(): number { return this.length * this._itemSize; }

	/** Return a reusable table object, positioned at the first element */
	abstract cursor(): T;

	/** Position the cursor c at element i and return it */
	abstract seek(c: T, i: number): T;
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

	_setBytes(o: number, v: BytesOut|BytesLike) {
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

	_addInplaceBytes(o: number, t: BytesLike) {
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

	_setBytes(idx: number, v: BytesOut|BytesLike): void {
		if (!(v instanceof BytesOut)) v = this._writer.constructBytes(v);
		this._set(idx, v._offset - 10);
	}

	_addInplaceText(idx: number, v: string): void {
		console.assert(this._writer._size == this._end);
		const l = this._writer._writeText(v);
		this._set(idx, l);
	}

	_addInplaceBytes(idx: number, t: BytesLike): void {
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
		for (let i = 0; i < this.length; ++i) this.set(this._offset, i, inp.get(i));
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

	constructDirectTableList<T extends TableOut>(type: {
		new(writer: Writer, withHeader: boolean): T;
		_MAGIC: number; _SIZE: number;
		_IN: { new(reader: Reader, offset: number, size: number): CopyType<T> };
	}, size: number): ListOut<T, CopyType<T>> {
		// Write DIRECT_LIST header: DIRECT_LIST_MAGIC (4) + size as uint48 (6) = 10 bytes
		// Then inline: table_magic (4) + item_size (4) + size * _SIZE zeroed bytes
		this._reserve(18 + size * type._SIZE);
		this._data.setUint32(this._size, DIRECT_LIST_MAGIC, true);
		this._writeUint48(this._size + 4, size);
		this._size += 10;
		// Create ListOut now: _offset = this._size (just after header), so _setList stores header start ✓
		let dataStart = 0;
		const listOut = new ListOut<T, CopyType<T>>(
			this,
			size,
			'',
			0,
			false,
			(off: number, idx: number, v: T|CopyType<T>) => {
				if (v instanceof type._IN) {
					const s = this._size;
					this._size = dataStart + idx * type._SIZE;
					const item = new type(this, false);
					this._size = s;
					(item as any)._copy(v);
				}
			},
			(off: number, idx: number): T => {
				const s = this._size;
				this._size = dataStart + idx * type._SIZE;
				const item = new type(this, false);
				this._size = s;
				return item;
			});
		// Write inline data after creating listOut (closures capture dataStart by reference)
		this._data.setUint32(this._size, type._MAGIC, true);
		this._data.setUint32(this._size + 4, type._SIZE, true);
		this._size += 8;
		dataStart = this._size;
		for (let i = 0; i < size * type._SIZE; ++i) this._data.setUint8(this._size++, 0);
		return new Proxy<ListOut<T, CopyType<T>>>(listOut, listOutHandel);
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
	  ListOut<BytesLike|BytesOut, Uint8Array|null> {
		return new Proxy<ListOut<BytesLike|BytesOut, Uint8Array|null>>(
		  new ListOut<BytesLike|BytesOut, Uint8Array|null>(
			this,
			size,
			'\0\0\0\0\0\0',
			size,
			!_inplace,
			(off: number, idx: number, v: BytesOut|BytesLike|null) => {
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

	constructBytes(t: BytesLike): BytesOut {
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
