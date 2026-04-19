"""
Retailer factory for KEEPTHECHANGE.com

This module creates retailer instances based on configuration.
"""

import logging
from typing import List, Optional, Dict, Any
from app.core.config import settings

from .retailer_base import RetailerInterface
from .mock_retailer import create_mock_retailers, MockRetailer
from .walmart_retailer import create_walmart_retailer
from .target_retailer import create_target_retailer
from .amazon_retailer import create_amazon_retailer

logger = logging.getLogger(__name__)


class RetailerFactory:
    """Factory for creating retailer instances"""
    
    @staticmethod
    def create_retailers(use_mock: bool = False) -> List[RetailerInterface]:
        """
        Create retailer instances based on configuration.
        
        Args:
            use_mock: If True, create mock retailers for testing.
                     If False, create real retailers based on API key availability.
        
        Returns:
            List of retailer instances
        """
        if use_mock:
            logger.info("Creating mock retailers for testing")
            return create_mock_retailers()
        
        retailers = []
        
        # Create Walmart retailer if API key is configured
        if settings.WALMART_API_KEY:
            try:
                walmart_retailer = create_walmart_retailer(settings.WALMART_API_KEY)
                retailers.append(walmart_retailer)
                logger.info("Created Walmart retailer")
            except Exception as e:
                logger.error(f"Failed to create Walmart retailer: {str(e)}")
                # Fall back to mock
                retailers.append(MockRetailer(name="walmart"))
        else:
            logger.warning("Walmart API key not configured, using mock")
            retailers.append(MockRetailer(name="walmart"))
        
        # Create Target retailer if API key is configured
        if settings.TARGET_API_KEY:
            try:
                target_retailer = create_target_retailer(settings.TARGET_API_KEY)
                retailers.append(target_retailer)
                logger.info("Created Target retailer")
            except Exception as e:
                logger.error(f"Failed to create Target retailer: {str(e)}")
                # Fall back to mock
                retailers.append(MockRetailer(name="target"))
        else:
            logger.warning("Target API key not configured, using mock")
            retailers.append(MockRetailer(name="target"))
        
        # Create Amazon retailer if credentials are configured
        if settings.AMAZON_ASSOCIATE_TAG:
            try:
                # Note: Amazon API requires API key and secret from environment
                # These should be set in .env file
                amazon_api_key = getattr(settings, "AMAZON_API_KEY", "")
                amazon_api_secret = getattr(settings, "AMAZON_API_SECRET", "")
                
                if amazon_api_key and amazon_api_secret:
                    amazon_retailer = create_amazon_retailer(
                        api_key=amazon_api_key,
                        api_secret=amazon_api_secret,
                        associate_tag=settings.AMAZON_ASSOCIATE_TAG,
                        region="US"
                    )
                    retailers.append(amazon_retailer)
                    logger.info("Created Amazon retailer")
                else:
                    logger.warning("Amazon API key/secret not configured, using mock")
                    retailers.append(MockRetailer(name="amazon"))
            except Exception as e:
                logger.error(f"Failed to create Amazon retailer: {str(e)}")
                # Fall back to mock
                retailers.append(MockRetailer(name="amazon"))
        else:
            logger.warning("Amazon Associate Tag not configured, using mock")
            retailers.append(MockRetailer(name="amazon"))
        
        # Add additional mock retailers for testing
        if len(retailers) < 3:
            # Add some additional mock retailers for variety
            additional_retailers = [
                MockRetailer(name="costco"),
                MockRetailer(name="kroger"),
                MockRetailer(name="whole_foods")
            ]
            retailers.extend(additional_retailers[:3 - len(retailers)])
        
        logger.info(f"Created {len(retailers)} retailers: {[r.retailer_name for r in retailers]}")
        return retailers
    
    @staticmethod
    def create_retailer_by_name(name: str, use_mock: bool = False) -> Optional[RetailerInterface]:
        """
        Create a specific retailer by name.
        
        Args:
            name: Retailer name (walmart, target, amazon, etc.)
            use_mock: If True, create mock retailer
        
        Returns:
            Retailer instance or None if not found/configured
        """
        name_lower = name.lower()
        
        if use_mock:
            return MockRetailer(name=name_lower)
        
        if name_lower == "walmart" and settings.WALMART_API_KEY:
            try:
                return create_walmart_retailer(settings.WALMART_API_KEY)
            except Exception as e:
                logger.error(f"Failed to create Walmart retailer: {str(e)}")
                return MockRetailer(name="walmart")
        
        elif name_lower == "target" and settings.TARGET_API_KEY:
            try:
                return create_target_retailer(settings.TARGET_API_KEY)
            except Exception as e:
                logger.error(f"Failed to create Target retailer: {str(e)}")
                return MockRetailer(name="target")
        
        elif name_lower == "amazon" and settings.AMAZON_ASSOCIATE_TAG:
            try:
                amazon_api_key = getattr(settings, "AMAZON_API_KEY", "")
                amazon_api_secret = getattr(settings, "AMAZON_API_SECRET", "")
                
                if amazon_api_key and amazon_api_secret:
                    return create_amazon_retailer(
                        api_key=amazon_api_key,
                        api_secret=amazon_api_secret,
                        associate_tag=settings.AMAZON_ASSOCIATE_TAG,
                        region="US"
                    )
                else:
                    logger.warning("Amazon API key/secret not configured, using mock")
                    return MockRetailer(name="amazon")
            except Exception as e:
                logger.error(f"Failed to create Amazon retailer: {str(e)}")
                return MockRetailer(name="amazon")
        
        else:
            logger.warning(f"Retailer {name} not configured or not found, using mock")
            return MockRetailer(name=name_lower)
    
    @staticmethod
    def get_available_retailers() -> List[Dict[str, Any]]:
        """
        Get list of available retailers and their configuration status.
        
        Returns:
            List of retailer information dictionaries
        """
        retailers = []
        
        # Walmart
        walmart_info = {
            "name": "Walmart",
            "id": "walmart",
            "configured": bool(settings.WALMART_API_KEY),
            "requires_api_key": True,
            "description": "Walmart - Save Money. Live Better.",
            "website": "https://www.walmart.com",
            "free_shipping_threshold": 35.0
        }
        retailers.append(walmart_info)
        
        # Target
        target_info = {
            "name": "Target",
            "id": "target",
            "configured": bool(settings.TARGET_API_KEY),
            "requires_api_key": True,
            "description": "Target - Expect More. Pay Less.",
            "website": "https://www.target.com",
            "free_shipping_threshold": 35.0,
            "supports_store_pickup": True
        }
        retailers.append(target_info)
        
        # Amazon
        amazon_info = {
            "name": "Amazon",
            "id": "amazon",
            "configured": bool(settings.AMAZON_ASSOCIATE_TAG),
            "requires_api_key": True,
            "requires_associate_tag": True,
            "description": "Amazon - Earth's Most Customer-Centric Company",
            "website": "https://www.amazon.com",
            "free_shipping_threshold": 25.0,
            "supports_prime": True
        }
        retailers.append(amazon_info)
        
        # Mock retailers (always available)
        mock_retailers = [
            {
                "name": "Costco",
                "id": "costco",
                "configured": True,
                "requires_api_key": False,
                "description": "Costco Wholesale",
                "website": "https://www.costco.com",
                "requires_membership": True
            },
            {
                "name": "Kroger",
                "id": "kroger",
                "configured": True,
                "requires_api_key": False,
                "description": "Kroger Supermarkets",
                "website": "https://www.kroger.com",
                "supports_grocery_delivery": True
            },
            {
                "name": "Whole Foods",
                "id": "whole_foods",
                "configured": True,
                "requires_api_key": False,
                "description": "Whole Foods Market",
                "website": "https://www.wholefoodsmarket.com",
                "organic_focused": True
            }
        ]
        retailers.extend(mock_retailers)
        
        return retailers


# Singleton instance
retailer_factory = RetailerFactory()