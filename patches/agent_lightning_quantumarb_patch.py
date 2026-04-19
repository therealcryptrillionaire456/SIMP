"""
Agent Lightning QuantumArb Patch

This patch integrates Agent Lightning with the QuantumArb agent,
adding LLM call tracing for arbitrage analysis and trade execution.
"""

import logging
from typing import Dict, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)

def patch_quantumarb_for_agent_lightning(quantumarb_agent):
    """Patch the QuantumArb agent to integrate Agent Lightning"""
    
    try:
        from simp.integrations.agent_lightning import (
            agent_lightning_manager,
            AgentLightningMiddleware
        )
        
        logger.info("Patching QuantumArb agent for Agent Lightning integration")
        
        if not agent_lightning_manager.config.enabled:
            logger.info("Agent Lightning integration disabled in configuration")
            return quantumarb_agent
        
        # Check if QuantumArb should use Agent Lightning
        agent_id = "quantumarb"
        if not agent_lightning_manager.is_enabled_for_agent(agent_id):
            logger.info(f"Agent Lightning not enabled for {agent_id}")
            return quantumarb_agent
        
        # Create Agent Lightning middleware
        middleware = AgentLightningMiddleware(agent_id)
        
        # Patch key LLM methods in QuantumArb
        
        # 1. Patch analyze_arbitrage_opportunities
        if hasattr(quantumarb_agent, 'analyze_arbitrage_opportunities'):
            original_analyze = quantumarb_agent.analyze_arbitrage_opportunities
            quantumarb_agent.analyze_arbitrage_opportunities = middleware.wrap_llm_call(original_analyze)
            logger.debug("Patched analyze_arbitrage_opportunities for Agent Lightning")
        
        # 2. Patch execute_trade
        if hasattr(quantumarb_agent, 'execute_trade'):
            original_execute = quantumarb_agent.execute_trade
            quantumarb_agent.execute_trade = middleware.wrap_llm_call(original_execute)
            logger.debug("Patched execute_trade for Agent Lightning")
        
        # 3. Patch calculate_risk
        if hasattr(quantumarb_agent, 'calculate_risk'):
            original_risk = quantumarb_agent.calculate_risk
            quantumarb_agent.calculate_risk = middleware.wrap_llm_call(original_risk)
            logger.debug("Patched calculate_risk for Agent Lightning")
        
        # 4. Patch generate_trading_signal
        if hasattr(quantumarb_agent, 'generate_trading_signal'):
            original_signal = quantumarb_agent.generate_trading_signal
            quantumarb_agent.generate_trading_signal = middleware.wrap_llm_call(original_signal)
            logger.debug("Patched generate_trading_signal for Agent Lightning")
        
        # 5. Patch monitor_markets
        if hasattr(quantumarb_agent, 'monitor_markets'):
            original_monitor = quantumarb_agent.monitor_markets
            quantumarb_agent.monitor_markets = middleware.wrap_llm_call(original_monitor)
            logger.debug("Patched monitor_markets for Agent Lightning")
        
        # Add Agent Lightning optimization to prompts
        if hasattr(quantumarb_agent, 'optimize_prompt'):
            original_optimize = quantumarb_agent.optimize_prompt
            
            def patched_optimize_prompt(prompt: str, context: Dict[str, Any] = None) -> str:
                # First use Agent Lightning APO
                optimized = middleware.optimize_prompt(prompt, context)
                # Then use QuantumArb's own optimization
                return original_optimize(optimized, context) if original_optimize else optimized
            
            quantumarb_agent.optimize_prompt = patched_optimize_prompt
            logger.debug("Enhanced optimize_prompt with Agent Lightning APO")
        
        # Add performance monitoring method
        def get_lightning_performance(hours: int = 24) -> Dict[str, Any]:
            """Get Agent Lightning performance metrics for QuantumArb"""
            return middleware.get_performance_metrics(hours)
        
        quantumarb_agent.get_lightning_performance = get_lightning_performance
        
        # Add trace logging for arbitrage decisions
        def log_arbitrage_decision(opportunity: Dict[str, Any], decision: str, 
                                  reason: str, profit_estimate: float):
            """Log arbitrage decision to Agent Lightning"""
            from simp.integrations.agent_lightning import LLMCallTrace
            import uuid
            
            trace = LLMCallTrace(
                trace_id=str(uuid.uuid4()),
                agent_id=agent_id,
                intent_type="arbitrage_decision",
                model="quantumarb_decision_engine",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                response_time_ms=0,
                success=True,
                metadata={
                    "asset": opportunity.get('asset', 'unknown'),
                    "exchange_from": opportunity.get('exchange_from', 'unknown'),
                    "exchange_to": opportunity.get('exchange_to', 'unknown'),
                    "spread_percent": opportunity.get('spread_percent', 0),
                    "decision": decision,
                    "reason": reason,
                    "profit_estimate": profit_estimate,
                    "timestamp": opportunity.get('timestamp', 'unknown')
                }
            )
            
            agent_lightning_manager.trace_llm_call(trace)
            logger.debug(f"Logged arbitrage decision: {decision} for {opportunity.get('asset')}")
        
        quantumarb_agent.log_arbitrage_decision = log_arbitrage_decision
        
        # Patch the main process_intent method
        if hasattr(quantumarb_agent, 'process_intent'):
            original_process_intent = quantumarb_agent.process_intent
            
            @wraps(original_process_intent)
            def patched_process_intent(intent_data: Dict[str, Any]) -> Dict[str, Any]:
                import time
                start_time = time.time()
                
                try:
                    # Process the intent
                    result = original_process_intent(intent_data)
                    
                    # Log to Agent Lightning
                    end_time = time.time()
                    response_time_ms = int((end_time - start_time) * 1000)
                    
                    from simp.integrations.agent_lightning import LLMCallTrace
                    trace = LLMCallTrace(
                        trace_id=intent_data.get('intent_id', str(uuid.uuid4())),
                        agent_id=agent_id,
                        intent_type=intent_data.get('intent_type', 'unknown'),
                        model="quantumarb_agent",
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        response_time_ms=response_time_ms,
                        success=result.get('success', False),
                        error_message=result.get('error'),
                        metadata={
                            "source_agent": intent_data.get('source_agent', 'unknown'),
                            "intent_type": intent_data.get('intent_type', 'unknown'),
                            "result_type": type(result).__name__
                        }
                    )
                    
                    agent_lightning_manager.trace_llm_call(trace)
                    
                    return result
                    
                except Exception as e:
                    # Log error to Agent Lightning
                    end_time = time.time()
                    response_time_ms = int((end_time - start_time) * 1000)
                    
                    from simp.integrations.agent_lightning import LLMCallTrace
                    trace = LLMCallTrace(
                        trace_id=intent_data.get('intent_id', str(uuid.uuid4())),
                        agent_id=agent_id,
                        intent_type=intent_data.get('intent_type', 'unknown'),
                        model="quantumarb_agent",
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        response_time_ms=response_time_ms,
                        success=False,
                        error_message=str(e),
                        metadata={
                            "source_agent": intent_data.get('source_agent', 'unknown'),
                            "intent_type": intent_data.get('intent_type', 'unknown'),
                            "error_type": type(e).__name__
                        }
                    )
                    
                    agent_lightning_manager.trace_llm_call(trace)
                    
                    raise
            
            quantumarb_agent.process_intent = patched_process_intent
            logger.debug("Patched process_intent for Agent Lightning tracing")
        
        logger.info("✅ QuantumArb agent patched for Agent Lightning integration")
        
        # Register QuantumArb with Agent Lightning
        from simp.integrations.agent_lightning import register_agent_with_lightning
        agent_info = {
            "name": "QuantumArb",
            "type": "arbitrage_trading",
            "capabilities": ["arbitrage_detection", "trade_execution", "risk_analysis"],
            "llm_model": "glm-4-plus",
            "version": getattr(quantumarb_agent, '__version__', '1.0.0')
        }
        register_agent_with_lightning(agent_id, agent_info)
        
        return quantumarb_agent
        
    except ImportError as e:
        logger.warning(f"Agent Lightning integration not available: {e}")
        return quantumarb_agent
    except Exception as e:
        logger.error(f"Failed to patch QuantumArb for Agent Lightning: {e}")
        return quantumarb_agent


def create_quantumarb_lightning_wrapper():
    """Create a wrapper class for QuantumArb with Agent Lightning integration"""
    
    wrapper_code = """
\"\"\"
QuantumArb Agent Lightning Wrapper

This wrapper adds Agent Lightning tracing and optimization to QuantumArb agent.
\"\"\"

import logging
from typing import Dict, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)

class QuantumArbLightningWrapper:
    \"\"\"Wrapper that adds Agent Lightning capabilities to QuantumArb\"\"\"
    
    def __init__(self, quantumarb_agent):
        self.agent = quantumarb_agent
        self.agent_id = "quantumarb"
        self.lightning_enabled = False
        
        # Try to import Agent Lightning
        try:
            from simp.integrations.agent_lightning import AgentLightningMiddleware
            self.middleware = AgentLightningMiddleware(self.agent_id)
            self.lightning_enabled = True
            logger.info(f"Agent Lightning enabled for QuantumArb")
        except ImportError as e:
            logger.warning(f"Agent Lightning not available: {e}")
            self.middleware = None
    
    def __getattr__(self, name):
        \"\"\"Delegate to wrapped agent\"\"\"
        return getattr(self.agent, name)
    
    def wrap_method(self, method_name: str):
        \"\"\"Wrap a method with Agent Lightning tracing\"\"\"
        if not self.lightning_enabled or not hasattr(self.agent, method_name):
            return
        
        original_method = getattr(self.agent, method_name)
        
        @wraps(original_method)
        def wrapped_method(*args, **kwargs):
            if self.middleware:
                return self.middleware.wrap_llm_call(original_method)(*args, **kwargs)
            else:
                return original_method(*args, **kwargs)
        
        setattr(self.agent, method_name, wrapped_method)
        logger.debug(f"Wrapped {method_name} for Agent Lightning tracing")
    
    def analyze_arbitrage_opportunities_with_lightning(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        \"\"\"Analyze arbitrage opportunities with Agent Lightning tracing\"\"\"
        if self.lightning_enabled:
            self.wrap_method('analyze_arbitrage_opportunities')
        
        return self.agent.analyze_arbitrage_opportunities(market_data)
    
    def execute_trade_with_lightning(self, trade_params: Dict[str, Any]) -> Dict[str, Any]:
        \"\"\"Execute trade with Agent Lightning tracing\"\"\"
        if self.lightning_enabled:
            self.wrap_method('execute_trade')
        
        return self.agent.execute_trade(trade_params)
    
    def get_performance_metrics(self, hours: int = 24) -> Dict[str, Any]:
        \"\"\"Get Agent Lightning performance metrics\"\"\"
        if self.lightning_enabled and self.middleware:
            return self.middleware.get_performance_metrics(hours)
        return {}
    
    def optimize_arbitrage_prompt(self, prompt: str, market_context: Dict[str, Any] = None) -> str:
        \"\"\"Optimize arbitrage analysis prompt using Agent Lightning APO\"\"\"
        if self.lightning_enabled and self.middleware:
            return self.middleware.optimize_prompt(prompt, market_context)
        return prompt


def wrap_quantumarb_agent(quantumarb_agent):
    \"\"\"Wrap a QuantumArb agent with Agent Lightning capabilities\"\"\"
    return QuantumArbLightningWrapper(quantumarb_agent)
"""
    
    return wrapper_code