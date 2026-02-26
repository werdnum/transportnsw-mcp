import pytest
import time
import sys
import os
from datetime import datetime

# Add the parent directory to path so we can import the api module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api import find_transport_stops, get_transport_alerts, get_departure_monitor, plan_trip, output_format, coord_output_format, incl_filter, api_version

# Test coordinates (Central Station, Sydney)
CENTRAL_STATION_COORD = '151.206290:-33.884080:EPSG:4326'

class TestCoordinateAPI:
    """Test suite for Transport NSW Coordinate API functionality."""
    
    def test_bus_stop_retrieval(self):
        """Test finding bus stops around a location."""
        bus_stops = find_transport_stops(CENTRAL_STATION_COORD, stop_type='BUS_POINT', radius=500)
        
        # Verify response structure
        assert bus_stops is not None
        assert 'locations' in bus_stops
        assert len(bus_stops['locations']) > 0
        
        # Verify location properties
        for location in bus_stops['locations'][:5]:
            assert 'name' in location
            assert 'id' in location
            assert 'type' in location
            assert 'coord' in location
    
    def test_poi_retrieval(self):
        """Test finding points of interest around a location."""
        poi_locations = find_transport_stops(CENTRAL_STATION_COORD, stop_type='POI_POINT', radius=500)
        
        # Verify response structure
        assert poi_locations is not None
        assert 'locations' in poi_locations
        
        # If POIs are found, verify their properties
        if poi_locations['locations']:
            for location in poi_locations['locations'][:5]:
                assert 'name' in location
                assert 'id' in location
                assert 'type' in location
                assert 'coord' in location
                
        # Verify location types are valid if POIs exist
        if poi_locations['locations']:
            location = poi_locations['locations'][0]
            assert location['type'] == 'poi'  # POIs should have type 'poi'
    
    def test_response_time(self):
        """Test API response time."""
        start_time = time.time()
        bus_stops = find_transport_stops(CENTRAL_STATION_COORD, stop_type='BUS_POINT', radius=500)
        elapsed = time.time() - start_time
        
        # API should respond within a reasonable time (5 seconds)
        assert elapsed < 5, f"API response took too long: {elapsed:.2f} seconds"
        assert bus_stops is not None
    
    def test_invalid_stop_type(self):
        """Test with an invalid stop type."""
        # With the new implementation, we should get None or an empty response rather than an exception
        result = find_transport_stops(CENTRAL_STATION_COORD, stop_type='INVALID_TYPE', radius=500)
        # Either the result is None or it doesn't have any valid locations
        if result is not None:
            assert 'locations' not in result or len(result['locations']) == 0
    
    def test_radius_parameter(self):
        """Test that different radius values affect the number of results."""
        # Small radius should return fewer results
        small_radius_results = find_transport_stops(CENTRAL_STATION_COORD, stop_type='BUS_POINT', radius=100)
        
        # Larger radius should return more results
        large_radius_results = find_transport_stops(CENTRAL_STATION_COORD, stop_type='BUS_POINT', radius=1000)
        
        # Only compare if both requests were successful
        if small_radius_results and large_radius_results:
            if 'locations' in small_radius_results and 'locations' in large_radius_results:
                # The larger radius should generally return more results
                # Note: This is not guaranteed but is likely in an urban area
                assert len(small_radius_results['locations']) <= len(large_radius_results['locations'])
    
    def test_different_location(self):
        """Test API with a different location."""
        # Coordinates for Sydney Opera House
        opera_house_coord = '151.214897:-33.857438:EPSG:4326'
        
        opera_house_stops = find_transport_stops(opera_house_coord, stop_type='BUS_POINT', radius=500)
        assert opera_house_stops is not None
        assert 'locations' in opera_house_stops


class TestTransportAlerts:
    """Test suite for Transport NSW Alert API functionality."""
    
    def test_basic_alert_retrieval(self):
        """Test basic alert retrieval with default parameters."""
        alerts = get_transport_alerts()
        assert alerts is not None
        assert 'version' in alerts
        assert alerts['version'] == api_version
        assert 'timestamp' in alerts
        assert 'infos' in alerts
    
    def test_filtered_alert_retrieval(self):
        """Test alert retrieval with mode of transport filter."""
        # Test for train alerts (mot_type=1)
        train_alerts = get_transport_alerts(mot_type=1)
        assert train_alerts is not None
        assert 'version' in train_alerts
        assert train_alerts['version'] == api_version
        
        # Test for bus alerts (mot_type=5)
        bus_alerts = get_transport_alerts(mot_type=5)
        assert bus_alerts is not None
        assert 'version' in bus_alerts
    
    def test_date_filtered_alert_retrieval(self):
        """Test alert retrieval with date filter."""
        # Test for alerts on a specific date
        future_date = '20-03-2025'
        date_alerts = get_transport_alerts(date=future_date)
        assert date_alerts is not None
        assert 'version' in date_alerts
    
    def test_multiple_filters(self):
        """Test alert retrieval with multiple filters."""
        # Test for train alerts on a specific date
        future_date = '20-03-2025'
        filtered_alerts = get_transport_alerts(date=future_date, mot_type=1)
        assert filtered_alerts is not None
        assert 'version' in filtered_alerts
    
    def test_response_structure(self):
        """Test the structure of the API response."""
        alerts = get_transport_alerts()
        assert 'infos' in alerts
        
        # The structure might not have 'info' attribute if there are no alerts
        # Instead, check that the response has a valid structure overall
        assert alerts['infos'] is not None
    
    def test_alerts_performance(self):
        """Test API response time."""
        start_time = time.time()
        alerts = get_transport_alerts()
        elapsed = time.time() - start_time
        
        # API should respond within a reasonable time (5 seconds)
        assert elapsed < 5, f"API response took too long: {elapsed:.2f} seconds"


class TestDepartureMonitor:
    """Test suite for Transport NSW Departure Monitor API functionality."""
    
    # Test stop ID for Central Station
    CENTRAL_STATION_ID = "200060"  # Central Station global ID
    
    def test_basic_departure_retrieval(self):
        """Test basic departure monitor retrieval with default parameters."""
        departures = get_departure_monitor(self.CENTRAL_STATION_ID)
        
        # Verify response structure
        assert departures is not None
        assert isinstance(departures, list), "Response should be a list of departures"
        
        # Check departure structure if any are returned
        if len(departures) > 0:
            # Verify the structure of a departure object
            departure = departures[0]
            assert isinstance(departure, dict), "Each departure should be a dictionary"
            assert 'stop_name' in departure, "Departure should have a stop_name"
            assert 'local_departure_time' in departure, "Departure should have a local_departure_time"
    
    def test_mot_type_filter(self):
        """Test departure retrieval with mode of transport filter."""
        # Test for train departures (mot_type=1)
        train_departures = get_departure_monitor(self.CENTRAL_STATION_ID, mot_type=1)
        assert train_departures is not None
        assert isinstance(train_departures, list), "Response should be a list of departures"
    
    def test_date_parameter(self):
        """Test departure retrieval with specific date."""
        # Test for departures on a specific date
        tomorrow = (datetime.now().date().replace(day=datetime.now().day + 1)).strftime('%d-%m-%Y')
        date_departures = get_departure_monitor(self.CENTRAL_STATION_ID, date=tomorrow)
        assert date_departures is not None
        assert isinstance(date_departures, list), "Response should be a list of departures"
    
    def test_time_parameter(self):
        """Test departure retrieval with specific time."""
        # Test for departures at a specific time
        time_departures = get_departure_monitor(self.CENTRAL_STATION_ID, time="12:00")
        assert time_departures is not None
        assert isinstance(time_departures, list), "Response should be a list of departures"
    
    def test_multiple_filters(self):
        """Test departure retrieval with multiple filters."""
        # Test for train departures with date and time
        filtered_departures = get_departure_monitor(
            self.CENTRAL_STATION_ID, 
            mot_type=1,
            time="12:00"
        )
        assert filtered_departures is not None
        assert isinstance(filtered_departures, list), "Response should be a list of departures"
    
    def test_invalid_stop_id(self):
        """Test behavior with invalid stop ID."""
        invalid_departures = get_departure_monitor("INVALID_ID")
        # The API might return an empty list or None for invalid IDs
        if invalid_departures is not None:
            # If a response is returned, it should be a list (possibly empty)
            assert isinstance(invalid_departures, list), "Response should be a list"
    
    def test_response_time(self):
        """Test API response time."""
        start_time = time.time()
        departures = get_departure_monitor(self.CENTRAL_STATION_ID)
        elapsed = time.time() - start_time
        
        # API should respond within a reasonable time (5 seconds)
        assert elapsed < 5, f"API response took too long: {elapsed:.2f} seconds"
        assert departures is not None


class TestTripPlanner:
    """Test suite for Transport NSW Trip Planner API functionality."""

    CENTRAL_STATION_ID = "200060"
    TOWN_HALL_STATION_ID = "200070"

    def test_basic_trip(self):
        """Test basic trip planning between two stops."""
        trips = plan_trip(
            origin=self.CENTRAL_STATION_ID,
            destination=self.TOWN_HALL_STATION_ID,
            origin_type='stop',
            destination_type='stop',
            num_trips=3,
        )
        assert trips is not None
        assert isinstance(trips, list), "Response should be a list of journeys"
        assert len(trips) > 0, "Should return at least one journey"

        # Verify journey structure
        journey = trips[0]
        assert 'legs' in journey, "Journey should have legs"
        assert len(journey['legs']) > 0, "Journey should have at least one leg"
        assert 'total_duration_minutes' in journey, "Journey should have total duration"

    def test_trip_leg_structure(self):
        """Test that trip legs contain expected fields."""
        trips = plan_trip(
            origin=self.CENTRAL_STATION_ID,
            destination=self.TOWN_HALL_STATION_ID,
            origin_type='stop',
            destination_type='stop',
            num_trips=1,
        )
        assert trips is not None
        assert len(trips) > 0

        leg = trips[0]['legs'][0]
        assert 'origin' in leg, "Leg should have origin"
        assert 'destination' in leg, "Leg should have destination"
        assert 'departure_planned' in leg, "Leg should have planned departure"
        assert 'arrival_planned' in leg, "Leg should have planned arrival"
        assert 'mode' in leg, "Leg should have mode"
        assert 'duration_minutes' in leg, "Leg should have duration"

    def test_trip_with_date_and_time(self):
        """Test trip planning with specific date and time."""
        trips = plan_trip(
            origin=self.CENTRAL_STATION_ID,
            destination=self.TOWN_HALL_STATION_ID,
            origin_type='stop',
            destination_type='stop',
            time='09:00',
        )
        assert trips is not None
        assert isinstance(trips, list)

    def test_trip_arrive_by(self):
        """Test trip planning with arrival time constraint."""
        trips = plan_trip(
            origin=self.CENTRAL_STATION_ID,
            destination=self.TOWN_HALL_STATION_ID,
            origin_type='stop',
            destination_type='stop',
            time='18:00',
            dep_arr='arr',
        )
        assert trips is not None
        assert isinstance(trips, list)

    def test_trip_by_name(self):
        """Test trip planning using location names instead of stop IDs."""
        trips = plan_trip(
            origin='Central Station, Sydney',
            destination='Town Hall Station, Sydney',
            num_trips=1,
        )
        assert trips is not None
        # The API may return journeys (list) or system_messages (dict) if names are ambiguous
        assert isinstance(trips, (list, dict)), "Response should be a list of journeys or a dict with system messages"

    def test_trip_exclude_modes(self):
        """Test trip planning with excluded transport modes."""
        trips = plan_trip(
            origin=self.CENTRAL_STATION_ID,
            destination=self.TOWN_HALL_STATION_ID,
            origin_type='stop',
            destination_type='stop',
            exclude_modes=[5, 7],  # Exclude bus and coach
        )
        assert trips is not None
        assert isinstance(trips, list)

    def test_trip_response_time(self):
        """Test trip planner API response time."""
        start_time = time.time()
        trips = plan_trip(
            origin=self.CENTRAL_STATION_ID,
            destination=self.TOWN_HALL_STATION_ID,
            origin_type='stop',
            destination_type='stop',
            num_trips=1,
        )
        elapsed = time.time() - start_time

        assert elapsed < 10, f"API response took too long: {elapsed:.2f} seconds"
        assert trips is not None


if __name__ == "__main__":
    pytest.main(["-v", "test_api.py"])
