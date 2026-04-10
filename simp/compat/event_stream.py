"""
Event Streaming for A2A Compatibility.

This module provides Server-Sent Events (SSE) for A2A event streaming,
enabling real-time communication between SIMP agents and external
A2A-compliant systems.

Key features:
- Server-Sent Events (SSE) implementation
- Event buffering and history
- Subscription management
- Event filtering and routing
- Heartbeat and keep-alive
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set, AsyncGenerator
from enum import Enum
from datetime import datetime
import logging
from collections import deque

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """A2A event types."""
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    AGENT_REGISTERED = "agent_registered"
    AGENT_HEARTBEAT = "agent_heartbeat"
    AGENT_OFFLINE = "agent_offline"
    SYSTEM_ALERT = "system_alert"
    HEALTH_CHECK = "health_check"
    SECURITY_EVENT = "security_event"
    CUSTOM = "custom"


class EventSeverity(str, Enum):
    """Event severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class A2AEvent:
    """A2A-compliant event."""
    event_id: str  # Unique event identifier
    type: EventType  # Event type
    data: Dict[str, Any]  # Event data
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = "simp_broker"  # Event source
    severity: EventSeverity = EventSeverity.INFO  # Event severity
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata
    
    def __post_init__(self):
        """Validate event after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate event fields."""
        # Event ID validation
        if not self.event_id or not isinstance(self.event_id, str):
            raise ValueError("event_id must be a non-empty string")
        
        # Event type validation
        if not isinstance(self.type, EventType):
            try:
                self.type = EventType(self.type)
            except ValueError:
                raise ValueError(f"type must be one of {[t.value for t in EventType]}")
        
        # Data validation
        if not isinstance(self.data, dict):
            raise ValueError("data must be a dictionary")
        
        # Timestamp validation
        try:
            datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError(f"Invalid timestamp format: {self.timestamp}")
        
        # Source validation
        if not isinstance(self.source, str):
            raise ValueError("source must be a string")
        
        # Severity validation
        if not isinstance(self.severity, EventSeverity):
            try:
                self.severity = EventSeverity(self.severity)
            except ValueError:
                raise ValueError(f"severity must be one of {[s.value for s in EventSeverity]}")
        
        # Metadata validation
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)
    
    def to_sse_format(self) -> str:
        """Convert to Server-Sent Events format."""
        event_dict = self.to_dict()
        
        # Format as SSE
        lines = []
        lines.append(f"event: {self.type.value}")
        lines.append(f"data: {json.dumps(event_dict)}")
        lines.append(f"id: {self.event_id}")
        lines.append(f"retry: 3000")  # 3 second retry
        lines.append("")  # Empty line to end event
        
        return "\n".join(lines)
    
    @classmethod
    def from_simp_intent(cls, simp_intent: Dict[str, Any]) -> "A2AEvent":
        """Create event from SIMP intent."""
        intent_type = simp_intent.get("intent_type", "custom")
        intent_id = simp_intent.get("intent_id", str(uuid.uuid4()))
        
        # Map intent type to event type
        event_type_map = {
            "trade_execution": EventType.TASK_CREATED,
            "market_analysis": EventType.TASK_CREATED,
            "research_request": EventType.TASK_CREATED,
            "health_check": EventType.HEALTH_CHECK,
            "security_audit": EventType.SECURITY_EVENT,
            "payment_request": EventType.TASK_CREATED,
            "ping": EventType.AGENT_HEARTBEAT,
        }
        
        event_type = event_type_map.get(intent_type, EventType.CUSTOM)
        
        return cls(
            event_id=f"event:{intent_id}",
            type=event_type,
            data={
                "intent": simp_intent,
                "action": "intent_received",
            },
            source=simp_intent.get("source_agent", "unknown"),
            severity=EventSeverity.INFO,
            metadata={
                "x-simp-intent-id": intent_id,
                "x-simp-intent-type": intent_type,
            },
        )


class EventStreamBuffer:
    """
    Buffer for A2A events with history and filtering.
    
    This class maintains a buffer of recent events and provides
    methods for subscribing to event streams.
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        retention_seconds: int = 3600
    ):
        """
        Initialize event stream buffer.
        
        Args:
            max_size: Maximum number of events to buffer
            retention_seconds: How long to keep events (seconds)
        """
        self.max_size = max_size
        self.retention_seconds = retention_seconds
        self.events: deque[A2AEvent] = deque(maxlen=max_size)
        self.subscriptions: Dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.info(f"Initialized event stream buffer (max_size={max_size}, retention={retention_seconds}s)")
    
    async def start(self) -> None:
        """Start the event stream buffer."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Event stream buffer started")
    
    async def stop(self) -> None:
        """Stop the event stream buffer."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Clear all subscriptions
        async with self._lock:
            for subscription_id, queue in self.subscriptions.items():
                await queue.put(None)  # Signal termination
            self.subscriptions.clear()
        
        logger.info("Event stream buffer stopped")
    
    async def publish(self, event: A2AEvent) -> None:
        """
        Publish an event to the stream.
        
        Args:
            event: Event to publish
        """
        async with self._lock:
            # Add to buffer
            self.events.append(event)
            
            # Send to all subscriptions
            for subscription_id, queue in self.subscriptions.items():
                try:
                    await queue.put(event)
                except asyncio.QueueFull:
                    logger.warning(f"Subscription queue full for {subscription_id}")
                except Exception as e:
                    logger.error(f"Error publishing to {subscription_id}: {e}")
        
        logger.debug(f"Published event: {event.type} from {event.source}")
    
    async def subscribe(
        self,
        subscription_id: Optional[str] = None,
        filter_types: Optional[List[EventType]] = None,
        filter_sources: Optional[List[str]] = None,
        filter_severity: Optional[EventSeverity] = None,
        buffer_size: int = 100
    ) -> AsyncGenerator[A2AEvent, None]:
        """
        Subscribe to event stream with optional filtering.
        
        Args:
            subscription_id: Optional subscription ID
            filter_types: Only receive events of these types
            filter_sources: Only receive events from these sources
            filter_severity: Only receive events of this severity or higher
            buffer_size: Subscription queue size
            
        Yields:
            A2AEvent objects matching the filter
        """
        if subscription_id is None:
            subscription_id = str(uuid.uuid4())
        
        # Create subscription queue
        queue = asyncio.Queue(maxsize=buffer_size)
        
        async with self._lock:
            self.subscriptions[subscription_id] = queue
        
        logger.info(f"New subscription: {subscription_id} (filters: types={filter_types}, sources={filter_sources})")
        
        try:
            while True:
                event = await queue.get()
                
                # None is termination signal
                if event is None:
                    break
                
                # Apply filters
                if filter_types and event.type not in filter_types:
                    continue
                
                if filter_sources and event.source not in filter_sources:
                    continue
                
                if filter_severity:
                    severity_order = list(EventSeverity)
                    event_severity_idx = severity_order.index(event.severity)
                    filter_severity_idx = severity_order.index(filter_severity)
                    if event_severity_idx < filter_severity_idx:
                        continue
                
                yield event
                
        except asyncio.CancelledError:
            logger.debug(f"Subscription cancelled: {subscription_id}")
        finally:
            async with self._lock:
                if subscription_id in self.subscriptions:
                    del self.subscriptions[subscription_id]
            logger.info(f"Subscription ended: {subscription_id}")
    
    async def get_recent_events(
        self,
        limit: int = 100,
        filter_types: Optional[List[EventType]] = None,
        filter_sources: Optional[List[str]] = None,
        since: Optional[str] = None
    ) -> List[A2AEvent]:
        """
        Get recent events from buffer.
        
        Args:
            limit: Maximum number of events to return
            filter_types: Filter by event types
            filter_sources: Filter by event sources
            since: Only return events after this timestamp (ISO 8601)
            
        Returns:
            List of recent events
        """
        async with self._lock:
            events = list(self.events)
        
        # Apply filters
        filtered = []
        
        for event in reversed(events):  # Most recent first
            if filter_types and event.type not in filter_types:
                continue
            
            if filter_sources and event.source not in filter_sources:
                continue
            
            if since:
                try:
                    since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                    event_dt = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
                    if event_dt <= since_dt:
                        continue
                except ValueError:
                    logger.warning(f"Invalid timestamp format: {since}")
            
            filtered.append(event)
            
            if len(filtered) >= limit:
                break
        
        return filtered
    
    def get_subscription_count(self) -> int:
        """Get number of active subscriptions."""
        return len(self.subscriptions)
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean up old events."""
        try:
            while True:
                await asyncio.sleep(60)  # Run every minute
                await self._cleanup_old_events()
        except asyncio.CancelledError:
            pass
    
    async def _cleanup_old_events(self) -> None:
        """Remove events older than retention period."""
        async with self._lock:
            now = time.time()
            cutoff = now - self.retention_seconds
            
            # Convert events to list for processing
            events_list = list(self.events)
            kept_events = []
            
            for event in events_list:
                try:
                    event_dt = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
                    event_time = event_dt.timestamp()
                    
                    if event_time > cutoff:
                        kept_events.append(event)
                except ValueError:
                    # Keep events with invalid timestamps
                    kept_events.append(event)
            
            # Update buffer
            self.events.clear()
            self.events.extend(kept_events)
            
            removed_count = len(events_list) - len(kept_events)
            if removed_count > 0:
                logger.debug(f"Cleaned up {removed_count} old events")


class EventStreamManager:
    """
    Manager for A2A event streaming.
    
    This class provides a high-level interface for event streaming
    with Server-Sent Events (SSE) support.
    """
    
    def __init__(self):
        """Initialize event stream manager."""
        self.buffer = EventStreamBuffer()
        self._is_running = False
    
    async def start(self) -> None:
        """Start the event stream manager."""
        await self.buffer.start()
        self._is_running = True
        logger.info("Event stream manager started")
    
    async def stop(self) -> None:
        """Stop the event stream manager."""
        await self.buffer.stop()
        self._is_running = False
        logger.info("Event stream manager stopped")
    
    async def publish_event(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        source: str = "simp_broker",
        severity: EventSeverity = EventSeverity.INFO,
        metadata: Optional[Dict[str, Any]] = None
    ) -> A2AEvent:
        """
        Publish a new event.
        
        Args:
            event_type: Type of event
            data: Event data
            source: Event source
            severity: Event severity
            metadata: Additional metadata
            
        Returns:
            Published event
        """
        event = A2AEvent(
            event_id=f"event:{uuid.uuid4()}",
            type=event_type,
            data=data,
            source=source,
            severity=severity,
            metadata=metadata or {},
        )
        
        await self.buffer.publish(event)
        return event
    
    async def generate_sse_stream(
        self,
        subscription_id: Optional[str] = None,
        filter_types: Optional[List[EventType]] = None,
        filter_sources: Optional[List[str]] = None,
        filter_severity: Optional[EventSeverity] = None,
        heartbeat_interval: int = 30
    ) -> AsyncGenerator[str, None]:
        """
        Generate Server-Sent Events stream.
        
        Args:
            subscription_id: Optional subscription ID
            filter_types: Filter by event types
            filter_sources: Filter by event sources
            filter_severity: Filter by severity
            heartbeat_interval: Heartbeat interval in seconds
            
        Yields:
            SSE-formatted strings
        """
        # Send initial comment
        yield ": A2A Event Stream\n\n"
        
        # Create heartbeat task
        heartbeat_task = asyncio.create_task(self._heartbeat_generator(heartbeat_interval))
        
        try:
            # Subscribe to events
            async for event in self.buffer.subscribe(
                subscription_id=subscription_id,
                filter_types=filter_types,
                filter_sources=filter_sources,
                filter_severity=filter_severity,
            ):
                yield event.to_sse_format()
                
        except asyncio.CancelledError:
            logger.debug(f"SSE stream cancelled: {subscription_id}")
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
    
    async def _heartbeat_generator(self, interval: int) -> None:
        """Generate heartbeat events."""
        try:
            while True:
                await asyncio.sleep(interval)
                
                # Create heartbeat event
                heartbeat = A2AEvent(
                    event_id=f"heartbeat:{uuid.uuid4()}",
                    type=EventType.AGENT_HEARTBEAT,
                    data={"message": "heartbeat", "timestamp": datetime.utcnow().isoformat()},
                    source="simp_broker",
                    severity=EventSeverity.DEBUG,
                    metadata={"heartbeat": True},
                )
                
                await self.buffer.publish(heartbeat)
                
        except asyncio.CancelledError:
            pass
    
    async def get_event_history(
        self,
        limit: int = 100,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Get event history.
        
        Args:
            limit: Maximum number of events
            **kwargs: Filter arguments for get_recent_events
            
        Returns:
            List of event dictionaries
        """
        events = await self.buffer.get_recent_events(limit=limit, **kwargs)
        return [event.to_dict() for event in events]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event stream statistics."""
        return {
            "buffer_size": len(self.buffer.events),
            "subscription_count": self.buffer.get_subscription_count(),
            "max_buffer_size": self.buffer.max_size,
            "retention_seconds": self.buffer.retention_seconds,
            "is_running": self._is_running,
        }


# Global event stream manager instance
_event_stream_manager: Optional[EventStreamManager] = None


async def get_event_stream_manager() -> EventStreamManager:
    """Get or create the global event stream manager."""
    global _event_stream_manager
    
    if _event_stream_manager is None:
        _event_stream_manager = EventStreamManager()
        await _event_stream_manager.start()
    
    return _event_stream_manager


async def publish_a2a_event(
    event_type: EventType,
    data: Dict[str, Any],
    **kwargs
) -> A2AEvent:
    """
    Publish an A2A event (convenience function).
    
    Args:
        event_type: Type of event
        data: Event data
        **kwargs: Additional arguments for publish_event
        
    Returns:
        Published event
    """
    manager = await get_event_stream_manager()
    return await manager.publish_event(event_type, data, **kwargs)


async def get_event_stream(**kwargs) -> AsyncGenerator[str, None]:
    """
    Get SSE event stream (convenience function).
    
    Args:
        **kwargs: Arguments for generate_sse_stream
        
    Yields:
        SSE-formatted strings
    """
    manager = await get_event_stream_manager()
    async for event_data in manager.generate_sse_stream(**kwargs):
        yield event_data


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def example():
        # Create event stream manager
        manager = EventStreamManager()
        await manager.start()
        
        try:
            # Publish some events
            await manager.publish_event(
                event_type=EventType.TASK_CREATED,
                data={"task_id": "task_001", "action": "trade_execution"},
                source="quantumarb",
                severity=EventSeverity.INFO,
            )
            
            await manager.publish_event(
                event_type=EventType.SYSTEM_ALERT,
                data={"message": "High CPU usage", "level": "warning"},
                source="system_monitor",
                severity=EventSeverity.WARNING,
            )
            
            # Get event history
            history = await manager.get_event_history(limit=10)
            print(f"Event history ({len(history)} events):")
            for event in history:
                print(f"  - {event['type']} from {event['source']}: {event['data']}")
            
            # Get statistics
            stats = manager.get_stats()
            print(f"\nEvent stream stats: {stats}")
            
        finally:
            await manager.stop()
    
    # Run example
    asyncio.run(example())