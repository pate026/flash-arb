#!/usr/bin/env python3
"""
compare_dex.py - Jatkuva moniparin DEX-vertailuluuppi, likviditeettisuodatus ja Quoter-simulaattori (Polygon).
Tarkistaa uudet lohkot, suodattaa kuivuneet altaat ja ajaa Quoter-slippagesimulaation vain riittävällä likviditeetillä.
"""

import sys
import time
from web3 import Web3
from config import TOKENS
from dex import w3
from price_math import price_to_float
from pricing import read_quickswap_state, read_uniswap_slot0
from quickswap import get_quickswap_pool
from quickswap_quoter import quote_exact_input_single_quick
from uniswap import get_uniswap_pool
from uniswap_quoter import quote_exact_input_single

# Yksinkertainen ABI aktiivisen likviditeetin lukemiseen
LIQUIDITY_ABI = [
    {
        "inputs": [],
        "name": "liquidity",
        "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
        "stateMutability": "view",
        "type": "function",
    }
]

DECIMALS = {
    "USDC": 6,
    "WBTC": 8,
    "WETH": 18,
    "WMATIC": 18,
    "LINK": 18,
}

PAIRS_TO_CHECK = [
    ("WMATIC", "USDC", 500),   # 0.05% Uni
    ("WETH", "USDC", 500),     # 0.05% Uni
    ("WBTC", "USDC", 500),     # 0.05% Uni
    ("LINK", "USDC", 3000),    # 0.30% Uni
]

TEST_LOAN_AMOUNTS = [50, 150, 500]

# Minimilikviditeetti (L): kuivuneissa altaissa L on usein 0 tai mitätön (esim. < 100 000)
MIN_LIQUIDITY_THRESHOLD = 100_000


def get_pool_liquidity(pool_address: str) -> int:
    """Lukee altaan tämänhetkisen aktiivisen likviditeetin (uint128)."""
    try:
        c = w3.eth.contract(
            address=Web3.to_checksum_address(pool_address),
            abi=LIQUIDITY_ABI,
        )
        return c.functions.liquidity().call()
    except Exception:
        return 0


def init_pools():
    pools = []
    zero_addr = "0x0000000000000000000000000000000000000000"

    print("Alustetaan altaat...")
    for base_sym, quote_sym, uni_fee in PAIRS_TO_CHECK:
        base_addr = TOKENS[base_sym]
        quote_addr = TOKENS[quote_sym]

        if int(base_addr, 16) < int(quote_addr, 16):
            token0, token1 = base_addr, quote_addr
            dec0, dec1 = DECIMALS[base_sym], DECIMALS[quote_sym]
            invert = False
        else:
            token0, token1 = quote_addr, base_addr
            dec0, dec1 = DECIMALS[quote_sym], DECIMALS[base_sym]
            invert = True

        try:
            uni_pool = get_uniswap_pool(token0, token1, uni_fee)
            quick_pool = get_quickswap_pool(token0, token1)
        except Exception as e:
            print(f"[{base_sym}/{quote_sym}] Virhe allasosoitteessa: {e}")
            continue

        if uni_pool == zero_addr or quick_pool == zero_addr:
            print(f"[{base_sym}/{quote_sym}] Allas puuttuu, ohitetaan.")
            continue

        pools.append({
            "base_sym": base_sym,
            "quote_sym": quote_sym,
            "base_addr": base_addr,
            "quote_addr": quote_addr,
            "uni_fee": uni_fee,
            "uni_fee_pct": uni_fee / 10_000,
            "uni_pool": uni_pool,
            "quick_pool": quick_pool,
            "dec0": dec0,
            "dec1": dec1,
            "invert": invert,
        })

    print(f"Alustettu {len(pools)} allasparia.\n")
    return pools


def run_quoter_simulation(p: dict, direction: str):
    usdc_addr = p["quote_addr"]
    token_addr = p["base_addr"]
    uni_fee = p["uni_fee"]

    print("\n  [QUOTER-SIMULAATIO (Toteutuva tuotto / Slippage)]")

    for amt in TEST_LOAN_AMOUNTS:
        raw_in = amt * 10**6
        try:
            if direction == "UNI_TO_QUICK":
                q1 = quote_exact_input_single(usdc_addr, token_addr, raw_in, uni_fee)
                token_out = q1["amount_out"]
                q2 = quote_exact_input_single_quick(token_addr, usdc_addr, token_out)
                usdc_out = q2["amount_out"]
            else:
                q1 = quote_exact_input_single_quick(usdc_addr, token_addr, raw_in)
                token_out = q1["amount_out"]
                q2 = quote_exact_input_single(token_addr, usdc_addr, token_out, uni_fee)
                usdc_out = q2["amount_out"]

            owed = raw_in + (raw_in * 5) // 10000
            net_profit_usdc = (usdc_out - owed) / 10**6
            pct_return = (net_profit_usdc / amt) * 100

            status = "VOITOLLINEN!" if net_profit_usdc > 0 else "Tappio (slippage)"
            print(
                f"    Laina: {amt:>4} USDC | "
                f"Palautus: {usdc_out / 10**6:>8.3f} USDC | "
                f"Netto: {net_profit_usdc:>+7.3f} USDC ({pct_return:>+6.2f}%) | "
                f"{status}"
            )
        except Exception as e:
            print(f"    Laina: {amt:>4} USDC | Simulaatiovirhe: {e}")


def scan_block(block_number: int, pools: list) -> int:
    alerts = 0

    for p in pools:
        try:
            uni_slot0 = read_uniswap_slot0(p["uni_pool"])
            quick_state = read_quickswap_state(p["quick_pool"])
        except Exception:
            continue

        uni_sqrt_price = uni_slot0[0]
        quick_sqrt_price = quick_state[0]
        quick_fee_pct = quick_state[2] / 10_000

        price_uni = price_to_float(uni_sqrt_price, p["dec0"], p["dec1"], inverse=p["invert"])
        price_quick = price_to_float(quick_sqrt_price, p["dec0"], p["dec1"], inverse=p["invert"])

        diff = price_quick - price_uni
        pct_diff = (diff / price_uni) * 100
        abs_pct = abs(pct_diff)

        total_fee_estimate = p["uni_fee_pct"] + quick_fee_pct + 0.05

        if abs_pct > total_fee_estimate:
            # Tarkistetaan molempien altaiden aktiivinen likviditeetti
            uni_liq = get_pool_liquidity(p["uni_pool"])
            quick_liq = get_pool_liquidity(p["quick_pool"])

            if price_uni < price_quick:
                dir_label = "Osta Uniswap -> Myy Quickswap"
                direction = "UNI_TO_QUICK"
            else:
                dir_label = "Osta Quickswap -> Myy Uniswap"
                direction = "QUICK_TO_UNI"

            net_edge = abs_pct - total_fee_estimate

            # Jos jommassakummassa altaassa ei ole riittävää likviditeettiä, ohitetaan Quoter
            if uni_liq < MIN_LIQUIDITY_THRESHOLD or quick_liq < MIN_LIQUIDITY_THRESHOLD:
                # Tulostetaan vain kompakti huomio eikä ammuta raskaampaa Quoter-kutsua
                continue

            alerts += 1
            print(f"\n{'!'*65}")
            print(f"[LOHKO {block_number}] SPOTTI-HALYTYS: {p['base_sym']}/{p['quote_sym']}")
            print(f"  Suunta:           {dir_label}")
            print(f"  Uniswap ({p['uni_fee_pct']:.2f}%):  {price_uni:.4f} {p['quote_sym']} (Liq: {uni_liq})")
            print(f"  Quickswap ({quick_fee_pct:.4f}%): {price_quick:.4f} {p['quote_sym']} (Liq: {quick_liq})")
            print(f"  Bruttoero:        {abs_pct:.4f} %")
            print(f"  Arvioidut kulut:  {total_fee_estimate:.4f} %")
            print(f"  Nettoedutus:      +{net_edge:.4f} %")

            run_quoter_simulation(p, direction)
            print(f"{'!'*65}\n")

    return alerts


def main():
    pools = init_pools()
    if not pools:
        print("Ei seurattavia altaita. Lopetetaan.")
        sys.exit(1)

    print("Kaynnistetaan lohkoseuranta + Liquidity Filter + Quoter (lopeta: Ctrl+C)...")
    last_checked_block = 0

    try:
        while True:
            try:
                current_block = w3.eth.block_number
            except Exception:
                time.sleep(1)
                continue

            if current_block > last_checked_block:
                last_checked_block = current_block
                alerts = scan_block(current_block, pools)
                timestamp = time.strftime("%H:%M:%S")
                if alerts == 0:
                    sys.stdout.write(
                        f"\r[{timestamp}] Lohko {current_block} tarkistettu | Seurataan {len(pools)} paria..."
                    )
                    sys.stdout.flush()

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nSeuranta pysaytettu.")


if __name__ == "__main__":
    main()

