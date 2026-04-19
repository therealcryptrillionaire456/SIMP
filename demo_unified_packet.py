#!/usr/bin/env python3
"""
Demo: The Unified MeshPacket that carries all four elements simultaneously.
This is the "cherry on top" - where sending a message and making a bet are the same operation.
"""

import json
import hashlib
import hmac
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
import uuid

@dataclass
class UnifiedMeshPacket:
    """A packet that carries intent, commitment, proof, and reputation update."""
    
    # Layer 1: Basic transport
    message_id: str
    sender: str
    recipient: str
    timestamp: str
    
    # Layer 2: Mesh routing
    message_type: str  # "INTENT", "PAYMENT", "SETTLEMENT", etc.
    priority: str
    ttl_seconds: int
    hops: list
    
    # Layer 3: Intent payload
    intent_payload: Dict[str, Any]  # The actual intent (risk_assessment, trade_signal, etc.)
    
    # Layer 4: Payment commitment (HTLC reference)
    payment_channel_id: Optional[str] = None
    htlc_hashlock: Optional[str] = None  # Hash of the preimage
    htlc_amount: Optional[float] = None
    htlc_timeout: Optional[int] = None
    
    # Layer 5: Delivery proof
    receipt_signature: Optional[str] = None  # HMAC signature
    receipt_timestamp: Optional[str] = None
    
    # Layer 6: Reputation metadata
    reputation_stake: Optional[float] = None  # Amount staked on this intent
    reputation_outcome: Optional[str] = None  # "SUCCESS", "FAILURE", "PENDING"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedMeshPacket':
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'UnifiedMeshPacket':
        return cls.from_dict(json.loads(json_str))
    
    def calculate_receipt(self, shared_secret: bytes) -> str:
        """Calculate HMAC receipt for this packet."""
        receipt_data = f"{self.message_id}:{self.sender}:{self.recipient}:{self.timestamp}"
        if self.payment_channel_id:
            receipt_data += f":{self.payment_channel_id}:{self.htlc_amount or 0}"
        
        h = hmac.new(shared_secret, receipt_data.encode(), hashlib.sha256)
        return h.hexdigest()
    
    def sign_with_receipt(self, shared_secret: bytes) -> 'UnifiedMeshPacket':
        """Sign this packet with a delivery receipt."""
        self.receipt_signature = self.calculate_receipt(shared_secret)
        self.receipt_timestamp = datetime.now(timezone.utc).isoformat()
        return self
    
    def verify_receipt(self, shared_secret: bytes) -> bool:
        """Verify the receipt signature."""
        if not self.receipt_signature:
            return False
        
        expected = self.calculate_receipt(shared_secret)
        return hmac.compare_digest(self.receipt_signature, expected)
    
    def create_payment_commitment(self, preimage: str, amount: float, timeout_seconds: int = 3600) -> 'UnifiedMeshPacket':
        """Add payment commitment to this packet."""
        self.payment_channel_id = f"channel_{self.sender}_{self.recipient}_{uuid.uuid4().hex[:8]}"
        self.htlc_hashlock = hashlib.sha256(preimage.encode()).hexdigest()
        self.htlc_amount = amount
        self.htlc_timeout = timeout_seconds
        self.reputation_stake = amount  # Stake equals payment amount
        return self
    
    def mark_outcome(self, outcome: str, actual_preimage: Optional[str] = None) -> 'UnifiedMeshPacket':
        """Mark the outcome of this intent (for reputation updates)."""
        self.reputation_outcome = outcome
        
        # If we have the preimage and it matches, we can settle
        if actual_preimage and self.htlc_hashlock:
            calculated_hash = hashlib.sha256(actual_preimage.encode()).hexdigest()
            if hmac.compare_digest(calculated_hash, self.htlc_hashlock):
                print(f"✓ Payment can be settled! Preimage matches hashlock")
        
        return self

def demo_quantumarb_kashclaw_interaction():
    """Demo the complete flow you described."""
    print("=" * 70)
    print("DEMO: Autonomous Mesh Intelligence")
    print("QuantumArb ↔ KashClaw - No Internet, No Broker, No HTTP")
    print("=" * 70)
    
    # Shared secret for HMAC receipts (in real system, from key exchange)
    shared_secret = b"test_shared_secret_123"
    
    print("\n1. QuantumArb boots with no internet")
    print("   • Advertises capabilities over BLE/UDP")
    print("   • 'risk_assessment', 'arb_signals', 'channel_capacity: 500.0'")
    
    print("\n2. KashClaw hears advertisement")
    print("   • Opens payment channel with QuantumArb")
    print("   • Wants risk assessment for ETH position")
    
    print("\n3. QuantumArb creates unified intent packet")
    
    # QuantumArb creates a prediction with confidence
    intent_payload = {
        "intent_type": "risk_assessment",
        "asset": "ETH",
        "position": "BUY",
        "amount": 0.5,
        "confidence": 0.87,
        "horizon_hours": 24,
        "reasoning": "MACD bullish crossover, RSI oversold bounce"
    }
    
    # Create the unified packet
    packet = UnifiedMeshPacket(
        message_id=f"intent_{uuid.uuid4().hex[:8]}",
        sender="quantumarb",
        recipient="kashclaw",
        timestamp=datetime.now(timezone.utc).isoformat(),
        message_type="INTENT",
        priority="HIGH",
        ttl_seconds=300,
        hops=[],
        intent_payload=intent_payload
    )
    
    # Add payment commitment (staking 50 credits)
    preimage = f"preimage_{uuid.uuid4().hex}"  # Secret that will reveal outcome
    packet.create_payment_commitment(preimage, amount=50.0)
    
    # Sign with delivery receipt
    packet.sign_with_receipt(shared_secret)
    
    print("\n4. Packet carries all four elements simultaneously:")
    print(f"   a) INTENT: {packet.intent_payload['intent_type']} for {packet.intent_payload['asset']}")
    print(f"   b) COMMITMENT: {packet.htlc_amount} credits in channel {packet.payment_channel_id}")
    print(f"   c) PROOF: Receipt signed with HMAC-SHA256")
    print(f"   d) REPUTATION: {packet.reputation_stake} credits staked")
    
    print("\n5. Packet travels over mesh (BLE/UDP)")
    print("   • No HTTP, no broker, no internet")
    print("   • Direct device-to-device")
    
    print("\n6. KashClaw receives packet")
    print("   • Verifies receipt: ", "✓ VALID" if packet.verify_receipt(shared_secret) else "✗ INVALID")
    print("   • Sees 87% confidence BUY ETH signal")
    print("   • Sees 50 credits staked")
    
    print("\n7. KashClaw decides to match")
    print("   • Counters with own assessment")
    print("   • Opens return channel with 50 credits")
    print("   • Partial agreement reached via channel updates")
    
    print("\n8. Time passes... Signal turns out to be RIGHT")
    print("   • ETH price increases 5% in 24 hours")
    
    print("\n9. Channel settles automatically")
    packet.mark_outcome("SUCCESS", actual_preimage=preimage)
    print(f"   • Outcome: {packet.reputation_outcome}")
    print("   • QuantumArb gains 50 credits")
    print("   • KashClaw loses 50 credits (but made more on the trade)")
    
    print("\n10. Reputation system updates")
    print("    • QuantumArb's reputation score ↑")
    print("    • Gossip router starts preferring routes through QuantumArb")
    print("    • Other agents learn: good predictions → profitable channels")
    
    print("\n" + "=" * 70)
    print("FEEDBACK LOOP ESTABLISHED:")
    print("accurate signal → channel gains value → reputation rises →")
    print("more routing weight → more signals → more opportunity →")
    print("back to: accurate signal")
    print("=" * 70)
    
    print("\nThe inverse for bad actors:")
    print("bad signal → channel drained → reputation falls →")
    print("less routing weight → isolation")
    
    print("\n" + "=" * 70)
    print("THE CHERRY ON TOP:")
    print("Sending a message and making a bet are the same operation.")
    print("The network learns which agents are worth listening to")
    print("purely from who ends up solvent.")
    print("=" * 70)
    
    # Show the actual packet structure
    print("\nActual UnifiedMeshPacket structure:")
    print(packet.to_json())

def demo_timesfm_integration():
    """Show how TimesFM integrates with this system."""
    print("\n" + "=" * 70)
    print("TIMESFM INTEGRATION: From Model Output to Economic Consequence")
    print("=" * 70)
    
    print("\nWithout mesh payment layer:")
    print("• TimesFM produces prediction: 'ETH +3.2% in 24h (confidence: 0.79)'")
    print("• It's just a number. No skin in the game.")
    
    print("\nWith unified mesh packet:")
    print("• TimesFM produces same prediction")
    print("• But now it's embedded in a UnifiedMeshPacket")
    print("• With 50 credits staked via payment channel")
    print("• With HMAC receipt proving delivery")
    print("• With reputation stake on the line")
    
    print("\nResult:")
    print("• TimesFM is no longer just producing numbers")
    print("• It's making commitments with financial consequences")
    print("• The mesh network polices accuracy automatically")
    print("• Good predictions get amplified, bad ones get isolated")
    
    print("\nThis is why it's novel:")
    print("• Most ML systems: produce predictions → human decides")
    print("• SIMP mesh: produce predictions → economic system enforces")

if __name__ == "__main__":
    demo_quantumarb_kashclaw_interaction()
    demo_timesfm_integration()
    
    print("\n" + "=" * 70)
    print("IMPLEMENTATION STATUS:")
    print("=" * 70)
    print("\nAlready built in SIMP:")
    print("✓ Layer 1: UDP multicast, BLE, Nostr transports")
    print("✓ Layer 2: EnhancedMeshBus with payment channels, receipts")
    print("✓ Layer 3: Intent schemas (CoordinationIntent, PeerIntentRequest)")
    print("✓ Layer 4: DeliveryReceiptManager, PaymentSettler databases")
    print("✓ Layer 5: A2A aggregator for consensus")
    print("✓ Layer 6: Payment channels with HTLC support")
    
    print("\nMissing piece:")
    print("• Wiring them together into UnifiedMeshPacket")
    print("• IntentMeshRouter that uses all six layers simultaneously")
    
    print("\nThe code for UnifiedMeshPacket (above) is 120 lines.")
    print("The IntentMeshRouter would be ~300 lines.")
    print("\nWe're literally 400 lines of code away from the cherry.")