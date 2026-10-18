"""Generate synthetic boot backup fixtures for EXP03 parser tests; not flashable."""
from pathlib import Path
import struct
import sys
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
def le(b,o,x):struct.pack_into("<I",b,o,x)
def be(b,o,x):struct.pack_into(">I",b,o,x)
b=bytearray(16384);b[:8]=b"ANDROID!"
for o,v in [(8,8192),(12,64),(20,1580),(40,3)]:le(b,o,v)
b[4096+56:4096+60]=b"ARMd"
b[12288:12296]=bytes.fromhex("1f8b080000000000")
(out/"boot_b.img").write_bytes(b)
v=bytearray(12288);v[:8]=b"VNDRBOOT"
for o,x in [(8,3),(12,4096),(24,64),(2096,2112),(2100,64)]:le(v,o,x)
v[4096:4104]=bytes.fromhex("1f8b080000000000")
v[8192:8200]=bytes.fromhex("d00dfeed00000040")
(out/"vendor_boot_b.img").write_bytes(v)
d=bytearray(4096)
for o,x in [(0,0xd7b7ab1e),(4,96),(8,32),(12,32),(16,1),(20,32),(24,4096),(28,0),(32,32),(36,64),(40,1),(44,1),(64,0xd00dfeed),(68,32)]:be(d,o,x)
(out/"dtbo_b.img").write_bytes(d)
a=bytearray(4096);a[:4]=b"AVB0";be(a,4,1);be(a,8,0)
(out/"vbmeta_b.img").write_bytes(a)
print("Synthetic nonflashable fixtures created")
