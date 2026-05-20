import os
import requests
from typing import Optional
from datetime import datetime, timedelta
import logging
from pydantic import BaseModel, Field
from langchain_core.tools import tool

class WeatherInput(BaseModel):
    location: str = Field(description='City or location for the weather check')
    date: str = Field(description='Date for the weather forecast. Format: YYYY-MM-DD')

class WeatherInputSchema(BaseModel):
    params: WeatherInput

# Setup logger
logger = logging.getLogger("weather_check")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
handler.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(handler)

@tool(args_schema=WeatherInputSchema)
def weather_check(params: WeatherInput):
    '''
    Check the weather for a given location and date using a weather API.
    If the date is too far in the future and no real forecast is available, return a message indicating this and suggest general weather based on LLM knowledge.
    If API data is available, return the real-time weather from the API.
    '''
    logger.info(f"Received weather check params: {params}")
    api_key = os.environ.get('WEATHER_API_KEY')
    if not api_key:
        logger.error('WEATHER_API_KEY environment variable is not set.')
        return {'error': 'WEATHER_API_KEY environment variable is not set.'}

    # Validate date format
    try:
        forecast_date = datetime.strptime(params.date, '%Y-%m-%d')
    except ValueError:
        logger.error(f"Invalid date format: {params.date}")
        return {'error': f'Invalid date format: {params.date}. Must be in YYYY-MM-DD format.'}

    today = datetime.now().date()
    max_forecast_days = 14  # Most APIs provide up to 14 days forecast
    days_ahead = (forecast_date.date() - today).days
    if days_ahead < 0:
        return {'error': 'Cannot check weather for a past date.'}

    if days_ahead > max_forecast_days:
        # Too far in the future, no real forecast available
        return {'info': f'Real-time weather forecast is not available for {params.date} in {params.location}. Here is a general weather summary for this time of year based on historical data and LLM knowledge.'}

    # Example using WeatherAPI.com (replace with your provider as needed)
    url = f"https://api.weatherapi.com/v1/forecast.json"
    query = {
        'key': api_key,
        'q': params.location,
        'dt': params.date,
        'days': 1,
        'aqi': 'no',
        'alerts': 'no'
    }
    try:
        response = requests.get(url, params=query, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'forecast' in data and 'forecastday' in data['forecast'] and data['forecast']['forecastday']:
            day = data['forecast']['forecastday'][0]['day']
            condition = day['condition']['text']
            avg_temp_c = day['avgtemp_c']
            max_temp_c = day['maxtemp_c']
            min_temp_c = day['mintemp_c']
            return {
                'location': params.location,
                'date': params.date,
                'condition': condition,
                'avg_temp_c': avg_temp_c,
                'max_temp_c': max_temp_c,
                'min_temp_c': min_temp_c,
                'source': 'WeatherAPI.com'
            }
        else:
            return {'error': f'No weather data available for {params.location} on {params.date}.'}
    except Exception as e:
        logger.error(f"Weather API error: {str(e)}")
        return {'error': f'Weather API error: {str(e)}'} 