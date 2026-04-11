#!/usr/bin/env python3
"""
Base module interface for BRP repository integration.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class BRPModule(ABC):
    """Base class for all BRP integration modules."""
    
    def __init__(self, name: str, repository: str, module_type: str):
        self.name = name
        self.repository = repository
        self.module_type = module_type  # defensive, offensive, intelligence
        self.initialized = False
        self.available = False
        self.capabilities = []
        
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the module."""
        pass
    
    @abstractmethod
    def check_availability(self) -> bool:
        """Check if the module is available (repository exists and is accessible)."""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[Dict[str, Any]]:
        """Get list of capabilities provided by this module."""
        pass
    
    @abstractmethod
    def execute(self, operation: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an operation using this module."""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get module status."""
        return {
            'name': self.name,
            'repository': self.repository,
            'type': self.module_type,
            'initialized': self.initialized,
            'available': self.available,
            'capabilities_count': len(self.capabilities),
            'capabilities': self.capabilities
        }

class DefensiveModule(BRPModule):
    """Base class for defensive modules."""
    
    def __init__(self, name: str, repository: str):
        super().__init__(name, repository, 'defensive')
    
    @abstractmethod
    def monitor(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Monitor data for threats."""
        pass
    
    @abstractmethod
    def analyze_threat(self, threat_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze threat data."""
        pass
    
    @abstractmethod
    def defend(self, threat: Dict[str, Any]) -> Dict[str, Any]:
        """Execute defensive action against threat."""
        pass

class OffensiveModule(BRPModule):
    """Base class for offensive modules."""
    
    def __init__(self, name: str, repository: str):
        super().__init__(name, repository, 'offensive')
    
    @abstractmethod
    def scan(self, target: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Scan target for vulnerabilities."""
        pass
    
    @abstractmethod
    def exploit(self, vulnerability: Dict[str, Any]) -> Dict[str, Any]:
        """Exploit a vulnerability."""
        pass
    
    @abstractmethod
    def execute_attack(self, attack_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute attack plan."""
        pass

class IntelligenceModule(BRPModule):
    """Base class for intelligence modules."""
    
    def __init__(self, name: str, repository: str):
        super().__init__(name, repository, 'intelligence')
    
    @abstractmethod
    def gather_intelligence(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Gather intelligence based on query."""
        pass
    
    @abstractmethod
    def analyze_patterns(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in data."""
        pass
    
    @abstractmethod
    def plan_response(self, threat: Dict[str, Any]) -> Dict[str, Any]:
        """Plan response to threat."""
        pass

class HybridModule(BRPModule):
    """Base class for hybrid modules with multiple capabilities."""
    
    def __init__(self, name: str, repository: str, module_types: List[str]):
        super().__init__(name, repository, 'hybrid')
        self.module_types = module_types  # List of types: ['defensive', 'offensive', 'intelligence']
    
    # Hybrid modules can implement methods from any base class
    # They should override the methods they support

class ModuleManager:
    """Manager for all BRP modules."""
    
    def __init__(self):
        self.modules = {}
        self.defensive_modules = {}
        self.offensive_modules = {}
        self.intelligence_modules = {}
        
    def register_module(self, module: BRPModule):
        """Register a module."""
        self.modules[module.name] = module
        
        if isinstance(module, DefensiveModule):
            self.defensive_modules[module.name] = module
        elif isinstance(module, OffensiveModule):
            self.offensive_modules[module.name] = module
        elif isinstance(module, IntelligenceModule):
            self.intelligence_modules[module.name] = module
        
        logger.info(f"Registered module: {module.name} ({module.module_type})")
    
    def initialize_all(self) -> Dict[str, Any]:
        """Initialize all modules."""
        results = {
            'successful': [],
            'failed': [],
            'details': {}
        }
        
        for name, module in self.modules.items():
            try:
                if module.initialize():
                    results['successful'].append(name)
                    results['details'][name] = 'Initialized successfully'
                else:
                    results['failed'].append(name)
                    results['details'][name] = 'Initialization failed'
            except Exception as e:
                results['failed'].append(name)
                results['details'][name] = f'Error: {str(e)}'
                logger.error(f"Failed to initialize module {name}: {e}")
        
        return results
    
    def get_module(self, name: str) -> Optional[BRPModule]:
        """Get module by name."""
        return self.modules.get(name)
    
    def get_modules_by_type(self, module_type: str) -> Dict[str, BRPModule]:
        """Get modules by type."""
        if module_type == 'defensive':
            return self.defensive_modules
        elif module_type == 'offensive':
            return self.offensive_modules
        elif module_type == 'intelligence':
            return self.intelligence_modules
        else:
            return {}
    
    def execute_operation(self, module_name: str, operation: str, 
                         parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute operation on module."""
        module = self.get_module(module_name)
        if not module:
            return {'error': f'Module {module_name} not found'}
        
        if not module.initialized:
            return {'error': f'Module {module_name} not initialized'}
        
        try:
            return module.execute(operation, parameters)
        except Exception as e:
            logger.error(f"Error executing operation {operation} on module {module_name}: {e}")
            return {'error': str(e)}
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status."""
        status = {
            'total_modules': len(self.modules),
            'defensive_modules': len(self.defensive_modules),
            'offensive_modules': len(self.offensive_modules),
            'intelligence_modules': len(self.intelligence_modules),
            'modules': {},
            'capabilities_by_type': {
                'defensive': [],
                'offensive': [],
                'intelligence': []
            }
        }
        
        for name, module in self.modules.items():
            module_status = module.get_status()
            status['modules'][name] = module_status
            
            # Add capabilities to type-specific lists
            for capability in module.capabilities:
                status['capabilities_by_type'][module.module_type].append({
                    'module': name,
                    'capability': capability.get('name', 'unknown'),
                    'description': capability.get('description', '')
                })
        
        return status