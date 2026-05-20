import os
from typing import Optional
from datetime import datetime
import logging
import time
import serpapi
from pydantic import BaseModel, Field
from langchain_core.tools import tool


class FlightsInput(BaseModel):
    departure_airport: str = Field(description='Departure airport code (IATA)')
    arrival_airport: str = Field(description='Arrival airport code (IATA)')
    outbound_date: str = Field(description='Parameter defines the outbound date. The format is YYYY-MM-DD. e.g. 2024-06-22')
    return_date: Optional[str] = Field(None, description='Parameter defines the return date. The format is YYYY-MM-DD. e.g. 2024-06-28')
    adults: Optional[int] = Field(1, description='Parameter defines the number of adults. Default to 1.')
    children: Optional[int] = Field(0, description='Parameter defines the number of children. Default to 0.')
    infants_in_seat: Optional[int] = Field(0, description='Parameter defines the number of infants in seat. Default to 0.')
    infants_on_lap: Optional[int] = Field(0, description='Parameter defines the number of infants on lap. Default to 0.')
    max_stops: Optional[int] = Field(1, description='Maximum number of stops allowed. Default to 1.')


class FlightsInputSchema(BaseModel):
    params: FlightsInput


def validate_date_format(date_str: str) -> bool:
    """Validate if the date string is in YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def validate_airport_code(code: str) -> bool:
    """Validate if the airport code is a valid 3-letter IATA code."""
    return (isinstance(code, str) and 
            len(code) == 3 and 
            code.isalpha())


# Setup logger
logger = logging.getLogger("flights_finder")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
handler.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(handler)


@tool(args_schema=FlightsInputSchema)
def flights_finder(params: FlightsInput):
    '''
    Find flights using the Google Flights engine via SerpAPI.
    Returns:
        dict: Flight search results with best flight options.
    '''
    logger.info(f"Received flight search params: {params}")
    api_key = os.environ.get('SERPAPI_API_KEY')
    if not api_key:
        logger.error('SERPAPI_API_KEY environment variable is not set.')
        print('SERPAPI_API_KEY environment variable is not set.')
        return {'error': 'SERPAPI_API_KEY environment variable is not set.'}

    # Validate airport codes
    if not validate_airport_code(params.departure_airport):
        logger.error(f"Invalid departure airport code: {params.departure_airport}")
        print(f"Invalid departure airport code: {params.departure_airport}")
        return {'error': f'Invalid departure airport code: {params.departure_airport}. Must be a valid 3-letter IATA code.'}
    if not validate_airport_code(params.arrival_airport):
        logger.error(f"Invalid arrival airport code: {params.arrival_airport}")
        print(f"Invalid arrival airport code: {params.arrival_airport}")
        return {'error': f'Invalid arrival airport code: {params.arrival_airport}. Must be a valid 3-letter IATA code.'}
    if not validate_date_format(params.outbound_date):
        logger.error(f"Invalid outbound date format: {params.outbound_date}")
        print(f"Invalid outbound date format: {params.outbound_date}")
        return {'error': f'Invalid outbound date format: {params.outbound_date}. Must be in YYYY-MM-DD format.'}
    if params.return_date and not validate_date_format(params.return_date):
        logger.error(f"Invalid return date format: {params.return_date}")
        print(f"Invalid return date format: {params.return_date}")
        return {'error': f'Invalid return date format: {params.return_date}. Must be in YYYY-MM-DD format.'}

    params_dict = {
        'api_key': api_key,
        'engine': 'google_flights',
        'hl': 'en',
        'gl': 'us',
        'departure_id': params.departure_airport.upper(),
        'arrival_id': params.arrival_airport.upper(),
        'outbound_date': params.outbound_date,
        'currency': 'USD',
        'adults': params.adults,
        'infants_in_seat': params.infants_in_seat,
        'stops': str(params.max_stops),
        'infants_on_lap': params.infants_on_lap,
        'children': params.children
    }
    if params.return_date:
        params_dict['return_date'] = params.return_date

    logger.debug(f"Calling serpapi.search with params: {params_dict}")
    max_retries = 3
    retry_delay = 2
    for attempt in range(max_retries):
        try:
            search = serpapi.search(params_dict, timeout=30)
            logger.debug(f"SerpAPI raw response: {getattr(search, 'data', None)}")
            if not hasattr(search, 'data') or 'best_flights' not in search.data:
                logger.error(f"No flight results found or unexpected API response format. Response: {getattr(search, 'data', None)}")
                print(f"No flight results found or unexpected API response format. Response: {getattr(search, 'data', None)}")
                return {'error': 'No flight results found or unexpected API response format.'}
            results = search.data['best_flights']
            formatted_results = []
            for option in results:
                first_leg = option['flights'][0] if option.get('flights') else {}
                formatted_flight = {
                    'airline': first_leg.get('airline', 'Unknown'),
                    'flight_number': first_leg.get('flight_number', 'Unknown'),
                    'departure_time': first_leg.get('departure_airport', {}).get('time', 'Unknown'),
                    'arrival_time': first_leg.get('arrival_airport', {}).get('time', 'Unknown'),
                    'duration': first_leg.get('duration', option.get('total_duration', 'Unknown')),
                    'price': f"${option.get('price', 'Unknown')} USD",
                    'stops': len(option['flights']) - 1 if option.get('flights') else 'Unknown'
                }
                formatted_results.append(formatted_flight)
            logger.info(f"Returning {len(formatted_results)} flight results.")
            return formatted_results[:5]
        except serpapi.SerpApiError as e:
            logger.error(f"SerpAPI error: {str(e)}")
            print(f"SerpAPI error: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                return {'error': f'SerpAPI error: {str(e)}. Please try again later.'}
        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            print(f"Unexpected error: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                return {'error': f'Unexpected error: {str(e)}. Please try again later.'}
