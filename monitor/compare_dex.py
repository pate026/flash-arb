#!/usr/bin/env python3
"""
compare_dex.py - Vertailee Uniswap V3:n ja Quickswap V3:n reaaliaikaisia hintoja.
"""

from decimal import Decimal
from config import TOKENS
from dex import w3
from price_math import price_to_float
from pricing import read_quickswap_state, read_uniswap_slot0
from quickswap import get_quickswap_pool
from uniswap import get_uniswap_pool


def main():
    token_a_sym = "WMATIC"
    token_b_sym = "USDC"

    token_a = TOKENS[token_a_sym]
    token_b = TOKENS[token_b_sym]

    # WMATIC = 18 desim, USDC = 6 desim
    # Koska 0x0d500... < 0x2791B..., token0 on WMATIC ja token1 on USDC
    dec0 = 18
    dec1 = 6

    print(f"Haetaan altaat parille {token_a_sym} / {token_b_sym}...")
    uni_pool = get_uniswap_pool(token_a, token_b, 500)  # 0.05%
    quick_pool = get_quickswap_pool(token_a, token_b)

    print(f"Uniswap V3 allas  : {uni_pool}")
    print(f"QuickSwap V3 allas: {quick_pool}")

    # Haetaan tilat
    uni_slot0 = read_uniswap_slot0(uni_pool)
    quick_state = read_quickswap_state(quick_pool)

    uni_sqrt_price = uni_slot0[0]
    quick_sqrt_price = quick_state[0]
    quick_fee_pct = quick_state[2] / 10_000  # fee pohjana 10000 -> %

    # Muunnetaan USDC / WMATIC (kuinka monta dollaria 1 WMATIC maksaa)
    price_uni = price_to_float(uni_sqrt_price, dec0, dec1, inverse=False)
    price_quick = price_to_float(quick_sqrt_price, dec0, dec1, inverse=False)

    print("\n" + "=" * 60)
    print(f"LOHKO: {w3.eth.block_number}")
    print("=" * 60)
    print(f"Uniswap V3 (0.05%): {price_uni:.6f} USDC / {token_a_sym}")
    print(
        f"QuickSwap V3 ({quick_fee_pct:.4f}%): {price_quick:.6f} USDC / {token_a_sym}"
    )

    diff = price_quick - price_uni
    pct_diff = (diff / price_uni) * 100

    print("-" * 60)
    print(f"Hintaero: {diff:+.6f} USDC ({pct_diff:+.4f} %)")

    if abs(pct_diff) > 0.1:
        if price_uni < price_quick:
            print(f"SUUNTA: Osta Uniswapista -> Myy Quickswapiin!")
        else:
            print(f"SUUNTA: Osta Quickswapista -> Myy Uniswapiin!")
    else:
        print("Hinnat kaytannossa taysin tasapainossa (ero alle 0.1%).")
    print("=" * 60)


if __name__ == "__main__":
    main()
