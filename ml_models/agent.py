import os
import time
import json
import random
import asyncio
import streamlit as st
from typing import Literal, Optional, List, Dict
from google.genai import types
from pydantic import BaseModel, Field
from google.adk.runners import Runner
from google.adk.tools import google_search, agent_tool
from google.adk.agents import Agent, LlmAgent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService
import requests

APP_NAME = "hotels_app"
USER_ID = "user_1"
SESSION_ID = "session_001"
SESSION_SERVICE = InMemorySessionService()


async def create_session():
    await SESSION_SERVICE.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )


# asyncio.run(create_session())

# CORRECTED instructions for a proper JSON list output
HOTEL_SEARCH_AGENT_INSTRUCTIONS = """
You are a hotel search assistant. Your goal is to find hotel names and basic information based on the user's query.

**Your Workflow:**
1. Use Google Search to find hotels based on the user's location query.
2. Extract the hotel name, its general location (e.g., the city), a rating, and an estimated cost.
3. STRICTLY follow this JSON output format. The 'hotels' key should contain a list of objects:
    {
        "text": "Optional introductory text about the search results.",
        "hotels": [
            {
                "hotel_name": "Name of Hotel",
                "location": "City or Area, Country",
                "rating": 4.5,
                "cost": 12000
            }
        ]
    }
4. Limit the JSON output to a maximum of 15 hotels.
  
**Search Guidelines:**
- Use multiple search queries if needed to get comprehensive results.
- Extract hotel names, rating, cost estimates in INR, and the location.
"""

# NEW BOOKING AGENT INSTRUCTIONS
BOOKING_AGENT_INSTRUCTIONS = """
You are a hotel booking assistant. Your role is to help users complete hotel bookings in a conversational manner.

**Your Workflow:**
1. When a user says they want to book a hotel (e.g., "book JW Hotel", "proceed to booking"), acknowledge their request and ask them to select a room type.
2. Present available room types with features (no prices shown).
3. After they select a room type, collect necessary booking details (check-in/check-out dates, number of guests).
4. Confirm the booking details and process the booking.
5. Provide a booking confirmation message.

**Room Types to Offer:**
- Standard Room - Basic amenities, city view
- Deluxe Room - Premium amenities, partial city view
- Executive Suite - Spacious suite, city view, executive lounge access
- Presidential Suite - Luxury suite, panoramic view, butler service

**Booking Flow:**
1. Confirm hotel selection
2. Ask for room type selection
3. Ask for check-in and check-out dates
4. Ask for number of guests
5. Confirm all details
6. Process booking and provide confirmation

**Response Format:**
**Response Format:**
Always respond in a friendly, conversational manner. Use emojis and formatting to make the interaction engaging.
"""

# Backend API Configuration
BACKEND_URL = os.environ.get("FLASK_BACKEND_URL", "http://localhost:5000")

# Try to get the API Key from environment variable first, otherwise use placeholder
api_key = os.environ.get("GOOGLE_API_KEY", "")
if api_key:
    os.environ["GOOGLE_API_KEY"] = api_key
else:
    # If not in env, you must replace this with your actual key
    os.environ["GOOGLE_API_KEY"] = "AIzaSyC8-_qo_VoqYKO32jpLni14-JAve8JOWMc"


class HotelSearchOutput(BaseModel):
    class Hotel(BaseModel):
        hotel_name: str
        location: str
        price: float = 0
        rating: float = Field(default=0, ge=0, le=5)
        link: str = ""

    output: list[Hotel]


HOTEL_SEARCH_AGENT = LlmAgent(
    name="hotel_search_agent",
    model="gemini-2.0-flash",
    description="Hotel Search Agent",
    instruction=HOTEL_SEARCH_AGENT_INSTRUCTIONS,
    generate_content_config=types.GenerateContentConfig(temperature=0),
    tools=[google_search],
)

BOOKING_AGENT = LlmAgent(
    name="booking_agent",
    model="gemini-2.0-flash",
    description="Hotel Booking Agent",
    instruction=BOOKING_AGENT_INSTRUCTIONS,
    generate_content_config=types.GenerateContentConfig(temperature=0.3),
    tools=[],
)

# Store booking state
if "booking_state" not in st.session_state:
    st.session_state.booking_state = {
        "active": False,
        "hotel_name": "",
        "room_type": "",
        "check_in": "",
        "check_out": "",
        "guests": 0,
        "total_price": 0,
        "step": "initial",  # initial, room_selection, date_selection, guest_selection, confirmation
    }

SEARCH_RUNNER = Runner(
    agent=HOTEL_SEARCH_AGENT, app_name=APP_NAME, session_service=SESSION_SERVICE
)
BOOKING_RUNNER = Runner(
    agent=BOOKING_AGENT, app_name=APP_NAME, session_service=SESSION_SERVICE
)


def mock_api_get_hotel_prices(hotel_name: str, location: str) -> Dict[str, Dict]:
    booking_sites = [
        "Booking.com",
        "Agoda",
        "MakeMyTrip",
        "Trivago",
        "Hotels.com",
        "Expedia",
        "Goibibo",
        "Cleartrip",
    ]
    hotel_prices = {}
    for site in booking_sites:
        if random.random() <= 0.8:
            price = random.randint(5000, 20000)
            site_domain = site.lower().replace(" ", "").replace(".", "")
            mock_link = f"https://www.{site_domain}.com/hotel/{hotel_name.lower().replace(' ', '-')}"
            hotel_prices[site] = {
                "price": price,
                "available": True,
                "link": mock_link,
                "currency": "INR",
            }
        else:
            hotel_prices[site] = {
                "price": None,
                "available": False,
                "link": None,
                "currency": "INR",
            }
    return hotel_prices


def get_best_hotel_deals(hotels_list: List[Dict]) -> List[Dict]:
    """
    Get prices for all hotels from multiple sites and return sorted by lowest price.
    """
    enhanced_hotels = []
    for hotel in hotels_list:
        hotel_name = hotel.get("hotel_name", "")
        location = hotel.get("location", "")
        site_prices = mock_api_get_hotel_prices(hotel_name, location)

        available_prices = [
            {"site": site, "price": details["price"], "link": details["link"]}
            for site, details in site_prices.items()
            if details["available"] and details.get("price") is not None
        ]

        # This block contains the fix
        if available_prices:
            best_deal = min(available_prices, key=lambda x: x["price"])

            # Safely get the rating, defaulting to 0 if it's None or missing
            rating_from_agent = hotel.get("rating")
            safe_rating = rating_from_agent if rating_from_agent is not None else 0

            enhanced_hotel = {
                "hotel_name": hotel_name,
                "location": location,
                "price": best_deal["price"],
                "rating": safe_rating,  # Use the safe, non-None value
                "link": best_deal["link"],
                "price_source": best_deal["site"],
                "all_prices": site_prices,
            }
        else:
            # Also ensure rating is safe here for hotels with no available prices
            rating_from_agent = hotel.get("rating")
            safe_rating = rating_from_agent if rating_from_agent is not None else 0
            enhanced_hotel = {
                "hotel_name": hotel_name,
                "location": location,
                "price": 0,
                "rating": safe_rating,
                "link": "",
                "price_source": "Not Available",
                "all_prices": site_prices,
            }
        enhanced_hotels.append(enhanced_hotel)

    enhanced_hotels.sort(key=lambda x: (x["price"] == 0, x["price"]))
    return enhanced_hotels


def detect_booking_intent(prompt: str) -> bool:
    """Detect if user wants to book a hotel"""
    booking_keywords = [
        "book",
        "booking",
        "reserve",
        "reservation",
        "proceed to booking",
        "i want to book",
        "book hotel",
        "make a booking",
        "reserve hotel",
    ]
    return any(keyword in prompt.lower() for keyword in booking_keywords)


def detect_intent(message):
    message = (message or "").lower()

    if "book" in message or "reserve" in message:
        return "book_room"
    elif "price" in message:
        return "price"
    elif "recommend" in message:
        return "recommend"
    elif "cancel" in message:
        return "cancel"
    else:
        return "general"


def extract_hotel_name_from_booking_request(prompt: str) -> str:
    """Extract hotel name from booking request"""
    prompt_lower = prompt.lower()

    # Look for patterns like "book [hotel name]" or "book the [hotel name]"
    if "book" in prompt_lower:
        parts = prompt_lower.split("book")
        if len(parts) > 1:
            hotel_part = parts[1].strip()
            # Remove common words
            hotel_part = hotel_part.replace("the ", "").replace("hotel", "").strip()
            return hotel_part.title()

    return ""


def get_room_types():
    """Get available room types without prices"""
    return [
        {"type": "Standard Room", "description": "Basic amenities, city view"},
        {"type": "Deluxe Room", "description": "Premium amenities, partial city view"},
        {
            "type": "Executive Suite",
            "description": "Spacious suite, city view, executive lounge access",
        },
        {
            "type": "Presidential Suite",
            "description": "Luxury suite, panoramic view, butler service",
        },
    ]


def process_booking_step(prompt: str, current_step: str):
    """Process different steps of booking flow"""
    if current_step == "initial":
        hotel_name = extract_hotel_name_from_booking_request(prompt)
        if hotel_name:
            st.session_state.booking_state["hotel_name"] = hotel_name
            st.session_state.booking_state["step"] = "room_selection"
            st.session_state.booking_state["active"] = True
            return (
                f"Great! I'll help you book {hotel_name}. Please select a room type:",
                "room_selection",
            )
        else:
            st.session_state.booking_state["step"] = "room_selection"
            st.session_state.booking_state["active"] = True
            return (
                "I'll help you with the booking. Please select a room type:",
                "room_selection",
            )

    elif current_step == "room_selection":
        room_types = get_room_types()
        selected_room = None

        for room in room_types:
            if room["type"].lower() in prompt.lower():
                selected_room = room
                break

        if selected_room:
            st.session_state.booking_state["room_type"] = selected_room["type"]
            st.session_state.booking_state["step"] = "date_selection"
            return (
                f"Perfect! You've selected {selected_room['type']}. Now please provide your check-in and check-out dates (e.g., 'Check-in: 2025-08-01, Check-out: 2025-08-03'):",
                "date_selection",
            )
        else:
            return "Please select one of the available room types:", "room_selection"

    elif current_step == "date_selection":
        # Simple date extraction (you can make this more sophisticated)
        st.session_state.booking_state["check_in"] = "2025-08-01"  # Default for demo
        st.session_state.booking_state["check_out"] = "2025-08-03"  # Default for demo
        st.session_state.booking_state["step"] = "guest_selection"
        return (
            "Thanks! Now please tell me how many guests will be staying:",
            "guest_selection",
        )

    elif current_step == "guest_selection":
        # Extract number of guests
        import re

        numbers = re.findall(r"\d+", prompt)
        if numbers:
            guests = int(numbers[0])
            st.session_state.booking_state["guests"] = guests
            st.session_state.booking_state["step"] = "confirmation"

            # Generate a random total price for demo purposes
            base_price = random.randint(8000, 15000)
            nights = 2
            total_price = base_price * nights
            st.session_state.booking_state["total_price"] = total_price

            return (
                f"Perfect! Let me confirm your booking details:\n\n"
                f"🏨 Hotel: {st.session_state.booking_state.get('hotel_name', 'Selected Hotel')}\n"
                f"🛏️ Room: {st.session_state.booking_state['room_type']}\n"
                f"📅 Check-in: {st.session_state.booking_state['check_in']}\n"
                f"📅 Check-out: {st.session_state.booking_state['check_out']}\n"
                f"👥 Guests: {guests}\n"
                f"💰 Total Price: ₹{total_price:,} ({nights} nights)\n\n"
                f"Type 'confirm' to complete the booking or 'cancel' to cancel.",
                "confirmation",
            )
        else:
            return (
                "Please specify the number of guests (e.g., '2 guests'):",
                "guest_selection",
            )

    elif current_step == "confirmation":
        if "confirm" in prompt.lower():
            # Generate booking confirmation
            booking_id = f"HTL{random.randint(100000, 999999)}"
            st.session_state.booking_state["booking_id"] = booking_id
            st.session_state.booking_state["step"] = "completed"

            return (
                f"🎉 **Booking Confirmed!** 🎉\n\n"
                f"Your booking has been successfully processed!\n\n"
                f"**Booking Details:**\n"
                f"📋 Booking ID: {booking_id}\n"
                f"🏨 Hotel: {st.session_state.booking_state.get('hotel_name', 'Selected Hotel')}\n"
                f"🛏️ Room: {st.session_state.booking_state['room_type']}\n"
                f"📅 Check-in: {st.session_state.booking_state['check_in']}\n"
                f"📅 Check-out: {st.session_state.booking_state['check_out']}\n"
                f"👥 Guests: {st.session_state.booking_state['guests']}\n"
                f"💰 Total Paid: ₹{st.session_state.booking_state['total_price']:,}\n\n"
                f"📧 A confirmation email has been sent to your registered email address.\n"
                f"📱 You can use booking ID {booking_id} for any future inquiries.\n\n"
                f"Thank you for choosing our service! Have a wonderful stay! 🌟",
                "completed",
            )
        elif "cancel" in prompt.lower():
            # Reset booking state
            st.session_state.booking_state = {
                "active": False,
                "hotel_name": "",
                "room_type": "",
                "check_in": "",
                "check_out": "",
                "guests": 0,
                "total_price": 0,
                "step": "initial",
            }
            return "Booking cancelled. How else can I help you today?", "initial"
        else:
            return (
                "Please type 'confirm' to complete the booking or 'cancel' to cancel.",
                "confirmation",
            )

    return "I'm not sure how to help with that. Can you please clarify?", current_step


async def call_agent(prompt, agent_type="search"):
    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    final_response_text = "Sorry, I couldn't generate a response."

    runner = SEARCH_RUNNER if agent_type == "search" else BOOKING_RUNNER

    async for event in runner.run_async(
        user_id=USER_ID, session_id=SESSION_ID, new_message=content
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                final_response_text = event.content.parts[0].text
            elif event.actions and event.actions.escalate:
                final_response_text = (
                    f"Agent escalated: {event.error_message or 'No specific message.'}"
                )
            break
    return final_response_text


# --- Streamlit UI ---
st.title("🏨 Smart Hotel Reservation Agent")
st.caption("Search for hotels and complete your booking in one place!")

# Initialize chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("⚙️ Settings")
    show_all_prices = st.checkbox("Show all site prices", value=False)
    max_hotels = st.slider("Maximum hotels to show", min_value=3, max_value=15, value=8)

    # Booking status
    st.header("📋 Booking Status")
    if st.session_state.booking_state["active"]:
        st.info(f"🔄 Booking in Progress")
        st.write(
            f"**Step:** {st.session_state.booking_state['step'].replace('_', ' ').title()}"
        )
        if st.session_state.booking_state["hotel_name"]:
            st.write(f"**Hotel:** {st.session_state.booking_state['hotel_name']}")
        if st.session_state.booking_state["room_type"]:
            st.write(f"**Room:** {st.session_state.booking_state['room_type']}")

        if st.button("Cancel Booking"):
            st.session_state.booking_state = {
                "active": False,
                "hotel_name": "",
                "room_type": "",
                "check_in": "",
                "check_out": "",
                "guests": 0,
                "total_price": 0,
                "step": "initial",
            }
            st.rerun()
    else:
        st.success("✅ Ready for new search or booking")

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["type"] == "text":
            st.write(message["content"])
        elif message["type"] == "booking":
            st.markdown(message["content"])
            # Show room types if in room selection step
            if "room_selection" in message.get("step", ""):
                st.write("### Available Room Types:")
                room_types = get_room_types()
                for room in room_types:
                    st.write(f"**{room['type']}**")
                    st.write(f"🏷️ {room['description']}")
                    st.divider()
        elif message["type"] == "hotels":
            # Re-render the hotel results when coming from history
            text_output = message["content"].get("text")
            hotels_data = message["content"].get("hotels")

            if text_output:
                st.markdown(text_output)

            if hotels_data:
                st.write("## 🎯 Best Hotel Deals (Sorted by Lowest Price)")
                for i, hotel in enumerate(hotels_data, 1):
                    if hotel["price"] > 0:
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            st.markdown(f"### {i}. {hotel['hotel_name']}")
                            st.write(f"📍 **Location:** {hotel['location']}")
                            st.write(
                                f"💰 **Best Price:** ₹{hotel['price']:,} per night"
                            )
                            st.write(f"Source: {hotel['price_source']}")
                            if hotel["rating"] > 0:
                                st.write(f"⭐ **Rating:** {hotel['rating']}/10")
                            st.markdown(f"🔗 [**Book Now**]({hotel['link']})")
                        with col2:
                            st.metric(label="Price/night", value=f"₹{hotel['price']:,}")
                        with col3:
                            if st.button(
                                f"📋 Book {hotel['hotel_name']}", key=f"book_{i}"
                            ):
                                st.session_state.booking_state["hotel_name"] = hotel[
                                    "hotel_name"
                                ]
                                st.session_state.booking_state["active"] = True
                                st.session_state.booking_state["step"] = (
                                    "room_selection"
                                )
                                st.rerun()

                        if show_all_prices:
                            with st.expander("View all price options"):
                                for site, details in hotel["all_prices"].items():
                                    if details["available"]:
                                        price_str = f"**₹{details['price']:,}**"
                                        st.markdown(f"- **{site}:** {price_str}")
                                    else:
                                        st.markdown(f"- **{site}:** Not Available")
                        st.divider()
                    else:
                        st.warning(f"❌ {hotel['hotel_name']} - No prices available")

                available_hotels = [h for h in hotels_data if h["price"] > 0]
                if available_hotels:
                    st.write("## 📊 Summary")
                    summary_cols = st.columns(3)
                    min_price = min(h["price"] for h in available_hotels)
                    max_price = max(h["price"] for h in available_hotels)
                    summary_cols[0].metric("Hotels Found", len(available_hotels))
                    summary_cols[1].metric("Cheapest Option", f"₹{min_price:,}")
                    summary_cols[2].metric("Priciest Option", f"₹{max_price:,}")

            elif not text_output and not hotels_data:
                st.warning("Sorry, I couldn't find any hotels matching your criteria.")

        elif message["type"] == "error":
            st.error(message["content"])

if prompt := st.chat_input("e.g., Find hotels in Mumbai or Book JW Marriott"):
    # Add user message to chat history
    st.session_state.messages.append(
        {"role": "user", "type": "text", "content": prompt}
    )
    # Display user message
    with st.chat_message("user"):
        st.write(prompt)

    # Process and display assistant response
    with st.chat_message("assistant"):
        if prompt.lower() == "hi":
            greeting_message = "Hello! I can help you search for hotels and complete bookings. What would you like to do today?"
            st.write(greeting_message)
            st.session_state.messages.append(
                {"role": "assistant", "type": "text", "content": greeting_message}
            )

        # Check if it's a booking request or if booking is already in progress
        elif detect_booking_intent(prompt) or st.session_state.booking_state["active"]:
            current_step = st.session_state.booking_state["step"]

            if (
                detect_booking_intent(prompt)
                and not st.session_state.booking_state["active"]
            ):
                current_step = "initial"

            response_text, next_step = process_booking_step(prompt, current_step)
            st.session_state.booking_state["step"] = next_step

            if next_step == "completed":
                st.session_state.booking_state["active"] = False

            st.markdown(response_text)

            # Show room types if in room selection step
            if next_step == "room_selection":
                st.write("### Available Room Types:")
                room_types = get_room_types()
                for room in room_types:
                    st.write(f"**{room['type']}**")
                    st.write(f"🏷️ {room['description']}")
                    st.divider()

            if next_step == "completed":
                # Send the booking to the backend API if we have enough info
                try:
                    booking_data = {
                        "hotel_name": st.session_state.booking_state.get("hotel_name"),
                        "room_type": st.session_state.booking_state.get("room_type"),
                        "check_in": st.session_state.booking_state.get("check_in"),
                        "check_out": st.session_state.booking_state.get("check_out"),
                        "guests": st.session_state.booking_state.get("guests"),
                        "total_price": st.session_state.booking_state.get(
                            "total_price"
                        ),
                        "booking_id": st.session_state.booking_state.get("booking_id"),
                    }
                    # Example POST request (would need actual endpoint in app.py to receive this shape)
                    # requests.post(f"{BACKEND_URL}/api/book/agent", json=booking_data)
                    pass
                except Exception as e:
                    print(f"Failed to sync booking to backend: {e}")

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "type": "booking",
                    "content": response_text,
                    "step": next_step,
                }
            )

        else:
            # Regular hotel search
            with st.spinner("Searching for hotels..."):
                response_text = asyncio.run(call_agent(prompt, "search"))

            try:
                cleaned_response = (
                    response_text.replace("```json", "").replace("```", "").strip()
                )
                response_json = json.loads(cleaned_response)

                text_output = response_json.get("text")
                hotels = response_json.get("hotels")

                # Store the entire processed hotel data for re-rendering
                processed_hotel_data = {
                    "text": text_output,
                    "hotels": [],  # This will be filled with enhanced hotels if found
                }

                if text_output:
                    st.markdown(text_output)

                if hotels:
                    with st.spinner(
                        "Comparing prices across multiple booking sites..."
                    ):
                        enhanced_hotels = get_best_hotel_deals(hotels)
                        enhanced_hotels = enhanced_hotels[:max_hotels]
                        processed_hotel_data["hotels"] = (
                            enhanced_hotels  # Store enhanced hotels
                        )

                    st.write("## 🎯 Best Hotel Deals (Sorted by Lowest Price)")

                    for i, hotel in enumerate(enhanced_hotels, 1):
                        if hotel["price"] > 0:
                            col1, col2, col3 = st.columns([3, 1, 1])
                            with col1:
                                st.markdown(f"### {i}. {hotel['hotel_name']}")
                                st.write(f"📍 **Location:** {hotel['location']}")
                                st.write(
                                    f"💰 **Best Price:** ₹{hotel['price']:,} per night"
                                )
                                st.write(f"Source: {hotel['price_source']}")
                                if hotel["rating"] > 0:
                                    st.write(f"⭐ **Rating:** {hotel['rating']}/10")
                                st.markdown(f"🔗 [**Book Now**]({hotel['link']})")
                            with col2:
                                st.metric(
                                    label="Price/night", value=f"₹{hotel['price']:,}"
                                )
                            with col3:
                                if st.button(
                                    f"📋 Book {hotel['hotel_name']}", key=f"book_{i}"
                                ):
                                    st.session_state.booking_state["hotel_name"] = (
                                        hotel["hotel_name"]
                                    )
                                    st.session_state.booking_state["active"] = True
                                    st.session_state.booking_state["step"] = (
                                        "room_selection"
                                    )
                                    st.rerun()

                            if show_all_prices:
                                with st.expander("View all price options"):
                                    for site, details in hotel["all_prices"].items():
                                        if details["available"]:
                                            price_str = f"**₹{details['price']:,}**"
                                            st.markdown(f"- **{site}:** {price_str}")
                                        else:
                                            st.markdown(f"- **{site}:** Not Available")
                            st.divider()
                        else:
                            st.warning(
                                f"❌ {hotel['hotel_name']} - No prices available"
                            )

                    available_hotels = [h for h in enhanced_hotels if h["price"] > 0]
                    if available_hotels:
                        st.write("## 📊 Summary")
                        summary_cols = st.columns(3)
                        min_price = min(h["price"] for h in available_hotels)
                        max_price = max(h["price"] for h in available_hotels)
                        summary_cols[0].metric("Hotels Found", len(available_hotels))
                        summary_cols[1].metric("Cheapest Option", f"₹{min_price:,}")
                        summary_cols[2].metric("Priciest Option", f"₹{max_price:,}")

                elif (
                    not text_output
                ):  # This handles cases where only "text" is missing but "hotels" might be empty list
                    st.warning(
                        "Sorry, I couldn't find any hotels matching your criteria."
                    )

                # Add the processed hotel data to history
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "type": "hotels",
                        "content": processed_hotel_data,
                    }
                )

            except json.JSONDecodeError:
                st.markdown(response_text)
                st.session_state.messages.append(
                    {"role": "assistant", "type": "text", "content": response_text}
                )
            except Exception as e:
                error_message = f"An unexpected error occurred: {e}"
                st.error(error_message)
                st.write("Raw agent response:")
                st.code(response_text)
                st.session_state.messages.append(
                    {"role": "assistant", "type": "error", "content": error_message}
                )
