"""
ProjectX Multimodal Processor — Step 2

Extends computer.py's basic screenshot+OCR with structured visual understanding:
  - Element detection: buttons, inputs, labels, links, dialogs
  - Layout parsing: grids, forms, navigation bars, content areas
  - Semantic labels: what each detected region likely does
  - Action hints: given a goal, which element should be clicked/typed?

Backends (in priority order):
  1. Pillow + regex/heuristic rules  (zero extra deps — always available)
  2. OpenCV  (if installed — better region detection)
  3. Claude Vision API  (if anthropic SDK present + API key set)

Designed to slot into ProjectXComputer as tier-0 (read-only) actions.
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import math
import re
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ElementType(str, Enum):
    BUTTON      = "button"
    INPUT       = "input"
    LABEL       = "label"
    LINK        = "link"
    HEADING     = "heading"
    IMAGE       = "image"
    DIALOG      = "dialog"
    MENU        = "menu"
    TEXT        = "text"
    UNKNOWN     = "unknown"


class ModalityType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


@dataclass
class VisualElement:
    element_type:   ElementType
    text:           str
    bbox:           Tuple[int, int, int, int]   # x, y, w, h
    confidence:     float = 1.0
    action_hint:    str = ""        # "click", "type", "scroll", ""
    metadata:       Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.element_type.value,
            "text": self.text,
            "bbox": list(self.bbox),
            "confidence": round(self.confidence, 3),
            "action_hint": self.action_hint,
        }


@dataclass
class LayoutRegion:
    label:      str     # "header", "nav", "main", "sidebar", "footer", "dialog", "form"
    bbox:       Tuple[int, int, int, int]
    elements:   List[VisualElement] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "bbox": list(self.bbox),
            "element_count": len(self.elements),
            "elements": [e.to_dict() for e in self.elements[:10]],
        }


@dataclass
class ScreenAnalysis:
    """Complete structured analysis of a screenshot."""
    timestamp:      float = field(default_factory=time.time)
    resolution:     Tuple[int, int] = (0, 0)
    elements:       List[VisualElement] = field(default_factory=list)
    regions:        List[LayoutRegion] = field(default_factory=list)
    text_blocks:    List[str] = field(default_factory=list)
    active_dialog:  bool = False
    backend_used:   str = "heuristic"
    hash:           str = ""

    def action_targets(self, goal: str) -> List[VisualElement]:
        """Return elements most likely relevant to a stated goal."""
        goal_words = set(re.findall(r"\b\w+\b", goal.lower()))
        scored = []
        for el in self.elements:
            el_words = set(re.findall(r"\b\w+\b", el.text.lower()))
            overlap = len(goal_words & el_words)
            if overlap > 0 or el.element_type in (ElementType.BUTTON, ElementType.INPUT):
                scored.append((overlap, el))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [el for _, el in scored[:5]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "resolution": list(self.resolution),
            "element_count": len(self.elements),
            "region_count": len(self.regions),
            "active_dialog": self.active_dialog,
            "backend_used": self.backend_used,
            "hash": self.hash,
            "elements": [e.to_dict() for e in self.elements[:20]],
            "regions": [r.to_dict() for r in self.regions],
            "text_summary": " | ".join(self.text_blocks[:10]),
        }


@dataclass
class TextAnalysis:
    text: str
    token_count: int
    line_count: int
    dominant_intent: str
    entities: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_count": self.token_count,
            "line_count": self.line_count,
            "dominant_intent": self.dominant_intent,
            "entities": self.entities,
            "action_items": self.action_items,
            "topics": self.topics,
        }


@dataclass
class AudioAnalysis:
    duration_seconds: float
    sample_rate: int
    channel_count: int
    sample_count: int
    amplitude_mean: float
    amplitude_peak: float
    transcript_hint: str = ""
    sound_profile: str = "unknown"
    detected_events: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "duration_seconds": round(self.duration_seconds, 3),
            "sample_rate": self.sample_rate,
            "channel_count": self.channel_count,
            "sample_count": self.sample_count,
            "amplitude_mean": round(self.amplitude_mean, 6),
            "amplitude_peak": round(self.amplitude_peak, 6),
            "transcript_hint": self.transcript_hint,
            "sound_profile": self.sound_profile,
            "detected_events": self.detected_events,
        }


@dataclass
class VideoAnalysis:
    byte_length: int
    estimated_duration_seconds: float
    frame_hint_count: int
    scene_count: int
    transcript_hint: str = ""
    extracted_text: List[str] = field(default_factory=list)
    narrative_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "byte_length": self.byte_length,
            "estimated_duration_seconds": round(self.estimated_duration_seconds, 3),
            "frame_hint_count": self.frame_hint_count,
            "scene_count": self.scene_count,
            "transcript_hint": self.transcript_hint,
            "extracted_text": self.extracted_text,
            "narrative_summary": self.narrative_summary,
        }


@dataclass
class MultimodalAssessment:
    modalities_present: List[str] = field(default_factory=list)
    text: Optional[TextAnalysis] = None
    image: Optional[ScreenAnalysis] = None
    audio: Optional[AudioAnalysis] = None
    video: Optional[VideoAnalysis] = None
    summary: str = ""
    action_hints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modalities_present": self.modalities_present,
            "summary": self.summary,
            "action_hints": self.action_hints,
            "text": self.text.to_dict() if self.text else None,
            "image": self.image.to_dict() if self.image else None,
            "audio": self.audio.to_dict() if self.audio else None,
            "video": self.video.to_dict() if self.video else None,
        }


# ── Heuristic analyser (no extra deps) ───────────────────────────────────────

_BUTTON_PATTERNS = re.compile(
    r"\b(ok|cancel|submit|save|login|sign in|sign up|continue|next|back|"
    r"confirm|delete|add|remove|search|apply|close|open|send|download|upload|"
    r"start|stop|run|yes|no|accept|decline|retry|refresh)\b",
    re.IGNORECASE,
)
_HEADING_PATTERNS = re.compile(r"^[A-Z][A-Za-z0-9 ,:'\-]{3,60}$")
_LINK_PATTERNS = re.compile(r"https?://|www\.|click here|read more|learn more", re.IGNORECASE)
_INPUT_PATTERNS = re.compile(r"\b(username|password|email|search|name|address|phone|url|query)\b", re.IGNORECASE)


class HeuristicAnalyser:
    """
    Classifies OCR text blocks into UI elements using regex heuristics.
    No dependencies beyond stdlib.
    """

    def analyse(self, ocr_results: List[Dict], resolution: Tuple[int, int]) -> ScreenAnalysis:
        elements: List[VisualElement] = []
        text_blocks: List[str] = []
        has_dialog = False

        for item in ocr_results:
            text = item.get("text", "").strip()
            if not text:
                continue
            bbox_raw = item.get("bbox", [0, 0, 100, 20])
            bbox = tuple(int(v) for v in bbox_raw[:4])
            conf = float(item.get("confidence", 0.5))
            text_blocks.append(text)

            el_type, action = self._classify(text)
            if text.lower() in ("dialog", "alert", "confirm", "error", "warning"):
                has_dialog = True

            elements.append(VisualElement(
                element_type=el_type,
                text=text,
                bbox=bbox,
                confidence=conf,
                action_hint=action,
            ))

        regions = self._infer_regions(elements, resolution)
        screen_hash = hashlib.md5(" ".join(text_blocks).encode()).hexdigest()[:8]

        return ScreenAnalysis(
            resolution=resolution,
            elements=elements,
            regions=regions,
            text_blocks=text_blocks,
            active_dialog=has_dialog,
            backend_used="heuristic",
            hash=screen_hash,
        )

    def _classify(self, text: str) -> Tuple[ElementType, str]:
        if _BUTTON_PATTERNS.search(text):
            return ElementType.BUTTON, "click"
        if _INPUT_PATTERNS.search(text):
            return ElementType.INPUT, "type"
        if _LINK_PATTERNS.search(text):
            return ElementType.LINK, "click"
        if _HEADING_PATTERNS.match(text) and len(text) < 60:
            return ElementType.HEADING, ""
        if text.endswith(":"):
            return ElementType.LABEL, ""
        return ElementType.TEXT, ""

    def _infer_regions(
        self, elements: List[VisualElement], resolution: Tuple[int, int]
    ) -> List[LayoutRegion]:
        w, h = resolution if resolution != (0, 0) else (1920, 1080)
        header_el = [e for e in elements if e.bbox[1] < h * 0.12]
        footer_el = [e for e in elements if e.bbox[1] > h * 0.88]
        main_el = [e for e in elements if h * 0.12 <= e.bbox[1] <= h * 0.88]

        regions = []
        if header_el:
            regions.append(LayoutRegion("header", (0, 0, w, int(h * 0.12)), header_el))
        if main_el:
            regions.append(LayoutRegion("main", (0, int(h * 0.12), w, int(h * 0.76)), main_el))
        if footer_el:
            regions.append(LayoutRegion("footer", (0, int(h * 0.88), w, int(h * 0.12)), footer_el))
        return regions


# ── Vision API analyser (Claude claude-haiku-4-5 / Sonnet) ────────────────────────────────

class VisionAPIAnalyser:
    """
    Uses the Anthropic Vision API to describe and parse a screenshot.
    Falls back gracefully to HeuristicAnalyser if API is unavailable.
    """

    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        self._model = model
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        if self._available is None:
            try:
                import anthropic  # noqa: F401
                import os
                self._available = bool(os.environ.get("ANTHROPIC_API_KEY"))
            except ImportError:
                self._available = False
        return self._available

    def analyse(self, image_bytes: bytes, resolution: Tuple[int, int]) -> Optional[ScreenAnalysis]:
        if not self.is_available():
            return None
        try:
            import anthropic
            client = anthropic.Anthropic()
            b64 = base64.standard_b64encode(image_bytes).decode()
            msg = client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": b64},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Analyse this screenshot. List all visible UI elements (buttons, "
                                "inputs, headings, links, dialogs) with their text and purpose. "
                                "Identify the main content regions (header, nav, main, dialog). "
                                "Output JSON with keys: elements (list of {type, text, action}), "
                                "regions (list of {label}), has_dialog (bool)."
                            ),
                        },
                    ],
                }],
            )
            raw = msg.content[0].text if msg.content else "{}"
            # Extract JSON from response
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if not m:
                return None
            data = __import__("json").loads(m.group())
            elements = [
                VisualElement(
                    element_type=ElementType(el.get("type", "unknown")
                                            if el.get("type") in ElementType._value2member_map_
                                            else "unknown"),
                    text=el.get("text", ""),
                    bbox=(0, 0, 0, 0),
                    confidence=0.9,
                    action_hint=el.get("action", ""),
                )
                for el in data.get("elements", [])
            ]
            return ScreenAnalysis(
                resolution=resolution,
                elements=elements,
                text_blocks=[e.text for e in elements],
                active_dialog=data.get("has_dialog", False),
                backend_used="claude_vision",
                hash=hashlib.md5(image_bytes[:1024]).hexdigest()[:8],
            )
        except Exception as exc:
            logger.warning("Vision API analysis failed: %s", exc)
            return None


# ── Main MultimodalProcessor ──────────────────────────────────────────────────

class MultimodalProcessor:
    """
    Analyses screenshots and returns structured ScreenAnalysis objects.

    Automatically selects the best available backend.

    Usage::

        proc = MultimodalProcessor()
        screenshot_bytes = computer.get_screenshot()
        analysis = proc.analyse_screenshot(screenshot_bytes)
        targets = analysis.action_targets("click the login button")
    """

    def __init__(self) -> None:
        self._heuristic = HeuristicAnalyser()
        self._vision_api = VisionAPIAnalyser()

    def analyse_screenshot(
        self,
        image_bytes: bytes,
        ocr_results: Optional[List[Dict]] = None,
        resolution: Optional[Tuple[int, int]] = None,
        use_vision_api: bool = True,
    ) -> ScreenAnalysis:
        """
        Analyse a PNG screenshot and return a ScreenAnalysis.

        Args:
            image_bytes:   PNG bytes from ProjectXComputer.get_screenshot().
            ocr_results:   Optional pre-computed OCR from computer.ocr_screen().
            resolution:    Screen resolution. Auto-detected from image if None.
            use_vision_api: Try Claude Vision API first (requires API key).
        """
        res = resolution or self._detect_resolution(image_bytes)

        # Try vision API first
        if use_vision_api and self._vision_api.is_available():
            result = self._vision_api.analyse(image_bytes, res)
            if result:
                return result

        # Fall back to heuristic + OCR
        if ocr_results is None:
            ocr_results = self._run_ocr(image_bytes)
        return self._heuristic.analyse(ocr_results, res)

    def analyse_image(
        self,
        image_bytes: bytes,
        ocr_results: Optional[List[Dict]] = None,
        resolution: Optional[Tuple[int, int]] = None,
        use_vision_api: bool = True,
    ) -> ScreenAnalysis:
        return self.analyse_screenshot(
            image_bytes=image_bytes,
            ocr_results=ocr_results,
            resolution=resolution,
            use_vision_api=use_vision_api,
        )

    def analyse_text(self, text: str) -> List[VisualElement]:
        """
        Classify a list of text strings as UI elements (no image needed).
        Useful when OCR results are already available.
        """
        elements = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                el_type, action = self._heuristic._classify(line)
                elements.append(VisualElement(
                    element_type=el_type, text=line, bbox=(0, 0, 0, 0),
                    confidence=0.7, action_hint=action,
                ))
        return elements

    def analyse_text_document(self, text: str) -> TextAnalysis:
        words = re.findall(r"\b\w+\b", text)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        lowered = text.lower()
        entities = self._extract_entities(text)
        topics = self._extract_topics(lowered)
        action_items = [
            line for line in lines
            if re.match(r"^(\d+\.\s+|[-*]\s+|todo[:\s]|action[:\s])", line.lower())
        ][:10]
        dominant_intent = "analysis"
        if any(term in lowered for term in ("fix", "patch", "refactor", "code", "bug")):
            dominant_intent = "code"
        elif any(term in lowered for term in ("search", "research", "find", "look up")):
            dominant_intent = "research"
        elif any(term in lowered for term in ("deploy", "runbook", "ship", "release")):
            dominant_intent = "operations"
        elif any(term in lowered for term in ("plan", "roadmap", "steps")):
            dominant_intent = "planning"
        return TextAnalysis(
            text=text,
            token_count=len(words),
            line_count=max(1, len(lines)) if text.strip() else 0,
            dominant_intent=dominant_intent,
            entities=entities[:12],
            action_items=action_items,
            topics=topics[:8],
        )

    def analyse_audio(
        self,
        audio_bytes: bytes,
        *,
        sample_rate: int = 16000,
        transcript_hint: str = "",
    ) -> AudioAnalysis:
        parsed_rate, channels, amplitudes = self._extract_audio_amplitudes(audio_bytes, sample_rate)
        sample_count = len(amplitudes)
        duration = sample_count / max(1, parsed_rate * max(1, channels))
        if sample_count:
            mean_amp = sum(abs(v) for v in amplitudes) / sample_count
            peak_amp = max(abs(v) for v in amplitudes)
        else:
            mean_amp = 0.0
            peak_amp = 0.0
        detected_events: List[str] = []
        if peak_amp > 0.85:
            detected_events.append("high_peak")
        if mean_amp < 0.02:
            detected_events.append("silence")
        if transcript_hint:
            detected_events.append("speech_hint")
        sound_profile = "speech" if transcript_hint else "quiet" if mean_amp < 0.02 else "active"
        return AudioAnalysis(
            duration_seconds=duration,
            sample_rate=parsed_rate,
            channel_count=channels,
            sample_count=sample_count,
            amplitude_mean=mean_amp,
            amplitude_peak=peak_amp,
            transcript_hint=transcript_hint[:500],
            sound_profile=sound_profile,
            detected_events=detected_events,
        )

    def analyse_video(
        self,
        video_bytes: bytes,
        *,
        transcript_hint: str = "",
        frame_texts: Optional[List[str]] = None,
    ) -> VideoAnalysis:
        frame_texts = [text.strip() for text in (frame_texts or []) if str(text).strip()]
        byte_length = len(video_bytes)
        estimated_duration = round(byte_length / 500_000.0, 3)
        scene_count = max(1, len(frame_texts) or int(math.ceil(max(byte_length, 1) / 1_500_000.0)))
        extracted_text = frame_texts[:8]
        narrative_summary = " ".join(extracted_text[:3])
        if transcript_hint and not narrative_summary:
            narrative_summary = transcript_hint[:240]
        return VideoAnalysis(
            byte_length=byte_length,
            estimated_duration_seconds=estimated_duration,
            frame_hint_count=len(frame_texts),
            scene_count=scene_count,
            transcript_hint=transcript_hint[:500],
            extracted_text=extracted_text,
            narrative_summary=narrative_summary,
        )

    def analyse_payload(
        self,
        *,
        text: str = "",
        image_bytes: Optional[bytes] = None,
        audio_bytes: Optional[bytes] = None,
        video_bytes: Optional[bytes] = None,
        transcript_hint: str = "",
        frame_texts: Optional[List[str]] = None,
    ) -> MultimodalAssessment:
        assessment = MultimodalAssessment()
        if text.strip():
            assessment.text = self.analyse_text_document(text)
            assessment.modalities_present.append(ModalityType.TEXT.value)
        if image_bytes:
            assessment.image = self.analyse_image(image_bytes, use_vision_api=False)
            assessment.modalities_present.append(ModalityType.IMAGE.value)
        if audio_bytes:
            assessment.audio = self.analyse_audio(audio_bytes, transcript_hint=transcript_hint)
            assessment.modalities_present.append(ModalityType.AUDIO.value)
        if video_bytes:
            assessment.video = self.analyse_video(
                video_bytes,
                transcript_hint=transcript_hint,
                frame_texts=frame_texts,
            )
            assessment.modalities_present.append(ModalityType.VIDEO.value)

        summary_parts: List[str] = []
        action_hints: List[str] = []
        if assessment.text:
            summary_parts.append(
                f"text:{assessment.text.dominant_intent}:{assessment.text.token_count}t"
            )
            action_hints.extend(assessment.text.action_items[:3])
        if assessment.image:
            summary_parts.append(
                f"image:{assessment.image.element_count if hasattr(assessment.image, 'element_count') else len(assessment.image.elements)} elements"
            )
            if assessment.image.elements:
                action_hints.extend(
                    [f"{el.action_hint}:{el.text}" for el in assessment.image.action_targets("next action")[:3] if el.action_hint]
                )
        if assessment.audio:
            summary_parts.append(
                f"audio:{assessment.audio.sound_profile}:{assessment.audio.duration_seconds:.2f}s"
            )
        if assessment.video:
            summary_parts.append(
                f"video:{assessment.video.scene_count} scenes:{assessment.video.estimated_duration_seconds:.2f}s"
            )
        assessment.summary = " | ".join(summary_parts)
        assessment.action_hints = action_hints[:8]
        return assessment

    @staticmethod
    def _extract_entities(text: str) -> List[str]:
        entities: List[str] = []
        seen = set()
        for match in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", text):
            value = match.group(0).strip()
            if value.lower() in {"the", "this", "that"}:
                continue
            if value not in seen:
                seen.add(value)
                entities.append(value)
        return entities

    @staticmethod
    def _extract_topics(lowered: str) -> List[str]:
        keywords = {
            "deployment": ("deploy", "release", "kubernetes", "docker"),
            "coding": ("code", "patch", "bug", "refactor", "python"),
            "research": ("research", "search", "source", "citation"),
            "safety": ("safety", "risk", "validate", "guardrail"),
            "media": ("image", "video", "audio", "screen", "ocr"),
            "planning": ("plan", "roadmap", "steps", "milestone"),
        }
        topics = []
        for topic, terms in keywords.items():
            if any(term in lowered for term in terms):
                topics.append(topic)
        return topics

    @staticmethod
    def _extract_audio_amplitudes(
        audio_bytes: bytes,
        default_rate: int,
    ) -> Tuple[int, int, List[float]]:
        try:
            import wave

            with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
                sample_rate = wav.getframerate() or default_rate
                channels = wav.getnchannels() or 1
                sample_width = wav.getsampwidth()
                frames = wav.readframes(wav.getnframes())
            if sample_width == 2:
                fmt = "<" + "h" * (len(frames) // 2)
                raw = struct.unpack(fmt, frames) if frames else ()
                return sample_rate, channels, [sample / 32768.0 for sample in raw]
            if sample_width == 1:
                return sample_rate, channels, [((byte - 128) / 128.0) for byte in frames]
        except Exception:
            pass
        amplitudes = [((byte - 128) / 128.0) for byte in audio_bytes[:16000]]
        return default_rate, 1, amplitudes

    @staticmethod
    def _detect_resolution(image_bytes: bytes) -> Tuple[int, int]:
        try:
            from PIL import Image
            import io as _io
            img = Image.open(_io.BytesIO(image_bytes))
            return img.size  # (width, height)
        except Exception:
            return (1920, 1080)

    @staticmethod
    def _run_ocr(image_bytes: bytes) -> List[Dict]:
        try:
            from PIL import Image
            import io as _io
            import pytesseract
            img = Image.open(_io.BytesIO(image_bytes))
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            results = []
            for i in range(len(data["text"])):
                t = data["text"][i].strip()
                if t and data["conf"][i] > 0:
                    results.append({
                        "text": t,
                        "bbox": [data["left"][i], data["top"][i],
                                 data["width"][i], data["height"][i]],
                        "confidence": float(data["conf"][i]) / 100.0,
                    })
            return results
        except Exception:
            return []


# Module-level singleton
_processor: Optional[MultimodalProcessor] = None


def get_multimodal_processor() -> MultimodalProcessor:
    global _processor
    if _processor is None:
        _processor = MultimodalProcessor()
    return _processor
