# UniswapV3 Python Client

A python client for interacting with UniswapV3. It supports swapping, and position management.

## Guides
Interacting with pool, router, and if deploying a new pool, factory contracts.
- Pool: https://github.com/Uniswap/uniswap-v3-core/blob/main/contracts/UniswapV3Pool.sol
- NonfungiblePositionManager: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/NonfungiblePositionManager.sol
- SwapRouter: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/SwapRouter.sol
- Quoter: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/lens/Quoter.sol
- TickLens: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/lens/TickLens.sol

Documentation is available here: https://docs.uniswap.org/concepts/V3-overview/glossary

## Usage

Instantiate either SwapRouter or PositionManager entities that wrap the respective uniswap-v3-periphery contracts.

## Design


### Future Improvements
- abstract univ3 test fixtures to conftest
- support permit
- int() cast rounding issues
- uniswapv3_math specific tests
- Add oracle support
- check for token decimals

### Other Libraries
- https://github.com/Uniswap/uniswap-v3-sdk
- https://github.com/uniswap-python/uniswap-python
- https://github.com/thanpolas/univ3prices

