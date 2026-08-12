"""测试 RSA 加密核心逻辑"""
modulus_hex = '00a767ca54db607dc96e5d69c60bf16f3878139ae4ecb4101912da759eaa6ee963aee8efc78a22fe413674480e1dc2168ab36f0153ac8b575e44b3f8fc0621958717ba1aef7a0b977f46a54044e71add31cb5e5534996de016c9a3600de424f6dbd6d0b9d335c26ca3083c53f21f37903cf576ca7fd1ea82f37fe0f1f4c884b3bb'
exponent_hex = '010001'

modulus = int(modulus_hex, 16)
exponent = int(exponent_hex, 16)

print(f'Modulus bits: {modulus.bit_length()}')
bi_high = (modulus.bit_length() + 15) // 16 - 1
print(f'biHighIndex(m): {bi_high}')
chunk_size = bi_high * 2
print(f'chunkSize: {chunk_size}')

# 测试短字符串
test = 'test'
a = [ord(c) for c in test]
# 补齐
while len(a) % chunk_size != 0:
    a.append(0)

print(f'array length: {len(a)}, chunk_size: {chunk_size}')

# 构建 block - 模拟前端
block_int2 = 0
for k in range(0, chunk_size, 2):
    val = a[k]
    if k + 1 < len(a):
        val += a[k + 1] << 8
    block_int2 = (block_int2 << 16) | val

print(f'block_int2: {hex(block_int2)}')

encrypted = pow(block_int2, exponent, modulus)
hex_str = hex(encrypted)[2:]
if len(hex_str) % 2:
    hex_str = '0' + hex_str
print(f'encrypted ({len(hex_str)//2} bytes): {hex_str[:100]}')
print(f'encrypted hex: {hex_str}')
