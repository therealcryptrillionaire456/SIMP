#!/usr/bin/env python3
"""
Bill Russell Protocol - Security Log Classifier (Demo)
"""

import json
import random
from datetime import datetime

class SecurityClassifier:
    def __init__(self, model_path):
        """Load model (simulated for demo)."""
        self.model_path = model_path
        self.loaded_at = datetime.now()
        
    def classify(self, log_text):
        """Classify log text as benign or malicious."""
        # Simulated classification logic
        # In production, this would use actual ML model
        
        suspicious_keywords = [
            'suspicious', 'malicious', 'attack', 'exploit', 'breach',
            'unauthorized', 'intrusion', 'scanning', 'brute force', 'ddos'
        ]
        
        text_lower = log_text.lower()
        
        # Check for suspicious keywords
        score = 0
        for keyword in suspicious_keywords:
            if keyword in text_lower:
                score += 1
        
        # Determine classification
        if score >= 2:
            prediction = "MALICIOUS"
            confidence = min(0.95, 0.7 + (score * 0.1))
        elif score == 1:
            prediction = "SUSPICIOUS"
            confidence = 0.6
        else:
            prediction = "BENIGN"
            confidence = 0.85
        
        return {
            "prediction": prediction,
            "confidence": confidence,
            "score": score,
            "keywords_found": [k for k in suspicious_keywords if k in text_lower],
            "timestamp": datetime.now().isoformat()
        }

def main():
    """Test the classifier."""
    classifier = SecurityClassifier("./model")
    
    test_logs = [
        "Normal HTTP connection completed successfully",
        "Multiple failed login attempts detected from IP 192.168.1.100",
        "Port scanning activity detected from external host",
        "Data exfiltration attempt blocked by firewall",
        "DNS query for known malicious domain"
    ]
    
    print("Security Log Classifier Demo")
    print("=" * 60)
    
    for log_text in test_logs:
        result = classifier.classify(log_text)
        print(f"\nLog: {log_text}")
        print(f"  Prediction: {result['prediction']} ({result['confidence']:.0%})")
        if result['keywords_found']:
            print(f"  Keywords: {', '.join(result['keywords_found'])}")
    
    print("\n" + "=" * 60)
    print("Note: This is a demonstration classifier.")
    print("Production model would use fine-tuned SecBERT.")

if __name__ == "__main__":
    main()
