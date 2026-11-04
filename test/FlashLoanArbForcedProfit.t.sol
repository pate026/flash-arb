// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console} from "forge-std/Test.sol";
import {FlashLoanArb} from "../src/FlashLoanArb.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/**
 * Mock-router, joka simuloi ISwapRouterV3.exactInputSingle-kutsua
 * KIINTEALLA, ETUKATEEN MAARITELLYLLA vaihtokurssilla.
 *
 * Tama mahdollistaa sen etta voimme PAKOTTAA kannattavan arbitraasin
 * ilman etta tarvitsee manipuloida oikeaa Uniswap-poolia. Testi
 * keskittyy talloin kontraktin OMAAN logiikkaan (approve, minProfit,
 * saldojen kasittely, event), ei DEXin hinnoittelumekaniikkaan.
 */
contract MockRouter {
    // exchangeRate kertoo kuinka monta tokenOut-yksikkoa yhta
    // tokenIn-yksikkoa kohden annetaan, skaalattuna 1e18:lla.
    // Testi asettaa nama arvot niin etta leg1 * leg2 > 1 -> voittoa syntyy.
    mapping(address => mapping(address => uint256)) public rate; // rate[in][out], scaled 1e18

    function setRate(address tokenIn, address tokenOut, uint256 rateScaled) external {
        rate[tokenIn][tokenOut] = rateScaled;
    }

    struct ExactInputSingleParams {
        address tokenIn;
        address tokenOut;
        uint24 fee;
        address recipient;
        uint256 deadline;
        uint256 amountIn;
        uint256 amountOutMinimum;
        uint160 sqrtPriceLimitX96;
    }

    function exactInputSingle(ExactInputSingleParams calldata params) external returns (uint256 amountOut) {
        uint256 r = rate[params.tokenIn][params.tokenOut];
        require(r > 0, "rate ei asetettu");

        // Vedetaan tokenIn kontraktilta (FlashLoanArb teki jo approve:n)
        IERC20(params.tokenIn).transferFrom(msg.sender, address(this), params.amountIn);

        amountOut = (params.amountIn * r) / 1e18;
        require(amountOut >= params.amountOutMinimum, "slippage");

        // Mock-router "painaa" tokenOut:ia ulos - testissa deal() on jo
        // antanut tallle routerille tarpeeksi tokenOut-saldoa etukateen.
        IERC20(params.tokenOut).transfer(params.recipient, amountOut);
    }
}

contract FlashLoanArbForcedProfitTest is Test {
    address constant AAVE_PROVIDER = 0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb;
    address constant USDC = 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174;
    address constant WETH = 0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619;

    FlashLoanArb arb;
    MockRouter mockRouter;

    function setUp() public {
        arb = new FlashLoanArb(AAVE_PROVIDER);
        mockRouter = new MockRouter();
        arb.setRouterAllowed(address(mockRouter), true);

        // Annetaan mock-routerille reilusti WETH- ja USDC-saldoa, jotta
        // se pystyy "maksamaan ulos" molemmissa swap-suunnissa.
        deal(WETH, address(mockRouter), 1_000e18);
        deal(USDC, address(mockRouter), 10_000_000e6);
    }

    /**
     * Pakotettu kannattava arbitraasi:
     * Leg 1: 10 000 USDC -> WETH kurssilla, joka antaa "halvan" WETH:n
     * Leg 2: WETH -> USDC kurssilla, joka antaa "kalliin" takaisinvaihdon
     * Yhdessa nama tuottavat n. 1% voiton lainatusta summasta.
     */
    function test_forcedProfitableArbitrage() public {
        uint256 loanAmount = 10_000e6; // 10 000 USDC

        // Leg 1: 1 USDC -> 0.0005 WETH (oletetaan ETH ~2000 USDC, tama on "oikea" hinta)
        // Skaalattu 1e18: 0.0005 * 1e18 = 5e14
        mockRouter.setRate(USDC, WETH, 5e26);

        // Leg 2: 1 WETH -> 2020 USDC (hieman yli "oikean" hinnan -> arbitraasivoitto)
        // USDC:lla on 6 desimaalia, joten 2020 USDC = 2020e6, skaalattu 1e18:
        // rate = 2020e6 * 1e18 / 1e18 (koska WETH:n amountIn on 18 desim.)
        // Selkeampi: amountOut = amountIn * rate / 1e18, missa amountIn on WETH (1e18-skaalaa)
        // Haluamme: 1e18 WETH -> 2020e6 USDC, joten rate = 2020e6 * 1e18 / 1e18 = 2020e6...
        // mutta rate pitaa skaalata niin etta amountOut tulee oikeassa yksikossa:
        // amountOut = amountIn(1e18) * rate / 1e18 = rate, jos haluamme rate=2020e6, amountIn=1e18
        mockRouter.setRate(WETH, USDC, 2020e6);

        FlashLoanArb.ArbParams memory p = FlashLoanArb.ArbParams({
            routerBuy: address(mockRouter),
            routerSell: address(mockRouter),
            tokenMid: WETH,
            feeBuy: 500,
            feeSell: 3000,
            minProfit: 1e6 // vaadi edes 1 USDC voittoa
        });

        // Ennen: kontraktilla ei ole USDC:ta
        assertEq(IERC20(USDC).balanceOf(address(arb)), 0);

        // Aja arbitraasi - EI PITAISI revertoitua, koska loimme kannattavan tilanteen
        arb.requestFlashLoan(USDC, loanAmount, p);

        // Jalkeen: kontraktille pitaisi jaada voittoa (Aaven flash loan
        // -preemio Polygonissa on n. 0.05%, eli hyvin pieni verrattuna
        // meidan n. 1% keinotekoiseen hintaeroon)
        uint256 finalBalance = IERC20(USDC).balanceOf(address(arb));
        console.log("Kontraktin USDC-saldo arbitraasin jalkeen:", finalBalance);

        assertGt(finalBalance, 0, "voittoa olisi pitanyt jaada kontraktille");
    }

    /**
     * Varmistetaan etta ArbExecuted-event emittoituu oikealla voitolla
     * onnistuneessa arbitraasissa.
     */
    function test_forcedProfitableArbitrage_emitsEvent() public {
        uint256 loanAmount = 10_000e6;

        mockRouter.setRate(USDC, WETH, 5e26);
        mockRouter.setRate(WETH, USDC, 2020e6);

        FlashLoanArb.ArbParams memory p = FlashLoanArb.ArbParams({
            routerBuy: address(mockRouter),
            routerSell: address(mockRouter),
            tokenMid: WETH,
            feeBuy: 500,
            feeSell: 3000,
            minProfit: 1e6
        });

        // Emme tieda etukateen tarkkaa profit-arvoa (Aave-preemio mukana),
        // joten tarkistamme vain etta event emittoituu asset- ja
        // amount-kentilla oikein (checkTopic1=true asset, checkTopic2=false
        // koska amount ei ole indexed, checkData=false koska emme tieda
        // tarkkaa profit-arvoa etukateen ilman preemion laskemista tassa).
        vm.expectEmit(true, false, false, false);
        emit FlashLoanArb.ArbExecuted(USDC, loanAmount, 0); // viimeinen arvo ei checkata (checkData=false)

        arb.requestFlashLoan(USDC, loanAmount, p);
    }
}
