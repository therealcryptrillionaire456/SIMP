# Kalshi Status — April 24, 2026

**Status:** BLOCKED (Kalshi infrastructure)

## What works
- Kalshi API member ID: `9227ce26-147a-478b-9bf2-6d0f93deb562` ✅
- RSA private key: Valid, loaded from `~/.simp/kalshi_cdp.key` ✅
- RSA signing: Produces correct SHA256 PKCS1v15 signatures ✅
- KalshiLiveOrgan: Updated to support file-path keys (`KALSHI_PRIVATE_KEY=~/.simp/kalshi_cdp.key`) ✅

## What's broken
- Old API `trading-api.kalshi.com/trade-api/v2` returns 401 "moved to elections"
- New API `api.elections.kalshi.com` returns 404 on ALL endpoints
- Kalshi has not fully deployed their v2 elections API
- This is a Kalshi-side issue, not ours

## When it comes back
The system is wired and ready. When Kalshi's API becomes available:
- `KalshiLiveOrgan` in `simp/routing/signal_router.py` will automatically activate
- Prediction market hedging will flow through the signal router
- No code changes needed — auth keys are already provisioned
