"""Create nonflashable comparison fixtures from the already published EXP01 Image.
The original user's boot partitions never enter CI. Images are synthetic and minimal.
"""
from pathlib import Path
import struct
import sys

root = Path(sys.argv[1])
image_path = Path(sys.argv[2])
image = image_path.read_bytes()
assert image[56:60] == b"ARMd"
assert len(image) == 30349328
orig_size = len(image) + 8
aligned = (orig_size + 4095) & ~4095
for mode in ("prefix-matches", "content-differs"):
    folder = root / mode
    folder.mkdir(parents=True, exist_ok=True)
    blob = bytearray(4096 + aligned + 4096)
    blob[:8] = b"ANDROID!"
    for offset, val in ((8, orig_size), (12, 64), (20, 1580), (40, 3)):
        struct.pack_into("<I", blob, offset, val)
    blob[4096:4096+len(image)] = image
    blob[4096+len(image):4096+orig_size] = bytes([255]*8)
    if mode == "content-differs":
        blob[4096 + 7000] ^= 1
    (folder / "boot_b.img").write_bytes(blob)
print("Created two synthetic, nonflashable EXP05 fixtures.")
