import os
import sys
import struct
import datetime
from typing import List, Tuple, Union, Optional
from PIL import Image, ImageDraw, ImageFont, ImageOps
try:
    from .tri_attr import rle_encode, dot_size_encode
except ImportError:
    from tri_attr import rle_encode, dot_size_encode


class TextToImageConverter:
    """Convert text with markdown-like formatting to PIL images and ESC/P2 raster data."""

    def __init__(
        self,
        font_path: Optional[str] = None,
        font_bold_path: Optional[str] = None, 
        font_mono_path: Optional[str] = None,
        font_mono_bold_path: Optional[str] = None,
        font_size: int = 20
    ):
        """
        Initialize the converter with font paths and size.
        
        Args:
            font_path: Path to regular font (if None, uses PIL default)
            font_bold_path: Path to bold font (if None, uses PIL default)
            font_mono_path: Path to monospace font (if None, uses PIL default)
            font_mono_bold_path: Path to monospace bold font (if None, uses PIL default)
            font_size: Font size in pixels
        """
        self.font_size = font_size
        self._load_fonts(
            font_path,
            font_bold_path,
            font_mono_path,
            font_mono_bold_path
        )
        self._calculate_baseline_offsets()
    
    def _load_fonts(
        self,
        font_path: Optional[str],
        font_bold_path: Optional[str], 
        font_mono_path: Optional[str],
        font_mono_bold_path: Optional[str]
    ):
        """Load fonts with fallbacks to cross-platform defaults."""

        prop_normal, prop_bold, mono_normal, mono_bold = self.get_fonts(self.font_size)
        
        self.font = prop_normal
        if font_path and os.path.exists(font_path):
            try:
                self.font = ImageFont.truetype(font_path, self.font_size, encoding='utf-8')
            except OSError:
                pass
        
        self.font_bold = prop_bold
        if font_bold_path and os.path.exists(font_bold_path):
            try:
                self.font_bold = ImageFont.truetype(font_bold_path, self.font_size, encoding='utf-8')
            except OSError:
                pass
        
        self.font_mono = mono_normal
        if font_mono_path and os.path.exists(font_mono_path):
            try:
                self.font_mono = ImageFont.truetype(font_mono_path, self.font_size, encoding='utf-8')
            except OSError:
                pass

        self.font_mono_bold = mono_bold
        if font_mono_bold_path and os.path.exists(font_mono_bold_path):
            try:
                self.font_mono_bold = ImageFont.truetype(font_mono_bold_path, self.font_size, encoding='utf-8')
            except OSError:
                pass

    def _calculate_baseline_offsets(self):
        """Calculate baseline offsets to align all fonts on the same baseline."""
        # Use a reference character to measure baselines
        ref_char = "Ag"  # Character with both ascender and descender
        
        # Get baseline metrics for each font
        fonts = {
            'normal': self.font,
            'bold': self.font_bold,
            'mono': self.font_mono,
            'mono_bold': self.font_mono_bold
        }
        
        baselines = {}
        max_ascent = 0
        
        for name, font in fonts.items():
            try:
                bbox = font.getbbox(ref_char)
                # bbox is (left, top, right, bottom)
                # top is negative for ascenders, bottom is positive for descenders
                ascent = abs(bbox[1])  # Distance from baseline to top
                descent = bbox[3]      # Distance from baseline to bottom
                baselines[name] = {'ascent': ascent, 'descent': descent}
                max_ascent = max(max_ascent, ascent)
            except:
                # Fallback for fonts that don't support getbbox properly
                baselines[name] = {'ascent': self.font_size * 0.8, 'descent': self.font_size * 0.2}
                max_ascent = max(max_ascent, self.font_size * 0.8)
        
        # Calculate offsets to align all fonts to the same baseline
        self.baseline_offsets = {}
        for name, metrics in baselines.items():
            # Offset = difference between this font's ascent and the maximum ascent
            self.baseline_offsets[name] = max_ascent - metrics['ascent']
            if name.startswith("mono"):
                self.baseline_offsets[name] = max_ascent - metrics['ascent'] + 1
    
    def _get_font_and_offset(self, font_type: str) -> Tuple[ImageFont.FreeTypeFont, int]:
        """Get font and its baseline offset."""
        font_map = {
            'normal': (self.font, 'normal'),
            'bold': (self.font_bold, 'bold'),
            'mono': (self.font_mono, 'mono'),
            'mono_bold': (self.font_mono_bold, 'mono_bold')
        }
        
        font, offset_key = font_map.get(font_type, (self.font, 'normal'))
        offset = self.baseline_offsets.get(offset_key, 0)
        return font, offset
    
    def _parse_text_blocks(self, text: str) -> List[Tuple[str, List[str]]]:
        """Parse text into blocks: normal text vs. tables."""
        lines = text.splitlines()
        blocks = []
        current_block = []
        in_table = False
        
        for line in lines + [""]:  # Add empty line to flush last block
            is_table_line = "|" in line and line.strip()
            
            if is_table_line and not in_table:
                # Start of table - save current text block
                if current_block:
                    blocks.append(("text", current_block))
                    current_block = []
                in_table = True
                current_block.append(line)
            elif not is_table_line and in_table:
                # End of table - save table block
                blocks.append(("table", current_block))
                current_block = []
                in_table = False
                current_block.append(line)
            else:
                current_block.append(line)
        
        # Add final block if not empty
        if current_block:
            block_type = "table" if in_table else "text"
            blocks.append((block_type, current_block))
        
        return blocks
    
    def _parse_table(self, table_lines: List[str]) -> Tuple[Optional[List[str]], List[List[str]]]:
        """Parse table lines into header and data rows."""
        rows = []
        for line in table_lines:
            if line.strip():
                # Remove leading/trailing | and split
                clean_line = line.strip().strip("|")
                cells = [cell.strip() for cell in clean_line.split("|")]
                rows.append(cells)
        
        if len(rows) < 2:
            return None, rows
        
        # Check if second row is alignment row (contains only -, :, and spaces)
        alignment_chars = set('-: ')
        is_alignment_row = all(set(cell).issubset(alignment_chars) for cell in rows[1])
        
        if is_alignment_row:
            return rows[0], rows[2:]  # Header, data (skip alignment row)
        else:
            return None, rows  # No header, all data
    
    def _parse_text_segments(self, text: str) -> List[Tuple[str, str, bool]]:
        """Parse text into segments with formatting (bold, underline, fixed-width, bold fixed-width)."""
        segments = []
        i = 0
        
        while i < len(text):
            if text.startswith("```", i):
                # Bold fixed-width text (triple backticks)
                end_pos = text.find("```", i + 3)
                if end_pos != -1:
                    segment = text[i + 3:end_pos]
                    segments.append((segment, 'mono_bold', False))
                    i = end_pos + 3
                else:
                    # No closing ```, treat as literal
                    segment = text[i + 3:]
                    segments.append((segment, 'mono_bold', False))
                    i = len(text)
            elif text.startswith("``", i):
                # Fixed-width text
                end_pos = text.find("``", i + 2)
                if end_pos != -1:
                    segment = text[i + 2:end_pos]
                    segments.append((segment, 'mono', False))
                    i = end_pos + 2
                else:
                    # No closing ``, treat as literal
                    segment = text[i + 2:]
                    segments.append((segment, 'mono', False))
                    i = len(text)
            elif text.startswith("**", i):
                # Bold text
                end_pos = text.find("**", i + 2)
                if end_pos != -1:
                    segment = text[i + 2:end_pos]
                    segments.append((segment, 'bold', False))
                    i = end_pos + 2
                else:
                    # No closing **, treat as literal
                    segment = text[i + 2:]
                    segments.append((segment, 'bold', False))
                    i = len(text)
            elif text.startswith("__", i):
                # Underlined text
                end_pos = text.find("__", i + 2)
                if end_pos != -1:
                    segment = text[i + 2:end_pos]
                    segments.append((segment, 'normal', True))
                    i = end_pos + 2
                else:
                    # No closing __, treat as literal
                    segment = text[i + 2:]
                    segments.append((segment, 'normal', True))
                    i = len(text)
            elif text.startswith("*", i) and not text.startswith("**", i):
                # Single asterisk for underline (alternative syntax)
                end_pos = text.find("*", i + 1)
                if end_pos != -1:
                    segment = text[i + 1:end_pos]
                    segments.append((segment, 'normal', True))
                    i = end_pos + 1
                else:
                    # No closing *, treat as literal
                    segment = text[i + 1:]
                    segments.append((segment, 'normal', True))
                    i = len(text)
            else:
                # Find next formatting marker
                next_markers = []
                for marker in ("```", "``", "**", "__", "*"):
                    pos = text.find(marker, i)
                    if pos >= 0:
                        next_markers.append(pos)
                
                if next_markers:
                    next_pos = min(next_markers)
                    segment = text[i:next_pos]
                    if segment:  # Only add non-empty segments
                        segments.append((segment, 'normal', False))
                    i = next_pos
                else:
                    # No more markers, take rest of text
                    segment = text[i:]
                    if segment:  # Only add non-empty segments
                        segments.append((segment, 'normal', False))
                    i = len(text)
        
        return segments
    
    def _calculate_table_column_widths(self, header: Optional[List[str]], 
                                     data: List[List[str]], draw: ImageDraw.Draw) -> List[int]:
        """Calculate the width of each table column considering formatting."""
        if not data and not header:
            return []
        
        # Determine number of columns
        max_cols = 0
        if header:
            max_cols = max(max_cols, len(header))
        for row in data:
            max_cols = max(max_cols, len(row))
        
        col_widths = [0] * max_cols
        
        # Measure header
        if header:
            for j, cell in enumerate(header):
                if j < len(col_widths):
                    width = self._measure_formatted_text(cell, draw)
                    col_widths[j] = max(col_widths[j], width)
        
        # Measure data rows
        for row in data:
            for j, cell in enumerate(row):
                if j < len(col_widths):
                    width = self._measure_formatted_text(cell.strip(), draw)
                    col_widths[j] = max(col_widths[j], width)
        
        return col_widths
    
    def _measure_formatted_text(self, text: str, draw: ImageDraw.Draw) -> int:
        """Measure the width of text considering formatting."""
        segments = self._parse_text_segments(text)
        total_width = 0
        for segment_text, font_type, _ in segments:
            if segment_text:
                font, _ = self._get_font_and_offset(font_type)
                total_width += draw.textlength(segment_text, font)
        return total_width

    def preview(
        self,
        image: Image.Image,
        h_dpi: int = 360,
        v_dpi: int = 120,
    ):
        width, height = image.size
        showimage = image.resize(
            (width, int(height*h_dpi/v_dpi)), resample=Image.NEAREST
        )
        showimage = ImageOps.invert(showimage)
        showimage.show()

    def convert_to_image(
        self,
        text: str,
        h_dpi: int = 360,
        v_dpi: int = 120,
        width: int = 2768,  # 2768 dots / h_dpi * 2,54 = 19,5 cm
        height: int = 1250,  # 1250 dots / v_dpi * 2,54 = 26,5 cm
        threshold: int = -1,
        line_spacing: int = 4,
        padding: int = 10,
        bg_color: str = "black", 
        text_color: str = "white",
    ) -> Image.Image:
        """
        Convert text to PIL Image with formatting support.

        A4: 210 mm x 297 mm = 2976 x 4209 dots @ 360dpi
        Letter: 8.5in. x 11in. = 21,59 cm x 27,94 cm = 3060 x 3960 dots @ 360dpi
        Current format: 19,5 cm x 26,5 cm ab. = 2768 x 3750 dots @ 360dpi, 2768 x 1250 @ 360x180dpi
        """

        # Create temporary image for measurements
        temp_img = Image.new("RGB", (1, 1), bg_color)
        draw = ImageDraw.Draw(temp_img)
        
        # Parse text into blocks
        blocks = self._parse_text_blocks(text)
        
        # Process blocks into renderable items
        render_items = []
        for block_type, content in blocks:
            if block_type == "text":
                for line in content:
                    render_items.append(("text", line))
            else:  # table
                header, data = self._parse_table(content)
                col_widths = self._calculate_table_column_widths(
                    header, data, draw
                )
                render_items.append(("table", header, data, col_widths))

        if threshold == -1:
            image = Image.new(
                '1', (int(width * v_dpi / h_dpi), height), color=bg_color
            )
        else:
            image = Image.new(
                'L', (int(width * v_dpi / h_dpi), height), color=bg_color
            )

        draw = ImageDraw.Draw(image)

        """
        x = 20  # Vertical test line at horizontal position 20
        draw.line([(x, 0), (x, height-1)], fill="white")
        """
        
        # Render content
        y = padding
        for item in render_items:
            if item[0] == "text":
                line = item[1]
        # Render content
        y = padding
        page_width = int(width * v_dpi / h_dpi) - padding * 2
        for item in render_items:
            if item[0] == "text":
                line = item[1]
                indent_level = len(line) - len(line.lstrip(" \t"))
                clean_line = line.strip()
                prefix = ""
                if clean_line.startswith(("-", "*")):
                    prefix = clean_line[0] + " "
                    clean_line = clean_line[1:].lstrip()
                x_base = padding + (indent_level * self.font_size // 2)
                # Prepare segments (prefix + formatted)
                segments = []
                if prefix:
                    segments.append((prefix, 'normal', False))
                segments.extend(self._parse_text_segments(clean_line))
                # Wrap segments into lines
                lines = []
                current_line = []
                current_width = 0
                for segment_text, font_type, underline in segments:
                    if not segment_text:
                        continue
                    font, offset = self._get_font_and_offset(font_type)
                    words = segment_text.split(' ')
                    for i, word in enumerate(words):
                        word_text = word
                        if i < len(words) - 1:
                            word_text += ' '
                        word_width = draw.textlength(word_text, font)
                        if current_width + word_width > page_width and current_line:
                            lines.append(current_line)
                            current_line = []
                            current_width = 0
                        current_line.append((word_text, font_type, underline))
                        current_width += word_width
                if current_line:
                    lines.append(current_line)
                # Draw wrapped lines
                for line_segments in lines:
                    x = x_base
                    for seg_text, seg_font_type, seg_underline in line_segments:
                        seg_font, seg_offset = self._get_font_and_offset(seg_font_type)
                        draw.text((x, y + seg_offset), seg_text, font=seg_font, fill=text_color)
                        seg_width = draw.textlength(seg_text, seg_font)
                        if seg_underline:
                            bbox = seg_font.getbbox(seg_text)
                            underline_y = y + seg_offset + bbox[3]
                            draw.line((x, underline_y, x + seg_width, underline_y), fill=text_color)
                        x += seg_width
                    y += self.font_size + line_spacing
            else:  # table
                _, header, data, col_widths = item
                
                # Draw header if present
                if header:
                    x = padding
                    for j, cell in enumerate(header):
                        if j < len(col_widths):
                            self._draw_formatted_text(draw, cell, x, y, text_color)
                            x += col_widths[j] + padding
                    y += self.font_size + line_spacing
                    
                    # Draw header underline
                    line_end_x = padding + sum(col_widths) + len(col_widths) * padding - padding
                    draw.line((padding, y - line_spacing//2, line_end_x, y - line_spacing//2), 
                            fill=text_color)
                    y += line_spacing
                
                # Draw data rows
                for row in data:
                    x = padding
                    for j, cell in enumerate(row):
                        if j < len(col_widths):
                            self._draw_formatted_text(draw, cell.strip(), x, y, text_color)
                            x += col_widths[j] + padding
                    y += self.font_size + line_spacing

        if threshold > -1:
            image = image.point(lambda x: 255 if x < threshold else 0, mode='1')

        image = image.resize(  # Resize width to fit the h_dpi x v_dpi dpi proportion
            (width, height), resample=Image.NEAREST
        )
        return image
    
    def _draw_formatted_text(self, draw: ImageDraw.Draw, text: str, x: int, y: int, color: str):
        """Draw text with formatting at the specified position."""
        segments = self._parse_text_segments(text)
        current_x = x
        for segment_text, font_type, underline in segments:
            if segment_text:
                font, offset = self._get_font_and_offset(font_type)
                draw.text((current_x, y + offset), segment_text, font=font, fill=color)
                segment_width = draw.textlength(segment_text, font)
                
                if underline:
                    bbox = font.getbbox(segment_text)
                    underline_y = y + offset + bbox[3]
                    draw.line((current_x, underline_y, current_x + segment_width, underline_y), 
                            fill=color)
                
                current_x += segment_width


    def get_system_fonts(self, size=12):
        """
        Get system fonts for all combinations: proportional/monospace × normal/bold
        Returns a dictionary with keys: 'prop_normal', 'prop_bold', 'mono_normal', 'mono_bold'
        """
        
        # Font definitions by platform and style
        font_configs = {
            'proportional': {
                'normal': {
                    'win32': ['segoeui.ttf', 'arial.ttf', 'calibri.ttf'],
                    'darwin': ['Helvetica', 'Arial', 'Lucida Grande'],
                    'linux': ['DejaVuSans.ttf', 'LiberationSans-Regular.ttf', 'arial.ttf']
                },
                'bold': {
                    'win32': ['segoeuib.ttf', 'arialbd.ttf', 'calibrib.ttf'],
                    'darwin': ['Helvetica-Bold', 'Arial-Bold', 'Lucida Grande Bold'],
                    'linux': ['DejaVuSans-Bold.ttf', 'LiberationSans-Bold.ttf', 'arialbd.ttf']
                }
            },
            'monospace': {
                'normal': {
                    'win32': ['consola.ttf', 'cour.ttf', 'lucon.ttf'],
                    'darwin': ['Menlo-Regular', 'Monaco', 'Courier New'],
                    'linux': ['DejaVuSansMono.ttf', 'LiberationMono-Regular.ttf', 'cour.ttf']
                },
                'bold': {
                    'win32': ['consolab.ttf', 'courbd.ttf', 'lucon.ttf'],
                    'darwin': ['Menlo-Bold', 'Monaco-Bold', 'Courier New Bold'],
                    'linux': ['DejaVuSansMono-Bold.ttf', 'LiberationMono-Bold.ttf', 'courbd.ttf']
                }
            }
        }
        
        def load_font(font_list, size):
            """Try to load a font from the given list"""
            platform = sys.platform
            
            # Try loading by font name first (works on macOS and some Linux)
            for font_name in font_list:
                try:
                    return ImageFont.truetype(font_name, size, encoding='utf-8')
                except (OSError, IOError):
                    continue
            
            # Platform-specific font directory search
            font_dirs = []
            if platform == 'win32':
                font_dirs = [
                    os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts'),
                    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Windows', 'Fonts')
                ]
            elif platform == 'darwin':
                font_dirs = [
                    '/System/Library/Fonts',
                    '/Library/Fonts',
                    os.path.expanduser('~/Library/Fonts')
                ]
            else:  # Linux and other Unix-like
                font_dirs = [
                    '/usr/share/fonts',
                    '/usr/local/share/fonts',
                    os.path.expanduser('~/.fonts'),
                    os.path.expanduser('~/.local/share/fonts'),
                    '/usr/share/fonts/truetype',
                    '/usr/share/fonts/TTF'
                ]
            
            # Search in font directories
            for font_dir in font_dirs:
                if not os.path.exists(font_dir):
                    continue
                    
                for font_name in font_list:
                    # Try exact filename
                    font_path = os.path.join(font_dir, font_name)
                    if os.path.exists(font_path):
                        try:
                            return ImageFont.truetype(font_path, size, encoding='utf-8')
                        except (OSError, IOError):
                            continue
                    
                    # Try recursive search for Linux
                    if platform.startswith('linux'):
                        for root, dirs, files in os.walk(font_dir):
                            if font_name.lower() in [f.lower() for f in files]:
                                font_path = os.path.join(root, font_name)
                                try:
                                    return ImageFont.truetype(font_path, size, encoding='utf-8')
                                except (OSError, IOError):
                                    continue
            
            # Final fallback
            return ImageFont.load_default()
        
        # Get current platform
        platform = sys.platform
        if platform.startswith('linux'):
            platform = 'linux'
        
        # Load all font combinations
        results = {}
        
        for style in ['proportional', 'monospace']:
            for weight in ['normal', 'bold']:
                font_list = font_configs[style][weight].get(platform, [])
                
                # Add fallbacks from other platforms
                for other_platform in font_configs[style][weight]:
                    if other_platform != platform:
                        font_list.extend(font_configs[style][weight][other_platform])
                
                key = f"{style[:4]}_{weight}"  # 'prop_normal', 'prop_bold', etc.
                results[key] = load_font(font_list, size)
        
        return results

    def get_fonts(self, size=12):
        """
        Simplified interface - returns fonts as individual variables
        Returns: (prop_normal, prop_bold, mono_normal, mono_bold)
        """
        fonts = self.get_system_fonts(size)
        return (
            fonts['prop_normal'],
            fonts['prop_bold'], 
            fonts['mono_normal'],
            fonts['mono_bold']
        )


class EpsonEscp2:
    """Generate ESC/P2 sequences from text or image."""
    
    def __init__(
        self,
        color: int = 0,
        bit_length: int = 3,  # can be 1, small, 2, middle, 3, large
        compress: bool = True,
        max_block_h: int = 128,  # also 60 is good
    ):
        if bit_length not in (1, 2, 3):
            raise ValueError("bit_length must be 1, 2, or 3")
        self.color = color
        self.bit_length = bit_length
        self.compress = compress
        self.max_block_h = max_block_h

        # Define general printer sequences
        self.LF = b'\n'     # 0x0A
        self.SP = b' '      # 0x20 (space)
        self.NUL = b'\x00'  # 0x00 (null)
        self.FF = b'\x0c'   # flush buffer
        self.INITIALIZE_PRINTER = b'\x1b@'

        # Define specific Epson sequences
        self.EXIT_PACKET_MODE = b'\x00\x00\x00\x1b\x01@EJL 1284.4\n@EJL     \n'
        self.ENTER_D4 = b'\x00\x00\x00\x1b\x01@EJL 1284.4\n@EJL\n@EJL\n'
        self.REMOTE_MODE = b'\x1b' + self.remote_cmd("(R", b'\x00REMOTE1')  # ESC "(R" 08H 00H 00H "REMOTE1"
        self.ENTER_REMOTE_MODE = (
            self.INITIALIZE_PRINTER +
            self.INITIALIZE_PRINTER +
            self.REMOTE_MODE
        )
        self.EXIT_REMOTE_MODE = b'\x1b\x00\x00\x00'
        self.JOB_START = self.remote_cmd("JS", b'\x00\x00\x00\x00')
        self.JOB_END = self.remote_cmd("JE", b'\x00')
        self.PRINT_NOZZLE_CHECK = self.remote_cmd("NC", b'\x00\x00')
        self.VERSION_INFORMATION = self.remote_cmd("VI", b'\x00\x00')
        self.LD = self.remote_cmd("LD", b'')

    def remote_cmd(self, cmd: str, args: bytes) -> bytes:
        """Generate a Remote Mode command."""
        if len(cmd) != 2:
            raise ValueError("command should be exactly 2 characters")
        return cmd.encode() + struct.pack('<H', len(args)) + args

    def set_timer(self) -> bytes:
        """Synchronize RTC by setting the current time with TI"""
        now = datetime.datetime.now()
        t_data = b'\x00'
        t_data += now.year.to_bytes(2, 'big')  # Year
        t_data += bytes([now.month, now.day, now.hour, now.minute, now.second])
        return self.remote_cmd("TI", t_data)

    def image_to_tri(
        self,
        image: Image.Image,
    ) -> bytes:
        """
        Convert a PIL image into a sequence of Epson "Transfer Raster image" (ESC i)
        raster commands and raster data, chunking the image into blocks of up to
        self.max_block_h rows.

        Returns full sequence of (ESC i commands + raster data): bytes
        """
        # Convert to bytestream
        width, height = image.size
        if width % 8 > 0:
            raise ValueError("width parameter is not a multiple of 8")

        bytestream = image.tobytes()

        if self.bit_length:
            bytestream = dot_size_encode(bytestream, self.bit_length)
            bytes_per_line = (width + 7) // 8 * 2
        else:
            bytes_per_line = (width + 7) // 8

        # Compute bytes per scanline (after bit_length expansion):
        bytes_per_line = ((width * 2 if self.bit_length else width) + 7) // 8

        output = bytearray()

        total_rows = height
        for y in range(0, total_rows, self.max_block_h):
            block_h = min(self.max_block_h, total_rows - y)

            # header parameters:
            n = bytes_per_line
            nL, nH = n & 0xFF, (n >> 8) & 0xFF
            mL, mH = block_h & 0xFF, (block_h >> 8) & 0xFF

            v_pos = "1b 28 76 04 00 " + self.max_block_h.to_bytes(4, 'little').hex(" ")  # Set relative vertical print position(extended) - ESC (v nL nH m1 m2 m3 m4
            if not output:
                v_pos = ""
            h_pos = "1b 28 24 04 00 " + int(16).to_bytes(4, 'little').hex(" ")  # Set absolute horizontal print position ESC ( $ nL nH m1 m2 m3 m4

            header = bytes([
                0x1B, 0x69,           # ESC i
                self.color,           # r
                0x01 if self.compress else 0x00,  # c
                0x02 if self.bit_length else 0x01, # b
                nL, nH, mL, mH        # nL/nH, mL/mH
            ])

            # slice out exactly block_h * bytes_per_line bytes from bytestream:
            start = y * bytes_per_line
            end = start + block_h * bytes_per_line
            block_data = bytestream[start:end]
            if block_data == b'\x00' * len(block_data):
                continue

            if self.compress:
                block_data = rle_encode(block_data)

            output += bytes.fromhex(v_pos + h_pos) + header + bytes(block_data)

        return bytes(output)

    def tri_to_escp2(
        self,
        tri,
        h_dpi: int = 360,
        v_dpi: int = 120,  # 360
        page: int = 120,  # 360
        unit: int = 1440,
        method_id: str = "11",  # "11" = Fast Eco bw only; "21" = normal
        dot_size_id: str = "11",  # 11 (fast eco)
    ):
        row_dots = int(
            21  # A4 (21 cm)
            / 2.54  # cm to in
            * page
        )
        page_dots = int(
            29.7  # A4 (29.7 cm)
            / 2.54  # cm to in
            * page
        )
        command_parts = (
            "1b 28 47 01 00 01"  # Select graphics mode
            + (
                "1b 28 55 05 00 "
                + f'{unit//page:02x} {unit//v_dpi:02x} {unit//h_dpi:02x} '
                + unit.to_bytes(2, byteorder='little').hex(" ")
            )  # ESC (U = Sets units P=12(120), V=12(120), H=4(360), mL mH - m=1440
            + "1b 55 00"  # selects bi-directional printing
            + "1b 28 69 01 00 00"  # no MicroWeave printing mode
            + (
                "1b 28 43 04 00 "
                + page_dots.to_bytes(4, byteorder='little', signed=True).hex(" ")
            )  # Set page length - ESC (C nL nH m1 m2 m3 m4
            #+ (
            #    "1b 28 63 08 00 "
            #    + int(-127).to_bytes(4, byteorder='little', signed=True).hex(" ")  # -381
            #    + int(1403).to_bytes(4, byteorder='little', signed=True).hex(" ")  # 4425
            #)  # Set page format (ext) - ESC (c nL nH t1 t2 t3 t4 b1 b2 b3 b4
            + (
                "1b 28 53 08 00 "
                + row_dots.to_bytes(4, byteorder='little', signed=True).hex(" ")
                + page_dots.to_bytes(4, byteorder='little', signed=True).hex(" ")
            )  # paper width=992 paper length=1403 -> 992 * 12 / 1440 *2,54 = 21cm A4 -> 1403 * 12 / 1440 * 2,54 = 29,7 cm = A4
            + "1b 28 4b 02 00 00 01"  # monochrome
            + "1b 28 4b 02 00 01 01"  # monochrome (2nd mode)
            + "1b 28 44 04 00 40 38 78 28"  # Set the raster image resolution; r=14400 v=120 h=40; Vertical resolution : 14400/120 = 120 dpi; Horizontal resolution = 14400/40=360 dpi
            + "1b 28 6d 01 00 " + method_id  # ESC (m - Set Print method ID 11 = Fast Eco bw only
            + "1b 28 65 02 00 00 " + dot_size_id  # Selects dot size ESC (e nL nH m d - n=2, d=11 (fast eco)
        )

        pattern = (
            self.INITIALIZE_PRINTER
            + self.REMOTE_MODE

            + self.EXIT_REMOTE_MODE
            + bytes.fromhex(command_parts)
            + tri

            + self.INITIALIZE_PRINTER
            + b'\r'
            + self.FF
            + self.INITIALIZE_PRINTER
            + self.REMOTE_MODE
            + self.LD
            + self.EXIT_REMOTE_MODE
            + self.INITIALIZE_PRINTER
            + self.REMOTE_MODE
            + self.LD
            + self.JOB_END
            + self.EXIT_REMOTE_MODE
        )
        return pattern


    def test_color_pattern(self, get_pattern=False, use_black23=False):
        """
        Print a one-page color test pattern at various quality levels via LPR.
        Optimized for XP-200, XP-205, XP-410 models.
        Returns True if the pattern was successfully printed (sending the
            print-out to the host by creating a LPR job), False otherwise.
        If get_pattern is True, returns the ESC/P2 command sequence for the
            patterns as bytes.
        """
        # Transfer Raster image commands (ESC i), Color, Run Length Encoding,
        # 2 bits per pixel, 4 pixels per byte, H: 80 bytes = 320 dots = h 2,26 cm @ 360dpi (320/360*2,54)
        TRI_BLACK = "1b6900010250008000"  # ESC i 0: Black, V: 128 dots/rows (monochrome, 180 dpi) = 128/120*2,54= v 2,7 cm
        TRI_MAGENTA = "1b6901010250002a00"  # ESC i 1: Magenta, V: 42 dots/rows (21 colored rows + 21 white rows)
        TRI_YELLOW = "1b6904010250002a00"  # ESC i 4: Yellow, V: 42 dots/rows dots
        TRI_CYAN = "1b6902010250002a00"  # ESC i 2: Cyan, V: 42 dots/rows
        TRI_BLACK2 = "1b6905010250002a00"  # ESC i 5: black2, V: 42 dots/rows
        TRI_BLACK3 = "1b6906010250002a00"  # ESC i 6: black3, V: 42 dots/rows

        SET_H_POS = "1b28240400"  # ESC ( $ = Set absolute horizontal print position, 4 bytes (n=length, first part)
        SET_V_POS = "1b28760400"  # ESC (v nL nH mL mH, 4 bytes (n=length, first part) = Set relative vertical print position

        USE_MONOCHROME = "1b284b02000001"  # ESC ( K = Monochrome Mode / Color Mode Selection, 01H: Monochrome mode
        USE_COLOR = "1b284b02000000"  # ESC ( K = Monochrome Mode / Color Mode Selection, 00H: Default mode (color mode)

        vsd_code = {  # Variable Sized Droplet
            -1: "00",  # VSD1 1bit or MC1-1 1 bit (for DOS)
            0: "10",  # Economy, Fast Draft
            1: "11",  # VSD1 2bit - fast eco, economy or speed/normal,
            2: "12",  # VSD2 2bit - fine/quality,
            3: "13",  # VSD3 2bit - super fine/high quality,
        }

        # Each sequence has 2 bits per pixel: 00=No, 01=Small, 10=Medium, 11=Large
        # Using Run-Length Encoding (RLE), d9 (217>127) means pattern repeated 257-217=40 times (160 dots per pattern).
        # These allow creating alternating patterns and are also used for solid patterns
        PATTERN_LARGE = "d9ff"  # ff = 11111111 = 11|11|11|11 = Large, 4 dots x 40
        PATTERN_MEDIUM = "d9aa"  # aa = 10101010 = 10|10|10|10 = Medium, 4 dots x 40
        PATTERN_SMALL = "d955"  # 55 = 01010101 = 01|01|01|01 = Small, 4 dots x 40
        PATTERN_NONE = "d900"  # 00 = 00000000 = 00|00|00|00 = No, 4 dots x 40
        PATTERN_NO_DOTS = PATTERN_NONE + PATTERN_NONE  # 320 dots, (4+4) dots x 40

        # Alternating patterns, 640 dots each = 2 hor. lines, one above the other
        PATTERN_LARGE_ALT = PATTERN_LARGE + PATTERN_NO_DOTS + PATTERN_LARGE
        PATTERN_MEDIUM_ALT = PATTERN_MEDIUM + PATTERN_NO_DOTS + PATTERN_MEDIUM
        PATTERN_SMALL_ALT = PATTERN_SMALL + PATTERN_NO_DOTS + PATTERN_SMALL

        # 6 vertically stacked printing segments, each of 4 hor stacked blocks
        printing_segments = [
            {
                "label_sequence": self.EXIT_REMOTE_MODE
                    + b'\r\n\r\nEconomy\r\n',
                "vsd": 0,
                "alternating_pattern": PATTERN_LARGE_ALT, 
                "solid_pattern": PATTERN_LARGE, 
            },
            {
                "label_sequence": self.INITIALIZE_PRINTER
                    + b"\r\n\n\n\nVSD1 - Medium dot size - Normal\r\n",
                "vsd": 1,
                "alternating_pattern": PATTERN_MEDIUM_ALT, 
                "solid_pattern": PATTERN_MEDIUM, 
            },
            {
                "label_sequence": self.INITIALIZE_PRINTER
                    + b"\r\n\n\n\nVSD2 - Medium dot size - Fine\r\n",
                "vsd": 2,
                "alternating_pattern": PATTERN_MEDIUM_ALT, 
                "solid_pattern": PATTERN_MEDIUM, 
            },
            {
                "label_sequence": self.INITIALIZE_PRINTER
                    + b"\r\n\n\n\nVSD3 - Large dot size - Super Fine\r\n",
                "vsd": 3,
                "alternating_pattern": PATTERN_LARGE_ALT, 
                "solid_pattern": PATTERN_LARGE, 
            },
            {
                "label_sequence": self.INITIALIZE_PRINTER
                    + b"\r\n\n\n\nVSD3 - Medium dot size - Super Fine\r\n",
                "vsd": 3,
                "alternating_pattern": PATTERN_MEDIUM_ALT, 
                "solid_pattern": PATTERN_MEDIUM, 
            },
            {
                "label_sequence": self.INITIALIZE_PRINTER
                    + b"\r\n\n\n\nVSD3 - Small dot size - Super Fine\r\n",
                "vsd": 3,
                "alternating_pattern": PATTERN_SMALL_ALT, 
                "solid_pattern": PATTERN_SMALL, 
            },
        ]

        def generate_patterns():
            """
            Generate the complete ESC/P2 command sequence for the patterns.
            """
            command_parts = []
            
            # Define the 4 hor stacked blocks for each vertically stacked segment 
            for segment in printing_segments:  # 6 printing segments

                # Label
                command_parts.append(segment["label_sequence"].hex())

                # Initialization
                command_parts.append(
                    "1b2847010001"  # Select graphics mode
                    + "1b28550500010101a005"  # ESC (U = Sets 360 DPI resolution, P=1, V=1, H=1, unit=1440
                    + "1b28430400c6410000"  # ESC (C = Configures page lenght, 16838 = 29.7cm
                    + "1b28630800ffffffffc6410000"  # ESC (c = Set page format, top=-1, bottom=16838
                    + "1b28530800822e0000c6410000"  # ESC (S = paper dimension specification, 11906x16838 = 21.0x29.7cm
                    + "1b28440400" + "68010301"  # ESC (D = raster image resolution, r=360, v=3, h=1; 360/3=120 dpi vertically, 360/1=360 dpi horizontally
                    + "1b2865020000" + vsd_code[segment["vsd"]]  # ESC (e = Select Ink Drop Size
                    + "1b5502"  # ESC U 02H = selects automatic printing direction control
                    + USE_MONOCHROME
                    + SET_V_POS + "00010000" # ESC (v = Set relative vertical print position, 256 units = 4.52 mm
                )

                # First block - black alternating
                command_parts.append(SET_H_POS + "00010000")  # ESC ( $ = Set absolute horizontal print position, 256 = 4,52 mm
                command_parts.append(TRI_BLACK)
                command_parts.append(segment["alternating_pattern"] * 64)  # 64 x 2 = 128 rows = v 2,7 cm

                # Second block - Yellow/Magenta/Cyan alternating
                # With colors, regardless the TRI sequence, yellow is hosted by the first 60 nozzle rows,
                # then magenta, then cyan. We are actually using 42 rows for each color.
                command_parts.append(USE_COLOR + SET_H_POS + "80060000")  # ESC ( $ = Set absolute horizontal print position, 1664 = 29,35 mm

                command_parts.append(TRI_MAGENTA)
                command_parts.append(segment["alternating_pattern"] * 21)  # 21 x (640 h dots per pattern / 320 h dots per line) = 42 v rows = v 0,88 cm

                command_parts.append(SET_H_POS + "80060000")  # ESC ( $ = Set absolute horizontal print position, 1664 = 29,35 mm        
                command_parts.append(TRI_YELLOW)
                command_parts.append(segment["alternating_pattern"] * 21)

                command_parts.append(SET_H_POS + "80060000")  # ESC ( $ = Set absolute horizontal print position, 1664 = 29,35 mm        
                command_parts.append(TRI_CYAN)
                command_parts.append(segment["alternating_pattern"] * 21)

                # Third block - Black solid
                command_parts.append(USE_MONOCHROME + SET_H_POS + "000c0000")  # ESC ( $ = Set absolute horizontal print position, 3072 = 54,35 mm
                
                command_parts.append(TRI_BLACK)
                command_parts.append(segment["solid_pattern"] * 256)  # 256 x (160 h dots per pattern / 320 h dots per line) = 128 v rows = v 2,7 cm

                # Fourth block - Yellow/Magenta/Cyan solid
                command_parts.append(USE_COLOR + SET_H_POS + "80110000")  # ESC ( $ = Set absolute horizontal print position, 4480 = 79 mm
                
                command_parts.append(TRI_MAGENTA)
                command_parts.append(segment["solid_pattern"] * 84) # 84 x (160 h dots per pattern / 320 h dots per line) = 42 v rows = v 0,88 cm

                command_parts.append(SET_H_POS + "80110000")  # ESC ( $ = Set absolute horizontal print position, 4480 = 79 mm        
                command_parts.append(TRI_YELLOW)
                command_parts.append(segment["solid_pattern"] * 84)

                command_parts.append(SET_H_POS + "80110000")  # ESC ( $ = Set absolute horizontal print position, 4480 = 79 mm        
                command_parts.append(TRI_CYAN)
                command_parts.append(segment["solid_pattern"] * 84)

                # Fifth block - Black/Black2/Black3 solid
                if use_black23:
                    command_parts.append(USE_COLOR + SET_H_POS + "00170000")  # ESC ( $ = Set absolute horizontal print position, 5888 = 103,8 mm
                    
                    command_parts.append(TRI_BLACK)
                    command_parts.append(segment["solid_pattern"] * 84)

                    command_parts.append(SET_H_POS + "00170000")  # ESC ( $ = Set absolute horizontal print position, 5888 = 103,8 mm
                    command_parts.append(TRI_BLACK2)
                    command_parts.append(segment["solid_pattern"] * 84)

                    command_parts.append(SET_H_POS + "00170000")  # ESC ( $ = Set absolute horizontal print position, 5888 = 103,8 mm
                    command_parts.append(TRI_BLACK3)
                    command_parts.append(segment["solid_pattern"] * 84)
                
                command_parts.append(SET_V_POS + "00030000")  # ESC (v = Set relative vertical print position
                # Relative vertical offset = 768 units = 13.54 mm

            command_parts.append(
                (
                    self.INITIALIZE_PRINTER
                    + b"\r\n\n\n\n"
                    + b"Epson Printer Configuration - Print Test Patterns"
                    + b"\r\n"
                ).hex()
            )
            # Join all command parts into final hex string
            return "".join(command_parts)

        if get_pattern:
            return bytes.fromhex(generate_patterns())
        pattern = (
            self.INITIALIZE_PRINTER
            + self.REMOTE_MODE
            + self.PRINT_NOZZLE_CHECK

            + bytes.fromhex(generate_patterns())

            + self.INITIALIZE_PRINTER
            + b'\r'
            + self.FF
            + self.INITIALIZE_PRINTER
            + self.REMOTE_MODE
            + self.LD
            + self.EXIT_REMOTE_MODE
            + self.INITIALIZE_PRINTER
            + self.REMOTE_MODE
            + self.LD
            + self.JOB_END
            + self.EXIT_REMOTE_MODE
        )

        return pattern


    def clean_nozzles(self, group_index, power_clean=False, has_alt_mode=None):
        """
        Initiates nozzles cleaning routine with optional power clean.
        """
        if has_alt_mode and (group_index > has_alt_mode or group_index) < 0:
            return None
        if not has_alt_mode and (group_index > 5 or group_index) < 0:
            return None
        group = group_index  # https://github.com/abrasive/x900-otsakupuhastajat/blob/master/emanage.py#L148-L154
        if power_clean:
            group |= 0x10  # https://github.com/abrasive/x900-otsakupuhastajat/blob/master/emanage.py#L220

        # Sequence list (Epson XP-205 207 Series Printing Preferences > Utilty > Clean Heads)
        commands = [
            self.EXIT_PACKET_MODE,                            # Exit packet mode
            self.ENTER_REMOTE_MODE,                           # Engage remote mode commands
            self.set_timer(),                                 # Sync RTC            
            self.remote_cmd("CH", b'\x00' + bytes([group])),  # Run print-head cleaning
            self.EXIT_REMOTE_MODE,                            # Disengage remote control
            self.ENTER_REMOTE_MODE,                           # Prepare for JOB_END
            self.JOB_END,                                     # Mark maintenance job complete
            self.EXIT_REMOTE_MODE                             # Close sequence
        ]

        if has_alt_mode and group_index == has_alt_mode:
            commands = [
                self.INITIALIZE_PRINTER,
                bytes.fromhex("1B 7C 00 06 00 19 07 84 7B 42 02")  # Head cleaning
            ]
        if has_alt_mode and group_index == has_alt_mode and power_clean:
            commands = [
                self.INITIALIZE_PRINTER,
                bytes.fromhex("1B 7C 00 06 00 19 07 84 7B 42 0A")  # Ink charge
            ]
        return b"".join(commands)


    def check_nozzles(self, type=0):
        """
        Print nozzle-check pattern.
        """
        # Sequence list
        nozzle_check = self.PRINT_NOZZLE_CHECK  # Issue nozzle-check print pattern
        if type == 1:
            nozzle_check = nozzle_check[:-1] + b'\x10'
        commands = [
            self.EXIT_PACKET_MODE,    # Exit packet mode
            self.ENTER_REMOTE_MODE,   # Engage remote mode commands
            nozzle_check,
            self.EXIT_REMOTE_MODE,    # Disengage remote control
            self.JOB_END              # Mark maintenance job complete
        ]
        return b"".join(commands)
