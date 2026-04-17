#!/usr/bin/env python3
"""
Resource Monitor for Sovereign Self Compiler v2.

Monitors system resources (CPU, memory, disk, network) during compilation
and provides adaptive throttling recommendations.
"""

import json
import logging
import time
import psutil
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from threading import Thread, Event
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class ResourceLevel(Enum):
    """Resource utilization levels."""
    LOW = "low"          # < 50% utilization
    MODERATE = "moderate"  # 50-75% utilization
    HIGH = "high"        # 75-90% utilization
    CRITICAL = "critical"  # > 90% utilization


@dataclass
class ResourceMetrics:
    """System resource metrics."""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    network_sent_mb: float
    network_recv_mb: float
    process_count: int
    load_average_1m: float
    load_average_5m: float
    load_average_15m: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ResourceAlert:
    """Resource utilization alert."""
    timestamp: str
    level: ResourceLevel
    resource_type: str
    current_value: float
    threshold: float
    message: str
    recommendation: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ThrottlingRecommendation:
    """Throttling recommendation based on resource usage."""
    timestamp: str
    current_level: ResourceLevel
    recommended_action: str
    pause_duration_seconds: int
    reduce_concurrency_by: int  # Percentage to reduce concurrency
    message: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ResourceMonitor:
    """Monitors system resources and provides throttling recommendations."""
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        alert_callback: Optional[Callable[[ResourceAlert], None]] = None
    ):
        """
        Initialize resource monitor.
        
        Args:
            config: Configuration dictionary
            alert_callback: Callback function for alerts
        """
        self.config = config or self._default_config()
        self.alert_callback = alert_callback
        
        # Resource thresholds
        self.thresholds = self.config.get("thresholds", {
            "cpu_critical": 90.0,
            "cpu_high": 75.0,
            "cpu_moderate": 50.0,
            "memory_critical": 90.0,
            "memory_high": 75.0,
            "memory_moderate": 50.0,
            "disk_critical": 90.0,
            "disk_high": 75.0,
            "disk_moderate": 50.0,
            "load_critical": 4.0,  # Load average per CPU core
            "load_high": 2.0,
            "load_moderate": 1.0
        })
        
        # Monitoring state
        self.metrics_history: List[ResourceMetrics] = []
        self.alerts: List[ResourceAlert] = []
        self.recommendations: List[ThrottlingRecommendation] = []
        self.max_history_size = self.config.get("max_history_size", 1000)
        
        # Network baseline
        self.network_baseline_sent = 0
        self.network_baseline_recv = 0
        self._init_network_baseline()
        
        logger.info("Resource monitor initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "monitoring_interval": 5.0,  # Seconds between measurements
            "alert_cooldown": 60.0,  # Seconds between same-type alerts
            "max_history_size": 1000,
            "thresholds": {
                "cpu_critical": 90.0,
                "cpu_high": 75.0,
                "cpu_moderate": 50.0,
                "memory_critical": 90.0,
                "memory_high": 75.0,
                "memory_moderate": 50.0,
                "disk_critical": 90.0,
                "disk_high": 75.0,
                "disk_moderate": 50.0,
                "load_critical": 4.0,
                "load_high": 2.0,
                "load_moderate": 1.0
            }
        }
    
    def _init_network_baseline(self) -> None:
        """Initialize network baseline."""
        net_io = psutil.net_io_counters()
        self.network_baseline_sent = net_io.bytes_sent
        self.network_baseline_recv = net_io.bytes_recv
    
    def collect_metrics(self) -> ResourceMetrics:
        """
        Collect current system resource metrics.
        
        Returns:
            ResourceMetrics object
        """
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Memory
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_gb = memory.used / (1024 ** 3)
        memory_total_gb = memory.total / (1024 ** 3)
        
        # Disk (monitor root filesystem)
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_used_gb = disk.used / (1024 ** 3)
        disk_total_gb = disk.total / (1024 ** 3)
        
        # Network
        net_io = psutil.net_io_counters()
        network_sent_mb = (net_io.bytes_sent - self.network_baseline_sent) / (1024 ** 2)
        network_recv_mb = (net_io.bytes_recv - self.network_baseline_recv) / (1024 ** 2)
        
        # Process count
        process_count = len(psutil.pids())
        
        # Load average
        load_avg = psutil.getloadavg()
        
        metrics = ResourceMetrics(
            timestamp=datetime.utcnow().isoformat() + "Z",
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_gb=memory_used_gb,
            memory_total_gb=memory_total_gb,
            disk_percent=disk_percent,
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb,
            network_sent_mb=network_sent_mb,
            network_recv_mb=network_recv_mb,
            process_count=process_count,
            load_average_1m=load_avg[0],
            load_average_5m=load_avg[1],
            load_average_15m=load_avg[2]
        )
        
        # Store in history
        self.metrics_history.append(metrics)
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history.pop(0)
        
        return metrics
    
    def _get_resource_level(self, resource_type: str, value: float) -> ResourceLevel:
        """
        Get resource utilization level.
        
        Args:
            resource_type: Type of resource (cpu, memory, disk, load)
            value: Current value
            
        Returns:
            ResourceLevel
        """
        if resource_type == "load":
            # Load average is per core, so we need to adjust
            cpu_count = psutil.cpu_count()
            normalized_value = value / cpu_count if cpu_count > 0 else value
            
            if normalized_value >= self.thresholds["load_critical"]:
                return ResourceLevel.CRITICAL
            elif normalized_value >= self.thresholds["load_high"]:
                return ResourceLevel.HIGH
            elif normalized_value >= self.thresholds["load_moderate"]:
                return ResourceLevel.MODERATE
            else:
                return ResourceLevel.LOW
        else:
            # For percentage-based resources
            threshold_critical = self.thresholds[f"{resource_type}_critical"]
            threshold_high = self.thresholds[f"{resource_type}_high"]
            threshold_moderate = self.thresholds[f"{resource_type}_moderate"]
            
            if value >= threshold_critical:
                return ResourceLevel.CRITICAL
            elif value >= threshold_high:
                return ResourceLevel.HIGH
            elif value >= threshold_moderate:
                return ResourceLevel.MODERATE
            else:
                return ResourceLevel.LOW
    
    def check_alerts(self, metrics: ResourceMetrics) -> List[ResourceAlert]:
        """
        Check for resource alerts based on metrics.
        
        Args:
            metrics: Current resource metrics
            
        Returns:
            List of ResourceAlert objects
        """
        alerts = []
        
        # Check CPU
        cpu_level = self._get_resource_level("cpu", metrics.cpu_percent)
        if cpu_level in [ResourceLevel.HIGH, ResourceLevel.CRITICAL]:
            alert = ResourceAlert(
                timestamp=metrics.timestamp,
                level=cpu_level,
                resource_type="cpu",
                current_value=metrics.cpu_percent,
                threshold=self.thresholds["cpu_high" if cpu_level == ResourceLevel.HIGH else "cpu_critical"],
                message=f"CPU utilization is {cpu_level.value} ({metrics.cpu_percent:.1f}%)",
                recommendation="Consider pausing compilation or reducing concurrency"
            )
            alerts.append(alert)
        
        # Check memory
        memory_level = self._get_resource_level("memory", metrics.memory_percent)
        if memory_level in [ResourceLevel.HIGH, ResourceLevel.CRITICAL]:
            alert = ResourceAlert(
                timestamp=metrics.timestamp,
                level=memory_level,
                resource_type="memory",
                current_value=metrics.memory_percent,
                threshold=self.thresholds["memory_high" if memory_level == ResourceLevel.HIGH else "memory_critical"],
                message=f"Memory utilization is {memory_level.value} ({metrics.memory_percent:.1f}%)",
                recommendation="Consider reducing memory usage or increasing swap"
            )
            alerts.append(alert)
        
        # Check disk
        disk_level = self._get_resource_level("disk", metrics.disk_percent)
        if disk_level in [ResourceLevel.HIGH, ResourceLevel.CRITICAL]:
            alert = ResourceAlert(
                timestamp=metrics.timestamp,
                level=disk_level,
                resource_type="disk",
                current_value=metrics.disk_percent,
                threshold=self.thresholds["disk_high" if disk_level == ResourceLevel.HIGH else "disk_critical"],
                message=f"Disk utilization is {disk_level.value} ({metrics.disk_percent:.1f}%)",
                recommendation="Consider cleaning up temporary files or expanding storage"
            )
            alerts.append(alert)
        
        # Check load average
        load_level = self._get_resource_level("load", metrics.load_average_1m)
        if load_level in [ResourceLevel.HIGH, ResourceLevel.CRITICAL]:
            alert = ResourceAlert(
                timestamp=metrics.timestamp,
                level=load_level,
                resource_type="load",
                current_value=metrics.load_average_1m,
                threshold=self.thresholds["load_high" if load_level == ResourceLevel.HIGH else "load_critical"],
                message=f"System load is {load_level.value} ({metrics.load_average_1m:.2f})",
                recommendation="Consider reducing concurrent tasks or adding more CPU cores"
            )
            alerts.append(alert)
        
        # Store alerts and trigger callbacks
        for alert in alerts:
            self.alerts.append(alert)
            if self.alert_callback:
                try:
                    self.alert_callback(alert)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")
        
        return alerts
    
    def get_throttling_recommendation(self, metrics: ResourceMetrics) -> ThrottlingRecommendation:
        """
        Get throttling recommendation based on resource usage.
        
        Args:
            metrics: Current resource metrics
            
        Returns:
            ThrottlingRecommendation object
        """
        # Get worst resource level
        cpu_level = self._get_resource_level("cpu", metrics.cpu_percent)
        memory_level = self._get_resource_level("memory", metrics.memory_percent)
        disk_level = self._get_resource_level("disk", metrics.disk_percent)
        load_level = self._get_resource_level("load", metrics.load_average_1m)
        
        # Determine overall level (take the worst)
        levels = [cpu_level, memory_level, disk_level, load_level]
        level_priority = {
            ResourceLevel.CRITICAL: 4,
            ResourceLevel.HIGH: 3,
            ResourceLevel.MODERATE: 2,
            ResourceLevel.LOW: 1
        }
        
        current_level = max(levels, key=lambda l: level_priority[l])
        
        # Generate recommendation based on level
        if current_level == ResourceLevel.CRITICAL:
            action = "PAUSE_COMPILATION"
            pause_duration = 300  # 5 minutes
            reduce_concurrency = 75  # Reduce by 75%
            message = "Critical resource levels detected. Pausing compilation."
        elif current_level == ResourceLevel.HIGH:
            action = "REDUCE_CONCURRENCY"
            pause_duration = 120  # 2 minutes
            reduce_concurrency = 50  # Reduce by 50%
            message = "High resource levels detected. Reducing concurrency."
        elif current_level == ResourceLevel.MODERATE:
            action = "SLIGHT_THROTTLE"
            pause_duration = 30  # 30 seconds
            reduce_concurrency = 25  # Reduce by 25%
            message = "Moderate resource levels detected. Slight throttling."
        else:
            action = "NO_ACTION"
            pause_duration = 0
            reduce_concurrency = 0
            message = "Resource levels are normal."
        
        recommendation = ThrottlingRecommendation(
            timestamp=metrics.timestamp,
            current_level=current_level,
            recommended_action=action,
            pause_duration_seconds=pause_duration,
            reduce_concurrency_by=reduce_concurrency,
            message=message
        )
        
        self.recommendations.append(recommendation)
        return recommendation
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get monitoring summary.
        
        Returns:
            Summary dictionary
        """
        if not self.metrics_history:
            return {"status": "no_metrics"}
        
        latest = self.metrics_history[-1]
        
        # Calculate averages
        if len(self.metrics_history) > 1:
            avg_cpu = sum(m.cpu_percent for m in self.metrics_history) / len(self.metrics_history)
            avg_memory = sum(m.memory_percent for m in self.metrics_history) / len(self.metrics_history)
            avg_disk = sum(m.disk_percent for m in self.metrics_history) / len(self.metrics_history)
        else:
            avg_cpu = latest.cpu_percent
            avg_memory = latest.memory_percent
            avg_disk = latest.disk_percent
        
        return {
            "timestamp": latest.timestamp,
            "current": {
                "cpu_percent": latest.cpu_percent,
                "memory_percent": latest.memory_percent,
                "disk_percent": latest.disk_percent,
                "load_average_1m": latest.load_average_1m
            },
            "averages": {
                "cpu_percent": avg_cpu,
                "memory_percent": avg_memory,
                "disk_percent": avg_disk
            },
            "alerts": {
                "total": len(self.alerts),
                "critical": len([a for a in self.alerts if a.level == ResourceLevel.CRITICAL]),
                "high": len([a for a in self.alerts if a.level == ResourceLevel.HIGH])
            },
            "recommendations": len(self.recommendations)
        }
    
    def save_metrics(self, filepath: Path) -> None:
        """
        Save metrics history to file.
        
        Args:
            filepath: Path to save file
        """
        data = {
            "config": self.config,
            "thresholds": self.thresholds,
            "metrics": [m.to_dict() for m in self.metrics_history],
            "alerts": [a.to_dict() for a in self.alerts],
            "recommendations": [r.to_dict() for r in self.recommendations]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Resource metrics saved to {filepath}")
    
    def load_metrics(self, filepath: Path) -> None:
        """
        Load metrics history from file.
        
        Args:
            filepath: Path to load file
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Reconstruct metrics
        self.metrics_history = []
        for m_dict in data.get("metrics", []):
            metrics = ResourceMetrics(**m_dict)
            self.metrics_history.append(metrics)
        
        # Reconstruct alerts
        self.alerts = []
        for a_dict in data.get("alerts", []):
            alert = ResourceAlert(**a_dict)
            self.alerts.append(alert)
        
        # Reconstruct recommendations
        self.recommendations = []
        for r_dict in data.get("recommendations", []):
            rec = ThrottlingRecommendation(**r_dict)
            self.recommendations.append(rec)
        
        logger.info(f"Resource metrics loaded from {filepath}")


class MonitoringThread(Thread):
    """Thread for continuous resource monitoring."""
    
    def __init__(
        self,
        monitor: ResourceMonitor,
        interval: float = 5.0,
        stop_event: Optional[Event] = None
    ):
        """
        Initialize monitoring thread.
        
        Args:
            monitor: ResourceMonitor instance
            interval: Monitoring interval in seconds
            stop_event: Event to signal thread stop
        """
        super().__init__(daemon=True)
        self.monitor = monitor
        self.interval = interval
        self.stop_event = stop_event or Event()
        self.running = False
        
    def run(self) -> None:
        """Run monitoring thread."""
        self.running = True
        logger.info(f"Resource monitoring thread started (interval: {self.interval}s)")
        
        while not self.stop_event.is_set():
            try:
                # Collect metrics
                metrics = self.monitor.collect_metrics()
                
                # Check for alerts
                alerts = self.monitor.check_alerts(metrics)
                
                # Get throttling recommendation
                recommendation = self.monitor.get_throttling_recommendation(metrics)
                
                # Log if there are alerts
                if alerts:
                    for alert in alerts:
                        logger.warning(f"Resource alert: {alert.message}")
                
                # Log recommendation if action is needed
                if recommendation.recommended_action != "NO_ACTION":
                    logger.info(f"Throttling recommendation: {recommendation.message}")
                
            except Exception as e:
                logger.error(f"Error in monitoring thread: {e}")
            
            # Wait for next interval
            self.stop_event.wait(self.interval)
        
        self.running = False
        logger.info("Resource monitoring thread stopped")
    
    def stop(self) -> None:
        """Stop monitoring thread."""
        if self.stop_event:
            self.stop_event.set()


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create monitor
    monitor = ResourceMonitor()
    
    # Start monitoring thread
    stop_event = Event()
    monitoring_thread = MonitoringThread(monitor, interval=2.0, stop_event=stop_event)
    monitoring_thread.start()
    
    try:
        # Run for 30 seconds
        print("Monitoring system resources for 30 seconds...")
        print("Press Ctrl+C to stop early")
        time.sleep(30)
    except KeyboardInterrupt:
        print("\nStopping monitoring...")
    finally:
        # Stop monitoring
        stop_event.set()
        monitoring_thread.join(timeout=5.0)
        
        # Print summary
        summary = monitor.get_summary()
        print("\nResource Monitoring Summary:")
        print(f"  Metrics collected: {len(monitor.metrics_history)}")
        print(f"  Alerts generated: {summary['alerts']['total']}")
        print(f"  Critical alerts: {summary['alerts']['critical']}")
        print(f"  High alerts: {summary['alerts']['high']}")
        print(f"  Recommendations: {summary['recommendations']}")
        
        # Save metrics
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = Path(f"resource_metrics_{timestamp}.json")
        monitor.save_metrics(output_file)
        print(f"\nMetrics saved to: {output_file}")