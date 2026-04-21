#!/usr/bin/env python3.10
"""
Apply Agent Lightning patch to running SIMP broker
"""

import sys
import os
import logging
import time

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def apply_agent_lightning_patch():
    """Apply Agent Lightning patch to the broker"""
    
    try:
        # Import the patch
        from patches.agent_lightning_broker_patch import patch_broker_for_agent_lightning
        
        # Try to get the broker instance
        # This depends on how the broker is structured
        try:
            from simp.server.broker import SimpBroker
            
            # Check if broker instance exists
            # In a real implementation, we might need to get it from a singleton or global
            broker_instance = None
            
            # Try to get from module
            import simp.server.broker as broker_module
            if hasattr(broker_module, 'broker_instance'):
                broker_instance = broker_module.broker_instance
            elif hasattr(broker_module, 'broker'):
                broker_instance = broker_module.broker
            
            if broker_instance:
                logger.info(f"Found broker instance: {broker_instance}")
                
                # Apply patch
                patched_broker = patch_broker_for_agent_lightning(broker_instance)
                
                if patched_broker:
                    logger.info("✅ Successfully applied Agent Lightning patch to broker")
                    
                    # Test the patch
                    test_agent_lightning_integration()
                    return True
                else:
                    logger.error("Failed to patch broker")
                    return False
            else:
                logger.warning("No broker instance found. Broker may not be running or structured differently.")
                
                # Try to patch the class itself
                logger.info("Attempting to patch SimpBroker class...")
                patched_class = patch_broker_for_agent_lightning(SimpBroker)
                
                if patched_class:
                    logger.info("✅ Patched SimpBroker class")
                    return True
                else:
                    logger.error("Failed to patch SimpBroker class")
                    return False
                
        except ImportError as e:
            logger.error(f"Failed to import broker: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Error applying Agent Lightning patch: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_agent_lightning_integration():
    """Test Agent Lightning integration"""
    
    try:
        # Test Agent Lightning manager
        from simp.integrations.agent_lightning import agent_lightning_manager
        
        logger.info("Testing Agent Lightning integration...")
        
        # Check if enabled
        if agent_lightning_manager.config.enabled:
            logger.info("✅ Agent Lightning is enabled")
            
            # Check health
            health = agent_lightning_manager.health_check()
            logger.info(f"Agent Lightning health: {health}")
            
            # Test proxy
            proxy_healthy = agent_lightning_manager.start_proxy()
            if proxy_healthy:
                logger.info("✅ Agent Lightning proxy is healthy")
            else:
                logger.warning("⚠️ Agent Lightning proxy is not running")
        else:
            logger.warning("⚠️ Agent Lightning is disabled in configuration")
            
            # Enable it for testing
            logger.info("Enabling Agent Lightning for testing...")
            agent_lightning_manager.config.enabled = True
            agent_lightning_manager.config.trace_all_agents = True
            
            # Set environment variables
            os.environ['AGENT_LIGHTNING_ENABLED'] = 'true'
            os.environ['AGENT_LIGHTNING_PROXY_HOST'] = 'localhost'
            os.environ['AGENT_LIGHTNING_PROXY_PORT'] = '8320'  # Our APO wrapper
            os.environ['AGENT_LIGHTNING_STORE_HOST'] = 'localhost'
            os.environ['AGENT_LIGHTNING_STORE_PORT'] = '43887'
            
            logger.info("✅ Agent Lightning enabled for testing")
            
    except ImportError as e:
        logger.error(f"Agent Lightning integration not available: {e}")
    except Exception as e:
        logger.error(f"Error testing Agent Lightning: {e}")

def setup_agent_lightning_environment():
    """Set up environment for Agent Lightning"""
    
    logger.info("Setting up Agent Lightning environment...")
    
    # Set environment variables
    os.environ['AGENT_LIGHTNING_ENABLED'] = 'true'
    os.environ['AGENT_LIGHTNING_PROXY_HOST'] = 'localhost'
    os.environ['AGENT_LIGHTNING_PROXY_PORT'] = '8320'  # Our APO wrapper
    os.environ['AGENT_LIGHTNING_STORE_HOST'] = 'localhost'
    os.environ['AGENT_LIGHTNING_STORE_PORT'] = '43887'
    os.environ['AGENT_LIGHTNING_MODEL'] = 'glm-4-plus'
    
    # Enable APO for Stray Goose
    os.environ['AGENT_LIGHTNING_ENABLE_APO'] = 'true'
    os.environ['AGENT_LIGHTNING_TRACE_ALL_AGENTS'] = 'true'
    
    logger.info("✅ Environment set up for Agent Lightning")

def main():
    """Main function"""
    
    logger.info("================================================")
    logger.info("🚀 Applying Agent Lightning Patch to SIMP Broker")
    logger.info("================================================")
    
    # Set up environment
    setup_agent_lightning_environment()
    
    # Apply patch
    success = apply_agent_lightning_patch()
    
    if success:
        logger.info("✅ Agent Lightning patch applied successfully")
        
        # Give some time for the patch to take effect
        logger.info("Waiting for integration to stabilize...")
        time.sleep(2)
        
        # Test integration
        test_agent_lightning_integration()
        
        logger.info("================================================")
        logger.info("🎉 Agent Lightning integration complete!")
        logger.info("================================================")
        
        # Next steps
        logger.info("\nNext steps:")
        logger.info("1. Test Agent Lightning with an intent")
        logger.info("2. Check dashboard for Agent Lightning widgets")
        logger.info("3. Monitor /tmp/apo_wrapper.log for APO activity")
        logger.info("4. Run integration tests")
        
    else:
        logger.error("❌ Failed to apply Agent Lightning patch")
        sys.exit(1)

if __name__ == "__main__":
    main()