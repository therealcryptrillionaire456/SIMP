"""
Keep the Change (KTC) Agent for SIMP System

This agent handles receipt processing, price comparison, and crypto investment
intents for the KTC application.
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import sqlite3
from pathlib import Path

from simp.agent import SimpAgent


@dataclass
class ReceiptItem:
    """Represents an item from a receipt"""
    name: str
    brand: Optional[str] = None
    quantity: int = 1
    price: float = 0.0
    unit_price: float = 0.0


@dataclass
class PriceComparison:
    """Represents a price comparison opportunity"""
    item_name: str
    current_price: float
    cheaper_price: float
    store: str
    savings: float
    distance_miles: float


@dataclass
class InvestmentResult:
    """Represents a crypto investment result"""
    success: bool
    amount_usd: float
    crypto_amount: float
    crypto_asset: str
    exchange_rate: float
    transaction_hash: Optional[str] = None
    error_message: Optional[str] = None


class KTCAgent(SimpAgent):
    """Keep the Change Agent for SIMP System"""
    
    def __init__(
        self,
        agent_id: str = "ktc_agent",
        organization: str = "ktc",
        private_key_pem: bytes = None,
        endpoint: str = "http://localhost:8765",
        db_path: str = "ktc.db",
        log_level: str = "INFO"
    ):
        """
        Initialize KTC Agent
        
        Args:
            agent_id: Unique agent identifier
            organization: Organization name
            private_key_pem: Private key for signing
            endpoint: HTTP endpoint for this agent
            db_path: Path to SQLite database
            log_level: Logging level
        """
        super().__init__(agent_id=agent_id, organization=organization, private_key_pem=private_key_pem)
        
        # Store additional parameters
        self.endpoint = endpoint
        
        # Set up logging
        self.logger = logging.getLogger(f"simp.agents.{agent_id}")
        self.logger.setLevel(getattr(logging, log_level))
        
        # Database setup
        self.db_path = Path(db_path)
        self._init_database()
        
        # Agent capabilities
        self.capabilities = [
            "receipt_processing",
            "price_comparison",
            "savings_calculation",
            "crypto_investment",
            "wallet_management"
        ]
        
        # Configuration
        self.config = {
            "min_savings_for_investment": 0.01,  # Minimum $0.01 to invest
            "auto_invest_enabled": True,
            "default_crypto_asset": "SOL",
            "price_comparison_radius_miles": 10,
            "max_investment_per_day": 100.00
        }
        
        self.logger.info(f"KTC Agent initialized: {agent_id}")
        self.logger.info(f"Capabilities: {', '.join(self.capabilities)}")
    
    def _init_database(self) -> None:
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ktc_users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE,
                wallet_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_savings DECIMAL(10,2) DEFAULT 0.0,
                total_invested DECIMAL(10,2) DEFAULT 0.0
            )
        """)
        
        # Create receipts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ktc_receipts (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                store_name TEXT,
                total_amount DECIMAL(10,2),
                receipt_date TIMESTAMP,
                image_path TEXT,
                processed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES ktc_users(id)
            )
        """)
        
        # Create receipt items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ktc_receipt_items (
                id TEXT PRIMARY KEY,
                receipt_id TEXT,
                item_name TEXT,
                brand TEXT,
                quantity INTEGER,
                price DECIMAL(10,2),
                unit_price DECIMAL(10,2),
                FOREIGN KEY (receipt_id) REFERENCES ktc_receipts(id)
            )
        """)
        
        # Create price comparisons table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ktc_price_comparisons (
                id TEXT PRIMARY KEY,
                receipt_item_id TEXT,
                alternative_store TEXT,
                alternative_price DECIMAL(10,2),
                savings DECIMAL(10,2),
                distance_miles DECIMAL(5,2),
                comparison_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (receipt_item_id) REFERENCES ktc_receipt_items(id)
            )
        """)
        
        # Create investments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ktc_investments (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                amount DECIMAL(10,2),
                crypto_amount DECIMAL(20,10),
                crypto_asset TEXT,
                exchange_rate DECIMAL(20,10),
                transaction_hash TEXT,
                investment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source_receipt_id TEXT,
                FOREIGN KEY (user_id) REFERENCES ktc_users(id),
                FOREIGN KEY (source_receipt_id) REFERENCES ktc_receipts(id)
            )
        """)
        
        conn.commit()
        conn.close()
        self.logger.info(f"Database initialized at {self.db_path}")
    
    def handle_intent(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming intents from SIMP broker
        
        Args:
            intent_data: Intent data from SIMP broker
            
        Returns:
            Response dictionary
        """
        intent_type = intent_data.get("intent_type", "")
        parameters = intent_data.get("parameters", {})
        
        self.logger.info(f"Handling intent: {intent_type}")
        
        try:
            if intent_type == "process_receipt":
                return self._handle_process_receipt(parameters)
            elif intent_type == "compare_prices":
                return self._handle_compare_prices(parameters)
            elif intent_type == "calculate_savings":
                return self._handle_calculate_savings(parameters)
            elif intent_type == "invest_savings":
                return self._handle_invest_savings(parameters)
            elif intent_type == "get_user_stats":
                return self._handle_get_user_stats(parameters)
            elif intent_type == "health_check":
                return self.health()
            else:
                return self._error_response(
                    f"Unsupported intent type: {intent_type}",
                    supported_intents=[
                        "process_receipt",
                        "compare_prices", 
                        "calculate_savings",
                        "invest_savings",
                        "get_user_stats",
                        "health_check"
                    ]
                )
        except Exception as e:
            self.logger.error(f"Error handling intent {intent_type}: {str(e)}")
            return self._error_response(f"Internal error: {str(e)}")
    
    def _handle_process_receipt(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process a receipt image and extract items"""
        # For now, mock implementation
        # In production, integrate with OCR service (Google Vision, Tesseract)
        
        receipt_id = params.get("receipt_id", f"rec_{int(time.time())}")
        user_id = params.get("user_id", "demo_user")
        store_name = params.get("store_name", "Unknown Store")
        
        # Mock receipt items
        mock_items = [
            ReceiptItem(name="Organic Milk", brand="Organic Valley", quantity=1, price=5.99, unit_price=5.99),
            ReceiptItem(name="Whole Wheat Bread", brand="Nature's Own", quantity=1, price=3.49, unit_price=3.49),
            ReceiptItem(name="Bananas", brand=None, quantity=6, price=2.94, unit_price=0.49),
            ReceiptItem(name="Eggs", brand="Happy Hens", quantity=12, price=4.99, unit_price=0.42),
            ReceiptItem(name="Coffee", brand="Starbucks", quantity=1, price=12.99, unit_price=12.99)
        ]
        
        total = sum(item.price for item in mock_items)
        
        # Save to database (mock)
        self._save_receipt_to_db(receipt_id, user_id, store_name, total, mock_items)
        
        return {
            "status": "success",
            "receipt_id": receipt_id,
            "items": [asdict(item) for item in mock_items],
            "total": total,
            "item_count": len(mock_items),
            "message": "Receipt processed successfully"
        }
    
    def _handle_compare_prices(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Compare prices for receipt items at nearby stores"""
        items = params.get("items", [])
        location = params.get("location", {})
        
        if not items:
            return self._error_response("No items provided for price comparison")
        
        # Mock price comparisons
        comparisons = []
        total_savings = 0.0
        
        for item in items[:3]:  # Compare first 3 items for demo
            item_name = item.get("name", "Unknown Item")
            current_price = item.get("price", 0.0)
            
            # Generate mock cheaper price (10-30% cheaper)
            cheaper_price = round(current_price * (0.7 + 0.2 * (hash(item_name) % 10) / 10), 2)
            savings = round(current_price - cheaper_price, 2)
            
            if savings > 0:
                comparison = PriceComparison(
                    item_name=item_name,
                    current_price=current_price,
                    cheaper_price=cheaper_price,
                    store=f"Store {(hash(item_name) % 5) + 1}",
                    savings=savings,
                    distance_miles=round(0.5 + (hash(item_name) % 10) / 2, 1)
                )
                comparisons.append(comparison)
                total_savings += savings
        
        return {
            "status": "success",
            "comparisons": [asdict(comp) for comp in comparisons],
            "total_potential_savings": round(total_savings, 2),
            "comparison_count": len(comparisons),
            "message": f"Found {len(comparisons)} savings opportunities"
        }
    
    def _handle_calculate_savings(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate total savings from price comparisons"""
        comparisons = params.get("comparisons", [])
        
        if not comparisons:
            return self._error_response("No comparisons provided")
        
        total_savings = sum(comp.get("savings", 0.0) for comp in comparisons)
        
        return {
            "status": "success",
            "total_savings": round(total_savings, 2),
            "eligible_for_investment": total_savings >= self.config["min_savings_for_investment"],
            "min_savings_required": self.config["min_savings_for_investment"],
            "message": f"Total savings: ${total_savings:.2f}"
        }
    
    def _handle_invest_savings(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Invest savings into crypto through SIMP QuantumArb agent"""
        amount = params.get("amount", 0.0)
        user_id = params.get("user_id", "demo_user")
        receipt_id = params.get("receipt_id")
        
        if amount < self.config["min_savings_for_investment"]:
            return self._error_response(
                f"Amount ${amount:.2f} below minimum ${self.config['min_savings_for_investment']:.2f}"
            )
        
        # Check daily investment limit
        daily_investment = self._get_daily_investment(user_id)
        if daily_investment + amount > self.config["max_investment_per_day"]:
            return self._error_response(
                f"Daily investment limit exceeded. "
                f"Already invested: ${daily_investment:.2f}, "
                f"Limit: ${self.config['max_investment_per_day']:.2f}"
            )
        
        # Mock investment - in production, this would route to QuantumArb agent
        mock_result = InvestmentResult(
            success=True,
            amount_usd=amount,
            crypto_amount=amount / 1666.67,  # Mock SOL price
            crypto_asset=self.config["default_crypto_asset"],
            exchange_rate=1666.67,
            transaction_hash=f"0x{int(time.time()):x}{hash(str(amount)) % 1000:03x}"
        )
        
        # Save investment to database
        self._save_investment_to_db(user_id, amount, mock_result, receipt_id)
        
        return {
            "status": "success",
            "investment": asdict(mock_result),
            "message": f"Successfully invested ${amount:.2f} into {mock_result.crypto_asset}"
        }
    
    def _handle_get_user_stats(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get user statistics"""
        user_id = params.get("user_id", "demo_user")
        
        # Mock user stats
        return {
            "status": "success",
            "user_id": user_id,
            "stats": {
                "total_receipts": 5,
                "total_savings": 15.75,
                "total_invested": 10.50,
                "crypto_balance": 0.0063,
                "crypto_asset": "SOL",
                "estimated_value": 10.50,
                "last_investment": "2026-04-10T14:30:00Z"
            },
            "message": "User statistics retrieved"
        }
    
    def _save_receipt_to_db(
        self, 
        receipt_id: str, 
        user_id: str, 
        store_name: str, 
        total: float,
        items: List[ReceiptItem]
    ) -> None:
        """Save receipt and items to database (mock implementation)"""
        self.logger.info(f"Mock: Saving receipt {receipt_id} for user {user_id}")
        # In production, implement actual database operations
    
    def _save_investment_to_db(
        self, 
        user_id: str, 
        amount: float, 
        result: InvestmentResult,
        receipt_id: Optional[str] = None
    ) -> None:
        """Save investment to database (mock implementation)"""
        self.logger.info(f"Mock: Saving investment of ${amount:.2f} for user {user_id}")
        # In production, implement actual database operations
    
    def _get_daily_investment(self, user_id: str) -> float:
        """Get today's total investment for a user (mock implementation)"""
        # In production, query database
        return 0.0
    
    def _error_response(self, message: str, **kwargs) -> Dict[str, Any]:
        """Create standardized error response"""
        response = {
            "status": "error",
            "error": message,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        response.update(kwargs)
        return response
    
    def health(self) -> Dict[str, Any]:
        """Return agent health status"""
        return {
            "status": "healthy",
            "agent_id": self.agent_id,
            "capabilities": self.capabilities,
            "database": str(self.db_path),
            "config": self.config,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    
    def close(self) -> None:
        """Clean up agent resources"""
        self.logger.info("KTC Agent shutting down")


def create_ktc_agent() -> KTCAgent:
    """Factory function to create KTC agent"""
    return KTCAgent(
        agent_id="ktc_agent",
        endpoint="http://localhost:8765",
        db_path="data/ktc.db",
        log_level="INFO"
    )


if __name__ == "__main__":
    # Example usage
    agent = create_ktc_agent()
    
    # Test receipt processing
    test_intent = {
        "intent_type": "process_receipt",
        "parameters": {
            "user_id": "test_user_123",
            "store_name": "Whole Foods",
            "receipt_id": "test_receipt_001"
        }
    }
    
    result = agent.handle_intent(test_intent)
    print("Test Result:", json.dumps(result, indent=2))
    
    # Test health check
    health = agent.health()
    print("\nHealth Check:", json.dumps(health, indent=2))