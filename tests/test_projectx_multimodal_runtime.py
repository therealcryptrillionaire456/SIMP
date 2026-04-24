from __future__ import annotations

import io
import wave

from simp.projectx.multimodal import ModalityType, MultimodalProcessor


def _make_wav_bytes(samples: list[int], sample_rate: int = 8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"".join(int(sample).to_bytes(2, "little", signed=True) for sample in samples))
    return buf.getvalue()


def test_multimodal_payload_supports_four_modalities() -> None:
    processor = MultimodalProcessor()
    audio_bytes = _make_wav_bytes([0, 1000, -1000, 2000, -2000] * 200)
    assessment = processor.analyse_payload(
        text="1. Deploy ProjectX with Docker and Kubernetes.\nAction: validate production readiness.",
        image_bytes=b"\x89PNG\r\n\x1a\n",
        audio_bytes=audio_bytes,
        video_bytes=b"\x00\x00\x00\x18ftypmp42video-bytes",
        transcript_hint="Operator says deploy the runtime safely.",
        frame_texts=["ProjectX dashboard", "Readiness report", "Deployment complete"],
    )

    assert set(assessment.modalities_present) == {
        ModalityType.TEXT.value,
        ModalityType.IMAGE.value,
        ModalityType.AUDIO.value,
        ModalityType.VIDEO.value,
    }
    assert assessment.text is not None
    assert assessment.audio is not None
    assert assessment.video is not None
    assert "video:" in assessment.summary
    assert assessment.text.dominant_intent in {"operations", "planning"}


def test_audio_analysis_extracts_basic_signal_metrics() -> None:
    processor = MultimodalProcessor()
    audio = processor.analyse_audio(
        _make_wav_bytes([0, 4000, -4000, 2000, -2000] * 100),
        transcript_hint="status update",
    )

    assert audio.sample_rate == 8000
    assert audio.channel_count == 1
    assert audio.sample_count > 0
    assert audio.amplitude_peak > 0
    assert "speech_hint" in audio.detected_events
