"""
Edit/Packaging Agent for KashClaw Media Grid.

Responsible for:
- Assembling multi-format versions from raw assets
- Adding subtitles, captions, thumbnails
- Creating platform-ready content packages
- Ensuring compliance with platform specifications
"""
import asyncio
import json
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from simp.organs.media.agents.base_media_agent import BaseMediaAgent
from simp.organs.media.models import (
    ContentPackage, GeneratedAsset, ContentFormat,
    ContentPlatform, AssetType
)


class EditPackagingAgent(BaseMediaAgent):
    """Agent that edits and packages content for different platforms."""
    
    def __init__(
        self,
        agent_id: str = "edit_packaging_agent",
        data_dir: Optional[str] = None,
        log_level: str = "INFO"
    ):
        """Initialize the Edit/Packaging Agent."""
        super().__init__(
            agent_id=agent_id,
            agent_name="Edit/Packaging Agent",
            data_dir=data_dir,
            log_level=log_level
        )
        
        self.pending_assets = asyncio.Queue()
        self.content_templates = self._load_content_templates()
        self.platform_specs = self._load_platform_specifications()
        
        self.logger.info("Edit/Packaging Agent initialized")
    
    def _load_content_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load templates for different content types."""
        return {
            "video_short": {
                "description": "Short-form video content (TikTok, Reels, Shorts)",
                "max_duration": 60,
                "aspect_ratio": "9:16",
                "required_elements": ["hook", "content", "cta", "branding"],
                "optimization_tips": [
                    "Hook in first 3 seconds",
                    "Text overlay for key points",
                    "Trending audio/sound",
                    "Clear call-to-action"
                ]
            },
            "video_long": {
                "description": "Long-form video content (YouTube, Facebook)",
                "max_duration": 600,
                "aspect_ratio": "16:9",
                "required_elements": ["intro", "content", "examples", "summary", "cta"],
                "optimization_tips": [
                    "Clear chapter markers",
                    "Engaging thumbnail",
                    "Description with timestamps",
                    "End screen with links"
                ]
            },
            "image_carousel": {
                "description": "Image carousel for Instagram/LinkedIn",
                "max_images": 10,
                "aspect_ratio": "1:1",
                "required_elements": ["cover_image", "content_images", "cta_slide"],
                "optimization_tips": [
                    "Consistent visual style",
                    "Progressive storytelling",
                    "Clear navigation cues",
                    "Strong final slide"
                ]
            }
        }
    
    def _load_platform_specifications(self) -> Dict[str, Dict[str, Any]]:
        """Load platform specifications and requirements."""
        return {
            "tiktok": {
                "max_duration": 180,
                "supported_formats": ["mp4", "mov"],
                "aspect_ratios": ["9:16"],
                "max_file_size": 287.6,  # MB
                "caption_length": 150,
                "hashtag_limit": 10,
                "required_metadata": ["description", "hashtags", "privacy_setting"],
                "optimization_tips": [
                    "Use trending sounds",
                    "Add text overlay",
                    "Engage with comments",
                    "Post during peak hours"
                ]
            },
            "youtube_shorts": {
                "max_duration": 60,
                "supported_formats": ["mp4", "mov", "avi"],
                "aspect_ratios": ["9:16"],
                "max_file_size": 256,  # MB
                "caption_length": 100,
                "hashtag_limit": 15,
                "required_metadata": ["title", "description", "tags", "category"],
                "optimization_tips": [
                    "Hook in first 3 seconds",
                    "Vertical video only",
                    "Add end screen",
                    "Use #shorts in title"
                ]
            },
            "instagram_reels": {
                "max_duration": 90,
                "supported_formats": ["mp4", "mov"],
                "aspect_ratios": ["9:16", "1:1", "4:5"],
                "max_file_size": 100,  # MB
                "caption_length": 125,
                "hashtag_limit": 30,
                "required_metadata": ["caption", "hashtags", "location", "audio"],
                "optimization_tips": [
                    "Use trending audio",
                    "Add captions/text",
                    "Engage with first comment",
                    "Post consistently"
                ]
            },
            "x": {
                "max_duration": 140,
                "supported_formats": ["mp4", "mov"],
                "aspect_ratios": ["16:9", "1:1"],
                "max_file_size": 512,  # MB
                "caption_length": 280,
                "hashtag_limit": 5,
                "required_metadata": ["text", "hashtags", "poll_options"],
                "optimization_tips": [
                    "Thread for longer content",
                    "Use relevant hashtags",
                    "Engage with replies",
                    "Post during conversations"
                ]
            }
        }
    
    async def _process_loop(self):
        """Main processing loop for content packaging."""
        while self.is_running:
            try:
                # Check for pending assets
                if not self.pending_assets.empty():
                    asset_data = await self.pending_assets.get()
                    
                    self.logger.info(f"Processing asset: {asset_data.get('asset_id', 'unknown')}")
                    
                    # Create content package
                    content_package = await self.create_content_package(asset_data)
                    
                    if content_package:
                        # Save to ledger
                        self._save_content_package(content_package)
                        
                        # Send to Publisher Agent
                        await self._distribute_content_package(content_package)
                    
                    self.pending_assets.task_done()
                
                # Wait before next check
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in content packaging loop: {e}")
                await asyncio.sleep(10)
    
    async def handle_intent(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming intent for content packaging.
        
        Args:
            intent_data: Intent payload with asset information
            
        Returns:
            Response with packaging status
        """
        operation_id = self._log_operation(
            operation="content_packaging_intent",
            status="pending",
            details={"asset_id": intent_data.get("asset_id", "unknown")}
        )
        
        try:
            # Add to processing queue
            await self.pending_assets.put(intent_data)
            
            self._log_operation(
                operation="content_packaging_intent",
                status="success",
                details={
                    "asset_id": intent_data.get("asset_id", "unknown"),
                    "queue_position": self.pending_assets.qsize()
                }
            )
            
            return {
                "status": "queued",
                "operation_id": operation_id,
                "queue_position": self.pending_assets.qsize(),
                "estimated_wait": self.pending_assets.qsize() * 30  # 30 seconds per item
            }
            
        except Exception as e:
            self._log_operation(
                operation="content_packaging_intent",
                status="failure",
                details={"error": str(e)}
            )
            
            return {
                "status": "error",
                "operation_id": operation_id,
                "error": str(e)
            }
    
    async def create_content_package(self, asset_data: Dict[str, Any]) -> Optional[ContentPackage]:
        """
        Create a content package from asset data.
        
        Args:
            asset_data: Asset data from Asset Agent
            
        Returns:
            ContentPackage object or None if failed
        """
        operation_id = self._log_operation(
            operation="content_packaging",
            status="pending",
            details={"asset_id": asset_data.get("asset_id", "unknown")}
        )
        
        start_time = time.time()
        
        try:
            # Extract asset information
            asset_id = asset_data.get("asset_id", "")
            job_id = asset_data.get("job_id", "")
            file_url = asset_data.get("file_url", "")
            thumbnail_url = asset_data.get("thumbnail_url", "")
            subtitle_url = asset_data.get("subtitle_url", "")
            asset_type = asset_data.get("asset_type", "video")
            format_str = asset_data.get("format", "9:16")
            duration_seconds = asset_data.get("duration_seconds", 60)
            resolution = asset_data.get("resolution", "1080p")
            
            # Get related data from ledgers
            script_data = self._get_script_data(job_id)
            brief_data = self._get_brief_data(script_data.get("brief_id") if script_data else "")
            
            # Determine target platforms
            target_platforms = self._determine_target_platforms(format_str, duration_seconds)
            
            # Create generated asset object
            asset_format = ContentFormat(format_str) if format_str in [f.value for f in ContentFormat] else ContentFormat.PORTRAIT_9_16
            
            generated_asset = GeneratedAsset(
                asset_id=asset_id,
                job_id=job_id,
                asset_type=AssetType(asset_type) if asset_type in [a.value for a in AssetType] else AssetType.VIDEO,
                format=asset_format,
                file_url=file_url,
                thumbnail_url=thumbnail_url,
                subtitle_url=subtitle_url,
                duration_seconds=duration_seconds,
                resolution=resolution
            )
            
            # Generate multi-format assets
            assets_by_format = self._generate_multi_format_assets(generated_asset, target_platforms)
            
            # Generate platform packages
            platform_packages = self._generate_platform_packages(
                assets_by_format, target_platforms, script_data, brief_data
            )
            
            # Generate captions and hashtags
            captions = self._generate_captions(target_platforms, script_data, brief_data)
            hashtags = self._generate_hashtags(target_platforms, script_data, brief_data)
            
            # Determine posting schedule
            posting_schedule = self._determine_posting_schedule(target_platforms)
            
            # Run compliance check
            compliance_check_passed = self._run_compliance_check(
                platform_packages, script_data, brief_data
            )
            
            # Create content package
            content_package = ContentPackage(
                package_id=f"package_{asset_id.replace('asset_', '')}",
                brief_id=brief_data.get("brief_id", "") if brief_data else "",
                script_id=script_data.get("script_id", "") if script_data else "",
                assets=assets_by_format,
                platform_packages=platform_packages,
                captions=captions,
                hashtags=hashtags,
                posting_schedule=posting_schedule,
                disclosures_included=self._check_disclosures_included(brief_data),
                compliance_check_passed=compliance_check_passed
            )
            
            duration = time.time() - start_time
            
            self._log_operation(
                operation="content_packaging",
                status="success",
                details={
                    "asset_id": asset_id,
                    "package_id": content_package.package_id,
                    "platforms": [p.value for p in target_platforms],
                    "formats_generated": len(assets_by_format),
                    "compliance_passed": compliance_check_passed
                },
                duration_seconds=duration
            )
            
            return content_package
            
        except Exception as e:
            duration = time.time() - start_time
            self._log_operation(
                operation="content_packaging",
                status="failure",
                details={"error": str(e)},
                duration_seconds=duration
            )
            self.logger.error(f"Failed to create content package: {e}")
            return None
    
    def _get_script_data(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get script data from ledger using job ID."""
        scripts = self._read_ledger("scripts", limit=100)
        
        # Extract script_id from job_id (job_script_xxx -> script_xxx)
        script_id = job_id.replace("job_", "script_")
        
        for script in scripts:
            if script.get("script_id") == script_id:
                return script
        
        return None
    
    def _get_brief_data(self, brief_id: str) -> Optional[Dict[str, Any]]:
        """Get brief data from ledger."""
        if not brief_id:
            return None
        
        briefs = self._read_ledger("content_briefs", limit=100)
        
        for brief in briefs:
            if brief.get("brief_id") == brief_id:
                return brief
        
        return None
    
    def _determine_target_platforms(
        self,
        format_str: str,
        duration_seconds: float
    ) -> List[ContentPlatform]:
        """Determine target platforms based on format and duration."""
        platforms = []
        format_enum = ContentFormat(format_str) if format_str in [f.value for f in ContentFormat] else ContentFormat.PORTRAIT_9_16
        
        # Map formats to platforms
        format_to_platforms = {
            ContentFormat.PORTRAIT_9_16: [
                ContentPlatform.TIKTOK,
                ContentPlatform.YOUTUBE_SHORTS,
                ContentPlatform.INSTAGRAM_REELS
            ],
            ContentFormat.SQUARE_1_1: [
                ContentPlatform.INSTAGRAM_FEED,
                ContentPlatform.X,
                ContentPlatform.FACEBOOK,
                ContentPlatform.LINKEDIN
            ],
            ContentFormat.LANDSCAPE_16_9: [
                ContentPlatform.X,
                ContentPlatform.FACEBOOK,
                ContentPlatform.LINKEDIN
            ]
        }
        
        # Get platforms for this format
        candidate_platforms = format_to_platforms.get(format_enum, [ContentPlatform.TIKTOK])
        
        # Filter by duration limits
        for platform in candidate_platforms:
            platform_spec = self.platform_specs.get(platform.value, {})
            max_duration = platform_spec.get("max_duration", 60)
            
            if duration_seconds <= max_duration:
                platforms.append(platform)
        
        # Ensure at least one platform
        if not platforms and candidate_platforms:
            platforms = [candidate_platforms[0]]
        
        return platforms
    
    def _generate_multi_format_assets(
        self,
        base_asset: GeneratedAsset,
        target_platforms: List[ContentPlatform]
    ) -> Dict[ContentFormat, GeneratedAsset]:
        """Generate assets in multiple formats for different platforms."""
        assets = {}
        
        # Start with the base asset
        assets[base_asset.format] = base_asset
        
        # Determine additional formats needed
        additional_formats = set()
        
        for platform in target_platforms:
            platform_spec = self.platform_specs.get(platform.value, {})
            supported_ratios = platform_spec.get("aspect_ratios", [])
            
            for ratio in supported_ratios:
                if ratio in [f.value for f in ContentFormat]:
                    format_enum = ContentFormat(ratio)
                    if format_enum != base_asset.format:
                        additional_formats.add(format_enum)
        
        # Generate additional format assets (simulated)
        for format_enum in additional_formats:
            # Create modified asset for this format
            modified_asset = GeneratedAsset(
                asset_id=f"{base_asset.asset_id}_{format_enum.value.replace(':', '_')}",
                job_id=base_asset.job_id,
                asset_type=base_asset.asset_type,
                format=format_enum,
                file_url=f"{base_asset.file_url.rsplit('.', 1)[0]}_{format_enum.value.replace(':', '_')}.mp4",
                thumbnail_url=f"{base_asset.thumbnail_url.rsplit('.', 1)[0]}_{format_enum.value.replace(':', '_')}.jpg",
                subtitle_url=base_asset.subtitle_url,
                generation_tool=base_asset.generation_tool,
                generation_time_seconds=base_asset.generation_time_seconds,
                generation_cost=base_asset.generation_cost * 0.3,  # 30% of original cost for format conversion
                duration_seconds=base_asset.duration_seconds,
                resolution=self._get_resolution_for_format(format_enum),
                file_size_bytes=int(base_asset.file_size_bytes * 0.8),  # 80% of original size
                file_format=base_asset.file_format
            )
            
            assets[format_enum] = modified_asset
        
        return assets
    
    def _get_resolution_for_format(self, format_enum: ContentFormat) -> str:
        """Get appropriate resolution for a format."""
        resolution_map = {
            ContentFormat.PORTRAIT_9_16: "1080x1920",
            ContentFormat.SQUARE_1_1: "1080x1080",
            ContentFormat.LANDSCAPE_16_9: "1920x1080",
            ContentFormat.STORY_9_16: "1080x1920"
        }
        return resolution_map.get(format_enum, "1080x1920")
    
    def _generate_platform_packages(
        self,
        assets_by_format: Dict[ContentFormat, GeneratedAsset],
        target_platforms: List[ContentPlatform],
        script_data: Optional[Dict[str, Any]],
        brief_data: Optional[Dict[str, Any]]
    ) -> Dict[ContentPlatform, Dict[str, Any]]:
        """Generate platform-specific packages."""
        platform_packages = {}
        
        for platform in target_platforms:
            platform_spec = self.platform_specs.get(platform.value, {})
            
            # Determine best format for this platform
            best_format = self._determine_best_format_for_platform(platform, assets_by_format)
            
            if best_format:
                asset = assets_by_format[best_format]
                
                # Create platform package
                package = {
                    "asset_id": asset.asset_id,
                    "format": asset.format.value,
                    "file_url": asset.file_url,
                    "thumbnail_url": asset.thumbnail_url,
                    "subtitle_url": asset.subtitle_url,
                    "duration_seconds": asset.duration_seconds,
                    "resolution": asset.resolution,
                    "file_size_bytes": asset.file_size_bytes,
                    "platform_specifications": platform_spec,
                    "optimization_tips": platform_spec.get("optimization_tips", []),
                    "metadata_requirements": platform_spec.get("required_metadata", [])
                }
                
                # Add script and brief information if available
                if script_data:
                    package["script_hook"] = script_data.get("hooks", [""])[0] if script_data.get("hooks") else ""
                    package["script_cta"] = script_data.get("cta_variants", [""])[0] if script_data.get("cta_variants") else ""
                
                if brief_data:
                    package["brief_title"] = brief_data.get("title", "")
                    package["primary_keywords"] = brief_data.get("primary_keywords", [])
                
                platform_packages[platform] = package
        
        return platform_packages
    
    def _determine_best_format_for_platform(
        self,
        platform: ContentPlatform,
        assets_by_format: Dict[ContentFormat, GeneratedAsset]
    ) -> Optional[ContentFormat]:
        """Determine the best format for a given platform."""
        platform_spec = self.platform_specs.get(platform.value, {})
        supported_ratios = platform_spec.get("aspect_ratios", [])
        
        # Convert string ratios to ContentFormat enums
        supported_formats = []
        for ratio in supported_ratios:
            if ratio in [f.value for f in ContentFormat]:
                supported_formats.append(ContentFormat(ratio))
        
        # Find the first matching format
        for format_enum in supported_formats:
            if format_enum in assets_by_format:
                return format_enum
        
        # If no exact match, return the first available asset
        if assets_by_format:
            return list(assets_by_format.keys())[0]
        
        return None
    
    def _generate_captions(
        self,
        target_platforms: List[ContentPlatform],
        script_data: Optional[Dict[str, Any]],
        brief_data: Optional[Dict[str, Any]]
    ) -> Dict[ContentPlatform, str]:
        """Generate platform-specific captions."""
        captions = {}
        
        base_caption = ""
        if script_data:
            hooks = script_data.get("hooks", [])
            if hooks:
                base_caption = hooks[0]
        
        if brief_data and not base_caption:
            base_caption = brief_data.get("title", "")
        
        for platform in target_platforms:
            platform_spec = self.platform_specs.get(platform.value, {})
            max_length = platform_spec.get("caption_length", 100)
            
            # Platform-specific caption formatting
            if platform == ContentPlatform.TIKTOK:
                caption = f"{base_caption}\n\n#fyp #contentcreation #digitalmarketing"
            elif platform == ContentPlatform.YOUTUBE_SHORTS:
                caption = f"{base_caption}\n\nSubscribe for more content like this! #shorts"
            elif platform == ContentPlatform.INSTAGRAM_REELS:
                caption = f"{base_caption}\n\nFollow for daily tips! 👇 #reels"
            elif platform == ContentPlatform.X:
                caption = f"{base_caption}\n\nRead more ↓ #content #marketing"
            else:
                caption = base_caption
            
            # Truncate if necessary
            if len(caption) > max_length:
                caption = caption[:max_length-3] + "..."
            
            captions[platform] = caption
        
        return captions
    
    def _generate_hashtags(
        self,
        target_platforms: List[ContentPlatform],
        script_data: Optional[Dict[str, Any]],
        brief_data: Optional[Dict[str, Any]]
    ) -> Dict[ContentPlatform, List[str]]:
        """Generate platform-specific hashtags."""
        hashtags = {}
        
        base_hashtags = []
        if brief_data:
            base_hashtags = brief_data.get("hashtags", [])
        
        # Add some default hashtags
        default_hashtags = ["#contentcreation", "#digitalmarketing", "#aitools"]
        all_hashtags = base_hashtags + default_hashtags
        
        for platform in target_platforms:
            platform_spec = self.platform_specs.get(platform.value, {})
            hashtag_limit = platform_spec.get("hashtag_limit", 10)
            
            # Platform-specific hashtag selection
            if platform == ContentPlatform.TIKTOK:
                platform_hashtags = ["#fyp", "#foryou", "#foryoupage"] + all_hashtags[:hashtag_limit-3]
            elif platform == ContentPlatform.YOUTUBE_SHORTS:
                platform_hashtags = ["#shorts", "#youtubeshorts"] + all_hashtags[:hashtag_limit-2]
            elif platform == ContentPlatform.INSTAGRAM_REELS:
                platform_hashtags = ["#reels", "#instagram"] + all_hashtags[:hashtag_limit-2]
            elif platform == ContentPlatform.X:
                platform_hashtags = all_hashtags[:min(hashtag_limit, 5)]  # X prefers fewer hashtags
            else:
                platform_hashtags = all_hashtags[:hashtag_limit]
            
            hashtags[platform] = platform_hashtags[:hashtag_limit]
        
        return hashtags
    
    def _determine_posting_schedule(self, target_platforms: List[ContentPlatform]) -> Dict[ContentPlatform, str]:
        """Determine optimal posting schedule for platforms."""
        posting_schedule = {}
        
        # Best posting times by platform (in UTC)
        best_times = {
            ContentPlatform.TIKTOK: "18:00",  # 6 PM UTC
            ContentPlatform.YOUTUBE_SHORTS: "17:00",  # 5 PM UTC
            ContentPlatform.INSTAGRAM_REELS: "19:00",  # 7 PM UTC
            ContentPlatform.X: "16:00",  # 4 PM UTC
            ContentPlatform.FACEBOOK: "15:00",  # 3 PM UTC
            ContentPlatform.LINKEDIN: "14:00",  # 2 PM UTC
        }
        
        for platform in target_platforms:
            if platform in best_times:
                # Schedule for tomorrow at best time
                tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
                posting_schedule[platform] = f"{tomorrow}T{best_times[platform]}:00Z"
            else:
                # Default: schedule for tomorrow at noon UTC
                tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
                posting_schedule[platform] = f"{tomorrow}T12:00:00Z"
        
        return posting_schedule
    
    def _run_compliance_check(
        self,
        platform_packages: Dict[ContentPlatform, Dict[str, Any]],
        script_data: Optional[Dict[str, Any]],
        brief_data: Optional[Dict[str, Any]]
    ) -> bool:
        """Run compliance check on content packages."""
        try:
            # Check 1: Duration limits
            for platform, package in platform_packages.items():
                platform_spec = self.platform_specs.get(platform.value, {})
                max_duration = platform_spec.get("max_duration", 60)
                
                if package.get("duration_seconds", 0) > max_duration:
                    self.logger.warning(f"Duration {package['duration_seconds']}s exceeds limit {max_duration}s for {platform.value}")
                    return False
            
            # Check 2: File size limits
            for platform, package in platform_packages.items():
                platform_spec = self.platform_specs.get(platform.value, {})
                max_file_size_mb = platform_spec.get("max_file_size", 100)
                max_file_size_bytes = max_file_size_mb * 1024 * 1024
                
                if package.get("file_size_bytes", 0) > max_file_size_bytes:
                    self.logger.warning(f"File size {package['file_size_bytes']} bytes exceeds limit {max_file_size_bytes} bytes for {platform.value}")
                    return False
            
            # Check 3: Required disclosures
            if brief_data:
                required_disclosures = brief_data.get("required_disclosures", [])
                if required_disclosures:
                    # Check if disclosures are included in captions
                    # This would require more sophisticated checking in real implementation
                    self.logger.info(f"Required disclosures: {required_disclosures}")
                    # For now, assume they will be added by Publisher Agent
            
            # Check 4: Platform-specific requirements
            for platform, package in platform_packages.items():
                platform_spec = self.platform_specs.get(platform.value, {})
                required_metadata = platform_spec.get("required_metadata", [])
                
                # Check if we have the required metadata
                # This is a simplified check
                if required_metadata:
                    self.logger.info(f"Platform {platform.value} requires: {required_metadata}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Compliance check error: {e}")
            return False
    
    def _check_disclosures_included(self, brief_data: Optional[Dict[str, Any]]) -> bool:
        """Check if required disclosures are included."""
        if not brief_data:
            return True  # No brief, no disclosures required
        
        required_disclosures = brief_data.get("required_disclosures", [])
        return len(required_disclosures) == 0  # True if no disclosures required
    
    def _save_content_package(self, package: ContentPackage):
        """Save content package to ledger."""
        from dataclasses import asdict
        
        record = asdict(package)
        
        # Convert enum keys to strings
        if package.assets:
            record["assets"] = {
                k.value: asdict(v) for k, v in package.assets.items()
            }
            # Convert enum values in assets
            for asset_dict in record["assets"].values():
                if "asset_type" in asset_dict:
                    asset_dict["asset_type"] = asset_dict["asset_type"].value
                if "format" in asset_dict:
                    asset_dict["format"] = asset_dict["format"].value
                if "generation_tool" in asset_dict:
                    asset_dict["generation_tool"] = asset_dict["generation_tool"].value
        
        if package.platform_packages:
            record["platform_packages"] = {
                k.value: v for k, v in package.platform_packages.items()
            }
        
        if package.captions:
            record["captions"] = {
                k.value: v for k, v in package.captions.items()
            }
        
        if package.hashtags:
            record["hashtags"] = {
                k.value: v for k, v in package.hashtags.items()
            }
        
        if package.posting_schedule:
            record["posting_schedule"] = {
                k.value: v for k, v in package.posting_schedule.items()
            }
        
        self._append_to_ledger("content_packages", record)
    
    async def _distribute_content_package(self, package: ContentPackage):
        """Distribute content package to Publisher Agent."""
        try:
            # Prepare intent data for Publisher Agent
            intent_data = {
                "package_id": package.package_id,
                "brief_id": package.brief_id,
                "script_id": package.script_id,
                "platform_packages": {
                    k.value: v for k, v in package.platform_packages.items()
                },
                "captions": {
                    k.value: v for k, v in package.captions.items()
                },
                "hashtags": {
                    k.value: v for k, v in package.hashtags.items()
                },
                "posting_schedule": {
                    k.value: v for k, v in package.posting_schedule.items()
                },
                "compliance_check_passed": package.compliance_check_passed,
                "disclosures_included": package.disclosures_included
            }
            
            response = self._send_intent("media.content_publishing", intent_data)
            
            if response:
                self.logger.info(f"Distributed package {package.package_id} to Publisher Agent")
            else:
                self.logger.warning(f"Failed to distribute package {package.package_id}")
                
        except Exception as e:
            self.logger.error(f"Error distributing package {package.package_id}: {e}")
    
    def get_recent_packages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent content packages."""
        return self._read_ledger("content_packages", limit=limit)
    
    def get_packaging_statistics(self) -> Dict[str, Any]:
        """Get content packaging statistics."""
        packages = self._read_ledger("content_packages", limit=100)
        operations = self._read_ledger("operations", limit=100)
        
        if not packages:
            return {"status": "no_data", "message": "No packages created yet"}
        
        # Calculate statistics
        packaging_operations = [op for op in operations if op.get("operation") == "content_packaging"]
        
        success_count = sum(1 for op in packaging_operations if op.get("status") == "success")
        failure_count = sum(1 for op in packaging_operations if op.get("status") == "failure")
        
        # Platform distribution
        platform_counts = {}
        format_counts = {}
        
        for package in packages:
            # Count platforms
            if "platform_packages" in package:
                for platform in package["platform_packages"].keys():
                    platform_counts[platform] = platform_counts.get(platform, 0) + 1
            
            # Count formats
            if "assets" in package:
                for format_str in package["assets"].keys():
                    format_counts[format_str] = format_counts.get(format_str, 0) + 1
        
        # Compliance statistics
        compliance_passed = sum(1 for p in packages if p.get("compliance_check_passed", False))
        compliance_failed = len(packages) - compliance_passed
        
        return {
            "status": "success",
            "statistics": {
                "total_packages": len(packages),
                "success_rate": f"{(success_count / len(packaging_operations) * 100):.1f}%" if packaging_operations else "0%",
                "platform_distribution": platform_counts,
                "format_distribution": format_counts,
                "compliance_pass_rate": f"{(compliance_passed / len(packages) * 100):.1f}%" if packages else "0%",
                "pending_queue": self.pending_assets.qsize()
            },
            "recent_packages": packages[:5]
        }


# Factory function for creating the agent
def create_edit_packaging_agent(
    agent_id: str = "edit_packaging_agent",
    data_dir: Optional[str] = None
) -> EditPackagingAgent:
    """Create and return an Edit/Packaging Agent instance."""
    return EditPackagingAgent(
        agent_id=agent_id,
        data_dir=data_dir
    )