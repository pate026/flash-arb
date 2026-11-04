from web3 import Web3

from dex import w3

UNISWAP_POOL_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"type": "uint160", "name": "sqrtPriceX96"},
            {"type": "int24", "name": "tick"},
            {"type": "uint16", "name": "observationIndex"},
            {"type": "uint16", "name": "observationCardinality"},
            {"type": "uint16", "name": "observationCardinalityNext"},
            {"type": "uint8", "name": "feeProtocol"},
            {"type": "bool", "name": "unlocked"},
        ],
        "stateMutability": "view",
        "type": "function",
    }
]

ALGEBRA_POOL_ABI = [
    {
        "inputs": [],
        "name": "globalState",
        "outputs": [
            {"type": "uint160", "name": "price"},
            {"type": "int24", "name": "tick"},
            {"type": "uint16", "name": "fee"},
            {"type": "uint16", "name": "timepointIndex"},
            {"type": "uint8", "name": "communityFeeToken0"},
            {"type": "uint8", "name": "communityFeeToken1"},
            {"type": "bool", "name": "unlocked"},
        ],
        "stateMutability": "view",
        "type": "function",
    }
]


def read_uniswap_slot0(pool):
    c = w3.eth.contract(
        address=Web3.to_checksum_address(pool),
        abi=UNISWAP_POOL_ABI,
    )
    return c.functions.slot0().call()


def read_quickswap_state(pool):
    c = w3.eth.contract(
        address=Web3.to_checksum_address(pool),
        abi=ALGEBRA_POOL_ABI,
    )
    return c.functions.globalState().call()


if __name__ == "__main__":

    from config import TOKENS
    from uniswap import get_uniswap_pool
    from quickswap import get_quickswap_pool

    uni = get_uniswap_pool(
        TOKENS["WMATIC"],
        TOKENS["USDC"],
        500,
    )

    quick = get_quickswap_pool(
        TOKENS["WMATIC"],
        TOKENS["USDC"],
    )

    print("\nUniswap")
    print(read_uniswap_slot0(uni))

    print("\nQuickSwap")
    print(read_quickswap_state(quick))
