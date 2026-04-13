"""Final complete sweep - replace ALL corrupted Unicode with clean ASCII."""
import re

path = "pages/3_under_the_hood.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Map every corrupted character to a clean replacement
char_map = {
    '\u20ac': ' ',      # € (euro) → space (appears in # ═══ comment lines)
    '\u0178': '',       # Ÿ (Y with diaeresis) → remove (corrupted emoji prefix)
    '\u017e': '',       # ž → remove (corrupted emoji suffix chars)
    '\u0161': '',       # š → remove
    '\u017d': '',       # Ž → remove
    '\u02c6': '',       # ˆ → remove (was part of █)
    '\u0153': '',       # œ → remove
    '\u2018': "'",      # ' → apostrophe
    '\u2019': "'",      # ' → apostrophe
    '\u201c': '"',      # " → quote
    '\u201d': '"',      # " → quote
    '\u2013': '-',      # – en dash → hyphen
    '\u2014': '-',      # — em dash → hyphen
    '\u00c2': '',       # Â → remove (double-encode artifact)
    '\u00e2': '',       # â → remove (double-encode artifact)
}

for bad, good in char_map.items():
    content = content.replace(bad, good)

# After removing Ÿ and similar, clean up double-spaces and empty metric labels
# Fix metric labels that now have empty string prefixes
content = re.sub(r'metric\("  ([^"]+)"', r'metric("\1"', content)
content = re.sub(r'metric\(" ([^"]+)"', r'metric("\1"', content)

# Fix comment lines: '#  $ $ ...' patterns from the ═══ section markers
content = re.sub(r'#\s+(\$\s+)+', '# ', content)

# Clean up double spaces left from removed chars
content = re.sub(r'  +', '  ', content)  # max 2 spaces

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

# Final audit
with open(path, "r", encoding="utf-8") as f:
    content2 = f.read()

bad_chars = [(i+1, ord(c), line.strip()[:60])
             for i, line in enumerate(content2.splitlines())
             for c in line
             if ord(c) > 0x7F and not (
                 ord(c) >= 0x1F000 or
                 ord(c) in (0x2699, 0xFE0F, 0x1F3AF, 0x1F9FE, 0x1F50D, 0x1F4CA,
                            0x2705, 0x26A0, 0x2022, 0x00B0, 0x00D7, 0x00B2)
             )]

print(f"Remaining suspicious chars: {len(bad_chars)}")
for ln, cp, ctx in bad_chars[:15]:
    print(f"  L{ln} U+{cp:04X}: {repr(ctx)}")

if not bad_chars:
    print("CLEAN!")
