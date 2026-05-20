# pylint: disable = invalid-name
import os
import uuid
import logging
import re
import streamlit as st
from datetime import date, timedelta
from langchain_core.messages import HumanMessage, AIMessage
from agents.agent import Agent
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sample list of major airports in Australia and New Zealand
AIRPORTS = [
    {"city": "Sydney", "iata": "SYD", "name": "Sydney Kingsford Smith"},
    {"city": "Melbourne", "iata": "MEL", "name": "Melbourne Tullamarine"},
    {"city": "Brisbane", "iata": "BNE", "name": "Brisbane"},
    {"city": "Perth", "iata": "PER", "name": "Perth"},
    {"city": "Adelaide", "iata": "ADL", "name": "Adelaide"},
    {"city": "Gold Coast", "iata": "OOL", "name": "Gold Coast"},
    {"city": "Cairns", "iata": "CNS", "name": "Cairns"},
    {"city": "Canberra", "iata": "CBR", "name": "Canberra"},
    {"city": "Hobart", "iata": "HBA", "name": "Hobart"},
    {"city": "Darwin", "iata": "DRW", "name": "Darwin"},
    {"city": "Auckland", "iata": "AKL", "name": "Auckland"},
    {"city": "Wellington", "iata": "WLG", "name": "Wellington"},
    {"city": "Christchurch", "iata": "CHC", "name": "Christchurch"},
    {"city": "Queenstown", "iata": "ZQN", "name": "Queenstown"},
    {"city": "Dunedin", "iata": "DUD", "name": "Dunedin"},
]

airport_options = [f"{a['city']} ({a['iata']}) - {a['name']}" for a in AIRPORTS]
iata_lookup = {f"{a['city']} ({a['iata']}) - {a['name']}": a['iata'] for a in AIRPORTS}

def initialize_agent():
    if 'agent' not in st.session_state:
        st.session_state.agent = Agent()
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'thread_id' not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())

def validate_budget(budget_str):
    """Validate and clean budget input. Returns (is_valid, cleaned_value, error_message)"""
    if not budget_str or budget_str.strip() == '':
        return True, None, None  # Budget is optional

    # Remove common currency symbols and whitespace
    cleaned = budget_str.strip().replace('$', '').replace(',', '').replace('AUD', '').replace('aud', '').strip()

    try:
        budget_value = float(cleaned)
        if budget_value <= 0:
            return False, None, "Budget must be a positive number"
        if budget_value > 1000000:
            return False, None, "Budget seems unrealistically high. Please enter a reasonable amount."
        return True, int(budget_value), None
    except ValueError:
        return False, None, "Please enter a valid number for budget (e.g., 3000 or 3,000)"

def extract_location_from_preferences(preferences, destination_city):
    """Extract specific location preferences for hotels"""
    if not preferences:
        return destination_city
    
    # Look for location keywords in preferences
    location_keywords = [
        'cbd', 'city center', 'downtown', 'beach', 'beachfront', 'airport', 
        'near airport', 'city centre', 'central', 'marina', 'waterfront',
        'old town', 'historic district', 'business district'
    ]
    
    preferences_lower = preferences.lower()
    for keyword in location_keywords:
        if keyword in preferences_lower:
            logger.info(f"🎯 Found location preference: {keyword}")
            return f"{destination_city} {keyword}"
    
    return destination_city

def render_custom_css():
    st.markdown(
        '''
        <style>
        .main-title {
            font-size: 2.8em;
            color: #2E86AB;
            text-align: center;
            margin-bottom: 0.8em;
            font-weight: bold;
            background: linear-gradient(135deg, #2E86AB, #A23B72);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .section-header {
            font-size: 1.5em;
            color: #2E86AB;
            font-weight: 600;
            margin-bottom: 1em;
            border-bottom: 2px solid #E8F4F8;
            padding-bottom: 0.5em;
        }
        .form-container {
            background: linear-gradient(135deg, #F8FDFF, #E8F4F8);
            border-radius: 15px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 20px rgba(46, 134, 171, 0.1);
            border: 1px solid #E8F4F8;
        }
        .chat-container {
            background: linear-gradient(135deg, #FFF9F0, #F0F8FF);
            border-radius: 15px;
            padding: 1.5rem;
            box-shadow: 0 4px 20px rgba(46, 134, 171, 0.1);
            border: 1px solid #E8F4F8;
        }
        .stTextInput>div>input, .stNumberInput>div>input, .stTextArea textarea {
            background-color: #ffffff;
            border-radius: 10px;
            border: 2px solid #E8F4F8;
            padding: 0.75rem;
            font-size: 1rem;
            transition: border-color 0.3s ease;
        }
        .stTextInput>div>input:focus, .stTextArea textarea:focus {
            border-color: #2E86AB;
            box-shadow: 0 0 0 2px rgba(46, 134, 171, 0.1);
        }
        .stSelectbox>div>div {
            background-color: #ffffff;
            border-radius: 10px;
            border: 2px solid #E8F4F8;
        }
        .stButton > button {
            background: linear-gradient(135deg, #2E86AB, #A23B72);
            color: white;
            border-radius: 10px;
            border: none;
            padding: 0.75rem 1.5rem;
            font-weight: 600;
            font-size: 1rem;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(46, 134, 171, 0.3);
        }
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(46, 134, 171, 0.4);
        }
        .success-message {
            background: linear-gradient(135deg, #D4EDDA, #C3E6CB);
            border-radius: 10px;
            padding: 1rem;
            margin: 1rem 0;
            border-left: 4px solid #28A745;
        }
        .chat-message {
            margin: 1rem 0;
            padding: 1rem;
            border-radius: 10px;
        }
        .user-message {
            background: linear-gradient(135deg, #E3F2FD, #BBDEFB);
            border-left: 4px solid #2196F3;
        }
        .assistant-message {
            background: linear-gradient(135deg, #F3E5F5, #E1BEE7);
            border-left: 4px solid #9C27B0;
        }
        /* Make dataframes more readable */
        .stDataFrame {
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        /* Improve radio button styling */
        .stRadio > div {
            display: flex;
            gap: 2rem;
        }
        /* Better spacing for the entire app */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        </style>
        ''', unsafe_allow_html=True)

def process_initial_query(departure, destination, check_in_date, check_out_date, preferences, energy_level, budget, trip_type):
    """Process the initial travel planning query"""
    if departure and destination and check_in_date and (check_out_date or trip_type == 'One Way'):
        # Validate budget first
        is_valid, cleaned_budget, error_msg = validate_budget(budget)
        if not is_valid:
            st.error(f'Invalid budget: {error_msg}')
            return False

        try:
            if trip_type == 'Return':
                num_days = (check_out_date - check_in_date).days
                date_str = f"from {check_in_date} to {check_out_date} ({num_days} days)"
            else:
                date_str = f"departing on {check_in_date} (one way)"

            budget_str = f" The total budget for the trip is {cleaned_budget} AUD. Please filter flights and hotels to fit within this budget if possible. If the API or tool requires USD, convert the budget from AUD to USD using the current exchange rate." if cleaned_budget else ""
            
            # Extract destination city for hotel location targeting
            destination_city = next(a['city'] for a in AIRPORTS if a['iata'] == destination)
            hotel_location = extract_location_from_preferences(preferences, destination_city)
            logger.info(f"🏨 Hotel search location: {hotel_location}")
            
            # Create enhanced hotel preferences
            hotel_preferences = ""
            if preferences:
                hotel_preferences = f" When searching for hotels, use location '{hotel_location}' and consider these preferences: {preferences}."

            user_prompt = f"""
            Plan a {trip_type.lower()} trip from {departure} to {destination} {date_str}. Preferences: {preferences}. Energy level: {energy_level}.{budget_str}
            1. Suggest a daily travel planner (with activities, rest, and meals).
            2. Recommend local attractions (museums, parks, landmarks) and restaurants.
            3. Use the weather_check tool to provide a multi-day weather forecast and alerts for {destination}. If the forecast is not available, provide a general weather summary based on historical data.
            4. Suggest packing tips based on the weather.
            5. Generate a travel checklist for this trip.
            6. Find best flights (from {departure} to {destination}) and hotels for the trip, using these dates{', and filter by budget' if budget else ''}.{hotel_preferences}
            For each flight option, display all available details: flight number, airline, duration, departure time, arrival time, and price. Do not just show the price.
            If flight or hotel information cannot be retrieved, continue to generate the rest of the plan (planner, attractions, restaurants, weather, packing tips, checklist).
            """

            return send_message(user_prompt)

        except Exception as e:
            st.error(f'Error generating travel plan: {str(e)}')
            logger.error(f"Error in process_initial_query: {str(e)}")
            return False
    else:
        st.error('Please enter a departure, destination, and valid dates.')
        return False

def send_message(message_content):
    """Send a message and get response from agent"""
    try:
        # Add user message to session
        st.session_state.messages.append({"role": "user", "content": message_content})
        
        # Prepare messages for agent
        messages = [HumanMessage(content=message_content)]
        config = {'configurable': {'thread_id': st.session_state.thread_id}}

        with st.spinner('Processing your request...'):
            logger.info(f"💬 Sending message to agent: {message_content[:100]}...")
            result = st.session_state.agent.graph.invoke({'messages': messages}, config=config)

            if not result or 'messages' not in result:
                raise Exception("No response from the travel assistant")

            assistant_response = result['messages'][-1].content

            # Check if the response contains error messages
            if any(error_marker in assistant_response for error_marker in ['[FLIGHTS ERROR]', '[HOTELS ERROR]']):
                st.warning('⚠️ Some information could not be retrieved. The plan includes alternative suggestions.')

            # Add assistant response to session
            st.session_state.messages.append({"role": "assistant", "content": assistant_response})
            logger.info("✅ Response received and added to session")
            
            return True

    except Exception as e:
        st.error(f'Error processing message: {str(e)}')
        logger.error(f"Error in send_message: {str(e)}")
        
        # Reset agent state if needed
        if 'agent' in st.session_state:
            del st.session_state.agent
            initialize_agent()
        return False

def display_chat_messages():
    """Display chat messages with proper formatting"""
    for message in st.session_state.messages:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.write(message["content"])
        else:
            with st.chat_message("assistant"):
                # Parse and display structured content
                display_structured_response(message["content"])

def display_structured_response(content):
    """Display assistant response with structured formatting for hotels and flights"""
    # Extract and display hotel options as a table
    hotel_block = re.search(r'(Hotel Options?:\n[\s\S]+?)(?:\n\n|$)', content)
    if hotel_block:
        hotels_data = {}
        current_hotel_name = None
        
        for line in hotel_block.group(1).split('\n'):
            line = line.strip()
            if line.startswith('Hotel Option'):
                current_hotel_name = line.replace(':', '').strip()
                hotels_data[current_hotel_name] = {}
            elif line and current_hotel_name and ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                # Skip image/logo fields for table display
                if key.lower() not in ['image', 'photo', 'picture', 'img', 'photo url', 'image url', 'logo', 'logo url']:
                    hotels_data[current_hotel_name][key] = value
        
        if hotels_data:
            st.markdown('#### 🏨 Hotel Options')
            df_hotels = pd.DataFrame(hotels_data)
            if not df_hotels.empty:
                st.dataframe(df_hotels, use_container_width=True)
        
        # Remove hotel block from content
        content = content.replace(hotel_block.group(1), '')
    
    # Extract and display flight options as a table
    flight_block = re.search(r'(Flight Options?:\n[\s\S]+?)(?:\n\n|$)', content)
    if flight_block:
        flights_data = {}
        current_flight_name = None
        
        for line in flight_block.group(1).split('\n'):
            line = line.strip()
            if line.startswith('Flight Option'):
                current_flight_name = line.replace(':', '').strip()
                flights_data[current_flight_name] = {}
            elif line and current_flight_name:
                # Handle both single colon format and pipe-separated format
                if '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    for part in parts:
                        if ':' in part:
                            key, value = part.split(':', 1)
                            key = key.strip()
                            value = value.strip()
                            if key.lower() not in ['airline logo', 'logo', 'image', 'photo', 'img', 'logo url', 'image url']:
                                flights_data[current_flight_name][key] = value
                elif ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    if key.lower() not in ['airline logo', 'logo', 'image', 'photo', 'img', 'logo url', 'image url']:
                        flights_data[current_flight_name][key] = value
        
        if flights_data:
            st.markdown('#### ✈️ Flight Options')
            df_flights = pd.DataFrame(flights_data)
            if not df_flights.empty:
                st.dataframe(df_flights, use_container_width=True)
        
        # Remove flight block from content
        content = content.replace(flight_block.group(1), '')
    
    # Display the remaining content
    st.markdown(content)

# --- Main App Layout ---
st.set_page_config(page_title="AI Travel Planner", page_icon="✈️", layout="wide")
render_custom_css()

# Header
st.markdown('<h1 class="main-title">✈️🌍 AI Travel Planner</h1>', unsafe_allow_html=True)

# Initialize agent and session
initialize_agent()

# Trip Planning Form Section
st.markdown('<h2 class="section-header">📋 Plan Your Trip</h2>', unsafe_allow_html=True)

with st.expander("ℹ️ How to use this app", expanded=False):
    st.markdown("""
    **🚀 Getting Started:**
    1. **Fill in your trip details** below (departure, destination, dates, preferences)
    2. **Click "Start Planning"** to generate your comprehensive travel itinerary
    3. **Use the chat section** below to refine, ask questions, or request changes
    4. **The AI remembers** your entire conversation for better recommendations
    
    **💡 Pro Tips:**
    - Be specific with preferences (e.g., "prefer CBD hotels", "love museums", "vegetarian food")
    - Use the chat to iterate: "Make it more budget-friendly" or "Add more outdoor activities"
    - The AI can adjust flights, hotels, activities, and more based on your feedback
    """)

# Form in columns for better organization
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("**🚀 Trip Details**")
    trip_type = st.radio('✈️ Trip Type', ['Return', 'One Way'], horizontal=True, key='trip_type')
    departure_display = st.selectbox('🛫 Departure Airport', airport_options, key='departure')
    destination_display = st.selectbox('🌍 Destination Airport', airport_options, key='destination')
    st.markdown("**📅 Travel Dates**")
    today = date.today()
    default_check_in = today + timedelta(days=1)
    default_check_out = today + timedelta(days=6)
    
    check_in_date = st.date_input('🗓️ Start Date (Check-in)', min_value=today, value=default_check_in, key='check_in_date')
    
    if trip_type == 'Return':
        check_out_date = st.date_input('🗓️ End Date (Check-out)', min_value=check_in_date + timedelta(days=1), value=default_check_out, key='check_out_date')
    else:
        check_out_date = None
        st.info("One-way trip selected - no return date needed")

with col2:
    st.markdown("**🎯 Preferences & Budget**")
    energy_level = st.selectbox('⚡ Energy Level', ['Relaxed', 'Balanced', 'Active'], key='energy_level')
    budget = st.text_input('💰 Budget (AUD, optional)', placeholder="e.g., 3000", key='budget')

    st.markdown("**✨ Your Travel Preferences**")
    preferences = st.text_area(
        '🎯 Tell us what you love (hotels, activities, food, etc.)', 
        placeholder="E.g., prefer hotels in CBD, love museums and local food, enjoy hiking, vegetarian meals, budget-conscious, family-friendly activities...", 
        height=100,
        key='preferences'
    )

# Extract IATA codes for backend use
departure = iata_lookup[departure_display]
destination = iata_lookup[destination_display]

# Action buttons
button_col1, button_col2= st.columns([1, 1])

with button_col1:
    if st.button('🚀 Start Planning Your Adventure', use_container_width=True, type="primary"):
        if trip_type == 'Return' and check_out_date <= check_in_date:
            st.error('❌ End date must be after start date.')
        else:
            success = process_initial_query(departure, destination, check_in_date, check_out_date, preferences, energy_level, budget, trip_type)
            if success:
                st.markdown('<div class="success-message">✅ <strong>Travel plan generated!</strong> Scroll down to see your personalized itinerary and continue the conversation in the chat section.</div>', unsafe_allow_html=True)

with button_col2:
    if st.button('🗑️ Clear Conversation', use_container_width=True):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.success("🔄 Conversation cleared! Ready for a new trip.")
        st.rerun()




# Chat Section
st.markdown('<h2 class="section-header">💬 Chat with Your AI Travel Assistant</h2>', unsafe_allow_html=True)


# Large chat container with improved height
chat_container = st.container(height=800)

with chat_container:
    display_chat_messages()

# Chat input at the bottom
if chat_input := st.chat_input("💬 Ask questions, request changes, or get more recommendations for your trip..."):
    if send_message(chat_input):
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)
