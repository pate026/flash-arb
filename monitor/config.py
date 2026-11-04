import os
from pathlib import Path
from dotenv import load_dotenv

# Etsi ja lataa projektin juuresta mahdollinen .env-tiedosto
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# ------------------------------------------------------------------
# RPC
# ------------------------------------------------------------------

# Ensisijaisesti .env / ymparistomuuttuja, toissijaisesti julkinen RPC
RPC_URL = os.getenv("POLYGON_RPC_URL", "https://polygon-bor-rpc.publicnode.com")

# ------------------------------------------------------------------
# Polygon tokenit
# ------------------------------------------------------------------

TOKENS = {
    "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    "WMATIC": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
    "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
    "WBTC": "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",
    "LINK": "0x53E0bca35eC356BD5ddDFebBD1Fc0fD03FaBad39",
}

# ------------------------------------------------------------------
# DEX Factory -osoitteet
# ------------------------------------------------------------------

DEX = {
    "UNISWAP_V3_FACTORY": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
    "QUICKSWAP_V3_FACTORY": "0x411b0fAcC3489691f28ad58c47006AF5E3Ab3A28",

    "UNISWAP_V3_QUOTER": "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",

    "QUICKSWAP_V3_QUOTER": "0xa15F0d7377B2A0C0c10db057f641bed21028FC89",
}

# ------------------------------------------------------------------
# Fee tierit
# ------------------------------------------------------------------

FEE_TIERS = [
    100,      # 0.01%
    500,      # 0.05%
    3000,     # 0.30%
    10000,    # 1.00%
]

# ------------------------------------------------------------------
# Monitorin asetukset
# ------------------------------------------------------------------

CHECK_INTERVAL = 10      # sekuntia
MIN_PROFIT_USDC = 1.0    # halytysraja
