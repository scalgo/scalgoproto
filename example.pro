#THIS IS A COMMENT

  //THIS IS A COMMENT

  /*
  this is also a comment
  */

  /*

  /*
  This is a nested comment
  */

  */

namespace tsng::monkey;  
    
table Location @1234556 {
	union {
		tile {
			x : UInt32;
			y : UInt32;
		}
                spider {
                }
	}
}

enum DataType {
	u8, 
	i8, 
	u16, 
	i16, 
	u32, 
	i32, 
	u64, 
	i64, 
	f32, 
	f64, 
	any,
}

enum Compression {
	none, 
	zstd, 
}

struct Monkey {
}

struct Hash {
	a : UInt64;
	b : UInt64;
	c : UInt64;
        d : UInt64;
}

table Metadata @1234558 {
	tileMatrixId :Int32;
	source :Location;
	target :Location;
	compressedSize :UInt64;
	uncompressedSize :UInt64;
	compression :Compression;
	hash :Hash;

        union {
        	custom {},
		raster {
			scale :Int8;
			dataType :DataType;
		},
		rasterChunk {
			scale :Int8;
			dataType :DataType;
			width :Int32;
			height :Int32;
		},
		floodingB {
			scale :UInt8;
			graphSize :UInt32;
		},
	}
}

table OptionDescription @12345512 {
	name :Text;
	help :Text;
	required :Bool = true;
	union {
		value {
			union {
				f64 {
					min :Optional Float64;
					max :Optional Float64;
				}
				i64 {
					min :Optional Int64;
					max :Optional Int64;
				}
				path {};
				paths {};
				bool {};
				text {};
				enum_ {
					values : List Text;
				}
			}
		}
		data {
			output :Bool;
			union {
				raster {
					dataType  :DataType;
				}
				custom {}
			}
		}
	}
}

table ModuleDescription @123455123 {
	name :Text;
	help :Text;
	options :List OptionDescription;
	specifyTileMatrix : Bool = false;
	spider :Bool = false;
	maxInputSizeMemoryFactor : Float64=0;
	sumInputSizeMemoryFactor : Float64=0;
	baseMemory : Float64=0;
}

table FloodingBInput @1334558 {
	scale :UInt32;
	numOfNodes :UInt32;
	location :Location;
}
