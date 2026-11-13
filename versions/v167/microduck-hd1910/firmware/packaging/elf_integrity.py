#!/usr/bin/env python3
"""Check the shipped ARM ELF file ranges once, before installation stops services."""
import json
from pathlib import Path
import struct
import sys

ELF_HEADER = struct.Struct('<16sHHIQQQIHHHHHH')
PROGRAM_HEADER = struct.Struct('<IIQQQQQQ')
SECTION_HEADER = struct.Struct('<IIQQQQIIQQ')
NATIVE_FILES = (
    'robotd', 'robotctl', 'padd', 'sounds', 'mediad', 'gamepad-r7/gamesir-xboxd',
    'onnxruntime/libonnxruntime.so.1.28.0',
    'onnxruntime/libonnxruntime_providers_shared.so',
)


def validate_elf(path):
    """Reject a truncated or incompatible ELF without loading or executing it."""
    path = Path(path)
    with path.open('rb') as stream:
        size = path.stat().st_size

        def bounded(offset, length, label):
            if offset < 0 or length < 0 or offset + length > size:
                raise ValueError(f'{path.name}: {label} exceeds file size '
                                 f'({offset}+{length}>{size})')

        def read(offset, length, label):
            bounded(offset, length, label)
            stream.seek(offset)
            value = stream.read(length)
            if len(value) != length:
                raise ValueError(f'{path.name}: short read of {label}')
            return value

        header = ELF_HEADER.unpack(read(0, ELF_HEADER.size, 'ELF header'))
        (ident, kind, machine, version, entry, program_offset, section_offset,
         flags, header_size, program_size, program_count, section_size,
         section_count, names_index) = header
        if (ident[:7] != b'\x7fELF\x02\x01\x01' or machine != 183
                or version != 1 or kind not in (2, 3) or header_size != ELF_HEADER.size):
            raise ValueError(f'{path.name}: requires ELF64 little-endian AArch64 executable/library')
        if not program_count or program_count == 0xffff or program_size != PROGRAM_HEADER.size:
            raise ValueError(f'{path.name}: invalid/unsupported ELF program table')
        bounded(program_offset, program_size * program_count, 'program table')
        load_count = 0
        for index in range(program_count):
            segment = PROGRAM_HEADER.unpack(read(program_offset + index * program_size,
                                                 program_size, f'program header {index}'))
            kind, flags, offset, address, physical, file_size, memory_size, alignment = segment
            if file_size:
                bounded(offset, file_size, f'program segment {index}')
            if kind == 1:  # PT_LOAD: these file ranges are mapped by the dynamic loader.
                load_count += 1
                if file_size > memory_size:
                    raise ValueError(f'{path.name}: PT_LOAD {index} file size exceeds memory size')
                if alignment > 1 and (alignment & (alignment - 1)
                                      or (address - offset) % alignment):
                    raise ValueError(f'{path.name}: PT_LOAD {index} has invalid alignment')
        if not load_count:
            raise ValueError(f'{path.name}: ELF has no PT_LOAD segments')
        if section_offset or section_count:
            # Shipped ELF files use ordinary section numbering. Do not silently
            # accept an unreadable or extended table as a file without sections.
            if (not section_offset or not section_count or section_size != SECTION_HEADER.size
                    or names_index >= section_count):
                raise ValueError(f'{path.name}: invalid/unsupported ELF section table')
            bounded(section_offset, section_size * section_count, 'section table')
            for index in range(section_count):
                section = SECTION_HEADER.unpack(read(section_offset + index * section_size,
                                                      section_size, f'section header {index}'))
                if section[1] != 8 and section[5]:  # SHT_NOBITS occupies memory only.
                    bounded(section[4], section[5], f'section {index}')
        elif names_index:
            raise ValueError(f'{path.name}: section name index without section table')
    return {'bytes': size, 'machine': 'AArch64', 'load_segments': load_count}


def validate_bundle(bundle):
    root = Path(bundle).resolve()
    result = {}
    for name in NATIVE_FILES:
        path = root / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError(f'{name}: missing or invalid native bundle file')
        try:
            result[name] = validate_elf(path)
        except ValueError as error:
            raise ValueError(f'{name}: {error}') from error
    return result


if __name__ == '__main__':
    try:
        result=validate_bundle(sys.argv[1])
        import os
        if os.environ.get('MICRODUCK_INSTALL_LOG') != '1':
            print(json.dumps({'elf_integrity':result},ensure_ascii=False))
    except (OSError, ValueError, IndexError) as error:
        print(f'固件 ELF 完整性校验失败：{error}', file=sys.stderr)
        sys.exit(1)
