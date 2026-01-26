#!/usr/bin/env python3
"""
LawPro Fast Converter - Key Vault
===================================
Upstage API 키를 암호화하여 내장합니다.
역설계를 어렵게 하기 위해 다중 레이어 난독화를 적용합니다.

보안 레이어:
1. Base64 인코딩
2. XOR 암호화 (동적 키)
3. 바이트 셔플
4. AES-like 치환
"""

import base64
import hashlib
import os
import json
from pathlib import Path


# ============================================================
# 난독화 상수 (빌드 시 생성)
# ============================================================
# XOR 키 시드 (해시로 확장)
_KS = b"LawPro2024SecureVault"
_SALT = b"upstage_ocr_engine_v1"

# 셔플 시드
_SHUFFLE_SEED = 42


def _derive_key(seed: bytes, length: int) -> bytes:
    """시드에서 지정 길이의 키 파생"""
    key = b""
    counter = 0
    while len(key) < length:
        h = hashlib.sha256(seed + counter.to_bytes(4, 'big')).digest()
        key += h
        counter += 1
    return key[:length]


def _xor_encrypt(data: bytes, key: bytes) -> bytes:
    """XOR 암호화/복호화"""
    extended_key = _derive_key(key, len(data))
    return bytes(a ^ b for a, b in zip(data, extended_key))


def _shuffle_bytes(data: bytes, reverse: bool = False) -> bytes:
    """바이트 위치 셔플/언셔플"""
    import random
    n = len(data)
    indices = list(range(n))
    rng = random.Random(_SHUFFLE_SEED)
    rng.shuffle(indices)

    result = bytearray(n)
    if reverse:
        for i, idx in enumerate(indices):
            result[idx] = data[i]
    else:
        for i, idx in enumerate(indices):
            result[i] = data[idx]
    return bytes(result)


def _substitute(data: bytes, reverse: bool = False) -> bytes:
    """바이트 치환 (S-Box)"""
    sbox = list(range(256))
    rng_sub = __import__('random').Random(0xDEAD)
    rng_sub.shuffle(sbox)

    if reverse:
        inv_sbox = [0] * 256
        for i, v in enumerate(sbox):
            inv_sbox[v] = i
        return bytes(inv_sbox[b] for b in data)
    else:
        return bytes(sbox[b] for b in data)


def encrypt_key(api_key: str) -> str:
    """
    API 키를 암호화하여 문자열로 반환

    Args:
        api_key: 원본 API 키

    Returns:
        암호화된 문자열 (base64)
    """
    data = api_key.encode('utf-8')

    # 레이어 1: XOR 암호화
    data = _xor_encrypt(data, _KS + _SALT)

    # 레이어 2: 바이트 치환
    data = _substitute(data)

    # 레이어 3: 바이트 셔플
    data = _shuffle_bytes(data)

    # 레이어 4: 2차 XOR
    secondary_key = hashlib.sha512(_KS + _SALT + b"layer2").digest()
    data = _xor_encrypt(data, secondary_key)

    # Base64 인코딩
    return base64.b64encode(data).decode('ascii')


def decrypt_key(encrypted: str) -> str:
    """
    암호화된 키를 복호화

    Args:
        encrypted: 암호화된 문자열 (base64)

    Returns:
        원본 API 키
    """
    data = base64.b64decode(encrypted.encode('ascii'))

    # 레이어 4: 2차 XOR 복호화
    secondary_key = hashlib.sha512(_KS + _SALT + b"layer2").digest()
    data = _xor_encrypt(data, secondary_key)

    # 레이어 3: 바이트 언셔플
    data = _shuffle_bytes(data, reverse=True)

    # 레이어 2: 바이트 역치환
    data = _substitute(data, reverse=True)

    # 레이어 1: XOR 복호화
    data = _xor_encrypt(data, _KS + _SALT)

    return data.decode('utf-8')


# ============================================================
# 내장 키 저장소
# ============================================================
# 빌드 시 CI/CD에서 이 값이 주입됩니다
# PLACEHOLDER는 빌드 파이프라인에서 실제 암호화된 키로 대체됩니다
_EMBEDDED_UPSTAGE_KEY = ""  # 빌드 시 주입


def get_embedded_upstage_key() -> str:
    """
    내장된 Upstage API 키를 반환

    우선순위:
    1. admin_config.json (개발 환경)
    2. 환경 변수 UPSTAGE_API_KEY
    3. 내장 암호화 키

    Returns:
        Upstage API 키 (없으면 빈 문자열)
    """
    # 1. admin_config.json에서 로드 (개발 환경)
    config_paths = [
        Path(os.path.dirname(os.path.abspath(__file__))) / "admin_config.json",
        Path.home() / ".lawpro" / "admin_config.json"
    ]
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                key = config.get('upstage_api_key', '')
                if key:
                    return key
            except Exception:
                pass

    # 2. 환경 변수
    env_key = os.environ.get('UPSTAGE_API_KEY', '')
    if env_key:
        return env_key

    # 3. 내장 암호화 키
    if _EMBEDDED_UPSTAGE_KEY:
        try:
            return decrypt_key(_EMBEDDED_UPSTAGE_KEY)
        except Exception:
            pass

    return ""


# ============================================================
# CLI: 키 암호화 유틸리티
# ============================================================
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("사용법:")
        print("  python key_vault.py encrypt <api_key>  - API 키 암호화")
        print("  python key_vault.py decrypt <encrypted> - 암호화된 키 복호화")
        print("  python key_vault.py test               - 암호화/복호화 테스트")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "encrypt" and len(sys.argv) > 2:
        api_key = sys.argv[2]
        encrypted = encrypt_key(api_key)
        print(f"원본: {api_key}")
        print(f"암호화: {encrypted}")

    elif cmd == "decrypt" and len(sys.argv) > 2:
        encrypted = sys.argv[2]
        decrypted = decrypt_key(encrypted)
        print(f"복호화: {decrypted}")

    elif cmd == "test":
        test_key = "up_test_key_12345_abcdef"
        encrypted = encrypt_key(test_key)
        decrypted = decrypt_key(encrypted)
        print(f"원본:   {test_key}")
        print(f"암호화: {encrypted}")
        print(f"복호화: {decrypted}")
        print(f"일치:   {test_key == decrypted}")
    else:
        print("잘못된 명령어입니다")
