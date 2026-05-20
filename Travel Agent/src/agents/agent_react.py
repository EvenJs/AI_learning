import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool

load_dotenv()

# 1. Define a weather tool that tries real API, falls back to generic
@tool
def weather_check(location: str, date: str):
    """Get the weather for a location and date (YYYY-MM-DD). Uses real API if possible, else generic info."""
    api_key = os.environ.get("WEATHER_API_KEY")
    if not api_key:
        return f"No weather API key set. Cannot get real weather for {location} on {date}."
    try:
        url = "https://api.weatherapi.com/v1/forecast.json"
        params = {
            "key": api_key,
            "q": location,
            "dt": date,
            "days": 1,
            "aqi": "no",
            "alerts": "no"
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if (
            "forecast" in data and
            "forecastday" in data["forecast"] and
            data["forecast"]["forecastday"]
        ):
            day = data["forecast"]["forecastday"][0]["day"]
            return f"{location} on {date}: {day['condition']['text']}, {day['avgtemp_c']}°C (min {day['mintemp_c']}°C, max {day['maxtemp_c']}°C)"
        else:
            return f"No real weather data for {location} on {date}."
    except Exception:
        # Fallback: generic info
        return f"No real weather data for {location} on {date}. Typical weather: mild, partly cloudy."

# 2. List of tools
TOOLS = [weather_check]

# 3. Create a simple system prompt
SYSTEM_PROMPT = (
    "You are a helpful travel planning agent. When given a destination and travel dates, "
    "create a day-by-day itinerary.\n\n"
    "For each day:\n"
    "1. Use the weather_check tool to get actual weather data for that specific date\n"
    "2. If weather data is unavailable, acknowledge this clearly and use general seasonal knowledge\n"
    "3. Suggest 2-3 activities appropriate for the weather conditions and destination\n"
    "4. Include meal recommendations\n\n"
    "After the daily itinerary:\n"
    "- Provide weather-based packing tips (appropriate clothing, accessories, etc.)\n"
    "- Create a concise travel checklist (5-7 essential items)\n\n"
    "Keep responses organized with clear headings and bullet points for easy reading."
)

# 4. Set up the agent
agent = create_react_agent(
    model=ChatOpenAI(model_name="gpt-4o", api_key=os.environ.get("OPENAI_API_KEY")),
    tools=TOOLS,
    prompt=SYSTEM_PROMPT
)

# Example user input: destination, start date, end date
user_input = (
    "I want to travel to Melbourne from 2025-05-18 to 2025-05-22. "
    "Please plan my trip."
)

# 5. Run the agent with a user message
result = agent.invoke({
    "messages": [
        {"role": "user", "content": user_input}
    ]
})

print(result["messages"][-1].content)
