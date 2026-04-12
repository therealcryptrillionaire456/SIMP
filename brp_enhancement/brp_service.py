#!/usr/bin/env python3
"""
Enhanced BRP Service
Runs the Bill Russell Protocol as a continuous service.
"""

import time
import logging
from integration.brp_enhanced_framework import BRPEnhancedFramework, OperationMode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BRPService:
    """BRP Service runner."""
    
    def __init__(self, mode='defensive'):
        # Convert string mode to OperationMode enum
        mode_map = {
            'defensive': OperationMode.DEFENSIVE,
            'offensive': OperationMode.OFFENSIVE,
            'hybrid': OperationMode.HYBRID,
            'intelligence': OperationMode.INTELLIGENCE
        }
        
        operation_mode = mode_map.get(mode.lower(), OperationMode.DEFENSIVE)
        self.brp = BRPEnhancedFramework(mode=operation_mode)
        self.running = False
        logger.info(f"BRP Service initialized in {mode} mode")
    
    def start(self):
        """Start the BRP service."""
        self.running = True
        logger.info("BRP Service started")
        
        try:
            while self.running:
                # Service heartbeat
                self.brp.heartbeat()
                
                # Check for events (in a real implementation, this would poll a queue)
                # For now, just sleep
                time.sleep(10)
                
        except KeyboardInterrupt:
            logger.info("BRP Service stopping...")
        except Exception as e:
            logger.error(f"BRP Service error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the BRP service."""
        self.running = False
        logger.info("BRP Service stopped")
    
    def process_event(self, event_data):
        """Process an event through the BRP framework."""
        return self.brp.process_event(event_data)

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else 'defensive'
    
    service = BRPService(mode=mode)
    service.start()
