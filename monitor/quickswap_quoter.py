#!/usr/bin/env python3
from web3 import Web3
from config import DEX
from dex import w3

# Algebra Quoter ABI (Quickswap V3) - palauttaa (amountOut, fee)
ALGEBRA_QUOTER_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenIn", "type": "address"},
            {"internalType": "address", "name": "tokenOut", "type": "address"},
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint160", "name": "limitSqrtPrice", "type": "uint160"},
        ],
        "name": "quoteExactInputSingle",
        "outputs": [
            {"internalType": "uint256", "name": "amountOut", "type": "uint256"},
            {"internalType": "uint16", "name": "fee", "type": "uint16"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

quoter = w3.eth.contract(
    address=Web3.to_checksum_address(DEX["QUICKSWAP_V3_QUOTER"]),
    abi=ALGEBRA_QUOTER_ABI,
)


def quote_exact_input_single_quick(token_in: str, token_out: str, amount_in: int):
    """
    Hakee Quickswap V3:lta (Algebra) simulaation vaihtotuloksesta.
    """
    amount_out, fee = quoter.functions.quoteExactInputSingle(
        Web3.to_checksum_address(token_in),
        Web3.to_checksum_address(token_out),
        amount_in,
        0,  # limitSqrtPrice = 0
    ).call()

    return {
        "amount_out": amount_out,
        "fee": fee,
        "fee_pct": fee / 10_000,
    }


if __name__ == "__main__":
    from config import TOKENS

    # Testataan 1 USDC -> WMATIC
    amount = 1_000_000
    q = quote_exact_input_single_quick(TOKENS["USDC"], TOKENS["WMATIC"], amount)
    print("\nQuickswap Quote Testi:")
    print(f"Input   : {amount / 10**6:.2f} USDC")
    print(f"Output  : {q['amount_out'] / 10**18:.6f} WMATIC")
    print(f"Fee     : {q['fee_pct']:.4f} %")
