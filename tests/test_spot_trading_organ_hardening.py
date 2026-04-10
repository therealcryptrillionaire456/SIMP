"""
Hardening tests for SpotTradingOrgan.

Tests for:
- Slippage tolerance validation
- Extreme value validation
- Parameter type safety
- Edge case handling
"""

import asyncio
import pytest
import sys
from datetime import datetime

sys.path.insert(0, '/sessions/fervent-elegant-johnson')

from simp.organs.spot_trading_organ import SpotTradingOrgan
from simp.integrations.trading_organ import ExecutionStatus


class TestSpotTradingOrganHardening:
    """Hardening tests for SpotTradingOrgan"""

    @pytest.fixture
    def organ(self):
        """Create a fresh organ for each test"""
        return SpotTradingOrgan(organ_id="test:spot:hardening", initial_balance=10000.0)

    @pytest.mark.asyncio
    async def test_slippage_tolerance_validation(self, organ):
        """Test that slippage_tolerance is properly validated"""
        test_cases = [
            # (slippage_tolerance, should_be_valid, description)
            (0.01, True, "normal 1% slippage"),
            (0.0, True, "zero slippage"),
            (0.5, True, "50% slippage (extreme but valid)"),
            (-0.01, False, "negative slippage"),
            ("not_a_number", False, "non-numeric slippage"),
            (None, True, "None slippage (should use default)"),
        ]
        
        for slippage, should_be_valid, description in test_cases:
            params = {
                "asset_pair": "SOL/USDC",
                "side": "BUY",
                "quantity": 10.0,
                "price": 150.0,
                "slippage_tolerance": slippage,
            }
            
            is_valid = await organ.validate_params(params)
            
            if should_be_valid:
                assert is_valid, f"Expected valid for {description}: {slippage}"
            else:
                assert not is_valid, f"Expected invalid for {description}: {slippage}"

    @pytest.mark.asyncio
    async def test_extreme_slippage_execution(self, organ):
        """Test execution with extreme slippage values"""
        # Test with very high slippage
        params = {
            "organ_id": "test:spot:hardening",
            "asset_pair": "SOL/USDC",
            "side": "BUY",
            "quantity": 5.0,
            "price": 150.0,
            "slippage_tolerance": 1.0,  # 100% slippage!
        }
        
        result = await organ.execute(params, "test:intent:001")
        
        # Should execute successfully (extreme slippage is allowed)
        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.executions) == 1
        execution = result.executions[0]
        assert execution.slippage >= 0  # Slippage should be non-negative
        assert execution.slippage <= 100  # Should not exceed 100%

    @pytest.mark.asyncio
    async def test_parameter_type_safety(self, organ):
        """Test that parameter types are properly handled"""
        test_cases = [
            # (params, should_be_valid, description)
            ({
                "asset_pair": "SOL/USDC",
                "side": "BUY",
                "quantity": "10.0",  # String that can be converted to float
                "price": "150.0",
                "slippage_tolerance": "0.01",
            }, True, "string numbers that can be converted"),
            ({
                "asset_pair": "SOL/USDC",
                "side": "BUY",
                "quantity": "not_a_number",  # Invalid string
                "price": 150.0,
            }, False, "non-numeric quantity string"),
            ({
                "asset_pair": "SOL/USDC",
                "side": "BUY",
                "quantity": 10.0,
                "price": "invalid_price",
            }, False, "non-numeric price string"),
            ({
                "asset_pair": "SOL/USDC",
                "side": "BUY",
                "quantity": 0.0,  # Zero quantity
                "price": 150.0,
            }, False, "zero quantity"),
            ({
                "asset_pair": "SOL/USDC",
                "side": "BUY",
                "quantity": -5.0,  # Negative quantity
                "price": 150.0,
            }, False, "negative quantity"),
            ({
                "asset_pair": "SOL/USDC",
                "side": "BUY",
                "quantity": 10.0,
                "price": 0.0,  # Zero price
            }, False, "zero price"),
            ({
                "asset_pair": "SOL/USDC",
                "side": "BUY",
                "quantity": 10.0,
                "price": -150.0,  # Negative price
            }, False, "negative price"),
        ]
        
        for params, should_be_valid, description in test_cases:
            is_valid = await organ.validate_params(params)
            
            if should_be_valid:
                assert is_valid, f"Expected valid for {description}"
            else:
                assert not is_valid, f"Expected invalid for {description}"

    @pytest.mark.asyncio
    async def test_edge_case_quantity_precision(self, organ):
        """Test edge cases with quantity precision"""
        # Test with very small quantity
        params = {
            "organ_id": "test:spot:hardening",
            "asset_pair": "SOL/USDC",
            "side": "BUY",
            "quantity": 0.00000001,  # Very small
            "price": 150.0,
            "slippage_tolerance": 0.01,
        }
        
        # Should validate successfully
        is_valid = await organ.validate_params(params)
        assert is_valid, "Very small quantity should be valid"
        
        # But execution might fail due to insufficient funds for fee
        result = await organ.execute(params, "test:intent:tiny")
        # Either completed or failed due to balance, but shouldn't crash
        assert result.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]

    @pytest.mark.asyncio
    async def test_missing_slippage_tolerance_default(self, organ):
        """Test that missing slippage_tolerance uses default value"""
        params = {
            "organ_id": "test:spot:hardening",
            "asset_pair": "SOL/USDC",
            "side": "BUY",
            "quantity": 5.0,
            "price": 150.0,
            # slippage_tolerance not specified - should use default 0.01
        }
        
        result = await organ.execute(params, "test:intent:default-slip")
        
        # Should execute successfully with default slippage
        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.executions) == 1
        execution = result.executions[0]
        assert execution.slippage >= 0
        assert execution.slippage <= 1.0  # Default is 1% max

    @pytest.mark.asyncio
    async def test_asset_pair_format_validation(self, organ):
        """Test asset pair format validation"""
        test_cases = [
            ("SOL/USDC", True, "valid pair with slash"),
            ("SOL-USDC", False, "dash separator not supported"),
            ("SOL", False, "missing quote currency"),
            ("SOL/USDC/EUR", False, "too many parts"),
            ("", False, "empty string"),
            (None, False, "None asset pair"),
            ("/USDC", False, "missing base currency"),
            ("SOL/", False, "missing quote currency"),
            ("BTC/USDT", True, "another valid pair"),
        ]
        
        for asset_pair, should_be_valid, description in test_cases:
            params = {
                "asset_pair": asset_pair,
                "side": "BUY",
                "quantity": 10.0,
                "price": 150.0,
            }
            
            is_valid = await organ.validate_params(params)
            
            if should_be_valid:
                assert is_valid, f"Expected valid for {description}: {asset_pair}"
            else:
                assert not is_valid, f"Expected invalid for {description}: {asset_pair}"

    @pytest.mark.asyncio
    async def test_side_case_insensitivity(self, organ):
        """Test that side parameter is case-insensitive"""
        test_cases = [
            ("BUY", True, "uppercase buy"),
            ("buy", True, "lowercase buy"),
            ("Buy", True, "mixed case buy"),
            ("SELL", True, "uppercase sell"),
            ("sell", True, "lowercase sell"),
            ("Sell", True, "mixed case sell"),
            ("HOLD", False, "invalid side"),
            ("", False, "empty side"),
            (None, False, "None side"),
        ]
        
        for side, should_be_valid, description in test_cases:
            params = {
                "asset_pair": "SOL/USDC",
                "side": side,
                "quantity": 10.0,
                "price": 150.0,
            }
            
            is_valid = await organ.validate_params(params)
            
            if should_be_valid:
                assert is_valid, f"Expected valid for {description}: {side}"
            else:
                assert not is_valid, f"Expected invalid for {description}: {side}"