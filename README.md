# **epson_escp2**

A Python module to generate raw ESC/P2 sequences from structured text or images, including markdown-style formatting, tables, and varying font styles.

The text or the image is converted into the "Transfer Raster image" ESC/P2 command `ESC i r c b nL nH mL mH d1......dk` and printed as monochrome B/W bitmap in draft/economy mode.

Supported modes:

- non compressed or "Run Length Encoding" compression method
- bit length 1, 2, or 3 (small dot: 01, medium dot: 10, large dot 03)

The `epson_escp2` module also provides tools for generating maintenance commands and decoding ESC/P2 command sequences.

The ESC/P2 decoder is comprehensive of all the individual command specifications and all remote mode commands described in the "EPSON Programming Guide For 4 Color EPSON Ink Jet Printer XP-410" and it is also able to print and dump tiled images produced by the "Transfer Raster image" ESC/P2 commands.

Epson’s **ESC/P2** is Epson’s extended page description language that enables advanced font manipulation, raster graphics, and layout control on Inkjet printers.

## Features

- Convert text with markdown-like formatting to ESC/P2 commands
- Convert images to ESC/P2 raster data
- Generate printer maintenance commands (nozzle checks, cleaning)
- Decode ESC/P2 commands into human-readable format
- Preview generated images before printing
- Direct printing support via LPR protocol (if pyprintlpr module is installed)

## Installation

```bash
pip install epson_escp2
pip install pyprintlpr  # optional module to use the LPR options of epson_escp2
```

## Command Line Interface

### Basic Usage

```bash
python -m epson_escp2 [command] [options]

usage: epson_escp2 [-h] [--dump] [--preview] [--version] [--compress] [--max-block-h] [--bit-length {1,2,3}] [--threshold THRESHOLD] [--font-size FONT_SIZE]
                   [--padding PADDING] [--line-spacing LINE_SPACING] [--host HOST] [--port PORT] [--queue QUEUE] [--label LABEL]
                   {text,file,image,demo} ...

Convert text and images to ESC/P2 printer format

positional arguments:
  {text,file,image,demo}
                        Available commands
    text                Convert text string to ESC/P2
    file                Convert text file to ESC/P2
    image               Convert image to ESC/P2
    demo                Generate demo output

optional arguments:
  -h, --help            show this help message and exit
  --dump                Dump data
  --preview             Show image preview
  --version             show program's version number and exit
  --compress            Enable RLE compression
  --max-block-h         Max height block
  --bit-length {1,2,3}  Dot size (1=small, 2=medium, 3=large)
  --threshold THRESHOLD
                        Threshold for 1-bit conversion (-1 for auto)
  --font-size FONT_SIZE
                        Font size in points
  --padding PADDING     Page padding in pixels
  --line-spacing LINE_SPACING
                        Line spacing in pixels
  --host HOST           Printer IP address
  --port PORT           Printer port
  --queue QUEUE         Print queue name
  --label LABEL         Job label

ESC/P2 Module Command Line Interface

Provides command-line tools for converting text and images to ESC/P2 printer format.

Usage:
    python -m epson_escp2 text "Hello World!" --output hello.escp2
    python -m epson_escp2 file README.md --font-size 12
    python -m epson_escp2 demo

Examples:
    # Convert text to ESC/P2
    python -m epson_escp2 text "**Bold** and ``code`` text" -o output.escp2

    # Convert file with custom settings
    python -m epson_escp2 file README.md --font-size 10

    # Convert image
    python -m epson_escp2 --compress --bit-length 3 image document.png

    # Show demo with preview
    python -m epson_escp2 --preview demo
```

### Usage examples

#### Convert Text
```bash
python -m epson_escp2 text "Hello **World**!" -o output.escp2
```

#### Convert Text File
```bash
python -m epson_escp2 file README.md --font-size 12
```

#### Convert Image
```bash
python -m epson_escp2 image document.png --compress
```

#### Generate Demo
```bash
python -m epson_escp2 demo --preview
```

### Common Options
- `--output`: Output file
- `--preview`: Show image preview
- `--compress`: Enable RLE compression
- `--bit-length`: Dot size (1=small, 2=medium, 3=large)
- `--font-size`: Font size in points
- `--host`: Printer IP for direct printing
- `--port`: Printer port (default: LPR)
- `--queue`: Print queue (default: PASSTHRU)
- `--label`: Print job label

## API Usage

### Text to ESC/P2 Conversion

Print "Hello World":

```python
from epson_escp2.epson_encode import TextToImageConverter, EpsonEscp2
escp2 = EpsonEscp2()
conv = TextToImageConverter()
img = conv.convert_to_image("Hello World")  # Render text → PIL image
img.show()
tri = escp2.image_to_tri(img)  # Encode to Epson TRI blocks
escp2_commands = escp2.tri_to_escp2(tri)  # Wrap in ESC/P2 escp2_commands

from pyprintlpr import LprClient
with LprClient("127.0.0.1") as lpr:
    lpr.send(escp2_commands)  # Send to printer via LPR
```

### Printer Maintenance

Check nozzles:

```python
from epson_escp2.epson_encode import EpsonEscp2
escp2 = EpsonEscp2()
pattern = escp2.check_nozzles(type=type)

from pyprintlpr import LprClient
with LprClient("127.0.0.1") as lpr:
    lpr.send(pattern)  # Send to printer via LPR
```

Clean nozzles:

```python
from epson_escp2.epson_encode import EpsonEscp2
escp2 = EpsonEscp2()
pattern = escp2.clean_nozzles(0, power_clean=False, has_alt_mode=None)

from pyprintlpr import LprClient
with LprClient("127.0.0.1") as lpr:
    lpr.send(pattern)  # Send to printer via LPR
```

Decoding example:

```python
from epson_escp2.epson_encode import EpsonEscp2
escp2 = EpsonEscp2()
pattern = escp2.test_color_pattern(get_pattern=False)

from epson_escp2.epson_decode import decode_escp2_commands
print(decode_escp2_commands(pattern, show_image=False))
```

## Text Formatting Support

The module supports basic markdown-like formatting:

- `**bold**` - Bold text
- ``monospace`` - Monospace text
- ```bold mono``` - Bold monospace
- `__underline__` - Underlined text
- Tables using pipe syntax:
  ```
  | Header | Another |
  |--------|---------|
  | Cell   | Value   |
  ```

## Examples

### Print "Hello World"
```python
from epson_escp2 import TextToImageConverter, EpsonEscp2
from pyprintlpr import LprClient

converter = TextToImageConverter()
escp2 = EpsonEscp2()

img = converter.convert_to_image("Hello World")
tri = escp2.image_to_tri(img)
escp2_data = escp2.tri_to_escp2(tri)

with LprClient("192.168.1.100") as lpr:
    lpr.send(escp2_data)
```

### Decode ESC/P2 Commands
```bash
python -m epson_escp2.epson_decode --file output.escp2
```

### Print Test Pattern
```bash
python -m epson_escp2.epson_decode --test-pattern
```

## Module API

This module provides comprehensive tools for working with Epson ESC/P2 printers, including text/image conversion to printer commands, maintenance functions, and command decoding.

### Core Classes

#### `TextToImageConverter`
Converts text with lightweight markdown-like formatting into a PIL image suitable for ESC/P2 raster printing.

**Methods**:
- `conv = TextToImageConverter(font_path=None, font_bold_path=None, font_mono_path=None, font_mono_bold_path=None, font_size=20)`  
  Initialize with optional custom fonts
- `conv.convert_to_image(text, h_dpi=360, v_dpi=120, width=2768, height=1250, threshold=-1, line_spacing=4, padding=10, bg_color="black", text_color="white")`  
  Convert text to PIL Image with formatting
- `conv.preview(image, h_dpi=360, v_dpi=120)`  
  Preview image with printer DPI simulation
- `conv.get_system_fonts(size=12)`  
  Get system fonts dictionary
- `conv.get_fonts(size=12)`  
  Get fonts as tuple (prop_normal, prop_bold, mono_normal, mono_bold)

#### `EpsonEscp2`
Generates ESC/P2 printer commands from images or for maintenance.

**Methods**:
- `escp2 = EpsonEscp2(color=0, bit_length=3, compress=True, max_block_h=128)`  
  Initialize printer command generator
- `escp2.image_to_tri(image)`  
  Convert PIL image to Transfer Raster Image (TRI) blocks
- `escp2.tri_to_escp2(tri, h_dpi=360, v_dpi=120, page=120, unit=1440, method_id="11", dot_size_id="11")`  
  Wrap TRI data in complete ESC/P2 commands
- `escp2.test_color_pattern(get_pattern=False, use_black23=False)`  
  Generate color test pattern
- `escp2.clean_nozzles(group_index, power_clean=False, has_alt_mode=None)`  
  Generate nozzle cleaning command
- `escp2.check_nozzles(type=0)`  
  Generate nozzle check pattern command

### Encoding Functions

#### `rle_encode(data)`
Run-Length Encode data
```python
# Example
compressed = rle_encode(b"Hello World")
```

#### `rle_decode(bytestream, expected_bytes)`
Decode RLE-compressed data
```python
# Example
decoded, _ = rle_decode(compressed_data, 1000)
```

#### `dot_size_encode(bytestream, bit_length)`
Encode data using dot size transformation
```python
# Example
encoded = dot_size_encode(image_data, 3)  # Large dots
```

#### `dot_size_decode(encoded)`
Decode dot size transformed data
```python
# Example
decoded, counts = dot_size_decode(encoded_data)
```

### Decoding Function

#### `decode_escp2_commands(data, show_image=False, dump_image=False)`
Decode ESC/P2 commands to human-readable format
```python
# Example
with open("printjob.escp2", "rb") as f:
    decoded = decode_escp2_commands(f.read(), show_image=True)
```

## Dependencies

- Pillow (PIL fork)
- hexdump2 (for decoding)
- pyprintlpr (for direct printing)

## Supported Printers

The module is compatible with Epson printers supporting ESC/P2 protocol, including:
- XP Series (XP-200, XP-205, XP-410, etc.)
- Workforce Series
- Expression Series
- Most modern Epson inkjet printers

---

# Notes

## Printing raster graphics

In inkjet printers such as the Epson XP-410, when printing raster graphics with the **ESC i** (*Transfer Raster Image*, ESC/P2) command:

* **Horizontal limit:** The maximum number of pixels per row is determined by the page width; the default horizontal resolution is **360 dpi**.
* **Vertical limit:** The maximum number of rows per ESC i command is constrained by the printhead’s nozzle layout.

The printhead ejects each color from its own fixed nozzle bank as the carriage passes. These nozzle banks are **vertically offset** in the paper-feed direction, so data sent for different colors at the *same logical position* will appear at different vertical positions on paper.

**Maximum rows per block:**

* Monochrome mode (black only): **180 rows** per ESC i block.
* Color mode: **60 rows** per ESC i block for each CMY color.

On the XP-410, the **yellow nozzles** define the *vertical baseline*. The other colors are offset downward:

* **Yellow** — prints at the commanded vertical position `α`.
* **Magenta** — prints \~**60/180 inch** (8.47 mm) lower than yellow.
* **Cyan** — prints \~**120/180 inch** (16.93 mm) lower than yellow.

This means that even if you send all three colors at the same absolute position, the printed result will be vertically staggered according to the head geometry.

**Example sequence:**

```
1B 28 4B 02 00 00 00           ; ESC (K — select default (color) mode
1B 28 24 04 00 80 06 00 00     ; ESC ($ — set absolute horizontal position ext (1664 = 29.35 mm)
1B 69 01 01 02 50 00 2A 00     ; ESC i — Magenta, RLE, 2 bpp, 80 bytes/row, 42 rows
1B 28 24 04 00 80 06 00 00     ; ESC ($ — same horizontal position
1B 69 04 01 02 50 00 2A 00     ; ESC i — Yellow, same size
1B 28 24 04 00 80 06 00 00     ; ESC ($ — same horizontal position
1B 69 02 01 02 50 00 2A 00     ; ESC i — Cyan, same size
```

**Printed result:**

1. Yellow block (at position `α`)
2. Magenta block **below** yellow by \~60/180″
3. Cyan block **below** magenta by \~60/180″

This vertical offset is a fixed physical property of the XP-410’s head design and must be compensated for in software.

## Showing the image corresponding to a printed page

The code is currently able to show the single images produced by each "ESC i (Transfer Raster Image)" and "ESC ." ESC/P2 commands and it is not able to accumulate these individual raster image tiles into a complete image page, consolidated as far as a form feed (FF) is encountered (which signals the end of the page).

This note iss for possible future developments.

The horizontal and vertical position before each Transfer Raster Image command shall determine the places where the single tiles have to be placed into the whole page image, which shall include the composition of all tiles.

Consider also the following:

- "ESC ." also increments the X printing position relative to the current X printing position by the amount: (256 x nH + nL) x h/3600 x 25.4mm. If this command specifies an X position in the non-printable area (right margin), the right margin position is automatically reset to the X value of the new printing position.

- "ESC i" does not increment the printing position.

- "1BH, 19H, n" sets page position to origin

- "FF" sets page position to origin

- "ESC (G" The printing position in the X direction is set to the origin upon the X axis.

- "ESC (c": The printing position in the Y direction is shifted to the origin of the position management coordinate system. At this time, the origin on the X axis is not changed.

- The relative vertical position setting value, the non-printable area, and the printing position in the Y direction are reset to their initial states by the "ESC @" and "ESC (G" commands.

- "ESC . 2": the printing position in the X direction is set to the origin upon the X axis.

To select showing the page image, add and use the "--show-page" command line option.
