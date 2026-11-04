# Flash-Arb: Cross-DEX Arbitrage Bot (Polygon)

Tämä on Polygon-verkossa toimiva automatisoitu arbitraasijärjestelmä. Järjestelmä koostuu kahdesta pääkomponentista:
1. **Python-skanneri (Off-chain):** Monitoroi jatkuvasti Uniswap V3- ja Quickswap V3 -poolien hintaeroja.
2. **Solidity-älysopimus (On-chain):** Suorittaa automaattiset arbitraasit hyödyntäen Aave V3:n flash loaneja riskittömästi. Jos siirto ei ole voitollinen verkkomaksujen jälkeen, koko transaktio peruutetaan (`revert`).

---

## ⚙️ Asennus ja Vaatimukset

Tarvitset asennettuna:
- **Python 3.x** (Skanneria varten)
- **Foundry / Forge** (Älysopimuksien kääntämiseen ja testaamiseen)

### 1. Ympäristömuuttujat (.env)

Projektin juuressa täytyy olla `.env` -tiedosto, joka sisältää salaiset avaimesi ja verkkoyhteyden. **Älä koskaan vie tätä tiedostoa GitHubiin!** 

Luo tiedosto `nano .env` ja lisää sinne seuraavat tiedot:

```env
POLYGON_RPC_URL="sinun_alchemy_tai_infura_polygon_urli_tähän"
PRIVATE_KEY="lompakkosi_yksityisavain_tähän_ilman_0x_alkua"
