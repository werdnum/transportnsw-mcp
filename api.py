from __future__ import print_function
from dotenv import load_dotenv
import os
import requests
from datetime import datetime

# Load environment variables
load_dotenv()
API_KEY = os.getenv('OPEN_TRANSPORT_API_KEY')

# Define common parameters for API requests
output_format = 'rapidJSON'  # Required for JSON output
coord_output_format = 'EPSG:4326'  # Standard coordinate format
incl_filter = 1  # Enable advanced filter mode
api_version = '10.2.1.42'  # API version

# Import MCP server
from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("Transport NSW")

@mcp.tool()
def find_transport_stops(location_coord, stop_type='BUS_POINT', radius=100):
    """
    Find transport stops around a specific location.
    
    Args:
        location_coord (str): Coordinates in format 'LONGITUDE:LATITUDE:EPSG:4326'
        stop_type (str): Type of stops to find: 'BUS_POINT', 'POI_POINT', or 'GIS_POINT'
        radius (int): Search radius in meters
        
    Returns:
        API response with transport stops
    """
    import requests
    
    # API endpoint
    API_ENDPOINT = 'https://api.transport.nsw.gov.au/v1/tp/coord'
    
    # Set up the request parameters
    params = {
        'outputFormat': output_format,
        'coord': location_coord,
        'coordOutputFormat': coord_output_format,
        'inclFilter': incl_filter,
        'type_1': stop_type,
        'radius_1': radius,
        'version': api_version
    }
    
    # Set up the headers with the API key
    headers = {
        'Authorization': f'apikey {API_KEY}'
    }
    
    try:
        # Make the request
        response = requests.get(API_ENDPOINT, params=params, headers=headers)
        
        # Check if the request was successful
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Request failed with status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception when calling Transport NSW API: {e}\n")
        return None

@mcp.tool()
def get_transport_alerts(date=None, mot_type=None, stop_id=None, line_number=None, operator_id=None):
    """
    Get transport alerts from the Transport NSW API.
    
    Args:
        date (str, optional): Date in DD-MM-YYYY format. Defaults to today's date.
        mot_type (int, optional): Mode of transport type filter. Options:
            1: Train
            2: Metro
            4: Light Rail
            5: Bus
            7: Coach
            9: Ferry
            11: School Bus
        stop_id (str, optional): Stop ID or global stop ID to filter by.
        line_number (str, optional): Line number to filter by (e.g., '020T1').
        operator_id (str, optional): Operator ID to filter by.
    
    Returns:
        dict: API response containing alerts information
    """
    import requests
    
    # API endpoint - the alerts are under /v1/tp/add_info (with an underscore)
    API_ENDPOINT = 'https://api.transport.nsw.gov.au/v1/tp/add_info'
    
    # Set default date to today if not provided
    if date is None:
        date = datetime.now().strftime('%d-%m-%Y')
    
    # Set up the request parameters
    params = {
        'outputFormat': output_format,
        'filterDateValid': date,
        'version': api_version
    }
    
    # Add optional filters if provided
    if mot_type is not None:
        params['filterMotType'] = mot_type
    
    if stop_id is not None:
        params['itdLPxxSelStop'] = stop_id
    
    if line_number is not None:
        params['itdLPxxSelLine'] = line_number
    
    if operator_id is not None:
        params['itdLPxxSelOperator'] = operator_id
        
    # Ensure parameter names match what the API expects
    # For the direct HTTP approach, some parameter names may be different than in Swagger
    
    # Set up the headers with the API key
    headers = {
        'Authorization': f'apikey {API_KEY}'
    }
    
    try:
        # Make the request
        response = requests.get(API_ENDPOINT, params=params, headers=headers)
        
        # Check if the request was successful
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Request failed with status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception when calling Transport NSW API: {e}\n")
        return None

# Call the API to get real-time departure information for a specific stop
@mcp.tool()
def get_departure_monitor(stop_id, date=None, time=None, mot_type=None, max_results=1):
    """
    Get real-time departure monitor information for a specific stop from the Trip Planner API.
    This function uses direct HTTP requests to the Transport NSW API.
    
    Args:
        stop_id (str): Stop ID or global stop ID
        date (str, optional): Date in DD-MM-YYYY format. Defaults to today's date.
        time (str, optional): Time in HH:MM format. Defaults to current time.
        mot_type (int, optional): Mode of transport type filter. Options:
            1: Train
            2: Metro
            4: Light Rail
            5: Bus
            7: Coach
            9: Ferry
            11: School Bus
        max_results (int, optional): Maximum number of results to return. Default is 1.
        
    Returns:
        list: Simplified list of departure information
    """
    import requests
    from datetime import datetime, timezone, timedelta
    
    # API endpoint
    API_ENDPOINT = 'https://api.transport.nsw.gov.au/v1/tp/departure_mon'
    
    # Set default date and time to now if not provided
    now = datetime.now()
    
    # Format date as YYYYMMDD for the API
    if date is None:
        itd_date = now.strftime('%Y%m%d')
    else:
        # Convert from DD-MM-YYYY to YYYYMMDD
        day, month, year = date.split('-')
        itd_date = f"{year}{month}{day}"
    
    # Format time as HHMM for the API
    if time is None:
        itd_time = now.strftime('%H%M')
    else:
        # Convert from HH:MM to HHMM
        itd_time = time.replace(':', '')
    
    # Parse the target time for later filtering
    target_time = None
    if time is not None:
        time_parts = time.split(':')
        hour = int(time_parts[0])
        minute = int(time_parts[1]) if len(time_parts) > 1 else 0
        # Create a datetime object with today's date and the specified time
        # Make it timezone-aware to match the converted API times
        target_time = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        # Add timezone info to make it comparable with timezone-aware datetimes
        target_time = target_time.astimezone()
    
    # Always request more results than needed to ensure we have enough for filtering
    # Set up the request parameters exactly as in the documentation
    params = {
        'outputFormat': 'rapidJSON',
        'coordOutputFormat': 'EPSG:4326',
        'mode': 'direct',
        'type_dm': 'stop',
        'name_dm': stop_id,
        'depArrMacro': 'dep',
        'itdDate': itd_date,
        'itdTime': itd_time,
        'TfNSWDM': 'true',
        'version': api_version,
        'radius_dm': 100,
        'limit': max(20, max_results * 2)  # Request more results than needed for better filtering
    }
    
    # Add mot_type filter if provided
    if mot_type is not None:
        params['motType'] = mot_type
    
    # Set up the headers with the API key
    headers = {
        'Authorization': f'apikey {API_KEY}'
    }
    
    try:
        # Make the request
        response = requests.get(API_ENDPOINT, params=params, headers=headers)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Parse the JSON response
            data = response.json()
            
            # Limit the number of stop events to max_results if specified
            if 'stopEvents' in data and len(data['stopEvents']) > max_results:
                data['stopEvents'] = data['stopEvents'][:max_results]
                print(f"Limited results to {max_results} departures")
            
            # Process response
            stops = data.get('stopEvents', [])
            
            # Process stops and prepare for filtering/sorting
            processed_stops = []
            
            # Get current date and time for filtering
            now_local = datetime.now()
            today_date = now_local.strftime('%Y-%m-%d')
            
            # Convert all departure times to datetime objects for easier processing
            for stop in stops:
                departure_time = stop.get('departureTimePlanned', '')
                if not departure_time:  # Skip entries without departure time
                    continue
                    
                # Parse the departure time (API returns times in UTC with Z suffix)
                try:
                    # Remove any fractional seconds and handle Z suffix
                    clean_time = departure_time.split('.')[0]
                    if clean_time.endswith('Z'):
                        clean_time = clean_time[:-1]  # Remove Z suffix
                    
                    # Parse the UTC time from the API
                    departure_dt_utc = datetime.strptime(clean_time, "%Y-%m-%dT%H:%M:%S")
                    departure_dt_utc = departure_dt_utc.replace(tzinfo=timezone.utc)
                    
                    # Convert to local time for easier comparison
                    departure_dt_local = departure_dt_utc.astimezone()
                    
                    # Add the parsed datetime to the stop for easier sorting
                    stop['departure_dt_local'] = departure_dt_local
                    
                    # Only include departures from today or future dates
                    departure_date = departure_dt_local.strftime('%Y-%m-%d')
                    if departure_date >= today_date:
                        processed_stops.append(stop)
                except ValueError:
                    print(f"Could not parse departure time: {departure_time}")
                    continue
            
            # Sort the stops based on time parameter if provided
            if target_time is not None:
                # Calculate time difference for each stop
                for stop in processed_stops:
                    departure_dt_local = stop['departure_dt_local']
                    
                    # Calculate time difference in seconds
                    time_diff = abs((departure_dt_local - target_time).total_seconds())
                    stop['time_diff'] = time_diff
                
                # Sort by time difference (closest to target time first)
                processed_stops.sort(key=lambda x: x.get('time_diff', float('inf')))
            else:
                # Sort by departure time if no specific time is provided (earliest first)
                processed_stops.sort(key=lambda x: x['departure_dt_local'])
            
            # Limit to max_results
            if max_results > 0 and len(processed_stops) > max_results:
                processed_stops = processed_stops[:max_results]
                print(f"Limited results to {max_results} departures")
            
            # Create a more concise version of the data for LLMs
            concise_stops = []
            for stop in processed_stops:
                # Format local time for better readability
                local_time = stop['departure_dt_local'].strftime('%Y-%m-%d %H:%M:%S')
                
                # Extract only the essential information
                concise_stop = {
                    'stop_name': stop.get('location', {}).get('name', ''),
                    'route_number': stop.get('transportation', {}).get('number', ''),
                    'route_name': stop.get('transportation', {}).get('description', ''),
                    'destination': stop.get('transportation', {}).get('destination', {}).get('name', ''),
                    'operator': stop.get('transportation', {}).get('operator', {}).get('name', ''),
                    'planned_departure': stop.get('departureTimePlanned', ''),
                    'estimated_departure': stop.get('departureTimeEstimated', ''),
                    'local_departure_time': local_time,
                    'wheelchair_access': stop.get('properties', {}).get('WheelchairAccess', 'false')
                }
                concise_stops.append(concise_stop)
            
            return concise_stops
        else:
            print(f"Request failed with status code: {response.status_code}")
            print(f"Response text: {response.text[:500]}...")  # Print first 500 chars
            return None
    except Exception as e:
        print(f"Exception when calling Transport NSW API: {e}\n")
        return None


if __name__ == "__main__":
    mcp.run(transport="stdio")
