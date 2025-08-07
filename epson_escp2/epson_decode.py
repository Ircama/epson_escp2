import struct
from collections import Counter
from typing import Tuple, List, Dict, Any
from PIL import Image, ImageOps  # pip install pillow
try:
    from .tri_attr import rle_decode, dot_size_decode
except ImportError:
    from tri_attr import rle_decode, dot_size_decode
try:
    from hexdump2 import hexdump, color_always  # pip install hexdump2
    HEXDUMP_AVAILABLE = True
except ImportError:
    HEXDUMP_AVAILABLE = False

def decode_escp2_commands(
    data: bytes,
    show_image: bool = False,
    dump_image: bool = False
) -> str:
    """
    Decode Epson ESC/P2 printer commands from a bytes sequence.
    
    Args:
        data: Raw bytes sequence containing ESC/P2 commands
        dump_image: If True, dump image data using hexdump2 (requires hexdump2 package)
        
    Returns:
        String representation of decoded commands
    """
    
    def decode_remote_cmd(pos: int) -> Tuple[str, int]:
        """Decode a remote mode command starting at position pos."""
        if pos + 6 > len(data):
            return f"INCOMPLETE_REMOTE_CMD at {pos:04x}", pos + 1
            
        cmd = data[pos:pos+2].decode('ascii', errors='ignore')
        length = struct.unpack('<H', data[pos+2:pos+4])[0]
        
        if pos + 4 + length > len(data):
            return f"INCOMPLETE_REMOTE_CMD {cmd} (length {length}) at {pos:04x}", pos + 4
            
        args = data[pos+4:pos+4+length]
        
        # Decode specific remote commands based on the "Other commands" section
        if cmd == "TI":  # Timer/RTC command - set_timer()
            if length >= 8:
                year_bytes = args[1:3]
                if len(year_bytes) == 2:
                    year = struct.unpack('>H', year_bytes)[0]
                    if len(args) >= 8:
                        month, day, hour, minute, second = args[3:8]
                        return f"TI set_timer remote_cmd ({year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d})", pos + 4 + length
            return f"TI remote_cmd (args: {args.hex()})", pos + 4 + length
        elif cmd == "JS":  # JOB_START
            return f"JS (job start) remote_cmd: {args.hex()}", pos + 4 + length
        elif cmd == "NC":  # PRINT_NOZZLE_CHECK
            return "NC print_nozzle_check remote_cmd", pos + 4 + length
        elif cmd == "VI":  # VERSION_INFORMATION
            return "VI remote_cmd version_information", pos + 4 + length
        elif cmd == "LD":  # SN command
            if args == b'':
                return "LD (Load Power-On Default NVR into RAM) remote_cmd: valid", pos + 4 + length
            else:
                return "LD (Load Power-On Default NVR into RAM) remote_cmd: invalid", pos + 4 + length
        elif cmd == "SN":  # SN command
            if args == b'\x00':
                return "SN (Paper Feed Setup) remote_cmd: valid", pos + 4 + length
            else:
                return "SN (Paper Feed Setup) remote_cmd: invalid", pos + 4 + length
        elif cmd == "JE":  # JE command
            if args == b'\x00':
                return "JE (End job) remote_cmd: valid", pos + 4 + length
            else:
                return "JE (End job) remote_cmd: invalid", pos + 4 + length
        elif cmd == "FP":  # Set horizontal print position (Remote Mode)
            if length == 3 and args[0] == 0x00:
                position = struct.unpack('<H', args[1:])[0]
                mm = position / 360 * 25.4  # convert to mm

                if position == 0:
                    note = " (standard position)"
                elif position == 0xFFB0:
                    note = " (borderless print position)"
                else:
                    note = " (unknown)"
                return (
                    f'FP set_horizontal_print_position remote_cmd ({position} units = {mm:.3f}mm){note}',
                    pos + 4 + length
                )
            else:
                return f"FP remote_cmd INVALID format or length (args: {args.hex()})", pos + 4 + length

        elif cmd == "ST":  # Turn printer state reply on/off (Remote Mode)
            if length == 2 and args[0] == 0x00:
                note = int(args[1])

                if note == 0x10:
                    note = " Binary state reply Off"
                elif note == 0x11:
                    note = " Binary state reply On"
                else:
                    note = " Unknown"
                return (
                    f'ST Turn printer state reply remote_cmd: {note}',
                    pos + 4 + length
                )
            else:
                return f"ST Turn printer state reply remote_cmd - INVALID format or length (args: {args.hex()})", pos + 4 + length

        elif cmd == "MI":  # Select paper media
            paper = {
                0: "A4",
                1: "Letter (8 1/2 x 11 in)",
                2: "Legal (8 1/2 x 14 in)",
                3: "A5",
                4: "A6",
                5: "B5",
                6: "Executive (7 1/4 x 10 1/2 in)",
                7: "Half-Letter (5 1/2 x 8 1/2 in)",
                8: "Panoramic Photo Paper",
                9: "Photo Paper (4 x 6 in) with perforated",
                10: "Photo Paper (4 x 6 in)",
                11: "5 x 8 in",
                12: "8 x 10 in",
                13: "Photo Paper (100 x 150 mm)",
                14: "Photo Paper (200 x 300 mm)",
                15: "L size",
                16: "Japanese Postcard",
                17: "Japanese Double Postcard",
                18: "Envelope #10 (4 1/8 x 9 1/2 in) Landscape",
                19: "Envelope C6 Landscape",
                20: "Envelope DL Landscape",
                21: "Envelope (220 x 132 mm) Landscape",
                22: "Japanese CHOKEI 3",
                23: "Japanese CHOKEI 4",
                24: "Japanese YOKEI 1",
                25: "Japanese YOKEI 2",
                26: "Japanese YOKEI 3"
            }
            format_str = {
                0: "Plain Paper - Bright White Paper",
                1: "360dpi Ink Jet Paper"
            }
            if length == 4 and args[0] == 0x00:
                format = args[1] | (args[2] << 8) | (args[3] << 16)
                description = format_str.get(format)
                paper_description = paper.get(args[3], "Unknown paper format")
                if description:
                    return (f'MI Select paper media remote_cmd: {format} ({description}, {paper_description})', pos + 4 + length)
                else:
                    return (f'MI Select paper media remote_cmd: {format} (unknown, {paper_description})', pos + 4 + length)
            else:
                return f"MI Select paper media - INVALID format or length (args: {args.hex()})", pos + 4 + length

        elif cmd == "DP":  # DP command
            definitions = {
                0x00: (
                    "Duplex mode",
                    {
                        0x00: "Duplex mode off",
                        0x01: "Duplex mode on",
                    }
                )
            }
            mode = {}
            for m1, (item_name, m2_map) in definitions.items():
                for m2, setting in m2_map.items():
                    cmd = bytes([m1, m2])
                    mode[cmd] = f"{item_name}: {setting}"
            desc = mode.get(args, "Unknown command")
            return f"DP (Select Duplex Printing) remote_cmd - {desc}", pos + 4 + length
        elif cmd == "PP":  # PP command
            definitions = {
                0x01: (
                    "Paper",
                    {
                        0x00: "Cut Sheet Rear",
                        0xfe: "Auto Select (Choose A4 or Letter)",
                    }
                )
            }
            mode = {}
            for m1, (item_name, m2_map) in definitions.items():
                for m2, setting in m2_map.items():
                    cmd = bytes([0x00, m1, m2])
                    mode[cmd] = f"{item_name}: {setting}"
            desc = mode.get(args, "Unknown command")
            return f"PP (Select paper path) remote_cmd - {desc}", pos + 4 + length
        elif cmd == "US":  # US command
            definitions = {
                0x00: (
                    "Bottom margin setting",
                    {
                        0x00: "Standard",
                        0x01: "Max",
                        0x02: "Borderless",
                    }
                ),
                0x04: (
                    "Economy print setting",
                    {
                        0x00: "Fast-Mode",
                        0x01: "Normal-Mode",
                    }
                ),
                0x05: (
                    "Load mode setting",
                    {
                        0x00: "Fast-Mode (Default)",
                        0x01: "Silent-Mode",
                    }
                ),
            }
            mode = {}
            for m1, (item_name, m2_map) in definitions.items():
                for m2, setting in m2_map.items():
                    cmd = bytes([0x00, m1, m2])
                    mode[cmd] = f"{item_name}: {setting}"
            desc = mode.get(args, "Unknown command " + args.hex(" "))
            return f"US (User Setting) remote_cmd - {desc}", pos + 4 + length
        elif cmd == "JH":  # Job name set
            # Format: "JH" nL nH 00H m1 m2 m3 m4 m5 <job name>
            # nL = (length of <job name>) + 6
            # nH = 00H
            if length < 6:
                return f"JH remote_cmd INVALID_LENGTH (expected at least 6 bytes, got {length})", pos + 4 + length
                
            # Check for 00H byte after nL/nH
            if args[0] != 0x00:
                return f"JH remote_cmd INVALID_FORMAT (expected 00H byte, got 0x{args[0]:02x})", pos + 4 + length
                
            # Extract parameters
            m1 = args[1]  # Job name type
            m2, m3, m4, m5 = args[2:6]  # Job ID bytes
            job_name_bytes = args[6:]
            
            # Map m1 to job name type
            job_types = {
                0x00: "Host name",
                0x01: "Product ID",
                0x02: "Document name",
                0x03: "User name"
            }
            job_type = job_types.get(m1, f"unknown_type_0x{m1:02x}")
            
            # Format Job ID
            job_id = f"0x{m2:02x}{m3:02x}{m4:02x}{m5:02x}"
            
            # Decode job name (up to 32 bytes)
            job_name = job_name_bytes.hex()
                
            return f"JH (Job name set) remote_cmd (type={job_type}, job_id={job_id}, name={job_name})", pos + 4 + length
        else:
            # Generic remote command
            return f"{cmd} remote_cmd" + (f" (args: {args.hex()})" if args else ""), pos + 4 + length

    def decode_esc_sequence(pos: int) -> Tuple[str, int]:
        """
        Decode a single ESC/P2 command or sequence at the given position.
        Handles standard ESC commands, extended ESC ( ... ) commands, and context-sensitive decoding.
        Returns:
            Tuple[str, int]: (decoded string, new position after command)
        """
        nonlocal remote_mode_active, current_color
        
        if pos + 1 >= len(data):
            return f"INCOMPLETE_ESC at {pos:04x}", pos + 1
            
        next_byte = data[pos + 1]
        
        if next_byte == 0x40:  # ESC @
            return "❬ESC @❭ Initialize Printer", pos + 2
        elif next_byte == 0x19:  # ESC 0x19 n (CSF control)
            if pos + 2 < len(data):
                n = data[pos + 2]
                if n == 0x31:
                    return "❬ESC 19❭ CSF (cut sheet feeder): select bin 1 for next and all subsequent paper feeding", pos + 3
                elif n == 0x52:
                    return "❬ESC 19❭ CSF (cut sheet feeder): eject paper", pos + 3
                else:
                    return f"ESC_19_n=0x{n:02X}", pos + 3
            return "INCOMPLETE_ESC_19", pos + 2

        elif next_byte == 0x55:  # ESC U
            if pos + 2 < len(data):
                n = data[pos + 2]
                modes = {
                    0x00: "select_bidirectional_printing",
                    0x01: "select_unidirectional_printing (0→80 col)",
                    0x02: "select_automatic_printing_direction",
                    0x03: "select_unidirectional_printing (80→0 col)",
                    0x30: "select_bidirectional_printing (ASCII '0')",
                    0x31: "select_unidirectional_printing (0→80 col, ASCII '1')",
                    0x32: "select_automatic_printing_direction (ASCII '2')",
                    0x33: "select_unidirectional_printing (80→0 col, ASCII '3')"
                }
                mode = modes.get(n, f"unknown_mode (n=0x{n:02X})")
                return f"❬ESC U❭ {mode}", pos + 3
            return "INCOMPLETE_ESC_U", pos + 2

        elif next_byte == 0x24:  # ESC $ nL nH: Set absolute horizontal print position
            if pos + 3 < len(data):
                n = struct.unpack('<H', data[pos + 2:pos + 4])[0]
                nL, nH = data[pos + 2], data[pos + 3]
                
                # Validate nL and nH ranges per specification
                if nL > 0x18 or nH > 0x8F:
                    return f"❬ESC $❭ set_absolute_horizontal_position(INVALID: n={n} outside range, nL=0x{nL:02X}, nH=0x{nH:02X})", pos + 4
                
                # Get current horizontal units
                P = unit_dict["P"] if unit_dict["P"] else 1
                unit = unit_dict["unit"] if unit_dict["unit"] else 1
                
                try:
                    # Calculate position in inches using the general formula:
                    # (256 × nH + nL) × Base_Unit(m) / AHP_units
                    inches = (n * P) / (unit * 3600)
                    
                    # Convert to mm for display
                    mm = inches * 25.4
                    
                    # Validate against maximum allowed position (323.074mm or 12.719 inches)
                    if inches <= 12.719:
                        # Add resolution info based on current P value
                        resolution_info = {
                            1: "1/2880 inch (0.004mm)",
                            2: "1/1440 inch (0.008mm)",
                            5: "1/720 inch (0.035mm)",
                            10: "1/360 inch (0.071mm)",
                            20: "1/180 inch (0.141mm)",
                            30: "1/120 inch (0.211mm)",
                            40: "1/90 inch (0.282mm)",
                            50: "1/72 inch (0.353mm)",
                            60: "1/60 inch (0.423mm)"
                        }
                        res = resolution_info.get(P, f"1/{3600//P} inch")
                        return f"❬ESC $❭ set_absolute_horizontal_position({n} = {mm:.3f}mm, resolution: {res})", pos + 4
                    else:
                        return f"❬ESC $❭ set_absolute_horizontal_position(INVALID: {mm:.3f}mm > 323.074mm maximum)", pos + 4
                except Exception:
                    return f"❬ESC $❭ set_absolute_horizontal_position(ERROR: calculation failed for n={n})", pos + 4
            return "INCOMPLETE_ESC_$", pos + 2

        elif next_byte == 0x69:  # ESC i (Transfer Raster Image)
            if pos + 8 > len(data):
                return "INCOMPLETE_ESC_i", pos + 2
            
            # ESC i r c b nL nH mL mH
            color = data[pos + 2]  # r
            compression = data[pos + 3]  # c  
            bit_depth = data[pos + 4]  # b
            h_bytes = struct.unpack('<H', data[pos + 5:pos + 7])[0]  # nL nH
            v_dots = struct.unpack('<H', data[pos + 7:pos + 9])[0]  # mL mH
            
            # Color mapping based on TRI constants
            color_names = {
                0: "black",      # TRI_BLACK
                1: "magenta",    # TRI_MAGENTA  
                2: "cyan",       # TRI_CYAN
                4: "yellow",     # TRI_YELLOW
                5: "black2",     # TRI_BLACK2
                6: "black3"      # TRI_BLACK3
            }
            color_name = color_names.get(color, f"color_{color}")
            
            # Map compression method
            compression_methods = {
                0x00: "non-compressed",
                0x01: "Run Length Encoding"
            }
            compression_str = compression_methods.get(compression, f"unknown_compression_0x{compression:02x}")
            
            # Map bit depth
            bit_depths = {
                0x01: "1 bit/pixel",
                0x02: "2 bits/pixel"
            }
            bit_depth_str = bit_depths.get(bit_depth, f"unknown_bit_depth_0x{bit_depth:02x}")
            
            # Calculate expected image data size: (nH*256 + nL) * (mH*256 + mL)
            expected_bytes = h_bytes * v_dots
            cmd_desc = (f"❬ESC i❭ transfer_raster_image({color_name}, compression={compression_str}, "
                         f"bit_depth={bit_depth_str}, {v_dots} rows, {h_bytes} bytes/row")
            if compression:
                cmd_desc += f", uncompressed {expected_bytes} bytes"
            else:
                cmd_desc += f", total {expected_bytes} bytes"

            image_start_pos = pos + 9
            if compression:
                try:
                    image_data, image_end_pos = rle_decode(data[image_start_pos:], expected_bytes)
                except ValueError as e:
                    return f"❬ESC i❭ RLE decode error: {str(e)}", image_start_pos
                image_end_pos += image_start_pos
                if len(image_data) != expected_bytes:
                    cmd_desc += f". Decoded data length: {len(image_data)} bytes"
            else:
                image_end_pos = image_start_pos + expected_bytes
                image_data = data[image_start_pos:image_end_pos]
            actual_bytes = image_end_pos - image_start_pos
            non_zero_bytes = sum(1 for b in image_data if b != 0)
            if compression:
                cmd_desc += f", {non_zero_bytes} non-zero). Compressed {actual_bytes} bytes"
            else:
                cmd_desc += f", {non_zero_bytes} non-zero). Actual {actual_bytes} bytes"

            if bit_depth == 2:
                image_data, seq_counts = dot_size_decode(image_data)
                cmd_desc += f"; count of sequences: {seq_counts}"

            if show_image:
                img = Image.frombytes(
                    '1', (int(h_bytes/bit_depth*8), v_dots), image_data
                )
                # Map color variable to RGB
                color_map = {
                    0: (0, 0, 0),        # black
                    1: (255, 0, 255),    # magenta
                    2: (0, 255, 255),    # cyan
                    4: (255, 255, 0),    # yellow
                    5: (0, 0, 0),        # black
                    6: (0, 0, 0),        # black
                }
                rgb = color_map.get(color, (128, 128, 128))
                mask = img.convert('L')
                color_img = Image.new('RGB', img.size, rgb)
                white_bg = Image.new('RGB', img.size, (255, 255, 255))
                img = Image.composite(color_img, white_bg, mask)
                img.show()

            # Add hexdump if requested and available
            if dump_image and HEXDUMP_AVAILABLE:
                color_always()
                cmd_desc += "\n" + hexdump(image_data, result='return')

            return cmd_desc, image_end_pos

        elif next_byte == 0x2E:  # ESC . 
            if pos + 3 > len(data):
                return "INCOMPLETE_ESC_.", pos + 2

            c = data[pos + 2]

            # Case: Enter TIFF Compressed Mode → ESC . '2' v h 1 0 0
            if (
                c == 0x32 and
                pos + 7 <= len(data) and
                data[pos + 5] == 0x00 and data[pos + 6] == 0x00
            ):
                v = data[pos + 3]
                h = data[pos + 4]
                allowed_densities = {(10, 10): (360, 360), (5, 5): (720, 720)}
                if (v, h) in allowed_densities:
                    dpi_v, dpi_h = allowed_densities[(v, h)]
                    return (
                        f"❬ESC .❭ enter_tiff_compression_mode "
                        f"(v={dpi_v} dpi, h={dpi_h} dpi)",
                        pos + 7
                    )
                else:
                    return (
                        f"❬ESC .❭ INVALID TIFF density v={v}, h={h} - ignored",
                        pos + 7
                    )

            # Case: Print Raster Graphics → ESC . c v h m nL nH d...
            if pos + 8 > len(data):
                return "INCOMPLETE_ESC_.", pos + 2

            compression = c
            v = data[pos + 3]
            h = data[pos + 4]
            m = data[pos + 5]
            nL = data[pos + 6]
            nH = data[pos + 7]
            width_dots = nH * 256 + nL

            compression_modes = {
                0x00: "non-compressed",
                0x01: "Run Length Encoding",
                0x02: "TIFF compression (requires m = 1)"
            }

            if compression not in compression_modes:
                return f"❬ESC .❭ INVALID compression c=0x{compression:02X}", pos + 2

            if compression == 0x02 and m != 1:
                return f"❬ESC .❭ TIFF compression requires m=1, found m={m}", pos + 2

            if v not in (5, 10, 20, 30) or h not in (5, 10):
                return f"❬ESC .❭ INVALID resolution v={v}, h={h}", pos + 2

            bits_per_line = width_dots
            bytes_per_line = (bits_per_line + 7) // 8
            expected_bytes = m * bytes_per_line if compression in (0x00, 0x01) else None
            data_start = pos + 8

            if compression == 0x00:  # Non-compressed
                data_end = data_start + expected_bytes
                if data_end > len(data):
                    return f"❬ESC .❭ INCOMPLETE raster data, expected {expected_bytes} bytes", pos + 2
                image_data = data[data_start:data_end]

            elif compression == 0x01:  # RLE
                try:
                    image_data, consumed = rle_decode(data[data_start:], expected_bytes)
                    data_end = data_start + consumed
                    if len(image_data) != expected_bytes:
                        return f"❬ESC .❭ RLE mismatch: expected {expected_bytes}, got {len(image_data)}", data_end
                except ValueError as e:
                    return f"❬ESC .❭ RLE decode failed: {e}", data_start + 1

            else:  # compression == 0x02
                return f"❬ESC .❭ TIFF compression not supported", pos + 2

            if show_image:
                try:
                    img = Image.frombytes('1', (width_dots, m), image_data)
                    # Map color variable to RGB
                    color_map = {
                        0: (0, 0, 0),        # black
                        1: (255, 0, 255),    # magenta
                        2: (0, 255, 255),    # cyan
                        4: (255, 255, 0),    # yellow
                    }
                    rgb = color_map.get(current_color, (128, 128, 128))
                    mask = img.convert('L')
                    color_img = Image.new('RGB', img.size, rgb)
                    white_bg = Image.new('RGB', img.size, (255, 255, 255))
                    img = Image.composite(color_img, white_bg, mask)
                    img.show()
                except Exception as e:
                    print(f"Could not show image for ESC .: {e}")

            non_zero = sum(1 for b in image_data if b != 0)
            cmd_str = (
                f"❬ESC .❭ print_raster_graphics("
                f"compression={compression_modes[compression]}, "
                f"v={v}/3600 dpi, h={h}/3600 dpi, "
                f"{m} lines, width={width_dots} dots, "
                f"{non_zero} non-zero bytes)"
            )

            return cmd_str, data_end

        elif next_byte == 0x5C:  # ESC \
            if pos + 3 >= len(data):
                return "INCOMPLETE_ESC_\\", pos + 2

            nL = data[pos + 2]
            nH = data[pos + 3]

            # Convert to signed value using 16-bit two's complement
            value = nH << 8 | nL
            if nH & 0x40:  # bit 6 of nH indicates negative
                value = value - 0x10000  # two's complement

            P = unit_dict.get("P", 1)
            unit = unit_dict.get("unit", 1)
            mm = value * P / unit * 25.4

            return (
                f"❬ESC \\❭ set_relative_horizontal_position("
                f"{value} units = {mm:.3f}mm)", pos + 4
            )

        elif next_byte == 0x72:  # ESC r
            if pos + 2 < len(data):
                n = data[pos + 2]
                color_map = {
                    0x00: "black",
                    0x01: "magenta",
                    0x02: "cyan",
                    0x04: "yellow"
                }
                color = color_map.get(n)
                if color:
                    current_color = n
                    return f"❬ESC r❭ select_printing_color({color})", pos + 3
                else:
                    return f"❬ESC r❭ INVALID n=0x{n:02X} (ignored)", pos + 3
            return "INCOMPLETE_ESC_r", pos + 2

        # --------------------------- Process ESC ( ---------------------------
        elif next_byte == 0x28:  # ESC ( - Extended commands
            if pos + 5 > len(data):
                return "INCOMPLETE_ESC_PAREN", pos + 2

            cmd_char = chr(data[pos + 2])
            length = struct.unpack('<H', data[pos + 3:pos + 5])[0]

            if pos + 5 + length > len(data):
                return f"INCOMPLETE_ESC_({cmd_char}) length={length}", pos + 5

            args = data[pos + 5:pos + 5 + length]

            if cmd_char == 'R':  # Remote mode
                if args == b'\x00REMOTE1':
                    remote_mode_active = True
                    return "❬...REMOTE1❭ Enter Remote Mode", pos + 5 + length
                else:
                    return f"ESC_(R) args={args.hex()}", pos + 5 + length
            elif cmd_char == 'U':  # Set units
                # Map m value to units and DPI
                m_units = {
                    0x05: (5, 720),   # 0.035mm (5/3600 inch)
                    0x0A: (10, 360),  # 0.071mm (10/3600 inch)
                    0x14: (20, 180),  # 0.141mm (20/3600 inch)
                    0x1E: (30, 120),  # 0.211mm (30/3600 inch)
                    0x28: (40, 90),   # 0.282mm (40/3600 inch)
                    0x32: (50, 72),   # 0.353mm (50/3600 inch)
                    0x3C: (60, 60),   # 0.423mm (60/3600 inch)
                }
                if length == 1:  # Simple format: nL=1, nH=0, m
                    m = args[0]
                    if m in m_units:
                        units, dpi = m_units[m]
                        # Set all units (horizontal, vertical, page) to same value
                        unit_dict["P"] = units
                        unit_dict["V"] = units
                        unit_dict["H"] = units
                        unit_dict["unit"] = 3600
                        return f"❬ESC (U❭ set_units(units={units}/3600={dpi} DPI)", pos + 5 + length
                    else:
                        return f"❬ESC (U❭ set_units(m=0x{m:02X}: ignored - out of range)", pos + 5 + length
                elif length >= 5:  # Extended format
                    p, v, h = args[0], args[1], args[2]
                    m = struct.unpack('<H', args[3:5])[0]
                    unit_dict["P"] = p
                    unit_dict["V"] = v
                    unit_dict["H"] = h
                    unit_dict["unit"] = m
                    return f"❬ESC (U❭ set_units(P={p}, V={v}, H={h}, unit={m})", pos + 5 + length
                return f"set_units(args={args.hex()})", pos + 5 + length
            elif cmd_char == 'i':  # MicroWeave
                if length == 1:  # Standard format: nL=1, nH=0, n
                    n = args[0]
                    # Map parameter values to their meanings
                    microweave_modes = {
                        0x00: "deselect microweave mode",
                        0x01: "select microweave mode",
                        0x30: "deselect microweave mode (alternate)",
                        0x31: "select microweave mode (alternate)"
                    }
                    mode_desc = microweave_modes.get(n, f"unknown mode (0x{n:02X})")
                    return f"❬ESC (i❭ {mode_desc}", pos + 5 + length
                return f"❬ESC (i❭ microweave_mode(INVALID args={args.hex()})", pos + 5 + length
            elif cmd_char == 'C':  # Page length
                if length == 4:  # extended format nL=4, nH=0, m1, m2, m3, m4
                    page_length = struct.unpack('<i', args)[0]
                    # Use P/unit for calculation if available
                    P = unit_dict["P"] if unit_dict["P"] else 1
                    unit = unit_dict["unit"] if unit_dict["unit"] else 1
                    # Calculate length in cm using P/unit
                    try:
                        cm = page_length * P / unit * 2.54
                    except Exception:
                        cm = 0
                    return f"❬ESC (C❭ set_page_length({page_length} = {cm:.1f}cm)", pos + 5 + length
                elif length == 2:  # nL=2, nH=0, mL, mH format
                    if len(args) == 4:
                        page_len_units = struct.unpack('<H', args[2:4])[0]
                        page_mgmt_val = unit_dict["unit"] if unit_dict["unit"] else 1
                        mm = page_len_units * page_mgmt_val * 25.4
                        return f"❬ESC (C❭ set_page_length({page_len_units} units = {mm:.1f}mm)", pos + 5 + length
                    else:
                        return f"❬ESC (C❭ set_page_length(INVALID args length: {len(args)})", pos + 5 + length
                return f"❬ESC (C❭ set_page_length(args={args.hex()})", pos + 5 + length
            elif cmd_char == 'G':  # Graphics mode
                if length == 1:
                    if args[0] == 0x01:
                        desc = "select_graphics_mode (m=0x01: standard)"
                    elif args[0] == 0x31:
                        desc = "select_graphics_mode (m=0x31: alternate)"
                    else:
                        desc = f"select_graphics_mode (m=0x{m:02X}: ignored)"
                    return f"❬ESC (G❭ {desc}", pos + 5 + length
                else:
                    return f"❬ESC (G❭ select_graphics_mode(INVALID args: {args.hex()})", pos + 5 + length
            elif cmd_char == 'c':  # Page format
                if length == 4:  # nL=4, nH=0, tL, tH, bL, bH format
                    if len(args) == 4:
                        top = struct.unpack('<H', args[0:2])[0]
                        bottom = struct.unpack('<H', args[2:4])[0]
                        
                        # Validate top < bottom
                        if top >= bottom:
                            return f"❬ESC (c❭ set_page_format(INVALID: top={top} >= bottom={bottom})", pos + 5 + length
                            
                        # Calculate in mm using page management value
                        page_mgmt_val = unit_dict["unit"] if unit_dict["unit"] else 1
                        top_mm = top * page_mgmt_val * 25.4
                        bottom_mm = bottom * page_mgmt_val * 25.4
                        
                        # Check if bottom margin is within allowed range (≤ 44 inches = 1117.6mm)
                        if bottom_mm <= 1117.6:
                            return f"❬ESC (c❭ set_page_format(top={top}={top_mm:.1f}mm, bottom={bottom}={bottom_mm:.1f}mm)", pos + 5 + length
                        else:
                            return f"❬ESC (c❭ set_page_format(INVALID: bottom margin {bottom_mm:.1f}mm > 1117.6mm)", pos + 5 + length
                    else:
                        return f"❬ESC (c❭ set_page_format(INVALID args length: {len(args)})", pos + 5 + length
                elif length == 8:  # Extended format
                    top = struct.unpack('<i', args[0:4])[0]
                    bottom = struct.unpack('<i', args[4:8])[0]
                    # Use P/unit for extended format calculation
                    P = unit_dict["P"] if unit_dict["P"] else 1
                    unit = unit_dict["unit"] if unit_dict["unit"] else 1
                    top_mm = top * P / unit * 25.4
                    bottom_mm = bottom * P / unit * 25.4
                    return f"❬ESC (c❭ set_page_format_extended(top={top}={top_mm:.1f}mm, bottom={bottom}={bottom_mm:.1f}mm)", pos + 5 + length
                return f"❬ESC (c❭ set_page_format(args={args.hex()})", pos + 5 + length
            elif cmd_char == 'S':  # Paper size
                if length == 8:
                    width = struct.unpack('<i', args[0:4])[0]
                    height = struct.unpack('<i', args[4:8])[0]

                    # Use P/unit for calculation if available
                    P = unit_dict["P"] if unit_dict["P"] else 1
                    unit = unit_dict["unit"] if unit_dict["unit"] else 1

                    width_cm = width * P / unit * 2.54
                    height_cm = height * P / unit * 2.54
                    return f"❬ESC (S❭ set_paper_size({width}x{height} = {width_cm:.1f}x{height_cm:.1f}cm)", pos + 5 + length
                return f"❬ESC (S❭ set_paper_size(args={args.hex()})", pos + 5 + length
            elif cmd_char == 'K':  # Color/Monochrome mode selection
                if length == 2:  # nL=1, nH=0, m, n format
                    if len(args) == 2:
                        m, n = args[0], args[1]
                        # Handle both standard (m=0x00) and alternate (m=0x01) formats
                        if m in (0x00, 0x01):
                            # For m=0x00, use standard mode mapping
                            if m == 0x00:
                                modes = {
                                    0x00: "default (color)",
                                    0x01: "monochrome",
                                    0x02: "color"
                                }
                                if n in modes:
                                    return f"❬ESC (K❭ select_{modes[n]}_mode", pos + 5 + length
                            # For m=0x01, only n=0x01 is valid for monochrome
                            elif m == 0x01 and n == 0x01:
                                return "❬ESC (K❭ select_monochrome_mode (alternate format)", pos + 5 + length
                            
                            return f"❬ESC (K❭ select_mode(INVALID n value: 0x{n:02X} - command ignored)", pos + 5 + length
                        else:
                            return f"❬ESC (K❭ select_mode(INVALID m value: 0x{m:02X} - expected 0x00 or 0x01)", pos + 5 + length
                    else:
                        return f"❬ESC (K❭ select_mode(INVALID args length: {len(args)})", pos + 5 + length
                return f"❬ESC (K❭ select_mode(INVALID format: args={args.hex()})", pos + 5 + length
            elif cmd_char == 'D':  # Raster resolution
                if length == 4:
                    # rL, rH, v, h
                    r = struct.unpack('<H', args[0:2])[0]
                    v = args[2]
                    h = args[3]
                    vert_dpi = r // v if v else 0
                    horz_dpi = r // h if h else 0
                    return (
                        f"❬ESC (D❭ set_raster_resolution(r={r}, v={v}, h={h}) "
                        f"Vertical resolution: {r}/{v}={vert_dpi} dpi; "
                        f"Horizontal resolution: {r}/{h}={horz_dpi} dpi"
                    ), pos + 5 + length

            elif cmd_char == 'm':  # ESC (m – Set Print Method ID
                if length == 1 and len(args) == 1:
                    n = args[0]
                    valid_methods = {
                        0x10: "method_0x10",
                        0x11: "fast_eco",
                        0x12: "fine",
                        0x13: "super fine",
                        0x20: "method_0x20",
                        0x21: "normal",
                        0x30: "method_0x30",
                        0x31: "method_0x31",
                        0x50: "method_0x50",
                        0x51: "method_0x51",
                        0x52: "method_0x52",
                        0x53: "method_0x53",
                        0x70: "method_0x70",
                        0x71: "method_0x71",
                        0xA0: "method_0xA0"
                    }
                    if n in valid_methods:
                        return f"❬ESC (m❭ set_print_method({valid_methods[n]})", pos + 5 + length
                    else:
                        return f"❬ESC (m❭ INVALID n=0x{n:02X} - ignored", pos + 5 + length
                return f"❬ESC (m❭ INVALID length={length}", pos + 5 + length

            elif cmd_char == 'e':  # Dot size selection
                if length >= 2:
                    dot_size = args[1]
                    sizes = {
                        0x00: "VSD1 1-bit (DOS compatible)",
                        0x10: "economy",
                        0x11: "VSD1 2-bit mode, fast eco",
                        0x12: "VSD2 2-bit mode",
                        0x13: "VSD3 2-bit mode"
                    }
                    size_desc = sizes.get(dot_size, f"unknown mode (0x{dot_size:02x})")
                    return f"❬ESC (e❭ select_dot_size({size_desc})", pos + 5 + length
                return f"❬ESC (e❭ select_dot_size(INVALID args={args.hex()})", pos + 5 + length
            elif cmd_char == 'v':  # Vertical position
                if length == 4:
                    pos_val = struct.unpack('<i', args)[0]

                    # Use P/unit for calculation if available
                    P = unit_dict["P"] if unit_dict["P"] else 1
                    unit = unit_dict["unit"] if unit_dict["unit"] else 1

                    mm = pos_val * P / unit * 25.4
                    return f"❬ESC (v❭ set_relative_vertical_position_ext({pos_val} = {mm:.2f}mm)", pos + 5 + length
                elif length == 2:  # Short format: mL, mH
                    if len(args) == 2:
                        pos_val = struct.unpack('<H', args)[0]
                        P = unit_dict["P"] if unit_dict["P"] else 1
                        unit = unit_dict["unit"] if unit_dict["unit"] else 1
                        mm = pos_val * P / unit * 25.4
                        return f"❬ESC (v❭ set_relative_vertical_position({pos_val} = {mm:.2f}mm)", pos + 5 + length
                    else:
                        return f"❬ESC (v❭ set_relative_vertical_position(INVALID args length: {len(args)})", pos + 5 + length
            elif cmd_char == 'V':  # Set absolute vertical print position
                if length == 2:  # nL=2, nH=0, mL, mH format
                    if len(args) == 2:
                        pos_val = struct.unpack('<H', args[0:2])[0]
                        # Use P/unit for calculation if available
                        P = unit_dict["P"] if unit_dict["P"] else 1
                        unit = unit_dict["unit"] if unit_dict["unit"] else 1
                        mm = pos_val * P / unit * 25.4
                        return f"❬ESC (V❭ set_absolute_vertical_position({pos_val} = {mm:.2f}mm)", pos + 5 + length
                    else:
                        return f"❬ESC (V❭ set_absolute_vertical_position(INVALID args length: {len(args)})", pos + 5 + length
                elif length == 4:  # extended format nL=4, nH=0, m1, m2, m3, m4
                    if len(args) == 4:
                        pos_val = struct.unpack('<i', args)[0]
                        # Check if value is within allowed range (0 <= val*1440 <= 0x1FFFFFFF)
                        if 0 <= pos_val * 1440 <= 0x1FFFFFFF:
                            # Use P/unit for calculation if available
                            P = unit_dict["P"] if unit_dict["P"] else 1
                            unit = unit_dict["unit"] if unit_dict["unit"] else 1
                            mm = pos_val * P / unit * 25.4
                            return f"❬ESC (V❭ set_absolute_vertical_position_extended({pos_val} = {mm:.2f}mm)", pos + 5 + length
                        else:
                            return f"❬ESC (V❭ set_absolute_vertical_position_extended(INVALID value: outside range)", pos + 5 + length
                    else:
                        return f"❬ESC (V❭ set_absolute_vertical_position_extended(INVALID args length: {len(args)})", pos + 5 + length
                return f"❬ESC (V❭ set_absolute_vertical_position(args={args.hex()})", pos + 5 + length
                return f"❬ESC (v❭ set_relative_vertical_position(args={args.hex()})", pos + 5 + length
            elif cmd_char == '$':  # Extended absolute horizontal position
                if length == 4:  # Extended format: nL=4, nH=0, m1, m2, m3, m4
                    if len(args) == 4:
                        m = struct.unpack('<i', args)[0]
                        
                        # Get current horizontal units and validate
                        P = unit_dict["P"] if unit_dict["P"] else 1
                        unit = unit_dict["unit"] if unit_dict["unit"] else 1
                        
                        try:
                            # Calculate position in inches
                            inches = m * P / unit
                            mm = inches * 25.4

                            # Validate against maximum allowed position (323.074mm or 12.719 inches)
                            if not (0 <= m <= 73264):
                                return f"❬ESC ($❭ set_absolute_horizontal_position_ext(INVALID: position count {m} outside range 0-73264)", pos + 5 + length

                            return f"❬ESC ($❭ set_absolute_horizontal_position_ext({m} = {mm:.2f}mm)", pos + 5 + length
                        except Exception:
                            return f"❬ESC ($❭ set_absolute_horizontal_position_ext(ERROR: calculation failed for m={m})", pos + 5 + length
                    else:
                        return f"❬ESC ($❭ set_absolute_horizontal_position_ext(INVALID args length: {len(args)})", pos + 5 + length
                return f"❬ESC ($❭ set_absolute_horizontal_position_ext(INVALID format: args={args.hex()})", pos + 5 + length
            elif cmd_char == 'd':  # Packet mode
                args = data[pos+5:pos+5+length]
                total = len(args)
                if total:
                    counts = Counter(args)
                    byte, cnt = counts.most_common(1)[0]
                    if cnt == total:
                        desc = f"❬ESC (d❭ packet_mode_data({total} bytes, all 0x{byte:02x})"
                    else:
                        desc = f"❬ESC (d❭ packet_mode_data({total} bytes, 0x{byte:02x} x{cnt})"
                else:
                    desc = "❬ESC (d❭ packet_mode_data(0 bytes)"
                return desc, pos + 5 + length
            elif cmd_char == 'r':  # Select color
                if length == 2:
                    m, n = args[0], args[1]
                    if m == 0x00:
                        color_map = {
                            0x00: "Black",
                            0x01: "Magenta",
                            0x02: "Cyan",
                            0x04: "Yellow"
                        }
                        color = color_map.get(n, None)
                        if color:
                            return f"❬ESC (r❭ select_color({color})", pos + 5 + length
                        else:
                            return f"❬ESC (r❭ select_color(INVALID n=0x{n:02X} - ignored)", pos + 5 + length
                    elif m == 0x01:
                        return f"❬ESC (r❭ m=0x01 is reserved for future use or undefined (n=0x{n:02X})", pos + 5 + length
                    else:
                        return f"❬ESC (r❭ INVALID m=0x{m:02X} - command ignored", pos + 5 + length
                else:
                    return f"❬ESC (r❭ INVALID length={length} (expected 2)", pos + 5 + length

            elif cmd_char == '/':  # Set relative horizontal print position (extended)
                if length == 4 and len(args) == 4:
                    raw = struct.unpack('<i', args)[0]

                    P = unit_dict.get("P", 1)
                    unit = unit_dict.get("unit", 1)
                    mm = raw * P / unit * 25.4

                    return (
                        f"❬ESC (/❭ set_relative_horizontal_position_ext("
                        f"{raw} units = {mm:.3f}mm)", pos + 5 + length
                    )
                else:
                    return f"❬ESC (/❭ INVALID args length: {len(args)}", pos + 5 + length

            elif cmd_char == 'A':  # Unknown command
                return f"UNKNOWN_ESC_(A) args={args.hex()}", pos + 5 + length
            else:
                return f"ESC_({cmd_char}) args={args.hex()}", pos + 5 + length
        elif next_byte == 0x00:  # ESC NUL NUL NUL - Exit remote mode
            if pos + 4 <= len(data) and data[pos+1:pos+4] == b'\x00\x00\x00':
                remote_mode_active = False
                return "Exit Remote Mode", pos + 4
            return f"ESC_00 (incomplete)", pos + 2
        else:
            return f"ESC_{next_byte:02x}", pos + 2
    
    # Main decoding loop
    result = []
    pos = 0
    # Track unit values
    unit_dict = {"P": 12, "V": 12, "H": 4, "unit": 1440}
    # Track remote mode state
    remote_mode_active = False
    current_color = 0  # black
    
    while pos < len(data):
        start = pos
        cmd_str = None

        # PRIORITY: Check for special sequences FIRST, before any other processing

        # Check for Exit Packet Mode sequence - exact 27-byte pattern
        if (pos + 27 <= len(data) and 
            data[pos:pos+27] == b'\x00\x00\x00\x1b\x01@EJL 1284.4\n@EJL     \n'):
            cmd_str = "[@EJL 1284.4@EJL...] Exit Packet Mode"
            pos += 27

        # Check for ENTER_D4 sequence  
        elif (pos + 18 <= len(data) and 
            data[pos:pos+18] == b'\x00\x00\x00\x1b\x01@EJL 1284.4\n@EJL\n@EJL\n'):
            cmd_str = "ENTER_D4"
            pos += 18

        # Now process individual commands
        elif data[pos] == 0x1b:  # ESC
            cmd_str, pos = decode_esc_sequence(pos)

        elif data[pos] == 0x0d and pos + 1 < len(data) and data[pos + 1] == 0x0c:
            cmd_str = "Carriage return + Form feed: buffer printed and sheet ejected."
            pos += 2

        elif data[pos] == 0x0c:  # FF - Form feed
            cmd_str = "form_feed: buffer printed and sheet ejected"
            pos += 1

        elif data[pos] == 0x20:  # SP - Space
            cmd_str = "space"
            pos += 1

        elif data[pos] == 0x00:  # NUL
            # Count consecutive null bytes (but don't double-count packet mode sequences)
            null_start = pos
            while pos < len(data) and data[pos] == 0x00:
                pos += 1
            null_count = pos - null_start
            if null_count > 1:
                cmd_str = f"null_bytes x{null_count}"
            else:
                cmd_str = "null_byte"

        # Group consecutive unknown bytes. ESC (0x1b) and FF (0x0c) break the group
        elif (
            not (remote_mode_active and pos + 4 <= len(data) and 32 <= data[pos] <= 126 and 32 <= data[pos+1] <= 126)
            and data[pos] not in (0x1b, 0x0c)
        ):
            group_start = pos
            while pos < len(data) and (
                data[pos] not in (0x1b, 0x0c)
                and not (remote_mode_active and pos + 4 <= len(data) and 32 <= data[pos] <= 126 and 32 <= data[pos+1] <= 126)
            ):
                pos += 1
            group_bytes = data[group_start:pos]
            if group_bytes:
                # If group_bytes only contains CR and LF, print each as its own command
                if all(b in (0x0d, 0x0a) for b in group_bytes):
                    for b in group_bytes:
                        if b == 0x0d:
                            result.append("carriage_return (X position set to origin)")
                        elif b == 0x0a:
                            result.append("line_feed (X position set to origin, Y increased)")
                    cmd_str = None
                else:
                    if HEXDUMP_AVAILABLE:
                        color_always()
                        cmd_str = f"Bytes: (total {len(group_bytes)})\n" + hexdump(group_bytes, result='return')
                    else:
                        cmd_str = f"Bytes:  (total {len(group_bytes)})\n{group_bytes.hex(' ')}"
            else:
                cmd_str = None

        # Print CR and LF as their own commands if not handled above
        elif data[pos] == 0x0d:
            cmd_str = "carriage_return (X position set to origin)"
            pos += 1
        elif data[pos] == 0x0a:
            cmd_str = "line_feed (X position set to origin, Y increased)"
            pos += 1

        else:
            # Check if this might be a remote command (2 ASCII chars + length) ONLY if in remote mode
            if (remote_mode_active and 
                pos + 4 <= len(data) and 
                32 <= data[pos] <= 126 and 32 <= data[pos+1] <= 126):
                try:
                    cmd_str, new_pos = decode_remote_cmd(pos)
                    pos = new_pos
                except:
                    cmd_str = f"unknown_byte_0x{data[pos]:02x}"
                    pos += 1
            else:
                cmd_str = f"unknown_byte_0x{data[pos]:02x}"
                pos += 1

        # Capture the byte sequence for this command
        byte_seq = data[start:pos]

        # Special handling for large data commands
        if cmd_str and cmd_str.startswith("❬ESC i❭ transfer_raster_image"):
            # Only show header for raster images
            hex_str = byte_seq[:9].hex(" ") if len(byte_seq) >= 9 else byte_seq.hex(" ")
        elif cmd_str and cmd_str.startswith("❬ESC (d❭ packet_mode_data"):
            # Only show header for packet mode data
            header_length = min(5, len(byte_seq))
            hex_str = byte_seq[:header_length].hex(" ")
        else:
            hex_str = byte_seq.hex(" ")

        if cmd_str:
            # For grouped bytes (hexdump), do not prepend hex sequence
            if cmd_str.startswith("Bytes:"):
                result.append(cmd_str)
            else:
                result.append(f"{hex_str} → {cmd_str}")

    return '\n'.join(result)

# Test with data in sample.py
if __name__ == "__main__":
    import argparse
    try:
        from .sample import sample_byte_sequence, parse_hex_lines, sample_output
    except ImportError:
        from sample import sample_byte_sequence, parse_hex_lines, sample_output
    try:
        from .epson_encode import EpsonEscp2
    except ImportError:
        from epson_encode import EpsonEscp2

    parser = argparse.ArgumentParser(description="Decode ESC/P2 commands from binary data.")
    parser.add_argument('--test-pattern', action='store_true', help="Render and display the test pattern")
    parser.add_argument('--file', type=str, help="Path to the binary file to decode")
    parser.add_argument('--show-image', action='store_true', help="Render and display the decoded image")
    parser.add_argument('--dump-image', action='store_true', help="Save the decoded image to disk")
    args = parser.parse_args()

    if args.test_pattern:
        escp2 = EpsonEscp2()
        print(decode_escp2_commands(escp2.test_color_pattern(), show_image=args.show_image, dump_image=args.dump_image))
    elif args.file:
        with open(args.file, "rb") as file:
            data = file.read()
            print(decode_escp2_commands(data, show_image=args.show_image, dump_image=args.dump_image))
    else:
        # Default sample test
        test_bytes = parse_hex_lines(sample_byte_sequence)
        validity_check = decode_escp2_commands(test_bytes)
        decoded = decode_escp2_commands(test_bytes, show_image=args.show_image, dump_image=args.dump_image)
        print("\nDecoded:")
        print(decoded)
        is_valid = validity_check.strip() == sample_output.strip()
        print("\nValidity check:", is_valid)
        if not is_valid:
            # Show the first differing line and its number
            validity_lines = validity_check.strip().splitlines()
            sample_lines = sample_output.strip().splitlines()
            min_len = min(len(validity_lines), len(sample_lines))
            for i in range(min_len):
                if validity_lines[i] != sample_lines[i]:
                    print(f"Difference at line {i+1}:")
                    print(f"Decoded: {validity_lines[i]}")
                    print(f"Sample:  {sample_lines[i]}")
                    break
            else:
                if len(validity_lines) != len(sample_lines):
                    print(f"Output lengths differ: decoded={len(validity_lines)}, sample={len(sample_lines)}")
                    if len(validity_lines) > len(sample_lines):
                        print(f"Extra decoded line {len(sample_lines)+1}: {validity_lines[len(sample_lines)]}")
                    else:
                        print(f"Extra sample line {len(validity_lines)+1}: {sample_lines[len(validity_lines)]}")
