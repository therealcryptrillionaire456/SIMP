"""
CLI for content engagement prediction.

Usage:
    python -m simp.organs.media.predictors.cli predict --brief '{"title": "My video", "platform": "tiktok", "format": "short_video", "topic": "ai_tools"}'
    python -m simp.organs.media.predictors.cli predict --brief-file briefs.json
    python -m simp.organs.media.predictors.cli stats
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List

from simp.organs.media.predictors.engagement_predictor import (
    ContentEngagementPredictor,
    EngagementScore,
)


def _load_briefs(path: str) -> List[Dict[str, Any]]:
    """Load briefs from a JSON file. Expects a single object or array."""
    raw = Path(path).read_text()
    data = json.loads(raw)
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unexpected JSON structure in {path}")


def cmd_predict(args: argparse.Namespace) -> None:
    """Run prediction on one or more content briefs."""
    predictor = ContentEngagementPredictor(data_dir=args.data_dir)

    briefs: List[Dict[str, Any]] = []

    if args.brief:
        briefs.append(json.loads(args.brief))
    if args.brief_file:
        briefs.extend(_load_briefs(args.brief_file))

    if not briefs:
        print("ERROR: Provide --brief or --brief-file with content brief data.", file=sys.stderr)
        sys.exit(1)

    scores = predictor.predict_batch(briefs)

    if args.json:
        output = [s.to_dict() for s in scores]
        print(json.dumps(output, indent=2))
    else:
        for i, (brief, score) in enumerate(zip(briefs, scores)):
            title = brief.get("title", brief.get("brief", f"Item {i+1}"))
            print(f"{'='*60}")
            print(f"Content: {title}")
            print(f"  Score:       {score.score:.1f}/100")
            print(f"  Confidence:  {score.confidence:.2f}")
            print(f"  Views:       {score.predicted_views:.0f}")
            print(f"  Clicks:      {score.predicted_clicks:.0f}")
            print(f"  Conversions: {score.predicted_conversions:.2f}")
            print(f"  Revenue:     ${score.estimated_revenue:.2f}")
            print(f"  Top Factors: {', '.join(score.top_factors)}")
        print(f"{'='*60}")
        print(f"Total: {len(scores)} brief(s) scored.")


def cmd_stats(args: argparse.Namespace) -> None:
    """Show prediction statistics."""
    predictor = ContentEngagementPredictor(data_dir=args.data_dir)
    stats = predictor.get_stats()
    print(json.dumps(stats, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Content Engagement Predictor CLI"
    )
    parser.add_argument(
        "--data-dir",
        default="data/media/predictions",
        help="Directory for prediction data (default: data/media/predictions)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # predict subcommand
    predict_parser = subparsers.add_parser("predict", help="Score content briefs")
    predict_parser.add_argument(
        "--brief", type=str, default=None,
        help="JSON string of a content brief",
    )
    predict_parser.add_argument(
        "--brief-file", type=str, default=None,
        help="Path to a JSON file containing one or more briefs",
    )
    predict_parser.set_defaults(func=cmd_predict)

    # stats subcommand
    stats_parser = subparsers.add_parser("stats", help="Show prediction statistics")
    stats_parser.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
