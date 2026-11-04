#!/usr/bin/env python3
"""
monitor_arb.py - Jatkuva flash loan -arbitraasin seuranta (Polygon, Uniswap V3).

TURVALLINEN: VAIN LUKEE ja TULOSTAA. Ei laheta transaktioita, ei tarvitse
private keyta. Kyselee Uniswap V3 Quoterilta hintoja saannollisin valiajoin
ja halyttaa jos loytyy kannattava arbitraasi.

Tarkoitus: nahda konkreettisesti KUINKA USEIN (jos koskaan) mahdollisuus
vilahtaa ja kuinka nopeasti se katoaa. Opettaa MEV-kilpailun luonteen.

Kaytto:
    export POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/AVAIN
    python3 monitor_arb.py

    Lopeta: Ctrl+C (nayttaa yhteenvedon)

Riippuvuudet:
    pip install web3
"""

import os
import sys
import time
from datetime import datetime

from web3 import Web3

# ---------------------------------------------------------------------------
# Asetukset - saada naita vapaasti
# ---------------------------------------------------------------------------
CHECK_INTERVAL_SEC = 10       # kuinka usein tarkistetaan
MIN_PROFIT_USDC = 1.0         # halytysraja: vahintaan nain paljon voittoa

# Panoskoot joita kokeillaan joka kierroksella (USDC, 6 desim.)
TEST_AMOUNTS_USDC = [1_000, 2_000, 5_000, 10_000, 20_000]

# ---------------------------------------------------------------------------
# Polygon mainnet -osoitteet
# ---------------------------------------------------------------------------
QUOTER_V2 = Web3.to_checksum_address("0x61fFE014bA17989E743c5F6cB21bF9697530B21e")

USDC = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")  # 6 desim.
WETH = Web3.to_checksum_address("0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619")  # 18 desim.

AAVE_PREMIUM_BPS = 5   # 0.05 %

# Reitti: USDC --(feeBuy)--> WETH --(feeSell)--> USDC
FEE_BUY = 500
FEE_SELL = 3000

QUOTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"},
                ],
                "internalType": "struct IQuoterV2.QuoteExactInputSingleParams",
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "quoteExactInputSingle",
        "outputs": [
            {"internalType": "uint256", "name": "amountOut", "type": "uint256"},
            {"internalType": "uint160", "name": "sqrtPriceX96After", "type": "uint160"},
            {"internalType": "uint32", "name": "initializedTicksCrossed", "type": "uint32"},
            {"internalType": "uint256", "name": "gasEstimate", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


def get_quote(quoter, token_in, token_out, amount_in, fee):
    params = (token_in, token_out, amount_in, fee, 0)
    return quoter.functions.quoteExactInputSingle(params).call()[0]


def check_once(quoter):
    """Yksi tarkistuskierros. Palauttaa (paras_voitto_usdc, paras_panos_usdc)."""
    best_profit = None
    best_amount = 0

    for amount_usdc in TEST_AMOUNTS_USDC:
        amount_in = amount_usdc * 10**6
        try:
            weth_out = get_quote(quoter, USDC, WETH, amount_in, FEE_BUY)
            usdc_back = get_quote(quoter, WETH, USDC, weth_out, FEE_SELL)
        except Exception:
            continue

        amount_owed = amount_in + (amount_in * AAVE_PREMIUM_BPS) // 10_000
        profit_usdc = (usdc_back - amount_owed) / 10**6

        if best_profit is None or profit_usdc > best_profit:
            best_profit = profit_usdc
            best_amount = amount_usdc

    return best_profit, best_amount


def alert(profit, amount):
    """Halytys kun loytyy kannattava mahdollisuus."""
    # \a = terminaalin aanimerkki (bell)
    print("\a")
    print("=" * 72)
    print(f"  !!! MAHDOLLISUUS LOYTYI !!!")
    print(f"  Panos: {amount:,} USDC  ->  voitto: ~{profit:,.2f} USDC")
    print(f"  Aika: {datetime.now().strftime('%H:%M:%S')}")
    print(f"  HUOM: Tama on hetkellinen. Ehdit tuskin toimia ennen botteja.")
    print(f"  Tama on VAIN havainto - skripti ei laheta mitaan.")
    print("=" * 72)


def main():
    from config import RPC_URL

    rpc_url = RPC_URL
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        print(f"VIRHE: Ei yhteytta RPC:hen osoitteessa {rpc_url}.")
        sys.exit(1)

    quoter = w3.eth.contract(address=QUOTER_V2, abi=QUOTER_ABI)

    print("Jatkuva arbitraasin seuranta kaynnistetty.")
    print(f"Reitti: USDC --({FEE_BUY/10000:.2f}%)--> WETH --({FEE_SELL/10000:.2f}%)--> USDC")
    print(f"Tarkistusvali: {CHECK_INTERVAL_SEC}s | Halytysraja: {MIN_PROFIT_USDC} USDC")
    print("Lopeta: Ctrl+C")
    print("-" * 72)

    checks = 0
    opportunities = 0
    best_seen = None
    start = time.time()

    try:
        while True:
            checks += 1
            best_profit, best_amount = check_once(quoter)

            if best_profit is None:
                line = "quote epaonnistui"
            else:
                if best_seen is None or best_profit > best_seen:
                    best_seen = best_profit

                ts = datetime.now().strftime("%H:%M:%S")
                block = w3.eth.block_number
                line = (f"[{ts}] lohko {block} | paras: "
                        f"{best_profit:>10,.2f} USDC ({best_amount:,} panos)")

                if best_profit >= MIN_PROFIT_USDC:
                    opportunities += 1
                    print(line)
                    alert(best_profit, best_amount)
                else:
                    # Tavallinen rivi - ei mahdollisuutta
                    print(line)

            time.sleep(CHECK_INTERVAL_SEC)

    except KeyboardInterrupt:
        elapsed = time.time() - start
        print()
        print("-" * 72)
        print("SEURANTA LOPETETTU. Yhteenveto:")
        print(f"  Kesto:            {elapsed/60:.1f} min")
        print(f"  Tarkistuksia:     {checks}")
        print(f"  Mahdollisuuksia:  {opportunities}")
        if best_seen is not None:
            print(f"  Paras nahty:      {best_seen:,.2f} USDC")
        if opportunities == 0:
            print()
            print("  Ei yhtaan kannattavaa hetkea - juuri kuten odotettiin")
            print("  suositulla parilla. Botit pitavat hinnat linjassa.")
        print("-" * 72)


if __name__ == "__main__":
    main()
