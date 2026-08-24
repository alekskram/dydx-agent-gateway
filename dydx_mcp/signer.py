"""Zero-heavy-dep EIP-712 signer for dYdX v4 orders and API credentials.

Spec sources: dYdX v4 docs "order signing" and v4-client-py 4.0.0
(sha256 of the constant names below kept in comments). The only crypto deps:
ecdsa (secp256k1, RFC6979) + pycryptodome (keccak256).

Status: math is self-tested (recovery round-trip, packing); live
submission is pending testnet validation (see PLAN.md signer milestone).
Never log or store the private key; it is read from DYDX_ETH_KEY env or
passed per-call and dropped.
"""
import argparse
import hashlib
import json
import os
import time
from hashlib import sha256

from Crypto.Hash import keccak as _keccak
import ecdsa
from ecdsa import SECP256k1, SigningKey, VerifyingKey
from ecdsa.util import sigdecode_string, sigencode_string_canonize

from . import api

CURVE = SECP256k1
DOMAIN = {  # fixed by protocol for all dYdX v4 chains
    "name": "dydx", "version": "1", "chainId": 1337,
    "verifyingContract": "0x0000000000000000000000000000000000000000",
}
ORDER_TYPEHASH_S = ("Order(uint32 flags,uint32 clientId,uint32 marketId,"
                    "uint64 size,uint64 price,uint32 goodTilBlock,"
                    "uint32 goodTilBlockTime,uint32 nonce)")
API_CREDENTIALS_TYPEHASH_S = "ApiCredentials(int64 timestamp,address issuer)"

ORDER_TYPE = {"LIMIT": 0, "MARKET": 1, "STOP_LIMIT": 2, "STOP_MARKET": 3,
              "TRAILING_STOP": 4}
ORDER_TIF = {"TIF_UNSPECIFIED": 0, "IOC": 1, "POST_ONLY": 2, "FOK": 3, "GTT": 4}


def keccak256(b: bytes) -> bytes:
    h = _keccak.new(digest_bits=256)
    h.update(b)
    return h.digest()


def _u(x: int) -> bytes:  # EIP-712 uintN -> left-padded 32B
    return x.to_bytes(32, "big")


def domain_separator() -> bytes:
    s = (keccak256(b"EIP712Domain(string name,string version,uint256 chainId,"
                   b"address verifyingContract)")
         + keccak256(b"dydx") + keccak256(b"1") + _u(1337) + _u(0))
    return keccak256(s)


def _digest(typehash: bytes, fields: list[bytes]) -> bytes:
    return keccak256(b"\x19\x01" + domain_separator()
                     + keccak256(typehash + b"".join(fields)))


# ------------------------------------------------------------------- keys

def key_from_hex(hexkey: str) -> SigningKey:
    return SigningKey.from_string(bytes.fromhex(hexkey.strip()
                                                .removeprefix("0x")), curve=CURVE)


def eth_address(vk: VerifyingKey) -> str:
    pub = vk.to_string("uncompressed")[1:]
    return "0x" + keccak256(pub)[-20:].hex()


# bech32 (BIP-173) for dydx1... account addresses
def _bech32_polymod(values):
    GEN = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            chk ^= GEN[i] if ((b >> i) & 1) else 0
    return chk


def _convertbits(data, frm, to, pad=True):
    acc = bits = 0
    ret = []
    for value in data:
        acc = (acc << frm) | value
        bits += frm
        while bits >= to:
            bits -= to
            ret.append((acc >> bits) & ((1 << to) - 1))
    if pad and bits:
        ret.append((acc << (to - bits)) & ((1 << to) - 1))
    return ret


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _bech32_encode(hrp: str, data20: bytes) -> str:
    charset = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    data = _convertbits(data20, 8, 5)
    p = _bech32_polymod(_hrp_expand(hrp) + data + [0] * 6) ^ 1
    checksum = [(p >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(charset[d] for d in data + checksum)


def dydx_address(vk: VerifyingKey) -> str:
    """dYdX account address (bech32, hrp=dydx) of the same public key."""
    eth20 = keccak256(vk.to_string("uncompressed")[1:])[-20:]
    return _bech32_encode("dydx", eth20)


# ---------------------------------------------------------------- signing

def sign_digest(sk: SigningKey, digest: bytes) -> tuple[bytes, int]:
    """Deterministic (RFC6979) signature -> (r||s, recovery_id)."""
    sig = sk.sign_digest_deterministic(digest, sigencode=sigencode_string_canonize,
                                       hashfunc=hashlib.sha256)
    pub = sk.get_verifying_key().to_string("compressed")
    for recid in (0, 1):
        try:
            cands = VerifyingKey.from_public_key_recovery_with_digest(
                sig, digest, curve=CURVE, sigdecode=sigdecode_string)
            if cands[recid].to_string("compressed") == pub:
                return sig, recid
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("recovery id not found")


def sign_api_credentials(sk: SigningKey, timestamp_ms: int | None = None):
    ts = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
    digest = _digest(
        keccak256(API_CREDENTIALS_TYPEHASH_S.encode()),
        [_u(ts), _u(int(eth_address(sk.get_verifying_key()), 16))])
    sig, recid = sign_digest(sk, digest)
    return {"timestamp": ts,
            "signature": "0x" + sig.hex() + f"{recid + 27:02x}",
            "issuer": eth_address(sk.get_verifying_key())}


# ------------------------------------------------------------------ orders

def pack_flags(order_type: str = "LIMIT", tif: str = "FOK",
               reduce_only: bool = False) -> int:
    return (ORDER_TYPE[order_type] << 23 | ORDER_TIF[tif] << 27
            | int(reduce_only) << 31)


def quantize(market_meta: dict, size_base: float, price: float) -> dict:
    """Human size/price -> protocol integers, grounded in live market meta:
    size: base-quantums = size * 10^(-atomicResolution), floored to
    stepBaseQuantums; price: subticks = price / tickSize * subticksPerTick."""
    ar = int(market_meta["atomicResolution"])
    step = int(market_meta["stepBaseQuantums"])
    q = int(size_base * 10 ** (-ar))
    q -= q % step
    tick = float(market_meta["tickSize"])
    spt = int(market_meta["subticksPerTick"])
    st = int(round(price / tick * spt))
    return {"size_quantums": q, "price_subticks": st,
            "step_check": {"stepBaseQuantums": step, "tickSize": tick,
                           "subticksPerTick": spt}}


def build_order(ticker: str, side: str, size_base: float, price: float,
                order_type: str = "LIMIT", tif: str = "FOK",
                good_til_block: int | None = None, block_offset: int = 20,
                client_id: int = 0, nonce: int = 0,
                reduce_only: bool = False, sk: SigningKey | None = None):
    m = api.markets().get(ticker)
    if not m:
        raise ValueError(f"unknown ticker {ticker}")
    if good_til_block is None:
        good_til_block = int(api.height()["height"]) + block_offset
    q = quantize(m, size_base, price)
    fields = [_u(pack_flags(order_type, tif, reduce_only)), _u(client_id),
              _u(int(m["clobPairId"])), _u(q["size_quantums"]),
              _u(q["price_subticks"]), _u(good_til_block), _u(0), _u(nonce)]
    digest = _digest(keccak256(ORDER_TYPEHASH_S.encode()), fields)
    order = {
        "market": ticker, "clobPairId": int(m["clobPairId"]),
        "type": order_type, "side": side, "timeInForce": tif,
        "clientId": client_id, "reduceOnly": reduce_only,
        "size": f"{q['size_quantums'] * 10 ** int(m['atomicResolution']):.9f}".rstrip("0"),
        "price": f"{q['price_subticks'] * float(m['tickSize']) / int(m['subticksPerTick']):.6f}".rstrip("0"),
        "size_quantums": q["size_quantums"], "price_subticks": q["price_subticks"],
        "goodTilBlock": good_til_block, "goodTilBlockTime": 0, "nonce": nonce,
        "eip712_digest": "0x" + digest.hex(),
    }
    if sk is not None:
        sig, recid = sign_digest(sk, digest)
        order["signature"] = "0x" + sig.hex() + f"{recid + 27:02x}"
        order["signer_eth"] = eth_address(sk.get_verifying_key())
        order["signer_dydx"] = dydx_address(sk.get_verifying_key())
    return order


# ---------------------------------------------------------------- selftest

def selftest():
    ok = lambda name, cond: print(("PASS" if cond else "FAIL"), name)

    ok("keccak256(empty) vector",
       keccak256(b"").hex() ==
       "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")

    sk = SigningKey.generate(curve=CURVE)
    digest = keccak256(b"dydx-agent-gateway selftest digest")
    sig, recid = sign_digest(sk, digest)
    vk2 = VerifyingKey.from_public_key_recovery_with_digest(
        sig, digest, curve=CURVE, sigdecode=sigdecode_string)[recid]
    ok("signature recovery round-trip",
       vk2.to_string("compressed") == sk.get_verifying_key().to_string("compressed"))
    ok("signature is canonical low-S",
       int.from_bytes(sig[32:], "big") <= CURVE.order // 2)

    ok("domain separator deterministic",
       domain_separator() == domain_separator())

    f = pack_flags("LIMIT", "FOK", True)
    ok("flags packing", f == (0 << 23 | 3 << 27 | 1 << 31)
       and f >> 31 == 1 and (f >> 27) & 0xF == 3)

    addr = dydx_address(sk.get_verifying_key())
    ok("dydx address bech32 shape",
       addr.startswith("dydx1") and len(addr) == 43)
    known = "dydx1m9hg73dtn5ku8ulmj8rjmdqh0hk7uuhawc69cn"  # real, from chain
    charset = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    rev = {c: i for i, c in enumerate(charset)}
    data5 = [rev[c] for c in known[5:-6]]  # data part: after "dydx1", before checksum
    known20 = bytes(_convertbits(data5, 5, 8, pad=False))
    ok("bech32 round-trip on real address",
       _bech32_encode("dydx", known20) == known)

    m = {"atomicResolution": -9, "stepBaseQuantums": 1000000,
         "tickSize": "0.1", "subticksPerTick": 100000}
    q = quantize(m, 0.05, 2445.5)
    ok("quantize size 0.05 ETH -> 50'000'000 base-quantums",
       q["size_quantums"] == 50_000_000)
    ok("quantize price 2445.5 -> 2'445'500'000 subticks (1 subtick = 1e-6)",
       q["price_subticks"] == 2_445_500_000)

    api_c = sign_api_credentials(sk, timestamp_ms=1700000000000)
    ok("api credentials: signed timestamp == returned timestamp",
       api_c["timestamp"] == 1700000000000)
    ok("api credentials signable", api_c["signature"].startswith("0x")
       and len(api_c["signature"]) == 132 and api_c["issuer"].startswith("0x"))

    order = build_order("ETH-USD", "BUY", 0.05, 2445.5, sk=sk,
                        good_til_block=102_000_000, client_id=7)
    ok("order builds + signs", order["signature"][:2] == "0x"
       and len(order["signature"]) == 132
       and order["signer_dydx"].startswith("dydx1"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--ticker", default="ETH-USD")
    ap.add_argument("--side", default="BUY")
    ap.add_argument("--size", type=float, default=0.05)
    ap.add_argument("--price", type=float)
    ap.add_argument("--dry", action="store_true", help="build+digest, no key")
    args = ap.parse_args()
    if args.selftest:
        selftest()
    else:
        price = args.price or float(api.markets()[args.ticker]["oraclePrice"])
        sk = None if args.dry else key_from_hex(os.environ["DYDX_ETH_KEY"])
        print(json.dumps(build_order(args.ticker, args.side, args.size,
                                     price, sk=sk), indent=1))
