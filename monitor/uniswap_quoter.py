from web3 import Web3

from abi_loader import load_abi
from config import DEX
from dex import w3

QUOTER_ABI = load_abi("uniswap_quoter.json")

quoter = w3.eth.contract(
    address=Web3.to_checksum_address(
        DEX["UNISWAP_V3_QUOTER"]
    ),
    abi=QUOTER_ABI,
)


def quote_exact_input_single(
    token_in,
    token_out,
    amount_in,
    fee=500,
):
    params = (
        Web3.to_checksum_address(token_in),
        Web3.to_checksum_address(token_out),
        amount_in,
        fee,
        0,
    )

    amount_out, sqrt_after, ticks_crossed, gas_estimate = (
        quoter.functions.quoteExactInputSingle(params).call()
    )

    return {
        "amount_out": amount_out,
        "sqrt_price_after": sqrt_after,
        "ticks_crossed": ticks_crossed,
        "gas_estimate": gas_estimate,
    }


if __name__ == "__main__":

    from config import TOKENS

    amount_in = 1_000_000  # 1 USDC (6 decimals)

    quote = quote_exact_input_single(
        TOKENS["USDC"],
        TOKENS["WMATIC"],
        amount_in,
        500,
    )

    print("\nQuote")
    print(f"Input : {amount_in} USDC units")
    print(f"Output: {quote['amount_out']}")
    print(f"Ticks : {quote['ticks_crossed']}")
    print(f"Gas   : {quote['gas_estimate']}")
