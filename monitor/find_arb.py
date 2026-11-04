#!/usr/bin/env python3
"""
find_arb.py - Etsii optimaalisen flash loan -arbitraasin koon (Polygon, Uniswap V3).

TURVALLINEN: Tama skripti VAIN LASKEE ja TULOSTAA. Se ei laheta yhtaan
transaktiota eika tarvitse private keyta. Se kyselee Uniswap V3 Quoter
-kontraktilta todelliset swap-tulokset eri panoskoolla ja etsii sen
lainasumman, joka maksimoi arbitraasivoiton kahden fee-tierin valilla.

Kaytto:
    export POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/AVAIN
    python3 find_arb.py

Riippuvuudet:
    pip install web3

Idea:
    Leg 1: asset -> tokenMid  (fee-tier A, esim. 0.05%)
    Leg 2: tokenMid -> asset  (fee-tier B, esim. 0.3%)
    Jos lopputulos > panos + Aave-preemio, on olemassa arbitraasivoitto.
    Skripti hakee todellisen quote:n Uniswapilta useilla panoskoolla ja
    etsii parhaan (voitto on konkaavi kayra panoksen suhteen).
"""

import os
import sys
from web3 import Web3

# ---------------------------------------------------------------------------
# Polygon mainnet -osoitteet
# ---------------------------------------------------------------------------
# Uniswap V3 QuoterV2 (Polygon)
QUOTER_V2 = Web3.to_checksum_address("0x61fFE014bA17989E743c5F6cB21bF9697530B21e")

# Tokenit
USDC = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")  # 6 desim.
WETH = Web3.to_checksum_address("0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619")  # 18 desim.

# Aave V3 flash loan -preemio Polygonissa: 0.05 % = 5 bps
AAVE_PREMIUM_BPS = 5

# Fee-tierit joita testataan (Uniswap V3: 500 = 0.05%, 3000 = 0.3%, 10000 = 1%)
FEE_BUY = 500    # leg 1: USDC -> WETH
FEE_SELL = 3000  # leg 2: WETH -> USDC

# Panoskoot joita kokeillaan (USDC:n yksikoissa, 6 desimaalia)
# 1k, 2k, 5k, 10k, 20k, 50k, 100k, 200k USDC
TEST_AMOUNTS_USDC = [1_000, 2_000, 5_000, 10_000, 20_000, 50_000, 100_000, 200_000]

# ---------------------------------------------------------------------------
# QuoterV2 ABI (vain quoteExactInputSingle)
# ---------------------------------------------------------------------------
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
    """Hakee Uniswap V3 Quoterilta kuinka paljon token_out:ia saa.

    QuoterV2 ei ole 'view' (se simuloi swapin), joten kaytetaan .call()
    joka ajaa sen paikallisesti lahettamatta transaktiota - ei kuluta gasia.
    """
    params = (token_in, token_out, amount_in, fee, 0)
    result = quoter.functions.quoteExactInputSingle(params).call()
    return result[0]  # amountOut


def main():
    from config import RPC_URL

    rpc_url = RPC_URL
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        print(f"VIRHE: Ei yhteytta RPC:hen osoitteessa {rpc_url}.")
        sys.exit(1)


    print(f"Yhdistetty Polygoniin. Lohko: {w3.eth.block_number}")
    print(f"Reitti: USDC --({FEE_BUY/10000:.2f}%)--> WETH --({FEE_SELL/10000:.2f}%)--> USDC")
    print(f"Aave-preemio: {AAVE_PREMIUM_BPS/100:.2f}%")
    print("-" * 72)

    quoter = w3.eth.contract(address=QUOTER_V2, abi=QUOTER_ABI)

    best_profit = -(2**256)
    best_amount = 0
    results = []

    for amount_usdc in TEST_AMOUNTS_USDC:
        amount_in = amount_usdc * 10**6  # USDC 6 desimaalia

        try:
            # Leg 1: USDC -> WETH
            weth_out = get_quote(quoter, USDC, WETH, amount_in, FEE_BUY)
            # Leg 2: WETH -> USDC
            usdc_back = get_quote(quoter, WETH, USDC, weth_out, FEE_SELL)
        except Exception as e:
            print(f"{amount_usdc:>10,} USDC | quote epaonnistui: {e}")
            continue

        # Takaisinmaksu: laina + Aave-preemio
        amount_owed = amount_in + (amount_in * AAVE_PREMIUM_BPS) // 10_000
        profit_raw = usdc_back - amount_owed
        profit_usdc = profit_raw / 10**6

        results.append((amount_usdc, profit_usdc))

        marker = ""
        if profit_raw > best_profit:
            best_profit = profit_raw
            best_amount = amount_usdc
            marker = "  <-- paras toistaiseksi"

        status = "VOITTO" if profit_usdc > 0 else "tappio"
        print(f"{amount_usdc:>10,} USDC | {status}: {profit_usdc:>12,.2f} USDC{marker}")

    print("-" * 72)

    if best_profit > 0:
        print(f"PARAS: {best_amount:,} USDC lainalla -> "
              f"~{best_profit/10**6:,.2f} USDC voitto (ennen gas-kuluja)")
        print()
        print("HUOM: Tama ei viela huomioi gas-kuluja. Polygonissa ne ovat")
        print("pienia (~0.01-0.10 USD), mutta vahenna ne lopullisesta voitosta.")
        print("HUOM: Quote on hetkellinen - hinta voi muuttua ennen kuin ehdit")
        print("lahettaa transaktion (MEV-kilpailu). Tama on vain analyysi.")
    else:
        print("Ei kannattavaa arbitraasia nailla fee-tiereilla juuri nyt.")
        print("Tama on normaalia - arbitraasimahdollisuudet ovat harvinaisia")
        print("ja lyhytkestoisia. Kokeile eri token-pareja tai fee-tiereja.")


if __name__ == "__main__":
    main()
