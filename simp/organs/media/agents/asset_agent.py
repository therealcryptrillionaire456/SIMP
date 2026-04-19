"""
Asset Agent for KashClaw Media Grid.

Responsible for:
- Generating video/images/audio using AI tools (Higgsfield, Minimax, etc.)
- Handling async generation with webhook callbacks
- Managing generation costs and budgets
- Supporting multiple content formats (9:16, 1:1, 16:9)
"""
import asyncio
import json
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

from simp.organs.media.agents.base_media_agent import BaseMediaAgent
from simp.organs.media.models import (
    AssetJob, GeneratedAsset, ContentFormat, AssetType,
    GenerationTool, ScriptPackage
)


class AssetAgent(BaseMediaAgent):
    """Agent that generates media assets using AI tools."""
    
    def __init__(
        self,
        agent_id: str = "asset_agent",
        data_dir: Optional[str] = None,
        log_level: str = "INFO",
        default_tool: GenerationTool = GenerationTool.HIGGSFIELD,
        budget_per_job: float = 10.0  # USD
    ):
        """Initialize the Asset Agent."""
        super().__init__(
            agent_id=agent_id,
            agent_name="Asset Agent",
            data_dir=data_dir,
            log_level=log_level
        )
        
        self.default_tool = default_tool
        self.budget_per_job = budget_per_job
        self.pending_jobs = asyncio.Queue()
        self.active_jobs: Dict[str, AssetJob] = {}
        self.completed_assets: Dict[str, GeneratedAsset] = {}
        
        # Tool configurations
        self.tool_configs = self._load_tool_configurations()
        
        # Webhook server simulation
        self.webhook_port = 8888
        self.webhook_base_url = f"http://localhost:{self.webhook_port}"
        
        self.logger.info(f"Asset Agent initialized with {default_tool.value} as default tool")
    
    def _load_tool_configurations(self) -> Dict[str, Dict[str, Any]]:
        """Load configurations for different AI generation tools."""
        return {
            GenerationTool.HIGGSFIELD.value: {
                "name": "Higgsfield AI",
                "description": "Cinematic AI video generation",
                "cost_per_second": 0.15,  # USD per second of video
                "max_duration": 60,  # seconds
                "supported_formats": ["9:16", "16:9", "1:1"],
                "quality": "premium",
                "api_endpoint": "https://api.higgsfield.ai/v1/generate",
                "async_support": True,
                "webhook_support": True,
                "estimated_processing_time": 120  # seconds
            },
            GenerationTool.MINIMAX.value: {
                "name": "Minimax",
                "description": "AI video and image generation",
                "cost_per_second": 0.08,
                "max_duration": 30,
                "supported_formats": ["9:16", "1:1"],
                "quality": "good",
                "api_endpoint": "https://api.minimax.ai/v1/generate",
                "async_support": True,
                "webhook_support": True,
                "estimated_processing_time": 90
            },
            GenerationTool.KLING.value: {
                "name": "Kling AI",
                "description": "AI video generation",
                "cost_per_second": 0.10,
                "max_duration": 45,
                "supported_formats": ["9:16", "16:9"],
                "quality": "good",
                "api_endpoint": "https://api.kling.ai/v1/generate",
                "async_support": False,
                "webhook_support": False,
                "estimated_processing_time": 60
            },
            GenerationTool.ELEVENLABS.value: {
                "name": "ElevenLabs",
                "description": "AI voice generation",
                "cost_per_character": 0.0003,
                "max_characters": 5000,
                "supported_formats": ["mp3", "wav"],
                "quality": "premium",
                "api_endpoint": "https://api.elevenlabs.io/v1/text-to-speech",
                "async_support": False,
                "webhook_support": False,
                "estimated_processing_time": 10
            }
        }
    
    async def _process_loop(self):
        """Main processing loop for asset generation."""
        while self.is_running:
            try:
                # Check for pending jobs
                if not self.pending_jobs.empty():
                    job_data = await self.pending_jobs.get()
                    
                    self.logger.info(f"Processing asset job: {job_data.get('job_id', 'unknown')}")
                    
                    # Create and process asset job
                    asset_job = await self.create_asset_job(job_data)
                    
                    if asset_job:
                        # Start asset generation
                        generated_asset = await self.generate_asset(asset_job)
                        
                        if generated_asset:
                            # Save to ledger
                            self._save_generated_asset(generated_asset)
                            
                            # Send to Edit/Packaging Agent
                            await self._distribute_asset(generated_asset)
                    
                    self.pending_jobs.task_done()
                
                # Process active jobs (check status, handle callbacks)
                await self._process_active_jobs()
                
                # Wait before next check
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in asset generation loop: {e}")
                await asyncio.sleep(10)
    
    async def _process_active_jobs(self):
        """Process active jobs and handle callbacks."""
        jobs_to_remove = []
        
        for job_id, job in self.active_jobs.items():
            try:
                # Check if job is completed (simulated)
                if job.status == "processing":
                    # Simulate processing time
                    job_config = self.tool_configs.get(job.generation_tool.value, {})
                    processing_time = job_config.get("estimated_processing_time", 60)
                    
                    job_start = datetime.fromisoformat(job.created_at)
                    elapsed = (datetime.utcnow() - job_start).total_seconds()
                    
                    if elapsed > processing_time:
                        # Job should be completed by now
                        job.status = "completed"
                        job.updated_at = datetime.utcnow().isoformat()
                        
                        # Simulate webhook callback
                        await self._simulate_webhook_callback(job)
                        
                        jobs_to_remove.append(job_id)
                        
                        self.logger.info(f"Job {job_id} completed after {elapsed:.1f}s")
                
                elif job.status == "completed":
                    # Job already completed, remove from active
                    jobs_to_remove.append(job_id)
                
                elif job.status == "failed":
                    # Job failed, remove from active
                    jobs_to_remove.append(job_id)
                    self.logger.warning(f"Job {job_id} failed")
            
            except Exception as e:
                self.logger.error(f"Error processing job {job_id}: {e}")
                jobs_to_remove.append(job_id)
        
        # Remove processed jobs
        for job_id in jobs_to_remove:
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
    
    async def handle_intent(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming intent for asset generation.
        
        Args:
            intent_data: Intent payload with script information
            
        Returns:
            Response with asset generation status
        """
        operation_id = self._log_operation(
            operation="asset_generation_intent",
            status="pending",
            details={"script_id": intent_data.get("script_id", "unknown")}
        )
        
        try:
            # Add to processing queue
            await self.pending_jobs.put(intent_data)
            
            self._log_operation(
                operation="asset_generation_intent",
                status="success",
                details={
                    "script_id": intent_data.get("script_id", "unknown"),
                    "queue_position": self.pending_jobs.qsize()
                }
            )
            
            return {
                "status": "queued",
                "operation_id": operation_id,
                "queue_position": self.pending_jobs.qsize(),
                "estimated_wait": self.pending_jobs.qsize() * 60  # 60 seconds per job
            }
            
        except Exception as e:
            self._log_operation(
                operation="asset_generation_intent",
                status="failure",
                details={"error": str(e)}
            )
            
            return {
                "status": "error",
                "operation_id": operation_id,
                "error": str(e)
            }
    
    async def create_asset_job(self, script_data: Dict[str, Any]) -> Optional[AssetJob]:
        """
        Create an asset job from script data.
        
        Args:
            script_data: Script data from Script Agent
            
        Returns:
            AssetJob object or None if failed
        """
        operation_id = self._log_operation(
            operation="asset_job_creation",
            status="pending",
            details={"script_id": script_data.get("script_id", "unknown")}
        )
        
        start_time = time.time()
        
        try:
            # Extract script information
            script_id = script_data.get("script_id", "")
            brief_id = script_data.get("brief_id", "")
            title = script_data.get("title", "")
            scripts = script_data.get("scripts", [])
            target_platforms = script_data.get("target_platforms", [])
            brand_voice = script_data.get("brand_voice", "professional")
            
            if not scripts:
                self.logger.warning(f"No scripts provided for {script_id}")
                return None
            
            # Select the first script for asset generation
            primary_script = scripts[0] if scripts else {}
            
            # Determine asset type and tool
            asset_type = self._determine_asset_type(target_platforms, brand_voice)
            generation_tool = self._select_generation_tool(asset_type, target_platforms)
            
            # Determine target formats
            target_formats = self._determine_target_formats(target_platforms)
            
            # Create webhook URL for callback
            webhook_url = f"{self.webhook_base_url}/webhook/asset/{script_id}"
            
            # Calculate estimated cost
            estimated_cost = self._estimate_generation_cost(
                generation_tool=generation_tool,
                duration_seconds=primary_script.get("duration_estimate", 60),
                script_text=self._extract_script_text(primary_script)
            )
            
            # Create asset job
            asset_job = AssetJob(
                job_id=f"job_{script_id.replace('script_', '')}",
                script_id=script_id,
                asset_type=asset_type,
                generation_tool=generation_tool,
                script_text=self._extract_script_text(primary_script),
                style_reference=self._determine_style_reference(brand_voice),
                voice_preferences=self._determine_voice_preferences(brand_voice),
                visual_style=self._determine_visual_style(brand_voice, asset_type),
                target_formats=target_formats,
                duration_seconds=primary_script.get("duration_estimate", 60),
                resolution="1080p",
                estimated_cost=estimated_cost,
                budget_limit=self.budget_per_job,
                webhook_url=webhook_url,
                status="pending"
            )
            
            # Add to active jobs
            self.active_jobs[asset_job.job_id] = asset_job
            
            duration = time.time() - start_time
            
            self._log_operation(
                operation="asset_job_creation",
                status="success",
                details={
                    "script_id": script_id,
                    "job_id": asset_job.job_id,
                    "asset_type": asset_type.value,
                    "generation_tool": generation_tool.value,
                    "estimated_cost": estimated_cost,
                    "target_formats": [f.value for f in target_formats]
                },
                duration_seconds=duration
            )
            
            return asset_job
            
        except Exception as e:
            duration = time.time() - start_time
            self._log_operation(
                operation="asset_job_creation",
                status="failure",
                details={"error": str(e)},
                duration_seconds=duration
            )
            self.logger.error(f"Failed to create asset job: {e}")
            return None
    
    def _determine_asset_type(
        self,
        target_platforms: List[str],
        brand_voice: str
    ) -> AssetType:
        """Determine the appropriate asset type."""
        # For now, default to video for most content
        return AssetType.VIDEO
    
    def _select_generation_tool(
        self,
        asset_type: AssetType,
        target_platforms: List[str]
    ) -> GenerationTool:
        """Select the appropriate generation tool."""
        if asset_type == AssetType.VIDEO:
            # Choose based on platform requirements
            if "tiktok" in target_platforms or "instagram_reels" in target_platforms:
                # Short-form video platforms
                return random.choice([GenerationTool.HIGGSFIELD, GenerationTool.MINIMAX])
            else:
                # Other platforms
                return self.default_tool
        elif asset_type == AssetType.AUDIO:
            return GenerationTool.ELEVENLABS
        else:
            return self.default_tool
    
    def _determine_target_formats(self, target_platforms: List[str]) -> List[ContentFormat]:
        """Determine target formats based on platforms."""
        formats = set()
        
        format_mapping = {
            "tiktok": [ContentFormat.PORTRAIT_9_16],
            "youtube_shorts": [ContentFormat.PORTRAIT_9_16],
            "instagram_reels": [ContentFormat.PORTRAIT_9_16],
            "instagram_feed": [ContentFormat.SQUARE_1_1, ContentFormat.PORTRAIT_9_16],
            "x": [ContentFormat.LANDSCAPE_16_9, ContentFormat.SQUARE_1_1],
            "facebook": [ContentFormat.LANDSCAPE_16_9, ContentFormat.SQUARE_1_1],
            "linkedin": [ContentFormat.LANDSCAPE_16_9, ContentFormat.SQUARE_1_1]
        }
        
        for platform in target_platforms:
            if platform in format_mapping:
                formats.update(format_mapping[platform])
        
        # Default to 9:16 if no formats determined
        if not formats:
            formats.add(ContentFormat.PORTRAIT_9_16)
        
        return list(formats)
    
    def _estimate_generation_cost(
        self,
        generation_tool: GenerationTool,
        duration_seconds: int,
        script_text: str
    ) -> float:
        """Estimate generation cost."""
        tool_config = self.tool_configs.get(generation_tool.value, {})
        
        if generation_tool == GenerationTool.ELEVENLABS:
            # Cost per character for audio
            cost_per_char = tool_config.get("cost_per_character", 0.0003)
            char_count = len(script_text)
            return char_count * cost_per_char
        else:
            # Cost per second for video
            cost_per_second = tool_config.get("cost_per_second", 0.10)
            return duration_seconds * cost_per_second
    
    def _extract_script_text(self, script: Dict[str, Any]) -> str:
        """Extract text from script structure."""
        if "content" in script:
            # Join all section content
            sections = []
            for section in script["content"]:
                if isinstance(section, dict) and "content" in section:
                    sections.append(section["content"])
                elif isinstance(section, str):
                    sections.append(section)
            return " ".join(sections)
        return script.get("text", "")
    
    def _determine_style_reference(self, brand_voice: str) -> str:
        """Determine style reference based on brand voice."""
        style_mapping = {
            "professional": "clean, modern, corporate",
            "casual": "friendly, authentic, relatable",
            "enthusiastic": "energetic, dynamic, engaging",
            "educational": "clear, informative, structured"
        }
        return style_mapping.get(brand_voice, "clean, modern")
    
    def _determine_voice_preferences(self, brand_voice: str) -> Dict[str, Any]:
        """Determine voice preferences for audio generation."""
        voice_mapping = {
            "professional": {
                "gender": "female",
                "age": "adult",
                "accent": "american",
                "style": "conversational",
                "speed": 1.0
            },
            "casual": {
                "gender": "male",
                "age": "young_adult",
                "accent": "american",
                "style": "friendly",
                "speed": 1.1
            },
            "enthusiastic": {
                "gender": "female",
                "age": "young_adult",
                "accent": "american",
                "style": "excited",
                "speed": 1.2
            },
            "educational": {
                "gender": "male",
                "age": "adult",
                "accent": "british",
                "style": "narration",
                "speed": 0.9
            }
        }
        return voice_mapping.get(brand_voice, voice_mapping["professional"])
    
    def _determine_visual_style(self, brand_voice: str, asset_type: AssetType) -> str:
        """Determine visual style for asset generation."""
        if asset_type == AssetType.VIDEO:
            style_mapping = {
                "professional": "cinematic, clean, corporate",
                "casual": "authentic, vlog-style, natural",
                "enthusiastic": "dynamic, fast-paced, engaging",
                "educational": "clear, informative, tutorial-style"
            }
            return style_mapping.get(brand_voice, "cinematic")
        else:
            return "standard"
    
    async def generate_asset(self, asset_job: AssetJob) -> Optional[GeneratedAsset]:
        """
        Generate asset using the specified tool.
        
        Args:
            asset_job: Asset job specification
            
        Returns:
            GeneratedAsset object or None if failed
        """
        operation_id = self._log_operation(
            operation="asset_generation",
            status="pending",
            details={"job_id": asset_job.job_id}
        )
        
        start_time = time.time()
        
        try:
            # Update job status
            asset_job.status = "processing"
            asset_job.updated_at = datetime.utcnow().isoformat()
            
            # Get tool configuration
            tool_config = self.tool_configs.get(asset_job.generation_tool.value, {})
            
            # Simulate generation time
            processing_time = tool_config.get("estimated_processing_time", 60)
            
            self.logger.info(f"Starting {asset_job.generation_tool.value} generation for job {asset_job.job_id}")
            self.logger.info(f"Estimated processing time: {processing_time}s")
            
            # In real implementation, this would call the AI tool API
            # For now, simulate the generation
            
            # Calculate actual cost (simulated)
            actual_cost = asset_job.estimated_cost * random.uniform(0.8, 1.2)
            
            # Create generated asset
            generated_asset = GeneratedAsset(
                asset_id=f"asset_{asset_job.job_id.replace('job_', '')}",
                job_id=asset_job.job_id,
                asset_type=asset_job.asset_type,
                format=asset_job.target_formats[0] if asset_job.target_formats else ContentFormat.PORTRAIT_9_16,
                file_url=f"https://storage.kashclaw.com/assets/{asset_job.job_id}.mp4",
                thumbnail_url=f"https://storage.kashclaw.com/thumbnails/{asset_job.job_id}.jpg",
                subtitle_url=f"https://storage.kashclaw.com/subtitles/{asset_job.job_id}.srt",
                generation_tool=asset_job.generation_tool,
                generation_time_seconds=processing_time,
                generation_cost=actual_cost,
                duration_seconds=asset_job.duration_seconds,
                resolution=asset_job.resolution,
                file_size_bytes=random.randint(5000000, 20000000),  # 5-20 MB
                file_format="mp4"
            )
            
            # Update job status
            asset_job.status = "completed"
            asset_job.updated_at = datetime.utcnow().isoformat()
            
            # Store completed asset
            self.completed_assets[generated_asset.asset_id] = generated_asset
            
            duration = time.time() - start_time
            
            self._log_operation(
                operation="asset_generation",
                status="success",
                details={
                    "job_id": asset_job.job_id,
                    "asset_id": generated_asset.asset_id,
                    "generation_tool": asset_job.generation_tool.value,
                    "generation_cost": actual_cost,
                    "generation_time": processing_time
                },
                duration_seconds=duration
            )
            
            return generated_asset
            
        except Exception as e:
            duration = time.time() - start_time
            asset_job.status = "failed"
            asset_job.updated_at = datetime.utcnow().isoformat()
            
            self._log_operation(
                operation="asset_generation",
                status="failure",
                details={"error": str(e)},
                duration_seconds=duration
            )
            self.logger.error(f"Failed to generate asset for job {asset_job.job_id}: {e}")
            return None
    
    async def _simulate_webhook_callback(self, asset_job: AssetJob):
        """Simulate webhook callback for completed job."""
        try:
            # In real implementation, this would send a webhook to the callback URL
            # For now, just log it
            self.logger.info(f"Webhook callback simulated for job {asset_job.job_id}")
            
            # Update any waiting systems
            if asset_job.webhook_url:
                self.logger.info(f"Would send webhook to: {asset_job.webhook_url}")
                
        except Exception as e:
            self.logger.error(f"Error simulating webhook callback: {e}")
    
    def _save_generated_asset(self, asset: GeneratedAsset):
        """Save generated asset to ledger."""
        from dataclasses import asdict
        
        record = asdict(asset)
        
        # Convert enum values to strings
        record["asset_type"] = asset.asset_type.value
        record["format"] = asset.format.value
        record["generation_tool"] = asset.generation_tool.value
        
        self._append_to_ledger("generated_assets", record)
    
    async def _distribute_asset(self, asset: GeneratedAsset):
        """Distribute generated asset to Edit/Packaging Agent."""
        try:
            # Prepare intent data for Edit/Packaging Agent
            intent_data = {
                "asset_id": asset.asset_id,
                "job_id": asset.job_id,
                "file_url": asset.file_url,
                "thumbnail_url": asset.thumbnail_url,
                "subtitle_url": asset.subtitle_url,
                "asset_type": asset.asset_type.value,
                "format": asset.format.value,
                "duration_seconds": asset.duration_seconds,
                "resolution": asset.resolution
            }
            
            response = self._send_intent("media.content_packaging", intent_data)
            
            if response:
                self.logger.info(f"Distributed asset {asset.asset_id} to Edit/Packaging Agent")
            else:
                self.logger.warning(f"Failed to distribute asset {asset.asset_id}")
                
        except Exception as e:
            self.logger.error(f"Error distributing asset {asset.asset_id}: {e}")
    
    def get_active_jobs(self) -> List[Dict[str, Any]]:
        """Get list of active jobs."""
        jobs = []
        for job_id, job in self.active_jobs.items():
            job_dict = {
                "job_id": job_id,
                "script_id": job.script_id,
                "status": job.status,
                "generation_tool": job.generation_tool.value,
                "estimated_cost": job.estimated_cost,
                "created_at": job.created_at,
                "updated_at": job.updated_at
            }
            jobs.append(job_dict)
        return jobs
    
    def get_recent_assets(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent generated assets."""
        return self._read_ledger("generated_assets", limit=limit)
    
    def get_asset_statistics(self) -> Dict[str, Any]:
        """Get asset generation statistics."""
        assets = self._read_ledger("generated_assets", limit=100)
        operations = self._read_ledger("operations", limit=100)
        
        if not assets:
            return {"status": "no_data", "message": "No assets generated yet"}
        
        # Calculate statistics
        asset_operations = [op for op in operations if op.get("operation") == "asset_generation"]
        
        success_count = sum(1 for op in asset_operations if op.get("status") == "success")
        failure_count = sum(1 for op in asset_operations if op.get("status") == "failure")
        
        # Cost statistics
        total_cost = sum(asset.get("generation_cost", 0) for asset in assets)
        avg_cost = total_cost / len(assets) if assets else 0
        
        # Time statistics
        total_time = sum(asset.get("generation_time_seconds", 0) for asset in assets)
        avg_time = total_time / len(assets) if assets else 0
        
        # Tool usage
        tool_counts = {}
        for asset in assets:
            tool = asset.get("generation_tool", "unknown")
            tool_counts[tool] = tool_counts.get(tool, 0) + 1
        
        return {
            "status": "success",
            "statistics": {
                "total_assets": len(assets),
                "success_rate": f"{(success_count / len(asset_operations) * 100):.1f}%" if asset_operations else "0%",
                "total_generation_cost": f"${total_cost:.2f}",
                "average_asset_cost": f"${avg_cost:.2f}",
                "average_generation_time": f"{avg_time:.1f}s",
                "tool_usage": tool_counts,
                "active_jobs": len(self.active_jobs),
                "pending_queue": self.pending_jobs.qsize()
            },
            "recent_assets": assets[:5]
        }


# Factory function for creating the agent
def create_asset_agent(
    agent_id: str = "asset_agent",
    data_dir: Optional[str] = None,
    default_tool: GenerationTool = GenerationTool.HIGGSFIELD,
    budget_per_job: float = 10.0
) -> AssetAgent:
    """Create and return an Asset Agent instance."""
    return AssetAgent(
        agent_id=agent_id,
        data_dir=data_dir,
        default_tool=default_tool,
        budget_per_job=budget_per_job
    )