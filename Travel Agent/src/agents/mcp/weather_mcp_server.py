import os
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("Weather")

@mcp.tool()
async def get_weather(location: str, date: str) -> str:
    """Get the weather for a location and date (YYYY-MM-DD). Uses real API if possible, else generic info."""
    print(f"get_weather called with: {location}, {date}")
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


if __name__ == "__main__":
    mcp.run(transport="streamable-http")