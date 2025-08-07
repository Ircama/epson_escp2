import re

sample_byte_sequence = """
# Example of bytes sequence (here represented in hex and splitted into command lines with some description after #):

00 00 00 1b 01 40 45 4a 4c 20 31 32 38 34 2e 34 0a 40 45 4a 4c 20 20 20 20 20 0a # Exit Packet Mode
1b 40 # Initialize Printer
1b 40 # Initialize Printer
1b 28 52 08 00 00 52 45 4d 4f 54 45 31 # Enter Remote Mode
54 49 08 00 00 07 e9 08 05 06 1c 38 # TI remote_cmd...
4a 53 04 00 00 00 00 00 # JS remote_cmd...
4a 48 0c 00 00 01 79 a1 1c 29 00 15 5d 1b 6d 3b # JH remote_cmd...
48 44 03 00 00 03 02 # HD remote_cmd...
1b 00 00 00 # Exit Remote Mode
1b 28 64 ff 7f
00 * 32767 # repeated 32767 times
1b 28 64 ff 7f
00 * 32767 # repeated 32767 times
1b 28 64 ff 7f
00 * 32767 # repeated 32767 times
1b 28 64 ff 7f
00 * 32767 # repeated 32767 times
00 00 00 1b 01 40 45 4a 4c 20 31 32 38 34 2e 34 0a 40 45 4a 4c 20 20 20 20 20 0a # Exit Packet Mode
1b 40 # Initialize Printer
1b 40 # Initialize Printer
1b 28 52 08 00 00 52 45 4d 4f 54 45 31 # Enter Remote Mode
54 49 08 00 00 07 e9 08 05 06 1c 38 # TI remote_cmd...
50 4d 02 00 00 00 # PM remote_cmd...
44 50 02 00 00 00 # DP remote_cmd...
53 4e 01 00 00 # SN remote_cmd...
4d 49 04 00 00 01 00 00 # MI remote_cmd...
55 53 03 00 00 00 01 # US remote_cmd...
55 53 03 00 00 01 00 # US remote_cmd...
55 53 03 00 00 02 00 # US remote_cmd...
55 53 03 00 00 04 00 # US remote_cmd...
55 53 03 00 00 05 00 # US remote_cmd...
46 50 03 00 00 00 00 # FP remote_cmd...
50 50 03 00 00 01 ff # PP remote_cmd...
1b 00 00 00 # Exit Remote Mode
1b 28 41 09 00 00 00 00 00 00 00 00 00 00 # UNKNOWN


1b 28 47 01 00 01 # Select graphics mode
1b 28 55 05 00 0c 0c 04 a0 05 # ESC (U = Sets units P=12(120), V=12(120), H=4(360), mL mH - m=1440
1b 55 00 # selects bi-directional printing
1b 28 69 01 00 00 # no MicroWeave printing mode
1b 28 43 04 00 7b 05 00 00 # Set page length - ESC (C nL nH m1 m2 m3 m4 = 1403 -> 1403 * 12 / 1440 * 2,54 = 29,7 cm = A4
1b 28 63 08 00 81 ff ff ff c3 05 00 00 # Set page format (ext) - ESC (c nL nH t1 t2 t3 t4 b1 b2 b3 b4 = t=0xFFFFFF81=4294967169 (o -127),b=0x000005C3=1475
1b 28 53 08 00 e0 03 00 00 7b 05 00 00 # paper width=992 paper length=1403 -> 992 * 12 / 1440 *2,54 = 21cm A4 -> 1403 * 12 / 1440 * 2,54 = 29,7 cm = A4
1b 28 4b 02 00 00 01 # monochrome
1b 28 4b 02 00 01 01 # monochrome (2nd mode)
1b 28 44 04 00 40 38 78 28 # Set the raster image resolution; r=14400 v=120 h=40; Vertical resolution : 14400/120 = 120 dpi; Horizontal resolution = 14400/40=360 dpi
1b 28 6d 01 00 11 # ESC (m - Set Print method ID 11 = Fast Eco
1b 28 65 02 00 00 10 # Selects dot size ESC (e nL nH m d - d=10 (economy, unknown)
1b 28 76 04 00 9d 00 00 00 # Set relative vertical print position(extended) m=157
1b 28 24 04 00 20 00 00 00 # Set absolute horizontal print position = m=32
1b 69 00 01 02 1e 00 80 00 # Transfer Raster image: "ESC i r c b nL nH mL mH"; H=30 V=128; 128 rows, 30 bytes each one of 2 bits -> 15 bytes of 1 bit, 15x8 bit = 120
# following bytestream; Total numbers of data bytes, according to the following formula: (nH*256 + nL) * (mH*256 + mL) = 30 * 128 = 3840 bytes broken by 0d 0c, total of 529 graphic payload bytes

07 00 00 0f ff ff
f0 00 03 fc ff 05 fc 00 00 03 ff ff fc 00 05 3f
ff ff c0 00 00 06 00 ff ff c0 00 0f c0 fe 00 01
ff f0 fd 00 02 03 f0 3f fd 00 06 0f ff 00 0f ff
00 00 02 00 ff f0 fa 00 01 ff f0 fd 00 03 03 f0
3f fc fe 00 06 0f c0 00 00 3f fc 00 01 3f fc f9
00 01 ff f0 fd 00 0d ff f0 3f fc 00 00 03 ff c0
00 00 3f fc 00 01 3f fc f9 00 01 ff f0 fd 00 0d
fc 00 00 fc 00 00 03 ff c0 00 00 3f fc 00 01 3f
fc f9 00 01 ff f0 fe 00 0e 3f fc 00 00 ff f0 00
03 ff c0 00 00 3f fc 00 01 3f fc f9 00 01 ff f0
fe 00 0e 3f fc 00 00 ff f0 00 03 ff c0 00 00 3f
fc 00 01 3f fc f9 00 01 ff f0 fe 00 00 3f fd ff
09 f0 00 03 ff c0 00 00 3f fc 00 02 00 ff f0 fa
00 05 ff f0 00 00 0f ff fe 00 0a 03 ff c0 03 ff
c0 00 00 3f 00 00 06 00 ff ff c0 00 0f c0 fe 00
05 ff f0 00 00 0f ff fe 00 0a 03 ff c0 00 0f ff
00 0f ff 00 00 07 00 00 0f ff ff f0 00 03 fc ff
02 fc 0f c0 fd 00 09 0f c0 00 00 3f ff ff c0 00
00 e3 00 e3 00 e3 00 e3 00 e3 00 e3 00 e3 00 e3

00 e3 00 e3 00 e3 00 e3 00 e3 00 e3 00 e3 00 e3 * 13 # repeated 13 times

00 e3 00 e3 00 e3 00 e3 00 e3 00

# end of payload (the virtually remaining ones, not included, are 00)

0d 0c # form feed
1b 40 # Initialize Printer
1b 28 52 08 00 00 52 45 4d 4f 54 45 31 # Enter Remote Mode
4c 44 00 00 # LD remote_cmd
1b 00 00 00 # Exit Remote Mode
1b 40 # Initialize Printer
1b 28 52 08 00 00 52 45 4d 4f 54 45 31 # Enter Remote Mode
4c 44 00 00 # TE remote_cmd
4a 45 01 00 00 # JE remote_cmd
1b 00 00 00 # Exit Remote Mode
"""

sample_output = """
00 00 00 1b 01 40 45 4a 4c 20 31 32 38 34 2e 34 0a 40 45 4a 4c 20 20 20 20 20 0a → [@EJL 1284.4@EJL...] Exit Packet Mode
1b 40 → ❬ESC @❭ Initialize Printer
1b 40 → ❬ESC @❭ Initialize Printer
1b 28 52 08 00 00 52 45 4d 4f 54 45 31 → ❬...REMOTE1❭ Enter Remote Mode
54 49 08 00 00 07 e9 08 05 06 1c 38 → TI set_timer remote_cmd (2025-08-05 06:28:56)
4a 53 04 00 00 00 00 00 → JS (job start) remote_cmd: 00000000
4a 48 0c 00 00 01 79 a1 1c 29 00 15 5d 1b 6d 3b → JH (Job name set) remote_cmd (type=Product ID, job_id=0x79a11c29, name=00155d1b6d3b)
48 44 03 00 00 03 02 → HD remote_cmd (args: 000302)
1b 00 00 00 → Exit Remote Mode
1b 28 64 ff 7f → ❬ESC (d❭ packet_mode_data(32767 bytes, all 0x00)
1b 28 64 ff 7f → ❬ESC (d❭ packet_mode_data(32767 bytes, all 0x00)
1b 28 64 ff 7f → ❬ESC (d❭ packet_mode_data(32767 bytes, all 0x00)
1b 28 64 ff 7f → ❬ESC (d❭ packet_mode_data(32767 bytes, all 0x00)
00 00 00 1b 01 40 45 4a 4c 20 31 32 38 34 2e 34 0a 40 45 4a 4c 20 20 20 20 20 0a → [@EJL 1284.4@EJL...] Exit Packet Mode
1b 40 → ❬ESC @❭ Initialize Printer
1b 40 → ❬ESC @❭ Initialize Printer
1b 28 52 08 00 00 52 45 4d 4f 54 45 31 → ❬...REMOTE1❭ Enter Remote Mode
54 49 08 00 00 07 e9 08 05 06 1c 38 → TI set_timer remote_cmd (2025-08-05 06:28:56)
50 4d 02 00 00 00 → PM remote_cmd (args: 0000)
44 50 02 00 00 00 → DP (Select Duplex Printing) remote_cmd - Duplex mode: Duplex mode off
53 4e 01 00 00 → SN (Paper Feed Setup) remote_cmd: valid
4d 49 04 00 00 01 00 00 → MI Select paper media remote_cmd: 1 (360dpi Ink Jet Paper, A4)
55 53 03 00 00 00 01 → US (User Setting) remote_cmd - Bottom margin setting: Max
55 53 03 00 00 01 00 → US (User Setting) remote_cmd - Unknown command 00 01 00
55 53 03 00 00 02 00 → US (User Setting) remote_cmd - Unknown command 00 02 00
55 53 03 00 00 04 00 → US (User Setting) remote_cmd - Economy print setting: Fast-Mode
55 53 03 00 00 05 00 → US (User Setting) remote_cmd - Load mode setting: Fast-Mode (Default)
46 50 03 00 00 00 00 → FP set_horizontal_print_position remote_cmd (0 units = 0.000mm) (standard position)
50 50 03 00 00 01 ff → PP (Select paper path) remote_cmd - Unknown command
1b 00 00 00 → Exit Remote Mode
1b 28 41 09 00 00 00 00 00 00 00 00 00 00 → UNKNOWN_ESC_(A) args=000000000000000000
1b 28 47 01 00 01 → ❬ESC (G❭ select_graphics_mode (m=0x01: standard)
1b 28 55 05 00 0c 0c 04 a0 05 → ❬ESC (U❭ set_units(P=12, V=12, H=4, unit=1440)
1b 55 00 → ❬ESC U❭ select_bidirectional_printing
1b 28 69 01 00 00 → ❬ESC (i❭ deselect microweave mode
1b 28 43 04 00 7b 05 00 00 → ❬ESC (C❭ set_page_length(1403 = 29.7cm)
1b 28 63 08 00 81 ff ff ff c3 05 00 00 → ❬ESC (c❭ set_page_format_extended(top=-127=-26.9mm, bottom=1475=312.2mm)
1b 28 53 08 00 e0 03 00 00 7b 05 00 00 → ❬ESC (S❭ set_paper_size(992x1403 = 21.0x29.7cm)
1b 28 4b 02 00 00 01 → ❬ESC (K❭ select_monochrome_mode
1b 28 4b 02 00 01 01 → ❬ESC (K❭ select_monochrome_mode (alternate format)
1b 28 44 04 00 40 38 78 28 → ❬ESC (D❭ set_raster_resolution(r=14400, v=120, h=40) Vertical resolution: 14400/120=120 dpi; Horizontal resolution: 14400/40=360 dpi
1b 28 6d 01 00 11 → ❬ESC (m❭ set_print_method(fast_eco)
1b 28 65 02 00 00 10 → ❬ESC (e❭ select_dot_size(economy)
1b 28 76 04 00 9d 00 00 00 → ❬ESC (v❭ set_relative_vertical_position_ext(157 = 33.23mm)
1b 28 24 04 00 20 00 00 00 → ❬ESC ($❭ set_absolute_horizontal_position_ext(32 = 6.77mm)
1b 69 00 01 02 1e 00 80 00 → ❬ESC i❭ transfer_raster_image(black, compression=Run Length Encoding, bit_depth=2 bits/pixel, 128 rows, 30 bytes/row, uncompressed 3840 bytes, 157 non-zero). Compressed 529 bytes; count of sequences: {'00': 14925, '01': 0, '10': 0, '11': 435}
0d 0c → Carriage return + Form feed: buffer printed and sheet ejected.
1b 40 → ❬ESC @❭ Initialize Printer
1b 28 52 08 00 00 52 45 4d 4f 54 45 31 → ❬...REMOTE1❭ Enter Remote Mode
4c 44 00 00 → LD (Load Power-On Default NVR into RAM) remote_cmd: valid
1b 00 00 00 → Exit Remote Mode
1b 40 → ❬ESC @❭ Initialize Printer
1b 28 52 08 00 00 52 45 4d 4f 54 45 31 → ❬...REMOTE1❭ Enter Remote Mode
4c 44 00 00 → LD (Load Power-On Default NVR into RAM) remote_cmd: valid
4a 45 01 00 00 → JE (End job) remote_cmd: valid
1b 00 00 00 → Exit Remote Mode
"""

def parse_hex_lines(text: str) -> bytes:
    result = bytearray()
    last_line_bytes = bytearray()

    for line in text.splitlines():
        # Remove comment
        line = line.split('#', 1)[0].strip()
        if not line:
            continue  # Skip empty lines

        # Split tokens
        tokens = line.split()
        if not tokens:
            continue

        try:
            if '*' in tokens:
                star_index = tokens.index('*')
                hex_tokens = tokens[:star_index]
                repeat_count = int(tokens[star_index + 1])
            elif re.match(r'.*\*\s*\d+$', line):
                # Handles e.g. "00 01 02 * 10" even if * is not a separate token
                *hex_tokens, star, repeat_str = re.split(r'\s+', line)
                if star != '*':
                    raise ValueError
                repeat_count = int(repeat_str)
            else:
                hex_tokens = tokens
                repeat_count = 1
        except Exception as e:
            raise ValueError(f"Malformed repetition line: '{line}'") from e

        try:
            line_bytes = bytearray(int(h, 16) for h in hex_tokens)
        except ValueError as e:
            raise ValueError(f"Invalid hex data on line: '{line}'") from e

        result.extend(line_bytes * repeat_count)
        last_line_bytes = line_bytes

    return bytes(result)

if __name__ == '__main__':
    output_bytes = parse_hex_lines(sample_byte_sequence)
    print(output_bytes)
    print(f"Total bytes: {len(output_bytes)}")
