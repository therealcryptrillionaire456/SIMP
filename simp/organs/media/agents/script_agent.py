"""
Script Agent for KashClaw Media Grid.

Responsible for:
- Generating hooks (attention grabbers) for content
- Writing scripts for videos/posts
- Creating call-to-action (CTA) variants
- Generating platform-specific metadata
"""
import asyncio
import json
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

from simp.organs.media.agents.base_media_agent import BaseMediaAgent
from simp.organs.media.models import (
    ScriptPackage, ContentBrief, ContentPlatform, GenerationTool
)


class ScriptAgent(BaseMediaAgent):
    """Agent that generates scripts for content creation."""
    
    def __init__(
        self,
        agent_id: str = "script_agent",
        data_dir: Optional[str] = None,
        log_level: str = "INFO",
        generation_tool: GenerationTool = GenerationTool.CLAUDE
    ):
        """Initialize the Script Agent."""
        super().__init__(
            agent_id=agent_id,
            agent_name="Script Agent",
            data_dir=data_dir,
            log_level=log_level
        )
        
        self.generation_tool = generation_tool
        self.pending_briefs = asyncio.Queue()
        
        # Templates and patterns for script generation
        self.hook_templates = self._load_hook_templates()
        self.script_structures = self._load_script_structures()
        self.cta_templates = self._load_cta_templates()
        self.brand_voices = self._load_brand_voices()
        
        self.logger.info(f"Script Agent initialized with {generation_tool.value} generation")
    
    def _load_hook_templates(self) -> List[str]:
        """Load hook templates for different content types."""
        return [
            "Stop wasting time on [PROBLEM]. Here's how to [SOLUTION] in 60 seconds.",
            "I tried [TOOL/METHOD] for 30 days. Here's what happened...",
            "Most people get [PROBLEM] wrong. Here's the right way to do it.",
            "This [TOOL] changed how I [ACTIVITY]. Let me show you why.",
            "3 [ADJECTIVE] ways to [SOLUTION] that actually work.",
            "If you're still [PROBLEM], you need to see this.",
            "The secret to [GOAL] that nobody talks about.",
            "I was struggling with [PROBLEM] until I discovered [SOLUTION].",
            "This simple trick will [BENEFIT] instantly.",
            "Why [COMMON_MISTAKE] is holding you back from [GOAL]."
        ]
    
    def _load_script_structures(self) -> Dict[str, List[str]]:
        """Load script structures for different content angles."""
        return {
            "review": [
                "1. Introduction and personal experience",
                "2. Key features and benefits",
                "3. Pros and cons analysis", 
                "4. Who it's best for",
                "5. Final verdict and recommendation"
            ],
            "tutorial": [
                "1. Problem statement and why it matters",
                "2. Step-by-step walkthrough",
                "3. Tips and best practices",
                "4. Common mistakes to avoid",
                "5. Results and next steps"
            ],
            "comparison": [
                "1. Introduction to both options",
                "2. Feature-by-feature comparison",
                "3. Use case recommendations",
                "4. Price and value analysis",
                "5. Final recommendation based on needs"
            ],
            "case_study": [
                "1. Starting situation and challenges",
                "2. Solution implementation",
                "3. Process and methodology",
                "4. Results and metrics",
                "5. Key takeaways and lessons"
            ],
            "tips": [
                "1. Introduction to the topic",
                "2. Tip 1 with explanation",
                "3. Tip 2 with explanation",
                "4. Tip 3 with explanation",
                "5. Summary and action items"
            ]
        }
    
    def _load_cta_templates(self) -> List[str]:
        """Load CTA templates for different platforms."""
        return [
            "Check out [TOOL] in my bio for [BENEFIT].",
            "Want to [BENEFIT]? Link in bio to get started.",
            "Get [DISCOUNT]% off [TOOL] using my link below.",
            "Learn more about [TOPIC] on my website (link in bio).",
            "Ready to [GOAL]? Click the link to begin.",
            "Save this for later and follow for more [TOPIC] tips.",
            "What's your favorite [TOOL_TYPE]? Comment below!",
            "Follow for daily [TOPIC] tips and tutorials.",
            "Bookmark this for when you need to [SOLUTION].",
            "Share with someone who needs to see this!"
        ]
    
    def _load_brand_voices(self) -> Dict[str, Dict[str, Any]]:
        """Load different brand voice profiles."""
        return {
            "professional": {
                "tone": "authoritative, informative, clear",
                "language": "formal, precise, data-driven",
                "pace": "moderate, deliberate",
                "humor": "minimal, dry if any",
                "examples": ["according to research", "data shows", "studies indicate"]
            },
            "casual": {
                "tone": "friendly, conversational, relatable",
                "language": "informal, colloquial, simple",
                "pace": "natural, flowing",
                "humor": "light, self-deprecating",
                "examples": ["hey there", "so here's the thing", "let's be real"]
            },
            "enthusiastic": {
                "tone": "energetic, excited, passionate",
                "language": "expressive, emphatic, vivid",
                "pace": "fast, dynamic",
                "humor": "playful, exaggerated",
                "examples": ["OMG you guys", "this is absolutely game-changing", "I'm obsessed with"]
            },
            "educational": {
                "tone": "patient, thorough, supportive",
                "language": "clear, structured, explanatory",
                "pace": "slow, measured",
                "humor": "gentle, occasional",
                "examples": ["let me walk you through", "here's what you need to know", "the key concept is"]
            }
        }
    
    async def _process_loop(self):
        """Main processing loop for script generation."""
        while self.is_running:
            try:
                # Check for pending briefs
                if not self.pending_briefs.empty():
                    brief_data = await self.pending_briefs.get()
                    
                    self.logger.info(f"Processing brief: {brief_data.get('brief_id', 'unknown')}")
                    
                    # Generate script package
                    script_package = await self.generate_script_package(brief_data)
                    
                    if script_package:
                        # Save to ledger
                        self._save_script_package(script_package)
                        
                        # Send to Asset Agent for asset generation
                        await self._distribute_script_package(script_package)
                    
                    self.pending_briefs.task_done()
                
                # Wait before next check
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in script generation loop: {e}")
                await asyncio.sleep(10)
    
    async def handle_intent(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming intent for script generation.
        
        Args:
            intent_data: Intent payload with brief information
            
        Returns:
            Response with script generation status
        """
        operation_id = self._log_operation(
            operation="script_generation_intent",
            status="pending",
            details={"brief_id": intent_data.get("brief_id", "unknown")}
        )
        
        try:
            # Add to processing queue
            await self.pending_briefs.put(intent_data)
            
            self._log_operation(
                operation="script_generation_intent",
                status="success",
                details={
                    "brief_id": intent_data.get("brief_id", "unknown"),
                    "queue_position": self.pending_briefs.qsize()
                }
            )
            
            return {
                "status": "queued",
                "operation_id": operation_id,
                "queue_position": self.pending_briefs.qsize(),
                "estimated_wait": self.pending_briefs.qsize() * 30  # 30 seconds per item
            }
            
        except Exception as e:
            self._log_operation(
                operation="script_generation_intent",
                status="failure",
                details={"error": str(e)}
            )
            
            return {
                "status": "error",
                "operation_id": operation_id,
                "error": str(e)
            }
    
    async def generate_script_package(self, brief_data: Dict[str, Any]) -> Optional[ScriptPackage]:
        """
        Generate a script package from a content brief.
        
        Args:
            brief_data: Content brief data
            
        Returns:
            ScriptPackage object or None if failed
        """
        operation_id = self._log_operation(
            operation="script_generation",
            status="pending",
            details={"brief_id": brief_data.get("brief_id", "unknown")}
        )
        
        start_time = time.time()
        
        try:
            # Extract brief information
            brief_id = brief_data.get("brief_id", "")
            title = brief_data.get("title", "")
            description = brief_data.get("description", "")
            content_angle = brief_data.get("content_angle", "review")
            target_platforms = brief_data.get("target_platforms", ["tiktok"])
            
            # Get offer information if available
            primary_offer = brief_data.get("primary_offer")
            offer_name = primary_offer.get("name") if primary_offer else None
            offer_description = primary_offer.get("description") if primary_offer else ""
            
            # Generate hooks
            hooks = self._generate_hooks(title, description, offer_name, content_angle)
            
            # Generate scripts
            scripts = self._generate_scripts(title, description, offer_name, offer_description, content_angle)
            
            # Generate CTAs
            cta_variants = self._generate_cta_variants(offer_name, content_angle)
            
            # Generate platform metadata
            platform_metadata = self._generate_platform_metadata(target_platforms, title, hooks[0])
            
            # Determine brand voice
            brand_voice = self._determine_brand_voice(content_angle, target_platforms)
            
            # Create script package
            script_package = ScriptPackage(
                script_id=f"script_{brief_id.replace('brief_', '')}",
                brief_id=brief_id,
                title=title,
                hooks=hooks,
                scripts=scripts,
                cta_variants=cta_variants,
                platform_metadata=platform_metadata,
                brand_voice=brand_voice,
                tone=self._determine_tone(content_angle, brand_voice),
                generation_tool=self.generation_tool,
                generation_prompt=self._create_generation_prompt(
                    title, description, content_angle, offer_name
                )
            )
            
            duration = time.time() - start_time
            
            self._log_operation(
                operation="script_generation",
                status="success",
                details={
                    "brief_id": brief_id,
                    "script_id": script_package.script_id,
                    "hooks_generated": len(hooks),
                    "scripts_generated": len(scripts),
                    "ctas_generated": len(cta_variants)
                },
                duration_seconds=duration
            )
            
            return script_package
            
        except Exception as e:
            duration = time.time() - start_time
            self._log_operation(
                operation="script_generation",
                status="failure",
                details={"error": str(e)},
                duration_seconds=duration
            )
            self.logger.error(f"Failed to generate script package: {e}")
            return None
    
    def _generate_hooks(
        self,
        title: str,
        description: str,
        offer_name: Optional[str],
        content_angle: str
    ) -> List[str]:
        """Generate 10 hooks for the content."""
        hooks = []
        
        # Use templates and customize them
        for template in random.sample(self.hook_templates, min(10, len(self.hook_templates))):
            hook = template
            
            # Customize based on content
            if offer_name and "[TOOL]" in hook:
                hook = hook.replace("[TOOL]", offer_name)
            
            if "[PROBLEM]" in hook:
                # Extract problem from title/description
                problem_keywords = ["waste time", "struggle", "hard", "difficult", "problem", "challenge"]
                problem = "creating content"  # default
                for keyword in problem_keywords:
                    if keyword in description.lower():
                        problem = keyword
                        break
                hook = hook.replace("[PROBLEM]", problem)
            
            if "[SOLUTION]" in hook:
                solution = "save time"  # default
                if offer_name:
                    solution = f"use {offer_name}"
                hook = hook.replace("[SOLUTION]", solution)
            
            if "[BENEFIT]" in hook:
                benefit_keywords = ["save time", "make money", "grow faster", "work smarter"]
                benefit = random.choice(benefit_keywords)
                hook = hook.replace("[BENEFIT]", benefit)
            
            hooks.append(hook)
        
        # Ensure we have exactly 10 hooks
        while len(hooks) < 10:
            hooks.append(f"Here's what you need to know about {title.split(':')[0] if ':' in title else title}.")
        
        return hooks[:10]
    
    def _generate_scripts(
        self,
        title: str,
        description: str,
        offer_name: Optional[str],
        offer_description: str,
        content_angle: str
    ) -> List[Dict[str, Any]]:
        """Generate 3 scripts for the content."""
        scripts = []
        
        # Get script structure for this angle
        structure = self.script_structures.get(content_angle, self.script_structures["review"])
        
        for i in range(3):
            script = {
                "script_id": f"script_{i+1}",
                "structure": structure,
                "content": [],
                "duration_estimate": 45 + (i * 15),  # 45, 60, 75 seconds
                "style": self._get_script_style(i)
            }
            
            # Generate content for each section
            for j, section in enumerate(structure):
                section_content = self._generate_section_content(
                    section=section,
                    section_num=j+1,
                    title=title,
                    description=description,
                    offer_name=offer_name,
                    offer_description=offer_description,
                    content_angle=content_angle,
                    script_variant=i
                )
                script["content"].append({
                    "section": section,
                    "content": section_content,
                    "duration_estimate": 8 + (j * 2)  # Increasing duration per section
                })
            
            scripts.append(script)
        
        return scripts
    
    def _generate_section_content(
        self,
        section: str,
        section_num: int,
        title: str,
        description: str,
        offer_name: Optional[str],
        offer_description: str,
        content_angle: str,
        script_variant: int
    ) -> str:
        """Generate content for a specific script section."""
        
        # Different variants for different scripts
        if script_variant == 0:
            # Variant 1: Direct and concise
            if "introduction" in section.lower():
                return f"Today I'm talking about {title}. {description}"
            elif "features" in section.lower() or "benefits" in section.lower():
                if offer_name:
                    return f"{offer_name} helps you {offer_description.lower().split('helps you')[1] if 'helps you' in offer_description else 'achieve your goals'}."
                return "The key benefits are efficiency, time savings, and better results."
            elif "pros" in section.lower() or "cons" in section.lower():
                return "Pros: Easy to use, affordable. Cons: Learning curve, limited features."
            elif "recommendation" in section.lower() or "verdict" in section.lower():
                if offer_name:
                    return f"I recommend {offer_name} for anyone looking to improve their workflow."
                return "This approach is worth trying if you want better results."
        
        elif script_variant == 1:
            # Variant 2: Storytelling approach
            if "introduction" in section.lower():
                return f"Let me tell you about when I discovered {title.split(':')[0] if ':' in title else title}."
            elif "features" in section.lower() or "benefits" in section.lower():
                if offer_name:
                    return f"What surprised me about {offer_name} was how it simplified everything."
                return "The real game-changer was how much time I started saving."
            elif "pros" in section.lower() or "cons" in section.lower():
                return "What I loved: The simplicity. What could be better: More customization."
            elif "recommendation" in section.lower() or "verdict" in section.lower():
                if offer_name:
                    return f"Would I use {offer_name} again? Absolutely. It's become essential."
                return "This method transformed how I work. Give it a try."
        
        else:
            # Variant 3: Educational approach
            if "introduction" in section.lower():
                return f"In this video, we'll explore {title} and why it matters."
            elif "features" in section.lower() or "benefits" in section.lower():
                if offer_name:
                    return f"{offer_name} provides three key benefits: efficiency, scalability, and ease of use."
                return "Research shows this approach increases productivity by up to 40%."
            elif "pros" in section.lower() or "cons" in section.lower():
                return "Advantages: Proven results. Limitations: Requires initial setup time."
            elif "recommendation" in section.lower() or "verdict" in section.lower():
                if offer_name:
                    return f"Based on the data, {offer_name} is a solid choice for most users."
                return "The evidence supports adopting this approach for long-term benefits."
        
        # Default content
        return f"This section covers important aspects of {title.split(':')[0] if ':' in title else title}."
    
    def _get_script_style(self, variant: int) -> str:
        """Get style for script variant."""
        styles = ["direct", "storytelling", "educational"]
        return styles[variant % len(styles)]
    
    def _generate_cta_variants(
        self,
        offer_name: Optional[str],
        content_angle: str
    ) -> List[str]:
        """Generate 3 CTA variants."""
        ctas = []
        
        # Use templates and customize them
        templates = random.sample(self.cta_templates, min(5, len(self.cta_templates)))
        
        for template in templates[:3]:  # Use first 3 templates
            cta = template
            
            # Customize based on offer
            if offer_name and "[TOOL]" in cta:
                cta = cta.replace("[TOOL]", offer_name)
            
            if "[BENEFIT]" in cta:
                benefits = ["better results", "saving time", "increasing productivity", "growing faster"]
                cta = cta.replace("[BENEFIT]", random.choice(benefits))
            
            if "[GOAL]" in cta:
                goals = ["improve your workflow", "get started", "learn more", "master this skill"]
                cta = cta.replace("[GOAL]", random.choice(goals))
            
            if "[TOPIC]" in cta:
                topic = content_angle.replace("_", " ")
                cta = cta.replace("[TOPIC]", topic)
            
            if "[DISCOUNT]" in cta and offer_name:
                discount = random.choice(["10", "15", "20", "25"])
                cta = cta.replace("[DISCOUNT]", discount)
            
            ctas.append(cta)
        
        # Ensure we have exactly 3 CTAs
        while len(ctas) < 3:
            if offer_name:
                ctas.append(f"Try {offer_name} using the link in my bio.")
            else:
                ctas.append("Check the link in my bio for more resources.")
        
        return ctas[:3]
    
    def _generate_platform_metadata(
        self,
        platforms: List[str],
        title: str,
        hook: str
    ) -> Dict[str, Dict[str, Any]]:
        """Generate platform-specific metadata."""
        metadata = {}
        
        for platform in platforms:
            if platform == "tiktok":
                metadata[platform] = {
                    "caption": f"{hook}\n\n{title}\n\n#fyp #contentcreation #digitalmarketing",
                    "hashtags": ["#fyp", "#contentcreation", "#digitalmarketing", "#aitools", "#tutorial"],
                    "max_length": 150,
                    "features": ["stitch", "duet", "green_screen"],
                    "best_practices": [
                        "Use trending sounds",
                        "Keep under 60 seconds",
                        "Text overlay for key points"
                    ]
                }
            elif platform == "youtube_shorts":
                metadata[platform] = {
                    "caption": f"{title}\n\n{hook}\n\nSubscribe for more content like this!",
                    "hashtags": ["#shorts", "#youtubeshorts", content_angle],
                    "max_length": 100,
                    "features": ["remix", "subscribe_button"],
                    "best_practices": [
                        "Hook in first 3 seconds",
                        "Vertical video (9:16)",
                        "End screen with subscribe ask"
                    ]
                }
            elif platform == "instagram_reels":
                metadata[platform] = {
                    "caption": f"{hook}\n\n{title}\n\nFollow for daily tips! 👇",
                    "hashtags": ["#reels", "#instagram", "#contentcreator", "#digitalmarketing"],
                    "max_length": 125,
                    "features": ["remix", "collab", "template"],
                    "best_practices": [
                        "Use trending audio",
                        "Add captions/text",
                        "Engagement ask in comments"
                    ]
                }
            elif platform == "x":
                metadata[platform] = {
                    "caption": f"{hook}\n\n{title}\n\nRead more ↓",
                    "hashtags": ["#content", "#marketing", "#tech"],
                    "max_length": 280,
                    "features": ["thread", "poll", "spaces"],
                    "best_practices": [
                        "Thread for longer content",
                        "Engage with replies",
                        "Use relevant hashtags"
                    ]
                }
            else:
                # Default metadata
                metadata[platform] = {
                    "caption": f"{title}\n\n{hook}",
                    "hashtags": ["#content", "#digital", "#tips"],
                    "max_length": 200,
                    "features": [],
                    "best_practices": ["Optimize for platform specifics"]
                }
        
        return metadata
    
    def _determine_brand_voice(
        self,
        content_angle: str,
        platforms: List[str]
    ) -> str:
        """Determine appropriate brand voice for content."""
        # Map content angles to brand voices
        angle_to_voice = {
            "review": "professional",
            "tutorial": "educational",
            "comparison": "professional",
            "case_study": "casual",
            "tips": "enthusiastic",
            "news": "professional"
        }
        
        # Default to professional
        voice = angle_to_voice.get(content_angle, "professional")
        
        # Adjust based on platforms
        if "tiktok" in platforms or "instagram_reels" in platforms:
            # More casual for short-form video platforms
            if voice == "professional":
                voice = "casual"
        
        return voice
    
    def _determine_tone(self, content_angle: str, brand_voice: str) -> str:
        """Determine tone based on brand voice and content angle."""
        if brand_voice in self.brand_voices:
            return self.brand_voices[brand_voice]["tone"]
        
        # Fallback based on content angle
        tone_map = {
            "review": "balanced, objective",
            "tutorial": "clear, patient",
            "comparison": "analytical, fair",
            "case_study": "narrative, insightful",
            "tips": "helpful, actionable",
            "news": "timely, informative"
        }
        
        return tone_map.get(content_angle, "professional, clear")
    
    def _create_generation_prompt(
        self,
        title: str,
        description: str,
        content_angle: str,
        offer_name: Optional[str]
    ) -> str:
        """Create the generation prompt used for script creation."""
        prompt = f"""
        Create engaging content about: {title}
        
        Description: {description}
        
        Content Angle: {content_angle}
        {"Product: " + offer_name if offer_name else "Topic-focused content"}
        
        Requirements:
        1. Generate 10 attention-grabbing hooks
        2. Write 3 complete scripts (45-75 seconds each)
        3. Create 3 call-to-action variants
        4. Platform-specific optimization
        
        Target Audience: Content creators, marketers, entrepreneurs
        Brand Voice: {self._determine_brand_voice(content_angle, ["tiktok", "youtube_shorts"])}
        """
        
        return prompt
    
    def _save_script_package(self, script_package: ScriptPackage):
        """Save script package to ledger."""
        from dataclasses import asdict
        
        record = asdict(script_package)
        
        # Convert enum values to strings
        record["generation_tool"] = script_package.generation_tool.value
        
        # Convert platform metadata keys to strings
        if script_package.platform_metadata:
            record["platform_metadata"] = {
                str(k): v for k, v in script_package.platform_metadata.items()
            }
        
        self._append_to_ledger("scripts", record)
    
    async def _distribute_script_package(self, script_package: ScriptPackage):
        """Distribute script package to Asset Agent for asset generation."""
        try:
            # Prepare intent data for Asset Agent
            intent_data = {
                "script_id": script_package.script_id,
                "brief_id": script_package.brief_id,
                "title": script_package.title,
                "scripts": script_package.scripts,
                "target_platforms": list(script_package.platform_metadata.keys()),
                "brand_voice": script_package.brand_voice,
                "tone": script_package.tone
            }
            
            response = self._send_intent("media.asset_generation", intent_data)
            
            if response:
                self.logger.info(f"Distributed script {script_package.script_id} to Asset Agent")
            else:
                self.logger.warning(f"Failed to distribute script {script_package.script_id}")
                
        except Exception as e:
            self.logger.error(f"Error distributing script {script_package.script_id}: {e}")
    
    def get_recent_scripts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent script packages."""
        return self._read_ledger("scripts", limit=limit)
    
    def get_script_statistics(self) -> Dict[str, Any]:
        """Get script generation statistics."""
        scripts = self._read_ledger("scripts", limit=100)
        operations = self._read_ledger("operations", limit=100)
        
        if not scripts:
            return {"status": "no_data", "message": "No scripts generated yet"}
        
        # Calculate statistics
        script_operations = [op for op in operations if op.get("operation") == "script_generation"]
        
        success_count = sum(1 for op in script_operations if op.get("status") == "success")
        failure_count = sum(1 for op in script_operations if op.get("status") == "failure")
        
        # Average duration
        durations = [op.get("duration_seconds", 0) for op in script_operations if "duration_seconds" in op]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Count by brand voice
        voice_counts = {}
        for script in scripts:
            voice = script.get("brand_voice", "unknown")
            voice_counts[voice] = voice_counts.get(voice, 0) + 1
        
        return {
            "status": "success",
            "statistics": {
                "total_scripts": len(scripts),
                "success_rate": f"{(success_count / len(script_operations) * 100):.1f}%" if script_operations else "0%",
                "average_generation_time": f"{avg_duration:.1f}s",
                "brand_voice_distribution": voice_counts,
                "pending_queue": self.pending_briefs.qsize()
            },
            "recent_scripts": scripts[:5]
        }


# Factory function for creating the agent
def create_script_agent(
    agent_id: str = "script_agent",
    data_dir: Optional[str] = None,
    generation_tool: GenerationTool = GenerationTool.CLAUDE
) -> ScriptAgent:
    """Create and return a Script Agent instance."""
    return ScriptAgent(
        agent_id=agent_id,
        data_dir=data_dir,
        generation_tool=generation_tool
    )