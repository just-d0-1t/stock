#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 支持从标准输入读取的 XOR+Base64 加/解密
# 密码固定为 rich

import sys, base64

PW = b"rich"

def xor_bytes(data: bytes, pw: bytes) -> bytes:
    return bytes([data[i] ^ pw[i % len(pw)] for i in range(len(data))])

def encrypt(text: str) -> str:
    data = text.encode("utf-8")
    enc = xor_bytes(data, PW)
    return base64.b64encode(enc).decode("utf-8")

def decrypt(b64text: str) -> str:
    data = base64.b64decode(b64text.encode("utf-8"))
    dec = xor_bytes(data, PW)
    return dec.decode("utf-8")

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("encrypt", "decrypt"):
        print("用法: xor_b64_stdin.py encrypt|decrypt < 输入文本", file=sys.stderr)
        sys.exit(1)

    mode = sys.argv[1]
    text = sys.stdin.read().strip()   # 从标准输入读
    if mode == "encrypt":
        print(encrypt(text))
    else:
        print(decrypt(text))

