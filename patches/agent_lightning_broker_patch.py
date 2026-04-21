"""
Agent Lightning Broker Patch

This patch integrates Agent Lightning with the SIMP broker,
adding tracing for all intent deliveries and LLM calls.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

def patch_broker_for_agent_lightning(broker):
    """Patch the SIMP broker to integrate Agent Lightning"""
    
    # Try to import Agent Lightning integration
    try:
        from simp.integrations.agent_lightning import (
            agent_lightning_manager,
            trace_intent_delivery,
            integrate_with_broker
        )
        
        logger.info("Patching SIMP broker for Agent Lightning integration")
        
        # Store original methods
        original_deliver_intent = getattr(broker, '_deliver_intent', None)
        original_handle_intent = getattr(broker, 'handle_intent', None)
        
        if not agent_lightning_manager.config.enabled:
            logger.info("Agent Lightning integration disabled in configuration")
            return broker
        
        # Patch _deliver_intent method to add tracing
        def patched_deliver_intent(intent_data, target_url):
            """Patched version of _deliver_intent with Agent Lightning tracing"""
            
            # Extract intent information for tracing
            intent_id = intent_data.get('intent_id', 'unknown')
            source_agent = intent_data.get('source_agent', 'unknown')
            target_agent = intent_data.get('target_agent', 'unknown')
            intent_type = intent_data.get('intent_type', 'unknown')
            
            import time
            start_time = time.time()
            
            try:
                # Call original method
                if original_deliver_intent:
                    result = original_deliver_intent(intent_data, target_url)
                else:
                    # Fallback if method doesn't exist
                    import requests
                    response = requests.post(target_url, json=intent_data, timeout=30)
                    result = {
                        'success': response.status_code == 200,
                        'status_code': response.status_code,
                        'response': response.json() if response.status_code == 200 else None
                    }
                
                # Calculate response time
                end_time = time.time()
                response_time_ms = int((end_time - start_time) * 1000)
                
                # Trace successful delivery
                trace_intent_delivery(
                    intent_id=intent_id,
                    source_agent=source_agent,
                    target_agent=target_agent,
                    intent_type=intent_type,
                    success=result.get('success', False),
                    error_message=None
                )
                
                return result
                
            except Exception as e:
                # Calculate response time for error
                end_time = time.time()
                response_time_ms = int((end_time - start_time) * 1000)
                
                # Trace failed delivery
                trace_intent_delivery(
                    intent_id=intent_id,
                    source_agent=source_agent,
                    target_agent=target_agent,
                    intent_type=intent_type,
                    success=False,
                    error_message=str(e)
                )
                
                raise
        
        # Patch handle_intent method
        def patched_handle_intent(intent_data):
            """Patched version of handle_intent with Agent Lightning tracing"""
            
            # Extract intent information
            intent_id = intent_data.get('intent_id', 'unknown')
            source_agent = intent_data.get('source_agent', 'unknown')
            intent_type = intent_data.get('intent_type', 'unknown')
            
            import time
            start_time = time.time()
            
            try:
                # Call original method
                if original_handle_intent:
                    result = original_handle_intent(intent_data)
                else:
                    # Fallback
                    result = {'success': False, 'error': 'Original method not found'}
                
                # Calculate processing time
                end_time = time.time()
                processing_time_ms = int((end_time - start_time) * 1000)
                
                # Trace intent handling
                from simp.integrations.agent_lightning import LLMCallTrace
                trace = LLMCallTrace(
                    trace_id=intent_id,
                    agent_id='simp_broker',
                    intent_type=intent_type,
                    model='simp_broker',
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    response_time_ms=processing_time_ms,
                    success=result.get('success', False),
                    error_message=result.get('error'),
                    metadata={
                        'source_agent': source_agent,
                        'intent_type': intent_type,
                        'processing_stage': 'broker_handling'
                    }
                )
                
                # Send trace
                agent_lightning_manager.trace_llm_call(trace)
                
                return result
                
            except Exception as e:
                # Trace error
                from simp.integrations.agent_lightning import LLMCallTrace
                trace = LLMCallTrace(
                    trace_id=intent_id,
                    agent_id='simp_broker',
                    intent_type=intent_type,
                    model='simp_broker',
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    response_time_ms=int((time.time() - start_time) * 1000),
                    success=False,
                    error_message=str(e),
                    metadata={
                        'source_agent': source_agent,
                        'intent_type': intent_type,
                        'error_type': type(e).__name__
                    }
                )
                
                # Send trace
                agent_lightning_manager.trace_llm_call(trace)
                
                raise
        
        # Apply patches
        broker._deliver_intent = patched_deliver_intent
        broker.handle_intent = patched_handle_intent
        
        # Add Agent Lightning endpoints to broker
        integrate_with_broker(broker)
        
        logger.info("✅ SIMP broker patched for Agent Lightning integration")
        
        return broker
        
    except ImportError as e:
        logger.warning(f"Agent Lightning integration not available: {e}")
        return broker
    except Exception as e:
        logger.error(f"Failed to patch broker for Agent Lightning: {e}")
        return broker


def patch_agent_client_for_lightning(agent_client):
    """Patch agent client to use Agent Lightning proxy"""
    
    try:
        from simp.integrations.agent_lightning import agent_lightning_manager
        
        if not agent_lightning_manager.config.enabled:
            return agent_client
        
        logger.info("Patching agent client for Agent Lightning proxy")
        
        # Check if this agent should use Agent Lightning
        agent_id = getattr(agent_client, 'agent_id', 'unknown')
        
        if agent_lightning_manager.is_enabled_for_agent(agent_id):
            # Configure agent client to use Agent Lightning proxy
            proxy_url = agent_lightning_manager.get_proxy_url()
            
            # Patch HTTP client to use proxy
            if hasattr(agent_client, 'base_url'):
                original_base_url = agent_client.base_url
                
                # Check if base_url needs to be redirected to proxy
                # This would depend on the agent's configuration
                # For now, just log the information
                logger.info(f"Agent {agent_id} would use Agent Lightning proxy: {proxy_url}")
                logger.info(f"Original base URL: {original_base_url}")
            
            # Add Agent Lightning middleware to agent client
            if hasattr(agent_client, 'middleware'):
                from simp.integrations.agent_lightning import AgentLightningMiddleware
                lightning_middleware = AgentLightningMiddleware(agent_id)
                
                # Wrap LLM methods
                if hasattr(agent_client, 'call_llm'):
                    original_call_llm = agent_client.call_llm
                    agent_client.call_llm = lightning_middleware.wrap_llm_call(original_call_llm)
                    logger.debug(f"Wrapped call_llm for agent {agent_id}")
                
                if hasattr(agent_client, 'generate_response'):
                    original_generate_response = agent_client.generate_response
                    agent_client.generate_response = lightning_middleware.wrap_llm_call(original_generate_response)
                    logger.debug(f"Wrapped generate_response for agent {agent_id}")
        
        return agent_client
        
    except Exception as e:
        logger.warning(f"Failed to patch agent client for Agent Lightning: {e}")
        return agent_client