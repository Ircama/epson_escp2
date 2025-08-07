def rle_decode(bytestream, expected_bytes):
    """
    Decode a bytestream using Run-Length Encoding compression format until expected_bytes are decoded.
    Returns a tuple: (decoded_bytes, end_pos)
    Args:
        bytestream: bytes object or list of integers representing the compressed data
        expected_bytes: int, number of bytes to decode
    Returns:
        (bytes: decompressed data, int: position in bytestream after decoding)
    """
    if isinstance(bytestream, str):
        # Convert hex string to bytes
        bytestream = bytes.fromhex(bytestream)
    elif isinstance(bytestream, list):
        # Convert list of integers to bytes
        bytestream = bytes(bytestream)
    
    result = bytearray()
    i = 0
    
    while i < len(bytestream) and len(result) < expected_bytes:
        counter = bytestream[i]
        i += 1
        
        if 0 <= counter <= 127:
            # Literal data: copy the next (counter + 1) bytes
            literal_length = counter + 1
            if i + literal_length > len(bytestream):
                print(bytes(result).hex(" "))
                raise ValueError(f"Insufficient data: expected {literal_length} bytes at position {i} instead of {len(bytestream)}")
            take = min(literal_length, expected_bytes - len(result))
            result.extend(bytestream[i:i + take])
            i += literal_length
            
        elif 128 <= counter <= 255:
            # Compressed data: repeat the next byte (257 - counter) times
            if i >= len(bytestream):
                print(bytes(result).hex(" "))
                raise ValueError(f"Insufficient data: expected data byte at position {i}")
            
            repeat_byte = bytestream[i]
            repeat_count = 257 - counter
            take = min(repeat_count, expected_bytes - len(result))
            result.extend([repeat_byte] * take)
            i += 1
            
        else:
            # This should never happen since counter is a byte (0-255)
            raise ValueError(f"Invalid counter value: {counter} at position {i-1}")
    
    return bytes(result), i

def rle_encode(data):
    """
    Encode data using Run-Length Encoding compression format.
    
    Args:
        data: bytes object to compress
    
    Returns:
        bytes: compressed data using RLE format
    """
    if isinstance(data, str):
        data = data.encode('utf-8')
    elif isinstance(data, list):
        data = bytes(data)
    
    result = bytearray()
    i = 0
    
    while i < len(data):
        current_byte = data[i]
        
        # Count consecutive identical bytes (allow up to 129)
        run_length = 1
        while (i + run_length < len(data) and 
               data[i + run_length] == current_byte and 
               run_length < 129):
            run_length += 1
        
        if run_length >= 2:
            counter = 257 - run_length
            result.append(counter)
            result.append(current_byte)
            i += run_length
        else:
            literal_start = i
            while i < len(data):
                if i + 1 < len(data):
                    next_run = 1
                    while (i + next_run < len(data) and 
                           data[i + next_run] == data[i] and 
                           next_run < 129):
                        next_run += 1
                    if next_run >= 2:
                        break
                i += 1
                if i - literal_start >= 128:
                    break
            
            literal_length = i - literal_start
            if literal_length > 0:
                result.append(literal_length - 1)
                result.extend(data[literal_start:i])
    
    return bytes(result)

def dot_size_decode(encoded: bytes) -> tuple:
    """
    For each two-bit group in the input bitstream, emits one bit:
    1 if either of the two is 1, else 0.
    Input length must be even (so the total bit‐count is a multiple of 16,
    yielding a whole number of output bytes).
    Returns:
        (decoded_bytes, counts_dict)
        counts_dict: dict with keys '00', '01', '10', '11' and their counts
    """
    # unpack to a flat list of bits (MSB first)
    bits = [
        (b >> (7 - i)) & 1
        for b in encoded
        for i in range(8)
    ]
    # count two-bit sequences
    seq_counts = {'00': 0, '01': 0, '10': 0, '11': 0}
    for i in range(0, len(bits), 2):
        pair = (bits[i], bits[i+1])
        key = f"{pair[0]}{pair[1]}"
        if key in seq_counts:
            seq_counts[key] += 1
    # combine every two bits with OR
    out_bits = [
        bits[i] | bits[i + 1]
        for i in range(0, len(bits), 2)
    ]
    # pack into bytes
    out = bytearray(len(out_bits) // 8)
    for byte_index in range(len(out)):
        byte = 0
        base = byte_index * 8
        for bit_index in range(8):
            byte |= (out_bits[base + bit_index] << (7 - bit_index))
        out[byte_index] = byte
    return bytes(out), seq_counts

def dot_size_decode_ext(encoded, bit_length):
    """
    Inverse of dot_size
    """
    if len(encoded) % 2 != 0:
        raise ValueError("encoded length must be an even number")
    
    if bit_length == 1:
        nibble_map = [
            0b00000000, 0b00000001, 0b00000100, 0b00000101,
            0b00010000, 0b00010001, 0b00010100, 0b00010101,
            0b01000000, 0b01000001, 0b01000100, 0b01000101,
            0b01010000, 0b01010001, 0b01010100, 0b01010101,
        ]
    elif bit_length == 2:
        nibble_map = [
            0b00000000, 0b00000010, 0b00001000, 0b00001010,
            0b00100000, 0b00100010, 0b00101000, 0b00101010,
            0b10000000, 0b10000010, 0b10001000, 0b10001010,
            0b10100000, 0b10100010, 0b10101000, 0b10101010,
        ]
    else:  # bit_length == 3
        nibble_map = [
            0b00000000, 0b00000011, 0b00001100, 0b00001111,
            0b00110000, 0b00110011, 0b00111100, 0b00111111,
            0b11000000, 0b11000011, 0b11001100, 0b11001111,
            0b11110000, 0b11110011, 0b11111100, 0b11111111,
        ]
    
    reverse_map = {val: idx for idx, val in enumerate(nibble_map)}
    
    decoded = bytearray(len(encoded) // 2)
    for i in range(0, len(encoded), 2):
        hi = encoded[i]
        lo = encoded[i+1]
        if hi not in reverse_map or lo not in reverse_map:
            raise ValueError(f"Invalid encoded byte at positions {i}, {i+1}")
        upper_nibble = reverse_map[hi]
        lower_nibble = reverse_map[lo]
        decoded[i//2] = (upper_nibble << 4) | lower_nibble
    
    return bytes(decoded)

def dot_size_encode(bytestream, bit_length):
    """
    Create byte sequence according to bit length
    """
    # Create lookup table for 4-bit values (16 entries)
    # Each 4 input bits become 8 output bits (1 byte)
    if bit_length == 1:
        # 0->00, 1->01
        nibble_map = [
            0b00000000,  # 0000 -> 00000000
            0b00000001,  # 0001 -> 00000001
            0b00000100,  # 0010 -> 00000100
            0b00000101,  # 0011 -> 00000101
            0b00010000,  # 0100 -> 00010000
            0b00010001,  # 0101 -> 00010001
            0b00010100,  # 0110 -> 00010100
            0b00010101,  # 0111 -> 00010101
            0b01000000,  # 1000 -> 01000000
            0b01000001,  # 1001 -> 01000001
            0b01000100,  # 1010 -> 01000100
            0b01000101,  # 1011 -> 01000101
            0b01010000,  # 1100 -> 01010000
            0b01010001,  # 1101 -> 01010001
            0b01010100,  # 1110 -> 01010100
            0b01010101,  # 1111 -> 01010101
        ]
    elif bit_length == 2:
        # 0->00, 1->10
        nibble_map = [
            0b00000000,  # 0000 -> 00000000
            0b00000010,  # 0001 -> 00000010
            0b00001000,  # 0010 -> 00001000
            0b00001010,  # 0011 -> 00001010
            0b00100000,  # 0100 -> 00100000
            0b00100010,  # 0101 -> 00100010
            0b00101000,  # 0110 -> 00101000
            0b00101010,  # 0111 -> 00101010
            0b10000000,  # 1000 -> 10000000
            0b10000010,  # 1001 -> 10000010
            0b10001000,  # 1010 -> 10001000
            0b10001010,  # 1011 -> 10001010
            0b10100000,  # 1100 -> 10100000
            0b10100010,  # 1101 -> 10100010
            0b10101000,  # 1110 -> 10101000
            0b10101010,  # 1111 -> 10101010
        ]
    else:  # bit_length == 3
        # 0->00, 1->11
        nibble_map = [
            0b00000000,  # 0000 -> 00000000
            0b00000011,  # 0001 -> 00000011
            0b00001100,  # 0010 -> 00001100
            0b00001111,  # 0011 -> 00001111
            0b00110000,  # 0100 -> 00110000
            0b00110011,  # 0101 -> 00110011
            0b00111100,  # 0110 -> 00111100
            0b00111111,  # 0111 -> 00111111
            0b11000000,  # 1000 -> 11000000
            0b11000011,  # 1001 -> 11000011
            0b11001100,  # 1010 -> 11001100
            0b11001111,  # 1011 -> 11001111
            0b11110000,  # 1100 -> 11110000
            0b11110011,  # 1101 -> 11110011
            0b11111100,  # 1110 -> 11111100
            0b11111111,  # 1111 -> 11111111
        ]
    
    result = bytearray(len(bytestream) * 2)
    
    for i, byte_val in enumerate(bytestream):
        # Process upper and lower nibbles
        upper_nibble = (byte_val >> 4) & 0x0F
        lower_nibble = byte_val & 0x0F
        
        result[i * 2] = nibble_map[upper_nibble]
        result[i * 2 + 1] = nibble_map[lower_nibble]
    
    return bytes(result)
