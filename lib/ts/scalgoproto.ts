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

//////////////////////////////////////////////////////////////////////////////////////
// Writer
//
// Objects are appended to a single growing buffer. Everything after the end of the
// written data is zero, so newly allocated objects only need their non zero defaults
// written. All writes go through one DataView; generated setters write directly at
// constant offsets.
//////////////////////////////////////////////////////////////////////////////////////

let textEncoder: TextEncoder | null = null;

/**
 * Non ascii strings with at most this many remaining UTF-16 code units are encoded with
 * a JS loop, longer ones with TextEncoder, which has a fixed cost per call. Measured
 * crossover points: V8 32 to 48, SpiderMonkey above 128; at 48 V8 is within 10% of the
 * faster method.
 */
const TEXT_ENCODER_THRESHOLD = 48;

/**
 * Encode t from index i as utf-8 into u8 at o and return the end offset. Lone
 * surrogates become U+FFFD, like TextEncoder does. u8 must have room for 3 bytes per
 * remaining code unit
 */
function encodeUtf8(t: string, i: number, u8: Uint8Array, o: number): number {
	const n = t.length;
	while (i < n) {
		let c = t.charCodeAt(i++);
		if (c < 0x80) {
			u8[o++] = c;
		} else if (c < 0x800) {
			u8[o++] = 0xC0 | (c >> 6);
			u8[o++] = 0x80 | (c & 0x3F);
		} else {
			if (c >= 0xD800 && c < 0xE000) {
				const d = i < n ? t.charCodeAt(i) : 0;
				if (c < 0xDC00 && d >= 0xDC00 && d < 0xE000) {
					// A surrogate pair: 4 bytes
					++i;
					c = 0x10000 + ((c - 0xD800) << 10) + (d - 0xDC00);
					u8[o++] = 0xF0 | (c >> 18);
					u8[o++] = 0x80 | ((c >> 12) & 0x3F);
					u8[o++] = 0x80 | ((c >> 6) & 0x3F);
					u8[o++] = 0x80 | (c & 0x3F);
					continue;
				}
				c = 0xFFFD; // Lone surrogate
			}
			u8[o++] = 0xE0 | (c >> 12);
			u8[o++] = 0x80 | ((c >> 6) & 0x3F);
			u8[o++] = 0x80 | (c & 0x3F);
		}
	}
	return o;
}

/** Write v as an unsigned 48 bit integer at o */
function setU48(dv: DataView, o: number, v: number): void {
	const hi = Math.floor(v / TWO32);
	dv.setUint32(o, v - hi * TWO32, true);
	dv.setUint16(o + 4, hi, true);
}

/** Return a Uint8Array with the bytes of a latin1 encoded string. Used by generated code */
export function _defaultBytes(s: string): Uint8Array {
	const ans = new Uint8Array(s.length);
	for (let i = 0; i < s.length; ++i) ans[i] = s.charCodeAt(i);
	return ans;
}

/** A text in the message under construction, see Writer.constructText */
export class TextOut {
	declare readonly _w: Writer;
	/** Offset of the magic of the text */
	declare readonly _off: number;
	constructor(writer: Writer, offset: number) {
		this._w = writer;
		this._off = offset;
	}
}

/** Bytes in the message under construction, see Writer.constructBytes */
export class BytesOut {
	declare readonly _w: Writer;
	/** Offset of the magic of the bytes */
	declare readonly _off: number;
	constructor(writer: Writer, offset: number) {
		this._w = writer;
		this._off = offset;
	}
}

/** Constructor type of generated table writers */
export interface TableOutType<T> {
	new(writer: Writer, offset: number): T;
	readonly _MAGIC: number;
	readonly _SIZE: number;
	readonly _DEFAULT: Uint8Array;
	/** True if all bytes of _DEFAULT are zero */
	readonly _ZERO: boolean;
}

/** Constructor type of list writers */
export interface ListOutType<L> {
	new(writer: Writer, length: number, withHeader: boolean): L;
}

/** Base class of all list writers */
export abstract class ListOut<T> {
	declare readonly _w: Writer;
	/** Offset of the first element */
	declare readonly _off: number;
	/** Number of elements in the list */
	declare readonly length: number;

	constructor(writer: Writer, offset: number, length: number) {
		this._w = writer;
		this._off = offset;
		this.length = length;
	}

	/** Set the i'th element */
	abstract set(i: number, value: T): void;

	/** Set the elements starting at element offset to values */
	setAll(values: ArrayLike<T>, offset: number = 0): void {
		const n = values.length;
		if (!((offset >>> 0) === offset && offset + n <= this.length))
			throw new RangeError('Values do not fit in the list at offset ' + offset);
		for (let i = 0; i < n; ++i) this.set(offset + i, values[i]);
	}

	/** Copy the elements of a list read from another message */
	abstract _copy(inp: ListIn<any>): void;
}

function checkIndex(i: number, length: number): void {
	if (!((i >>> 0) === i && i < length)) _indexError(i, length);
}

function checkCopyLength(out: ListOut<unknown>, inp: ListIn<unknown>): void {
	if (out.length !== inp.length)
		throw new RangeError('Copying a list of length ' + inp.length + ' into one of length ' +
							 out.length);
}

/** Copy a list with the same byte layout, taking bytes bytes, by copying its bytes */
function copyBytes(out: ListOut<unknown>, inp: FixedListIn<unknown>, bytes: number): void {
	checkCopyLength(out, inp);
	const src = inp.bytes();
	if (src.length !== bytes) throw new TypeError('Copying a list of a different type');
	out._w._u8.set(src, out._off);
}

/**
 * Copy a typed array into a list of the same element type by copying bytes. Returns
 * false if values is not such a typed array
 */
function setAllTyped(out: ListOut<any>, values: ArrayLike<unknown>, offset: number,
					 ctor: {new(...a: any[]): ArrayBufferView; readonly BYTES_PER_ELEMENT: number}):
  boolean {
	// Compare the type tag rather than use instanceof, which fails for typed arrays from
	// another realm (iframe, worker module, vm)
	if (!ArrayBuffer.isView(values) || (values as any)[Symbol.toStringTag] !== ctor.name ||
		!LITTLE_ENDIAN)
		return false;
	const n = values.length;
	if (!((offset >>> 0) === offset && offset + n <= out.length))
		throw new RangeError('Values do not fit in the list at offset ' + offset);
	const w = ctor.BYTES_PER_ELEMENT;
	out._w._u8.set(new Uint8Array(values.buffer, values.byteOffset, n * w), out._off + offset * w);
	return true;
}

/** Base class of lists of numbers */
export abstract class NumberListOut<A> extends ListOut<number> {
	// setAll of the subclasses copies a typed array A of the element type in one go
	declare readonly _typedArray?: A;
}

export class Int8ListOut extends NumberListOut<Int8Array> {
	constructor(writer: Writer, length: number, withHeader: boolean) {
		super(writer, writer._list(length, length, withHeader, 0), length);
	}
	set(i: number, v: number): void {
		checkIndex(i, this.length);
		this._w._dv.setInt8(this._off + i, v);
	}
	setAll(values: ArrayLike<number> | Int8Array, offset: number = 0): void {
		if (!setAllTyped(this, values, offset, Int8Array)) super.setAll(values, offset);
	}
	_copy(inp: Int8ListIn): void { copyBytes(this, inp, this.length); }
}

export class Uint8ListOut extends NumberListOut<Uint8Array> {
	constructor(writer: Writer, length: number, withHeader: boolean) {
		super(writer, writer._list(length, length, withHeader, 0), length);
	}
	set(i: number, v: number): void {
		checkIndex(i, this.length);
		this._w._dv.setUint8(this._off + i, v);
	}
	setAll(values: ArrayLike<number> | Uint8Array, offset: number = 0): void {
		if (!setAllTyped(this, values, offset, Uint8Array)) super.setAll(values, offset);
	}
	_copy(inp: Uint8ListIn): void { copyBytes(this, inp, this.length); }
}

export class Int16ListOut extends NumberListOut<Int16Array> {
	constructor(writer: Writer, length: number, withHeader: boolean) {
		super(writer, writer._list(length, length * 2, withHeader, 0), length);
	}
	set(i: number, v: number): void {
		checkIndex(i, this.length);
		this._w._dv.setInt16(this._off + i * 2, v, true);
	}
	setAll(values: ArrayLike<number> | Int16Array, offset: number = 0): void {
		if (!setAllTyped(this, values, offset, Int16Array)) super.setAll(values, offset);
	}
	_copy(inp: Int16ListIn): void { copyBytes(this, inp, this.length * 2); }
}

export class Uint16ListOut extends NumberListOut<Uint16Array> {
	constructor(writer: Writer, length: number, withHeader: boolean) {
		super(writer, writer._list(length, length * 2, withHeader, 0), length);
	}
	set(i: number, v: number): void {
		checkIndex(i, this.length);
		this._w._dv.setUint16(this._off + i * 2, v, true);
	}
	setAll(values: ArrayLike<number> | Uint16Array, offset: number = 0): void {
		if (!setAllTyped(this, values, offset, Uint16Array)) super.setAll(values, offset);
	}
	_copy(inp: Uint16ListIn): void { copyBytes(this, inp, this.length * 2); }
}

export class Int32ListOut extends NumberListOut<Int32Array> {
	constructor(writer: Writer, length: number, withHeader: boolean) {
		super(writer, writer._list(length, length * 4, withHeader, 0), length);
	}
	set(i: number, v: number): void {
		checkIndex(i, this.length);
		this._w._dv.setInt32(this._off + i * 4, v, true);
	}
	setAll(values: ArrayLike<number> | Int32Array, offset: number = 0): void {
		if (!setAllTyped(this, values, offset, Int32Array)) super.setAll(values, offset);
	}
	_copy(inp: Int32ListIn): void { copyBytes(this, inp, this.length * 4); }
}

export class Uint32ListOut extends NumberListOut<Uint32Array> {
	constructor(writer: Writer, length: number, withHeader: boolean) {
		super(writer, writer._list(length, length * 4, withHeader, 0), length);
	}
	set(i: number, v: number): void {
		checkIndex(i, this.length);
		this._w._dv.setUint32(this._off + i * 4, v, true);
	}
	setAll(values: ArrayLike<number> | Uint32Array, offset: number = 0): void {
		if (!setAllTyped(this, values, offset, Uint32Array)) super.setAll(values, offset);
	}
	_copy(inp: Uint32ListIn): void { copyBytes(this, inp, this.length * 4); }
}

/** List of I64. set takes a number (exact up to 2^53) or a bigint */
export class Int64ListOut extends NumberListOut<BigInt64Array> {
	constructor(writer: Writer, length: number, withHeader: boolean) {
		super(writer, writer._list(length, length * 8, withHeader, 0), length);
	}
	set(i: number, v: number | bigint): void {
		checkIndex(i, this.length);
		if (typeof v === 'bigint')
			this._w._dv.setBigInt64(this._off + i * 8, v, true);
		else
			this._w._i64(this._off + i * 8, v);
	}
	setAll(values: ArrayLike<number> | BigInt64Array, offset: number = 0): void {
		if (!setAllTyped(this, values, offset, BigInt64Array)) super.setAll(values as ArrayLike<any>, offset);
	}
	_copy(inp: Int64ListIn): void { copyBytes(this, inp, this.length * 8); }
}

/** List of U64. set takes a number (exact up to 2^53) or a bigint */
export class Uint64ListOut extends NumberListOut<BigUint64Array> {
	constructor(writer: Writer, length: number, withHeader: boolean) {
		super(writer, writer._list(length, length * 8, withHeader, 0), length);
	}
	set(i: number, v: number | bigint): void {
		checkIndex(i, this.length);
		if (typeof v === 'bigint')
			this._w._dv.setBigUint64(this._off + i * 8, v, true);
		else
			this._w._u64(this._off + i * 8, v);
	}
	setAll(values: ArrayLike<number> | BigUint64Array, offset: number = 0): void {
		if (!setAllTyped(this, values, offset, BigUint64Array)) super.setAll(values as ArrayLike<any>, offset);
	}
	_copy(inp: Uint64ListIn): void { copyBytes(this, inp, this.length * 8); }
}

export class Float32ListOut extends NumberListOut<Float32Array> {
	constructor(writer: Writer, length: number, withHeader: boolean) {
		super(writer, writer._list(length, length * 4, withHeader, 0), length);
	}
	set(i: number, v: number): void {
		checkIndex(i, this.length);
		this._w._dv.setFloat32(this._off + i * 4, v, true);
	}
	setAll(values: ArrayLike<number> | Float32Array, offset: number = 0): void {
		if (!setAllTyped(this, values, offset, Float32Array)) super.setAll(values, offset);
	}
	_copy(inp: Float32ListIn): void { copyBytes(this, inp, this.length * 4); }
}

export class Float64ListOut extends NumberListOut<Float64Array> {
	constructor(writer: Writer, length: number, withHeader: boolean) {
		super(writer, writer._list(length, length * 8, withHeader, 0), length);
	}
	set(i: number, v: number): void {
		checkIndex(i, this.length);
		this._w._dv.setFloat64(this._off + i * 8, v, true);
	}
	setAll(values: ArrayLike<number> | Float64Array, offset: number = 0): void {
		if (!setAllTyped(this, values, offset, Float64Array)) super.setAll(values, offset);
	}
	_copy(inp: Float64ListIn): void { copyBytes(this, inp, this.length * 8); }
}

/** List of bools, packed 8 to a byte */
export class BoolListOut extends ListOut<boolean> {
	constructor(writer: Writer, length: number, withHeader: boolean) {
		super(writer, writer._list(length, (length + 7) >> 3, withHeader, 0), length);
	}
	set(i: number, v: boolean): void {
		checkIndex(i, this.length);
		const dv = this._w._dv, o = this._off + (i >> 3), b = 1 << (i & 7);
		const x = dv.getUint8(o);
		dv.setUint8(o, v ? x | b : x & ~b);
	}
	_copy(inp: BoolListIn): void {
		copyBytes(this, inp, (this.length + 7) >> 3);
		// Clear unused bits of the last byte
		if (this.length & 7) {
			const o = this._off + (this.length >> 3);
			this._w._u8[o] &= (1 << (this.length & 7)) - 1;
		}
	}
}

/** List of enums. null means no value */
export class EnumListOut<E> extends ListOut<E | null> {
	constructor(writer: Writer, length: number, withHeader: boolean) {
		super(writer, writer._list(length, length, withHeader, 255), length);
	}
	set(i: number, v: E | null): void {
		checkIndex(i, this.length);
		this._w._dv.setUint8(this._off + i, v === null ? 255 : v as any as number);
	}
	_copy(inp: EnumListIn<E>): void { copyBytes(this, inp, this.length); }
}

/** List of texts. null means no value */
export class TextListOut extends ListOut<string | TextOut | null> {
	constructor(writer: Writer, length: number, withHeader: boolean) {
		super(writer, writer._list(length, length * 6, withHeader, 0), length);
	}
	set(i: number, v: string | TextOut | null): void {
		checkIndex(i, this.length);
		this._w._setText(this._off + i * 6, v);
	}
	_copy(inp: TextListIn): void {
		checkCopyLength(this, inp);
		// Copy the bytes of the texts, without decoding and encoding them
		const r = inp._r, w = this._w;
		for (let i = 0; i < this.length; ++i) {
			const p = r._u48(inp._off + i * 6);
			w._u48(this._off + i * 6, p === 0 ? 0 : w._copyText(r, p));
		}
	}
}

/** List of bytes. null means no value */
export class BytesListOut extends ListOut<BytesLike | BytesOut | null> {
	constructor(writer: Writer, length: number, withHeader: boolean) {
		super(writer, writer._list(length, length * 6, withHeader, 0), length);
	}
	set(i: number, v: BytesLike | BytesOut | null): void {
		checkIndex(i, this.length);
		this._w._setBytes(this._off + i * 6, v);
	}
	_copy(inp: BytesListIn): void {
		checkCopyLength(this, inp);
		for (let i = 0; i < this.length; ++i) this.set(i, inp.get(i));
	}
}

/** Base class of generated lists of structs */
export abstract class StructListOut<S> extends ListOut<S> {
	/** Width of a struct in bytes */
	abstract get _width(): number;
	_copy(inp: StructListIn<S>): void { copyBytes(this, inp, this.length * this._width); }
}

/** Base class of generated lists of tables */
export abstract class TableListOut<T, TIn> extends ListOut<T | TIn | null> {
	/** Construct a new table, store it at index i and return it */
	abstract add(i: number): T;
	_copy(inp: ListIn<TIn | null>): void {
		checkCopyLength(this, inp);
		for (let i = 0; i < this.length; ++i) this.set(i, inp.get(i));
	}
}

/**
 * Base class of generated direct lists of tables. The tables are stored inline and
 * initialized with their defaults; get(i) returns a writer for the i'th table
 */
export abstract class DirectTableListOut<T, TIn> extends ListOut<TIn> {
	/** Return a writer for the i'th table */
	abstract get(i: number): T;
	_copy(inp: ListIn<TIn>): void {
		checkCopyLength(this, inp);
		for (let i = 0; i < this.length; ++i) this.set(i, inp.get(i));
	}
}

/** Base class of generated lists of unions; get(i) returns a writer for the i'th union */
export abstract class UnionListOut<U, UIn> extends ListOut<UIn> {
	/** Return a writer for the i'th union */
	abstract get(i: number): U;
	_copy(inp: ListIn<UIn>): void {
		checkCopyLength(this, inp);
		for (let i = 0; i < this.length; ++i) this.set(i, inp.get(i));
	}
}

/** Responsible for constructing a message */
export class Writer {
	declare _buffer: ArrayBuffer;
	declare _u8: Uint8Array;
	declare _dv: DataView;
	/** Number of bytes written */
	declare _size: number;

	/** Construct a writer, with an initial capacity in bytes */
	constructor(capacity: number = 1024) {
		this._buffer = new ArrayBuffer(Math.max(capacity, 16));
		this._u8 = new Uint8Array(this._buffer);
		this._dv = new DataView(this._buffer);
		this._size = 10; // Room for the message header
	}

	/** Make room for n more bytes */
	_reserve(n: number): void {
		const need = this._size + n;
		if (need <= this._buffer.byteLength) return;
		const nb = new ArrayBuffer(Math.max(this._buffer.byteLength * 2, need));
		const u8 = new Uint8Array(nb);
		u8.set(this._u8.subarray(0, this._size));
		this._buffer = nb;
		this._u8 = u8;
		this._dv = new DataView(nb);
	}

	/** Allocate n zeroed bytes at the end, and return their offset */
	_alloc(n: number): number {
		this._reserve(n);
		const o = this._size;
		this._size = o + n;
		return o;
	}

	_u48(o: number, v: number): void { setU48(this._dv, o, v); }

	_i64(o: number, v: number): void {
		const hi = Math.floor(v / TWO32);
		this._dv.setUint32(o, v - hi * TWO32, true);
		this._dv.setInt32(o + 4, hi, true);
	}

	_u64(o: number, v: number): void {
		const hi = Math.floor(v / TWO32);
		this._dv.setUint32(o, v - hi * TWO32, true);
		this._dv.setUint32(o + 4, hi, true);
	}

	/** Set the bits in mask of the byte at o */
	_setBits(o: number, mask: number): void {
		this._dv.setUint8(o, this._dv.getUint8(o) | mask);
	}

	/** Set or clear the bits in mask of the byte at o */
	_bit(o: number, mask: number, v: boolean): void {
		const x = this._dv.getUint8(o);
		this._dv.setUint8(o, v ? x | mask : x & ~mask);
	}

	/**
	 * Allocate a table with the given default content, optionally with a header, and
	 * return the offset of its content
	 */
	_table(magic: number, def: Uint8Array, zero: boolean, withHeader: boolean): number {
		const h = withHeader ? 10 : 0;
		const o = this._alloc(h + def.length);
		if (withHeader) {
			this._dv.setUint32(o, magic, true);
			setU48(this._dv, o + 4, def.length);
		}
		// Newly allocated bytes are zero
		if (!zero) this._u8.set(def, o + h);
		return o + h;
	}

	/**
	 * Allocate a list of length elements taking bytes bytes, optionally with a
	 * header, with all bytes set to fill. Return the offset of the first element
	 */
	_list(length: number, bytes: number, withHeader: boolean, fill: number): number {
		if (!((length >>> 0) === length)) throw new RangeError('Invalid list length ' + length);
		const h = withHeader ? 10 : 0;
		const o = this._alloc(h + bytes);
		if (withHeader) {
			this._dv.setUint32(o, LIST_MAGIC, true);
			setU48(this._dv, o + 4, length);
		}
		if (fill !== 0) this._u8.fill(fill, o + h, o + h + bytes);
		return o + h;
	}

	/**
	 * Allocate a direct list of length tables with the given default content,
	 * optionally with a header, and return the offset of the first table
	 */
	_directList(length: number, magic: number, def: Uint8Array, zero: boolean,
				withHeader: boolean): number {
		if (!((length >>> 0) === length)) throw new RangeError('Invalid list length ' + length);
		const h = withHeader ? 10 : 0;
		const o = this._alloc(h + 8 + length * def.length);
		if (withHeader) {
			this._dv.setUint32(o, DIRECT_LIST_MAGIC, true);
			setU48(this._dv, o + 4, length);
		}
		// The magic and size of the tables, followed by the tables
		this._dv.setUint32(o + h, magic, true);
		this._dv.setUint32(o + h + 4, def.length, true);
		const start = o + h + 8;
		if (!zero && length !== 0) {
			// Write the defaults once, then double the written part
			const u8 = this._u8, total = length * def.length;
			u8.set(def, start);
			for (let done = def.length; done < total; done *= 2)
				u8.copyWithin(start + done, start, start + Math.min(done, total - done));
		}
		return start;
	}

	/** Check that inplace content of the table ending at end is added right after it */
	_checkInplace(end: number): void {
		if (this._size !== end)
			throw new Error('Inplace members must be added right after their table is ' +
							'constructed, before anything else is written');
	}

	/**
	 * Write utf-8 encoded text followed by a zero byte, and return the number of bytes
	 * not including the zero
	 */
	_writeText(t: string): number {
		const n = t.length;
		this._reserve(n + 1);
		const start = this._size;
		let u8 = this._u8;
		let i = 0;
		for (; i < n; ++i) {
			const c = t.charCodeAt(i);
			if (c >= 0x80) break;
			u8[start + i] = c;
		}
		let len = i;
		if (i < n) {
			// Non ascii: at most 3 bytes per remaining UTF-16 code unit. Growing the
			// buffer only keeps the bytes before _size, so include the ascii prefix
			this._size = start + i;
			this._reserve((n - i) * 3 + 1);
			u8 = this._u8;
			if (n - i > TEXT_ENCODER_THRESHOLD) {
				if (textEncoder === null) textEncoder = new TextEncoder();
				len += textEncoder.encodeInto(t.substring(i), u8.subarray(start + i)).written;
			} else {
				len = encodeUtf8(t, i, u8, start + i) - start;
			}
		}
		u8[start + len] = 0;
		this._size = start + len + 1;
		return len;
	}

	/** Store a pointer to text (written if it is a string) at o; null stores no text */
	_setText(o: number, v: string | TextOut | null): void {
		let p = 0;
		if (v !== null) p = (v instanceof TextOut ? this._own(v) : this.constructText(v))._off;
		setU48(this._dv, o, p);
	}

	/** Store a pointer to bytes (written if needed) at o; null stores no bytes */
	_setBytes(o: number, v: BytesLike | BytesOut | null): void {
		let p = 0;
		if (v !== null) p = (v instanceof BytesOut ? this._own(v) : this.constructBytes(v))._off;
		setU48(this._dv, o, p);
	}

	/** Check that an object (table, list, text or bytes) belongs to this writer */
	_own<T extends {_w: Writer}>(v: T): T {
		if (v._w !== this) throw new Error('Object from another writer');
		return v;
	}

	/**
	 * Copy the text at p (the offset of its magic) of the message read by r, and return
	 * the offset of the copy. The bytes are copied as they are, without decoding
	 */
	_copyText(r: Reader, p: number): number {
		return this._textFromBytes(r._bytes(p + 10, r._size(p, TEXT_MAGIC)));
	}

	/** Write a text with the given utf-8 bytes, and return the offset of its magic */
	_textFromBytes(b: Uint8Array): number {
		const o = this._alloc(11 + b.length);
		this._dv.setUint32(o, TEXT_MAGIC, true);
		setU48(this._dv, o + 4, b.length);
		this._u8.set(b, o + 10); // The zero termination is already zero
		return o;
	}

	/** Write the utf-8 bytes of an inplace text and return their length */
	_inplaceTextFromBytes(b: Uint8Array): number {
		const o = this._alloc(b.length + 1);
		this._u8.set(b, o); // The zero termination is already zero
		return b.length;
	}

	/** Copy the 8 bytes at q of src to o */
	_copy8(o: number, src: DataView, q: number): void {
		this._dv.setUint32(o, src.getUint32(q, true), true);
		this._dv.setUint32(o + 4, src.getUint32(q + 4, true), true);
	}

	/** Write bytes without a header and return their length */
	_writeBytes(b: BytesLike): number {
		const u = b instanceof Uint8Array ? b : new Uint8Array(b);
		const o = this._alloc(u.length);
		this._u8.set(u, o);
		return u.length;
	}

	/** Construct a table of the given type */
	constructTable<T>(type: TableOutType<T>): T {
		return new type(this, this._table(type._MAGIC, type._DEFAULT, type._ZERO, true));
	}

	/** Write a text, which can then be stored in several places */
	constructText(t: string): TextOut {
		const o = this._alloc(10);
		// Note: writing may grow the buffer, so only use this._dv afterwards
		const len = this._writeText(t);
		this._dv.setUint32(o, TEXT_MAGIC, true);
		setU48(this._dv, o + 4, len);
		return new TextOut(this, o);
	}

	/** Write bytes, which can then be stored in several places */
	constructBytes(b: BytesLike): BytesOut {
		const o = this._alloc(10);
		const len = this._writeBytes(b); // May grow the buffer
		this._dv.setUint32(o, BYTES_MAGIC, true);
		setU48(this._dv, o + 4, len);
		return new BytesOut(this, o);
	}

	/**
	 * Construct a list of the given list type, e.g. Int32ListOut or a generated
	 * T_ListOut. values, if given, is stored in the list
	 */
	constructList<L extends ListOut<any>>(type: ListOutType<L>,
										   lengthOrValues: number | ArrayLike<any>): L {
		if (typeof lengthOrValues === 'number') return new type(this, lengthOrValues, true);
		const l = new type(this, lengthOrValues.length, true);
		l.setAll(lengthOrValues);
		return l;
	}

	constructInt8List(lengthOrValues: number | ArrayLike<number>): Int8ListOut {
		return this.constructList(Int8ListOut, lengthOrValues);
	}
	constructUint8List(lengthOrValues: number | ArrayLike<number>): Uint8ListOut {
		return this.constructList(Uint8ListOut, lengthOrValues);
	}
	constructInt16List(lengthOrValues: number | ArrayLike<number>): Int16ListOut {
		return this.constructList(Int16ListOut, lengthOrValues);
	}
	constructUint16List(lengthOrValues: number | ArrayLike<number>): Uint16ListOut {
		return this.constructList(Uint16ListOut, lengthOrValues);
	}
	constructInt32List(lengthOrValues: number | ArrayLike<number>): Int32ListOut {
		return this.constructList(Int32ListOut, lengthOrValues);
	}
	constructUint32List(lengthOrValues: number | ArrayLike<number>): Uint32ListOut {
		return this.constructList(Uint32ListOut, lengthOrValues);
	}
	constructInt64List(lengthOrValues: number | ArrayLike<number> | BigInt64Array):
	  Int64ListOut {
		return this.constructList(Int64ListOut, lengthOrValues);
	}
	constructUint64List(lengthOrValues: number | ArrayLike<number> | BigUint64Array):
	  Uint64ListOut {
		return this.constructList(Uint64ListOut, lengthOrValues);
	}
	constructFloat32List(lengthOrValues: number | ArrayLike<number>): Float32ListOut {
		return this.constructList(Float32ListOut, lengthOrValues);
	}
	constructFloat64List(lengthOrValues: number | ArrayLike<number>): Float64ListOut {
		return this.constructList(Float64ListOut, lengthOrValues);
	}
	constructBoolList(lengthOrValues: number | ArrayLike<boolean>): BoolListOut {
		return this.constructList(BoolListOut, lengthOrValues);
	}
	constructEnumList<E>(lengthOrValues: number | ArrayLike<E | null>): EnumListOut<E> {
		return this.constructList(EnumListOut, lengthOrValues) as EnumListOut<E>;
	}
	constructTextList(lengthOrValues: number | ArrayLike<string | TextOut | null>):
	  TextListOut {
		return this.constructList(TextListOut, lengthOrValues);
	}
	constructBytesList(lengthOrValues: number | ArrayLike<BytesLike | BytesOut | null>):
	  BytesListOut {
		return this.constructList(BytesListOut, lengthOrValues);
	}

	/**
	 * Finish the message with the given root table and return a copy of it, in a buffer
	 * of exactly its size
	 */
	finalize(root: {_w: Writer, _off: number}): Uint8Array {
		return this.finalizeView(root).slice();
	}

	/**
	 * Finish the message with the given root table and return it without copying, as a
	 * view of the writer's buffer.
	 *
	 * The buffer is larger than the message, so use the view itself, not its .buffer.
	 * The writer must not be used afterwards.
	 */
	finalizeView(root: {_w: Writer, _off: number}): Uint8Array {
		this._own(root);
		this._dv.setUint32(0, MESSAGE_MAGIC, true);
		setU48(this._dv, 4, root._off - 10);
		return this._u8.subarray(0, this._size);
	}
}
