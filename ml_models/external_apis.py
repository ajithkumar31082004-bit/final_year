"""
External Service APIs - Simulation Layer
=========================================
This module demonstrates how to connect Enterprise SaaS APIs into our AI Platform.
It wraps mock API logic simulating exactly how the integrations with Stripe Radar,
AWS Forecast, Google Travel, and AWS Personalize would work.
"""
import random

class StripeRadarAPI:
    """Mock for Stripe Radar Fraud Network API"""
    @classmethod
    def analyze_transaction(cls, booking_data: dict) -> dict:
        """
        Simulates calling an external payment network for cross-platform fraud history.
        """
        # In a real environment, this makes an HTTP POST to Stripe Radar.
        # We simulate the API scoring:
        
        # High value transaction often flagged by network
        amount = booking_data.get("total_amount", 0)
        email = booking_data.get("email", "")
        
        provider_score = random.uniform(0.01, 0.20)
        risk_level = "normal"
        flags = []

        if amount > 150000:  
            provider_score += 0.40
            flags.append("stripe_radar_high_velocity")
        
        if email and "test" in email.lower():
            provider_score += 0.30
            flags.append("sift_network_suspicious_email")

        if provider_score > 0.6:
            risk_level = "elevated"

        return {
            "api_provider": "Stripe/Sift",
            "external_risk_score": provider_score,
            "network_flags": flags,
            "risk_assessment": risk_level
        }


class AWSForecastAPI:
    """Mock for AWS Forecast API for Demand Prediction"""
    @classmethod
    def get_demand_forecast(cls, start_date: str, days: int) -> dict:
        """
        Simulates AWS Forecast returning time-series demand predictions. 
        """
        return {
            "api_provider": "AWS Forecast",
            "demand_multiplier": round(random.uniform(0.9, 1.4), 2),
            "confidence_interval": "P90"
        }


class GoogleTravelAPI:
    """Mock for Google Travel / Custom Market Pricing API"""
    @classmethod
    def get_competitor_pricing(cls, location: str, room_tier: str) -> dict:
        """
        Simulates fetching real-time market pricing from competitors via Google.
        """
        suggested_floor = 4000
        suggested_ceiling = 12000

        if room_tier == "vip":
            suggested_floor = 10000
            suggested_ceiling = 25000

        return {
            "api_provider": "Google Travel API",
            "market_demand": "high",
            "competitor_avg_price": random.randint(suggested_floor, suggested_ceiling),
        }


class AWSPersonalizeAPI:
    """Mock for AWS Personalize Recommendation Engine"""
    @classmethod
    def get_user_recommendations(cls, user_id: str) -> dict:
        """
        Simulates fetching personalized recommendations from AWS.
        """
        return {
            "api_provider": "AWS Personalize",
            "recommended_tier": random.choice(["vip", "deluxe", "standard", "couple"]),
            "personalization_score": round(random.uniform(0.70, 0.99), 2)
        }


class AWSComprehendAPI:
    """Mock for AWS Comprehend NLP Sentiment Analysis API"""
    @classmethod
    def analyze_sentiment(cls, text: str) -> dict:
        """
        Simulates AWS Comprehend's neural sentiment classification.
        Returns sentiment label and confidence scores (Positive/Negative/Neutral/Mixed).
        """
        # In a real environment, this calls boto3 -> comprehend.detect_sentiment()
        # We simulate a neural confidence distribution:
        text_lower = text.lower()
        
        # Simple heuristic to make a believable mock response
        pos_words = sum(1 for w in ["great", "excellent", "amazing", "good", "love", "fantastic", "perfect", "clean", "beautiful"] if w in text_lower)
        neg_words = sum(1 for w in ["terrible", "horrible", "bad", "dirty", "rude", "awful", "worst", "broken"] if w in text_lower)
        
        if pos_words > neg_words:
            sentiment = "POSITIVE"
            pos_conf = round(random.uniform(0.75, 0.98), 4)
            neg_conf = round((1 - pos_conf) * 0.3, 4)
        elif neg_words > pos_words:
            sentiment = "NEGATIVE"
            neg_conf = round(random.uniform(0.75, 0.98), 4)
            pos_conf = round((1 - neg_conf) * 0.3, 4)
        else:
            sentiment = "NEUTRAL"
            pos_conf = round(random.uniform(0.3, 0.55), 4)
            neg_conf = round(random.uniform(0.25, 0.45), 4)
        
        return {
            "api_provider": "AWS Comprehend",
            "sentiment": sentiment,
            "sentiment_scores": {
                "Positive": pos_conf,
                "Negative": neg_conf,
                "Neutral": round(random.uniform(0.05, 0.20), 4),
                "Mixed": round(random.uniform(0.02, 0.10), 4)
            }
        }
