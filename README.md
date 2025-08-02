# **epson_escp2**

*A Python module to generate raw ESC/P2 sequences from structured text or images, including markdown-style formatting, tables, and varying font styles.*

The text or the image is converted into the "Transfer Raster image" ESC/P2 command `ESC i r c b nL nH mL mH d1......dk` and printed as monochrome B/W bitmap in draft/economy mode.

Supported modes:

- non compressed or "Run Length Encoding" compression method
- bit length 1, 2, or 3 (small dot: 01, medium dot: 10, large dot 03)

---

Epson’s **ESC/P2** is Epson’s extended page description language that enables advanced font manipulation, raster graphics, and layout control on Inkjet printers.

## Installation

```bash
pip install epson_escp2
````

## Usage

```
usage: python -m epson_escp2 [-h] [--dump] [--preview] [--version] [--compress] [--max-block-h] [--bit-length {1,2,3}]
                   [--threshold THRESHOLD] [--font-size FONT_SIZE] [--padding PADDING] [--line-spacing LINE_SPACING]
                   [--host HOST] [--port PORT] [--queue QUEUE] [--label LABEL]
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

## Module API

### TextToImageConverter

Convert plain text with lightweight Markdown formatting into a PIL image suitable for ESC/P2 raster printing.

```python
from simple_escp2 import TextToImageConverter
```

#### Constructor

```python
TextToImageConverter(
    font_path: Optional[str] = None,
    font_bold_path: Optional[str] = None,
    font_mono_path: Optional[str] = None,
    font_mono_bold_path: Optional[str] = None,
    font_size: int = 20
)
```

* **font\_path** / **font\_bold\_path**: TTF path for proportional normal/bold.
* **font\_mono\_path** / **font\_mono\_bold\_path**: TTF path for monospace normal/bold.
* **font\_size**: pixel height of glyphs.

#### Methods

* **convert\_to\_image**

  ```python
  convert_to_image(
      text: str,
      h_dpi: int = 360,
      v_dpi: int = 120,
      width: int = 2768,
      height: int = 1250,
      threshold: int = -1,
      line_spacing: int = 4,
      padding: int = 10,
      bg_color: str = "black",
      text_color: str = "white"
  ) → PIL.Image.Image
  ```

  * Renders `text` into a monochrome or grayscale PIL image.
  * Supports headings, bullets, tables (`| a | b |`), inline code (`` `code` ``), bold (`**bold**`), underline (`__u__`), monospace (` `code` `), and triple-backtick bold-monospace.
  * Returns an image whose dimensions match the DPI/width/height parameters, ready for rasterization.

* **get\_system\_fonts**

  ```python
  get_system_fonts(size: int = 12) → Dict[str, ImageFont.FreeTypeFont]
  ```

  * Probes OS font directories for fallback fonts.
  * Returns a dict: `{ 'prop_normal', 'prop_bold', 'mono_normal', 'mono_bold' }`.

* **get\_fonts**

  ```python
  get_fonts(size: int = 12) → Tuple[ImageFont, ImageFont, ImageFont, ImageFont]
  ```

  * Simplified return of `(prop_normal, prop_bold, mono_normal, mono_bold)`.

---

### EpsonEscp2

Low-level ESC/P2 generator: takes a PIL image, encodes it into Epson “Transfer Raster Image” blocks, and wraps it in Remote Mode print commands.

```python
from simple_escp2 import EpsonEscp2
```

#### Constructor

```python
EpsonEscp2(
    color: int = 0,
    bit_length: int = 3,
    compress: bool = True,
    max_block_h: int = 128
)
```

* **color**: raster plane (0 = mono).
* **bit\_length**: 1 → 1-bit, 2 → 2-bit, 3 → 3-bit depth.
* **compress**: enable RLE compression.
* **max\_block\_h**: max rows per raster chunk.

Raises `ValueError` if `bit_length` ∉ {1,2,3}.

#### Methods

* **remote\_cmd**

  ```python
  remote_cmd(cmd: str, args: bytes) → bytes
  ```

  Build a two-char Remote Mode command header.

* **set\_timer**

  ```python
  set_timer() → bytes
  ```

  Pack current system clock into Epson TI (time-sync) command.

* **rle\_encode** / **rle\_decode**

  ```python
  rle_encode(data: Union[bytes,str,list]) → bytes
  rle_decode(bytestream: Union[bytes,str,list]) → bytes
  ```

  Encode/decode according to Epson’s RLE spec (counters 0–127 literal, 128–255 repeats).

* **dot\_size** / **decode\_dot\_size**

  ```python
  dot_size(bytestream: bytes) → bytes
  decode_dot_size(encoded: bytes) → bytes
  ```

  Map each 4-bit nibble to an 8-bit pattern according to `bit_length`.

* **image\_to\_tri**

  ```python
  image_to_tri(image: PIL.Image.Image) → bytes
  ```

  Slice the PIL image into `max_block_h`-row chunks, apply `dot_size`, optional RLE, and prepend `ESC i` headers.

* **tri\_to\_escp2**

  ```python
  tri_to_escp2(tri: bytes) → bytes
  ```

  Wrap raw `tri` with Remote-Mode initialization, graphics mode commands, page length/format, print-method selections, job start/end, and flush sequences.

* **test\_color\_pattern**

  ```python
  test_color_pattern(get_pattern=False, use_black23=False) → bytes
  ```

* **clean\_nozzles**

  ```python
  clean_nozzles(group_index, power_clean=False, has_alt_mode=None) → bytes
  ```

* **check\_nozzles**

  ```python
  check_nozzles(type=0) → bytes
  ```

---

## Example

```python
from epson_escp2 import TextToImageConverter, EpsonEscp2
from pyprintlpr import LprClient

# Render text → PIL image
conv = TextToImageConverter(font_size=14)
img = conv.convert_to_image("**Hello** - `ESC/P2` demo", padding=20)

# Encode to Epson TRI blocks
epson = EpsonEscp2(bit_length=3, compress=True)
tri = epson.image_to_tri(img)

# Wrap in ESC/P2 remote-mode packet
packet = epson.tri_to_escp2(tri)

# Send to printer via LPR
with LprClient("192.168.1.100", port="LPR", queue="PASSTHRU", label="Doc") as lpr:
    lpr.send(packet)
```
