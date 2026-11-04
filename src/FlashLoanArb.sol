// SPDX-License-Identifier: MIT
pragma solidity ^0.8.10;

/**
 * FlashLoanArb
 * Aave V3 flashLoanSimple -pohjainen arbitraasisopimus.
 *
 * Kulku: lainaa asset -> swap asset->tokenMid (routerBuy)
 *        -> swap tokenMid->asset (routerSell) -> maksa laina + preemio (0,05 %).
 * Jos lopputulos ei ylita minProfit-rajaa, KOKO tx reverttaa:
 * pahin mahdollinen tappio on aina vain gas, ei koskaan lainapaaoma.
 *
 * Hyodyllisia mainnet-osoitteita:
 *   Aave PoolAddressesProvider: 0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e
 *   Uniswap V3 SwapRouter:      0xE592427A0AEce92De3Edee1F18E0157C05861564
 *
 * HUOM:
 *  - Saada importit vastaamaan omaa remappings.txt:tasi.
 *  - Kirjoitettu OZ v5:lle (kaanna solc >= 0.8.20). OZ v4: vaihda
 *    forceApprove -> safeApprove ja Ownable() ilman constructor-argumenttia.
 */

import {FlashLoanSimpleReceiverBase} from "aave-v3-core/contracts/flashloan/base/FlashLoanSimpleReceiverBase.sol";
import {IPoolAddressesProvider} from "aave-v3-core/contracts/interfaces/IPoolAddressesProvider.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// Uniswap V3 -tyylinen router-rajapinta (klassinen SwapRouter).
/// Maaritelty inline, ettei tarvita v3-core-riippuvuutta pragma-ongelmineen.
interface ISwapRouterV3 {
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

    function exactInputSingle(ExactInputSingleParams calldata params) external payable returns (uint256 amountOut);
}

contract FlashLoanArb is FlashLoanSimpleReceiverBase, Ownable {
    using SafeERC20 for IERC20;

    struct ArbParams {
        address routerBuy; // 1. jalka: asset -> tokenMid
        address routerSell; // 2. jalka: tokenMid -> asset (eri DEX tai eri fee-tier)
        address tokenMid; // valitoken, esim. WETH kun asset = USDC
        uint24 feeBuy; // poolin fee 1. jalassa (500 / 3000 / 10000)
        uint24 feeSell; // poolin fee 2. jalassa
        uint256 minProfit; // vahimmaisvoitto assetin yksikoissa, muuten revert
    }

    event ArbExecuted(address indexed asset, uint256 amount, uint256 profit);

    /// Sallitut router-osoitteet. Vain omistaja voi muokata.
    /// Suojaa vahingoilta ja vaarilta router-osoitteilta.
    mapping(address => bool) public allowedRouters;

    event RouterAllowedSet(address indexed router, bool allowed);

    /// Salli tai poista router kayttolistalta. Vain omistaja.
    function setRouterAllowed(address router, bool allowed) external onlyOwner {
        allowedRouters[router] = allowed;
        emit RouterAllowedSet(router, allowed);
    }

    constructor(address addressesProvider)
        FlashLoanSimpleReceiverBase(IPoolAddressesProvider(addressesProvider))
        Ownable(msg.sender)
    {}

    /// Kaynnista arbitraasi. Vain omistaja voi kutsua.
    function requestFlashLoan(address asset, uint256 amount, ArbParams calldata p) external onlyOwner {
        POOL.flashLoanSimple(address(this), asset, amount, abi.encode(p), 0);
    }

    /// Aave-pool kutsuu tata lainan myontamisen jalkeen.
    function executeOperation(address asset, uint256 amount, uint256 premium, address initiator, bytes calldata params)
        external
        override
        returns (bool)
    {
        require(msg.sender == address(POOL), "kutsuja ei ole POOL");
        require(initiator == address(this), "vieras initiaattori");

        ArbParams memory p = abi.decode(params, (ArbParams));

        // 1. jalka: asset -> tokenMid
        uint256 midAmount = _swapExactIn(p.routerBuy, asset, p.tokenMid, p.feeBuy, amount);

        // 2. jalka: tokenMid -> asset
        _swapExactIn(p.routerSell, p.tokenMid, asset, p.feeSell, midAmount);

        uint256 amountOwed = amount + premium;
        uint256 balance = IERC20(asset).balanceOf(address(this));

        // Koko kaupan kannattavuustarkistus. Tama suojaa myos slippagelta,
        // siksi yksittaisissa swapeissa amountOutMinimum voi olla 0.
        require(balance >= amountOwed + p.minProfit, "ei kannattava");

        // Salli Aaven vetaa laina + preemio takaisin.
        IERC20(asset).forceApprove(address(POOL), amountOwed);

        emit ArbExecuted(asset, amount, balance - amountOwed);
        return true;
    }

    function _swapExactIn(address router, address tokenIn, address tokenOut, uint24 fee, uint256 amountIn)
        internal
        returns (uint256 amountOut)
    {
        require(allowedRouters[router], "router ei sallittu");
        IERC20(tokenIn).forceApprove(router, amountIn);
        amountOut = ISwapRouterV3(router)
            .exactInputSingle(
                ISwapRouterV3.ExactInputSingleParams({
                    tokenIn: tokenIn,
                    tokenOut: tokenOut,
                    fee: fee,
                    recipient: address(this),
                    deadline: block.timestamp,
                    amountIn: amountIn,
                    amountOutMinimum: 0, // lopullinen minProfit-require suojaa koko tx:n
                    sqrtPriceLimitX96: 0
                })
            );
    }

    /// Nosta kertyneet voitot (tai pelasta jumiin jaaneet tokenit).
    function withdrawToken(address token) external onlyOwner {
        IERC20 t = IERC20(token);
        t.safeTransfer(owner(), t.balanceOf(address(this)));
    }

    function withdrawETH() external onlyOwner {
        (bool ok,) = owner().call{value: address(this).balance}("");
        require(ok, "ETH-siirto epaonnistui");
    }

    receive() external payable {}
}
