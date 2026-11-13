//! R17 raw v1: direct serde-to-bytes, including exact IEEE f64 and 64-bit integers.
//! A record is u32-LE length, u8 kind, then either JSON metadata (1) or this tree (2/4).
use serde::Serialize;
use serde::ser::{self, SerializeMap, SerializeSeq, SerializeStruct};

pub const MAX_RECORD: usize = 8 * 1024 * 1024;

#[derive(Debug)]
pub struct Error(String);
impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        self.0.fmt(f)
    }
}
impl std::error::Error for Error {}
impl ser::Error for Error {
    fn custom<T: std::fmt::Display>(value: T) -> Self {
        Self(value.to_string())
    }
}
type Result<T> = std::result::Result<T, Error>;

pub fn record<T: Serialize + ?Sized>(kind: u8, value: &T) -> Result<Vec<u8>> {
    let mut encoder = Encoder {
        bytes: vec![0, 0, 0, 0, kind],
    };
    value.serialize(&mut encoder)?;
    finish(encoder.bytes)
}

pub fn json_record<T: Serialize>(value: &T) -> Result<Vec<u8>> {
    let mut bytes = vec![0, 0, 0, 0, 1];
    serde_json::to_writer(&mut bytes, value).map_err(|e| Error(e.to_string()))?;
    finish(bytes)
}

fn finish(mut bytes: Vec<u8>) -> Result<Vec<u8>> {
    let len = bytes.len() - 4;
    if len > MAX_RECORD {
        return Err(Error("raw record exceeds bounded wire size".into()));
    }
    bytes[..4].copy_from_slice(&(len as u32).to_le_bytes());
    Ok(bytes)
}

struct Encoder {
    bytes: Vec<u8>,
}
impl Encoder {
    fn text(&mut self, value: &str) -> Result<()> {
        let len = u32::try_from(value.len()).map_err(|_| Error("string too long".into()))?;
        self.bytes.extend_from_slice(&len.to_le_bytes());
        self.bytes.extend_from_slice(value.as_bytes());
        Ok(())
    }
    fn container(&mut self, tag: u8) -> Container<'_> {
        self.bytes.push(tag);
        let length_at = self.bytes.len();
        self.bytes.extend_from_slice(&0u32.to_le_bytes());
        Container {
            encoder: self,
            length_at,
            count: 0,
        }
    }
}
struct Container<'a> {
    encoder: &'a mut Encoder,
    length_at: usize,
    count: u32,
}
impl Container<'_> {
    fn element<T: Serialize + ?Sized>(&mut self, value: &T) -> Result<()> {
        self.count = self
            .count
            .checked_add(1)
            .ok_or_else(|| Error("array too long".into()))?;
        value.serialize(&mut *self.encoder)
    }
    fn finish(self) -> Result<()> {
        self.encoder.bytes[self.length_at..self.length_at + 4]
            .copy_from_slice(&self.count.to_le_bytes());
        Ok(())
    }
}
impl SerializeSeq for Container<'_> {
    type Ok = ();
    type Error = Error;
    fn serialize_element<T: Serialize + ?Sized>(&mut self, value: &T) -> Result<()> {
        self.element(value)
    }
    fn end(self) -> Result<()> {
        self.finish()
    }
}
impl ser::SerializeTuple for Container<'_> {
    type Ok = ();
    type Error = Error;
    fn serialize_element<T: Serialize + ?Sized>(&mut self, value: &T) -> Result<()> {
        self.element(value)
    }
    fn end(self) -> Result<()> {
        self.finish()
    }
}
impl ser::SerializeTupleStruct for Container<'_> {
    type Ok = ();
    type Error = Error;
    fn serialize_field<T: Serialize + ?Sized>(&mut self, value: &T) -> Result<()> {
        self.element(value)
    }
    fn end(self) -> Result<()> {
        self.finish()
    }
}
impl ser::SerializeTupleVariant for Container<'_> {
    type Ok = ();
    type Error = Error;
    fn serialize_field<T: Serialize + ?Sized>(&mut self, value: &T) -> Result<()> {
        self.element(value)
    }
    fn end(self) -> Result<()> {
        self.finish()
    }
}
impl SerializeMap for Container<'_> {
    type Ok = ();
    type Error = Error;
    fn serialize_key<T: Serialize + ?Sized>(&mut self, key: &T) -> Result<()> {
        let at = self.encoder.bytes.len();
        key.serialize(&mut *self.encoder)?;
        match self.encoder.bytes[at] {
            // Removing the tag moves only this short key, not the already encoded frame.
            6 => {
                self.encoder.bytes.remove(at);
            }
            tag @ (3 | 4) => {
                let word: [u8; 8] = self.encoder.bytes[at + 1..at + 9].try_into().unwrap();
                let name = if tag == 3 {
                    i64::from_le_bytes(word).to_string()
                } else {
                    u64::from_le_bytes(word).to_string()
                };
                self.encoder.bytes.truncate(at);
                self.encoder.text(&name)?;
            }
            _ => {
                return Err(Error(
                    "raw object keys must be strings or integer device IDs".into(),
                ));
            }
        }
        Ok(())
    }
    fn serialize_value<T: Serialize + ?Sized>(&mut self, value: &T) -> Result<()> {
        self.element(value)
    }
    fn end(self) -> Result<()> {
        self.finish()
    }
}
impl SerializeStruct for Container<'_> {
    type Ok = ();
    type Error = Error;
    fn serialize_field<T: Serialize + ?Sized>(
        &mut self,
        key: &'static str,
        value: &T,
    ) -> Result<()> {
        self.encoder.text(key)?;
        self.element(value)
    }
    fn end(self) -> Result<()> {
        self.finish()
    }
}
impl ser::SerializeStructVariant for Container<'_> {
    type Ok = ();
    type Error = Error;
    fn serialize_field<T: Serialize + ?Sized>(
        &mut self,
        key: &'static str,
        value: &T,
    ) -> Result<()> {
        SerializeStruct::serialize_field(self, key, value)
    }
    fn end(self) -> Result<()> {
        self.finish()
    }
}

impl<'a> ser::Serializer for &'a mut Encoder {
    type Ok = ();
    type Error = Error;
    type SerializeSeq = Container<'a>;
    type SerializeTuple = Container<'a>;
    type SerializeTupleStruct = Container<'a>;
    type SerializeTupleVariant = Container<'a>;
    type SerializeMap = Container<'a>;
    type SerializeStruct = Container<'a>;
    type SerializeStructVariant = Container<'a>;

    fn serialize_bool(self, v: bool) -> Result<()> {
        self.bytes.push(if v { 2 } else { 1 });
        Ok(())
    }
    fn serialize_i8(self, v: i8) -> Result<()> {
        self.serialize_i64(v.into())
    }
    fn serialize_i16(self, v: i16) -> Result<()> {
        self.serialize_i64(v.into())
    }
    fn serialize_i32(self, v: i32) -> Result<()> {
        self.serialize_i64(v.into())
    }
    fn serialize_i64(self, v: i64) -> Result<()> {
        self.bytes.push(3);
        self.bytes.extend_from_slice(&v.to_le_bytes());
        Ok(())
    }
    fn serialize_u8(self, v: u8) -> Result<()> {
        self.serialize_u64(v.into())
    }
    fn serialize_u16(self, v: u16) -> Result<()> {
        self.serialize_u64(v.into())
    }
    fn serialize_u32(self, v: u32) -> Result<()> {
        self.serialize_u64(v.into())
    }
    fn serialize_u64(self, v: u64) -> Result<()> {
        self.bytes.push(4);
        self.bytes.extend_from_slice(&v.to_le_bytes());
        Ok(())
    }
    fn serialize_f32(self, v: f32) -> Result<()> {
        self.serialize_f64(v.into())
    }
    fn serialize_f64(self, v: f64) -> Result<()> {
        self.bytes.push(5);
        self.bytes.extend_from_slice(&v.to_bits().to_le_bytes());
        Ok(())
    }
    fn serialize_char(self, v: char) -> Result<()> {
        self.serialize_str(v.encode_utf8(&mut [0; 4]))
    }
    fn serialize_str(self, v: &str) -> Result<()> {
        self.bytes.push(6);
        self.text(v)
    }
    fn serialize_bytes(self, v: &[u8]) -> Result<()> {
        let mut sequence = self.container(7);
        for byte in v {
            sequence.element(byte)?;
        }
        sequence.finish()
    }
    fn serialize_none(self) -> Result<()> {
        self.serialize_unit()
    }
    fn serialize_some<T: Serialize + ?Sized>(self, v: &T) -> Result<()> {
        v.serialize(self)
    }
    fn serialize_unit(self) -> Result<()> {
        self.bytes.push(0);
        Ok(())
    }
    fn serialize_unit_struct(self, _: &'static str) -> Result<()> {
        self.serialize_unit()
    }
    fn serialize_unit_variant(self, _: &'static str, _: u32, variant: &'static str) -> Result<()> {
        self.serialize_str(variant)
    }
    fn serialize_newtype_struct<T: Serialize + ?Sized>(self, _: &'static str, v: &T) -> Result<()> {
        v.serialize(self)
    }
    fn serialize_newtype_variant<T: Serialize + ?Sized>(
        self,
        _: &'static str,
        _: u32,
        variant: &'static str,
        v: &T,
    ) -> Result<()> {
        let mut map = self.container(8);
        SerializeStruct::serialize_field(&mut map, variant, v)?;
        map.finish()
    }
    fn serialize_seq(self, _: Option<usize>) -> Result<Self::SerializeSeq> {
        Ok(self.container(7))
    }
    fn serialize_tuple(self, _: usize) -> Result<Self::SerializeTuple> {
        Ok(self.container(7))
    }
    fn serialize_tuple_struct(
        self,
        _: &'static str,
        _: usize,
    ) -> Result<Self::SerializeTupleStruct> {
        Ok(self.container(7))
    }
    fn serialize_tuple_variant(
        self,
        _: &'static str,
        _: u32,
        variant: &'static str,
        _: usize,
    ) -> Result<Self::SerializeTupleVariant> {
        self.bytes.push(8);
        self.bytes.extend_from_slice(&1u32.to_le_bytes());
        self.text(variant)?;
        Ok(self.container(7))
    }
    fn serialize_map(self, _: Option<usize>) -> Result<Self::SerializeMap> {
        Ok(self.container(8))
    }
    fn serialize_struct(self, _: &'static str, _: usize) -> Result<Self::SerializeStruct> {
        Ok(self.container(8))
    }
    fn serialize_struct_variant(
        self,
        _: &'static str,
        _: u32,
        variant: &'static str,
        _: usize,
    ) -> Result<Self::SerializeStructVariant> {
        self.bytes.push(8);
        self.bytes.extend_from_slice(&1u32.to_le_bytes());
        self.text(variant)?;
        Ok(self.container(8))
    }
    fn is_human_readable(&self) -> bool {
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_keeps_u64_i64_and_every_f64_bit() {
        assert_eq!(
            record(2, &u64::MAX).unwrap(),
            [vec![10, 0, 0, 0, 2, 4], u64::MAX.to_le_bytes().to_vec()].concat()
        );
        assert_eq!(&record(2, &i64::MIN).unwrap()[6..], &i64::MIN.to_le_bytes());
        for bits in [
            0,
            (-0.0f64).to_bits(),
            f64::MAX.to_bits(),
            1u64,
            0x7ff8_0000_0000_0042,
        ] {
            assert_eq!(
                &record(2, &f64::from_bits(bits)).unwrap()[6..],
                &bits.to_le_bytes()
            );
        }
    }

    #[test]
    fn flattened_structs_and_numeric_device_maps_have_counted_raw_string_keys() {
        #[derive(Serialize)]
        struct Inner {
            n: u64,
        }
        #[derive(Serialize)]
        struct Outer {
            label: &'static str,
            #[serde(flatten)]
            inner: Inner,
        }
        let bytes = record(
            2,
            &Outer {
                label: "舵",
                inner: Inner { n: 7 },
            },
        )
        .unwrap();
        assert_eq!(&bytes[5..10], &[8, 2, 0, 0, 0]);
        assert_eq!(&bytes[10..19], &[5, 0, 0, 0, b'l', b'a', b'b', b'e', b'l']);
        let bytes = record(2, &std::collections::BTreeMap::from([(200u8, 3u64)])).unwrap();
        assert_eq!(&bytes[10..17], &[3, 0, 0, 0, b'2', b'0', b'0']);
        assert_eq!(
            u32::from_le_bytes(bytes[..4].try_into().unwrap()) as usize,
            bytes.len() - 4
        );
    }
}
