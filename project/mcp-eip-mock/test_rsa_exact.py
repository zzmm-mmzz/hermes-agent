"""
精确模拟前端 RSA 加密
前端的BigInt是LSB-first (digits[0] = 最低16位)
"""
import hashlib
import random
import string

modulus_hex = '00a767ca54db607dc96e5d69c60bf16f3878139ae4ecb4101912da759eaa6ee963aee8efc78a22fe413674480e1dc2168ab36f0153ac8b575e44b3f8fc0621958717ba1aef7a0b977f46a54044e71add31cb5e5534996de016c9a3600de424f6dbd6d0b9d335c26ca3083c53f21f37903cf576ca7fd1ea82f37fe0f1f4c884b3bb'
exponent_hex = '010001'

modulus = int(modulus_hex, 16)
exponent = int(exponent_hex, 16)

# 前端的 biFromHex 实现
# 从 hex 字符串的右边开始，每4个hex字符 = 1个digit（16位）
# digits[0] = 最右边的4个hex字符
# digits[1] = 倒数第2个4字符，以此类推
def bi_from_hex(hex_str):
    hex_str = hex_str.lower()
    if hex_str.startswith('0x'):
        hex_str = hex_str[2:]
    digits = []
    for i in range(len(hex_str), 0, -4):
        start = max(0, i - 4)
        chunk = hex_str[start:i]
        digits.append(int(chunk, 16))
    return digits

mod_digits = bi_from_hex(modulus_hex)
print(f"Modulus digits count: {len(mod_digits)}")
print(f"First few: {mod_digits[:5]}")
print(f"biHighIndex(m): {len(mod_digits) - 1}")  # highest non-zero index
print(f"chunkSize (2 * biHighIndex): {2 * (len(mod_digits) - 1)}")

chunk_size = 2 * (len(mod_digits) - 1)

# 测试数据
test_str = "test"
a = [ord(c) for c in test_str]
while len(a) % chunk_size != 0:
    a.append(0)

print(f"\nTest string char codes: {[c for c in a if c != 0]}")
print(f"Padded length: {len(a)}, chunk_size: {chunk_size}")

# 模拟前端的 block 构建
# for k = i; k < i + chunkSize; j++:
#   block.digits[j] = a[k++]        (low byte)
#   block.digits[j] += a[k++] << 8  (high byte -> 高位)
# 所以 digits[j] = low_byte | (high_byte << 8)
# 其中 low_byte 来自串中位置 k (低地址), high_byte 来自位置 k+1 (高地址)

block_digits = []
j = 0
for k in range(0, chunk_size, 2):
    low_byte = a[k]
    high_byte = a[k + 1] if k + 1 < len(a) else 0
    digit_val = low_byte | (high_byte << 8)
    block_digits.append(digit_val)
    print(f"  digit[{j}] = {low_byte} | ({high_byte} << 8) = {digit_val} (0x{digit_val:04x})")
    j += 1

# 将 digits (LSB first) 转为整数
# digits[0] = 最低16位, digits[1] = 次低16位, ...
block_int = 0
for j, d in enumerate(block_digits):
    block_int |= d << (16 * j)

print(f"\nBlock as int: {hex(block_int)}")
print(f"Block hex (big-endian): {hex(block_int)[2:]}")

# RSA 加密
encrypted = pow(block_int, exponent, modulus)
enc_hex = hex(encrypted)[2:]
if len(enc_hex) % 2:
    enc_hex = '0' + enc_hex

print(f"\nEncrypted hex: {enc_hex}")
print(f"Encrypted block count: 1 (since string < chunkSize)")

# 验证
print(f"\n--- 验证精确的前端 biToHex 实现 ---")
# biToHex 从最高 index 到最低 index
def digit_to_hex(n):
    mask = 0xf
    result = ""
    for i in range(4):
        result += "0123456789abcdef"[n & mask]
        n >>= 4
    return result[::-1]  # reverse

def bi_to_hex(digits):
    """digits: LSB-first list"""
    result = ""
    for i in range(len(digits) - 1, -1, -1):  # from high index to low
        result += digit_to_hex(digits[i])
    # 去掉前导零
    result = result.lstrip('0') or '0'
    return result

# 将 encrypted 转为前端 BigInt (LSB-first digits)
enc_digits = bi_from_hex(enc_hex)
enc_bi_to_hex = bi_to_hex(enc_digits)
print(f"biToHex: {enc_bi_to_hex}")

# 最终结果 = 空格拼接
final = enc_bi_to_hex
print(f"\nFinal result: {final}")
