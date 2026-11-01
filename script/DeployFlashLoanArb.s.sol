// SPDX-License-Identifier: MIT
pragma solidity ^0.8.10;

import {Script, console} from "forge-std/Script.sol";
import {FlashLoanArb} from "../src/FlashLoanArb.sol";

/// @notice Deploy-skripti FlashLoanArb-sopimukselle.
/// Valitsee Aave V3 PoolAddressesProvider -osoitteen automaattisesti
/// chain id:n perusteella. Voit ylikirjoittaa osoitteen ympäristömuuttujalla:
///   AAVE_PROVIDER=0x... forge script ...
contract DeployFlashLoanArb is Script {
    // Aave V3 PoolAddressesProvider -osoitteet (lähde: bgd-labs/aave-address-book)
    address internal constant PROVIDER_MAINNET = 0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e;
    address internal constant PROVIDER_SEPOLIA = 0x012bAC54348C0E635dCAc9D5FB99f06F24136C9A;
    // Polygon, Arbitrum ja Optimism jakavat saman osoitteen
    address internal constant PROVIDER_POL_ARB_OP = 0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb;

    function run() external returns (FlashLoanArb arb) {
        address provider = _providerForChain();

        vm.startBroadcast();
        // HUOM: oletus on constructor(address _addressProvider).
        // Jos konstruktorisi ottaa muitakin parametreja (esim. SwapRouter),
        // lisää ne tähän.
        arb = new FlashLoanArb(provider);
        vm.stopBroadcast();

        console.log("Chain ID:             ", block.chainid);
        console.log("PoolAddressesProvider:", provider);
        console.log("FlashLoanArb:         ", address(arb));
    }

    function _providerForChain() internal view returns (address) {
        // Ympäristömuuttuja ohittaa automaattisen valinnan
        address fromEnv = vm.envOr("AAVE_PROVIDER", address(0));
        if (fromEnv != address(0)) return fromEnv;

        if (block.chainid == 1) return PROVIDER_MAINNET; // Ethereum
        if (block.chainid == 11155111) return PROVIDER_SEPOLIA; // Sepolia
        if (block.chainid == 137) return PROVIDER_POL_ARB_OP; // Polygon
        if (block.chainid == 42161) return PROVIDER_POL_ARB_OP; // Arbitrum
        if (block.chainid == 10) return PROVIDER_POL_ARB_OP; // Optimism
        // Anvil-fork perii forkatun verkon chain id:n, joten yllaolevat toimivat myos forkilla

        revert("Tuntematon verkko: aseta AAVE_PROVIDER-ymparistomuuttuja");
    }
}
