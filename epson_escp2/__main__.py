#!/usr/bin/env python3
"""
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
"""

import argparse
import sys
import os
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
except ImportError:
    print("Error: PIL (Pillow) is required. Install with: pip install Pillow", file=sys.stderr)
    sys.exit(1)

from .epson_encode import TextToImageConverter, EpsonEscp2
from .__version__ import __version__
try:
    from pyprintlpr import LprClient
    USE_LPR = True
except ImportError:
    USE_LPR = False

def setup_argument_parser() -> argparse.ArgumentParser:
    """Set up command line argument parser."""
    parser = argparse.ArgumentParser(
        prog='epson_escp2',
        description='Convert text and images to ESC/P2 printer format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--dump', action='store_true', help='Dump data')
    parser.add_argument('--preview', action='store_true', help='Show image preview')
    parser.add_argument('--version', action='version', version=f'epson_escp2 {__version__}')
    parser.add_argument('--compress', action='store_true', help='Enable RLE compression')
    parser.add_argument('--max-block-h', action='store_true', help='Max height block', default=128)
    parser.add_argument('--bit-length', type=int, choices=[1, 2, 3], default=3,
                            help='Dot size (1=small, 2=medium, 3=large)')
    parser.add_argument('--threshold', type=int, default=-1,
                            help='Threshold for 1-bit conversion (-1 for auto)')
    parser.add_argument('--font-size', type=int, default=14, help='Font size in points')
    parser.add_argument('--padding', type=int, default=10, help='Page padding in pixels')
    parser.add_argument('--line-spacing', type=int, default=4, help='Line spacing in pixels')

    # Print command (if pyprintlpr is available)
    if USE_LPR:
        parser.add_argument('--host', default=None, help='Printer IP address')
        parser.add_argument('--port', default='LPR', help='Printer port')
        parser.add_argument('--queue', default='PASSTHRU', help='Print queue name')
        parser.add_argument('--label', default='Python Print Job', help='Job label')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Text command
    text_parser = subparsers.add_parser('text', help='Convert text string to ESC/P2')
    text_parser.add_argument('text', help='Text to convert (supports markdown formatting)')
    text_parser.add_argument('-o', '--output', help='Output file (default: stdout as hex)')
    
    # File command
    file_parser = subparsers.add_parser('file', help='Convert text file to ESC/P2')
    file_parser.add_argument('filename', help='Text file to convert')
    file_parser.add_argument('-o', '--output', help='Output file (default: input.escp2)')
    file_parser.add_argument('--font-size', type=int, default=14, help='Font size in points')
    file_parser.add_argument('--padding', type=int, default=10, help='Page padding in pixels')
    file_parser.add_argument('--line-spacing', type=int, default=4, help='Line spacing in pixels')
    file_parser.add_argument('--encoding', default='utf-8', help='File encoding')
    
    # Image command
    image_parser = subparsers.add_parser('image', help='Convert image to ESC/P2')
    image_parser.add_argument('filename', help='Image file to convert')
    image_parser.add_argument('-o', '--output', help='Output file (default: input.escp2)')

    # Demo command
    demo_parser = subparsers.add_parser('demo', help='Generate demo output')
    demo_parser.add_argument('-o', '--output', help='Output file (default: demo.escp2)')
    
    return parser


def handle_text_command(args) -> int:
    """Handle text conversion command."""
    try:
        converter = TextToImageConverter(font_size=args.font_size)
        image = converter.convert_to_image(
            args.text.strip(),
            padding=args.padding,
            line_spacing=args.line_spacing
        )
        if args.preview:
            converter.preview(image)
        epson = EpsonEscp2(
            bit_length=args.bit_length,
            compress=args.compress,
            max_block_h=args.max_block_h
        )
        tri = epson.image_to_tri(image)
        escp2_data = epson.tri_to_escp2(tri)
        
        if args.output:
            with open(args.output, 'wb') as f:
                f.write(escp2_data)
            print(f"ESC/P2 data written to {args.output} ({len(escp2_data)} bytes)")

        if USE_LPR and args.host:
            with LprClient(args.host, port=args.port, queue=args.queue, label=args.label) as lpr:
                lpr.send(escp2_data)
        if args.dump:
            print(escp2_data)

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def handle_file_command(args) -> int:
    """Handle file conversion command."""
    try:
        if not os.path.exists(args.filename):
            print(f"Error: File '{args.filename}' not found", file=sys.stderr)
            return 1
        
        with open(args.filename, 'r', encoding=args.encoding) as f:
            text = f.read()

        converter = TextToImageConverter(font_size=args.font_size)
        image = converter.convert_to_image(
            text,
            padding=args.padding,
            line_spacing=args.line_spacing
        )
        if args.preview:
            converter.preview(image)
        epson = EpsonEscp2(
            bit_length=args.bit_length,
            compress=args.compress,
            max_block_h=args.max_block_h
        )
        tri = epson.image_to_tri(image)
        escp2_data = epson.tri_to_escp2(tri)
        
        if args.output:
            with open(args.output, 'wb') as f:
                f.write(escp2_data)
            print(f"ESC/P2 data written to {args.output} ({len(escp2_data)} bytes)")

        if USE_LPR and args.host:
            with LprClient(args.host, port=args.port, queue=args.queue, label=args.label) as lpr:
                lpr.send(escp2_data)
        if args.dump:
            print(escp2_data)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def handle_image_command(args) -> int:
    """Handle image conversion command."""
    try:
        if not os.path.exists(args.filename):
            print(f"Error: Image file '{args.filename}' not found", file=sys.stderr)
            return 1
        
        image = Image.open(args.filename)
        
        if args.preview:
            converter = TextToImageConverter()
            converter.preview(image)
        epson = EpsonEscp2(
            bit_length=args.bit_length,
            compress=args.compress,
            max_block_h=args.max_block_h
        )
        tri = epson.image_to_tri(image)
        escp2_data = epson.tri_to_escp2(tri)
        
        if args.output:
            with open(args.output, 'wb') as f:
                f.write(escp2_data)
            print(f"ESC/P2 data written to {args.output} ({len(escp2_data)} bytes)")

        if USE_LPR and args.host:
            with LprClient(args.host, port=args.port, queue=args.queue, label=args.label) as lpr:
                lpr.send(escp2_data)
        if args.dump:
            print(escp2_data)

        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def handle_demo_command(args) -> int:
    """Handle demo generation command."""
    demo_text = """
Introduction
  - First level
    - __Indented underlined__
    - **Indented bold**
    - *underlined*
    - ``Fixed width code``
    - ```Bold fixed width```
  * Second level bullet
Conclusion

This is a paragraph with ``inline code``, ```bold monospace```, and **bold text**.

| Name     | Age | Role         |
|----------|-----|--------------|
| Alice    | 30  | **Engineer** |
| __Bob__  | 25  | ``Developer``|
| Charlie  | 35  | ```Manager```|

Generated by epson_escp2 module v""" + __version__

    try:
        converter = TextToImageConverter(font_size=args.font_size)
        image = converter.convert_to_image(
            demo_text,
            padding=args.padding,
            line_spacing=args.line_spacing
        )
        if args.preview:
            converter.preview(image)
        epson = EpsonEscp2(
            bit_length=args.bit_length,
            compress=args.compress,
            max_block_h=args.max_block_h
        )
        tri = epson.image_to_tri(image)
        escp2_data = epson.tri_to_escp2(tri)
        
        if args.output:
            with open(args.output, 'wb') as f:
                f.write(escp2_data)
            print(f"ESC/P2 data written to {args.output} ({len(escp2_data)} bytes)")

        if USE_LPR and args.host:
            with LprClient(args.host, port=args.port, queue=args.queue, label=args.label) as lpr:
                lpr.send(escp2_data)
        if args.dump:
            print(escp2_data)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point for command line interface."""
    parser = setup_argument_parser()
    
    if len(sys.argv) == 1:
        parser.print_help()
        return 1
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Route to appropriate handler
    handlers = {
        'text': handle_text_command,
        'file': handle_file_command,
        'image': handle_image_command,
        'demo': handle_demo_command,
    }
    
    handler = handlers.get(args.command)
    if handler:
        return handler(args)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
