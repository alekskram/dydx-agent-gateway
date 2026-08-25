"""B6: signer — golden EIP-712 vector (deterministic key + fields), key
handling, bech32. Fully offline. Cross-validation against the official
client remains a testnet milestone; this vector guards regressions."""
import pytest

from dydx_mcp import signer

GOLDEN_KEY = "0101010101010101010101010101010101010101010101010101010101010101"
GOLDEN_DIGEST = ("dbd94e7a54b4c182be1f77b097e3d4873d39d60232057c55ec"
                 "5931df6380a4c8")
GOLDEN_SIG = ("0x91d7fcedc8642bd6f1bd1e7975ec936d37d5f38502f39663409b8f736"
              "cf06cad30cdc3537fd0ac75c8347baf7a9ab031628a851e05bfbbc05db5"
              "3bfde802b0511b")
GOLDEN_ETH = "0x1a642f0e3c3af545e7acbd38b07251b3990914f1"
GOLDEN_DYDX = "dydx1rfjz7r3u8t65teavh5utquj3kwvsj98329d9g8"


def _golden_digest():
    fields = [signer._u(signer.pack_flags("LIMIT", "FOK", True)), signer._u(7),
              signer._u(1), signer._u(50_000_000), signer._u(2_445_500_000),
              signer._u(102_000_000), signer._u(0), signer._u(0)]
    return signer._digest(signer.keccak256(signer.ORDER_TYPEHASH_S.encode()),
                          fields)


def test_golden_eip712_vector():
    sk = signer.key_from_hex(GOLDEN_KEY)
    digest = _golden_digest()
    assert digest.hex() == GOLDEN_DIGEST  # packing/typehash regression guard
    sig, recid = signer.sign_digest(sk, digest)
    assert "0x" + sig.hex() + f"{recid + 27:02x}" == GOLDEN_SIG
    assert signer.eth_address(sk.get_verifying_key()) == GOLDEN_ETH
    assert signer.dydx_address(sk.get_verifying_key()) == GOLDEN_DYDX


def test_signature_is_deterministic():
    sk = signer.key_from_hex(GOLDEN_KEY)
    s1, _ = signer.sign_digest(sk, _golden_digest())
    s2, _ = signer.sign_digest(sk, _golden_digest())
    assert s1 == s2  # RFC6979


def test_key_from_hex_short_and_prefixed():
    a = signer.key_from_hex("0x01")
    b = signer.key_from_hex("01".rjust(64, "0"))
    assert a.to_string() == b.to_string()  # short hex is zero-padded


def test_keccak_known_vectors():
    assert signer.keccak256(b"").hex() == \
        "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    assert signer.keccak256(b"abc").hex() == \
        "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"


def test_dydx_address_checksum_valid():
    from scanner import valid
    assert valid(GOLDEN_DYDX)  # our generator emits BIP-173-valid addresses
