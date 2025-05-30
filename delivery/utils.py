from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from geopy.distance import geodesic
import requests
import logging
from time import sleep
from django.core.cache import cache

logger = logging.getLogger(__name__)

def geocode_address(address):
    """
    Convert address to (latitude, longitude) using Nominatim.
    Returns None if geocoding fails.
    """
    cache_key = f"geocode_{address}"
    cached_coords = cache.get(cache_key)
    if cached_coords:
        logger.info(f"Retrieved cached coordinates for {address}")
        return cached_coords

    for attempt in range(3):
        try:
            response = requests.get(
                f"https://nominatim.openstreetmap.org/search?q={address}&format=json",
                headers={'User-Agent': 'MuindiMwesiApp/1.0'},
                timeout=5
            )
            response.raise_for_status()
            results = response.json()
            if results:
                latitude = float(results[0]['lat'])
                longitude = float(results[0]['lon'])
                cache.set(cache_key, (latitude, longitude), timeout=86400)
                logger.info(f"Geocoded {address} to ({latitude}, {longitude})")
                return (latitude, longitude)
            logger.warning(f"No coordinates found for {address}")
            return None
        except requests.RequestException as e:
            logger.error(f"Geocoding attempt {attempt + 1} failed for {address}: {str(e)}")
            if attempt < 2:
                sleep(1)
    return None

def compute_shortest_route(start_location, locations):
    """
    Compute shortest route starting and ending at start_location through locations.
    Args:
        start_location: Tuple (lat, lng)
        locations: List of tuples [(lat, lng), ...]
    Returns:
        List of [lat, lng] representing the route, or None if failed.
    """
    if not locations or not start_location:
        logger.warning("Empty locations or invalid start_location provided")
        return None

    all_locations = [start_location] + locations
    n = len(all_locations)

    # Create distance matrix (meters)
    distance_matrix = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                distance_matrix[i][j] = int(geodesic(all_locations[i], all_locations[j]).meters)

    # Initialize routing model
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)  # 1 vehicle, start at index 0
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Set search parameters
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = 10  # Limit computation time

    # Solve
    try:
        solution = routing.SolveWithParameters(search_parameters)
        if solution:
            route = []
            index = routing.Start(0)
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                route.append(list(all_locations[node]))  # Convert tuple to list [lat, lng]
                index = solution.Value(routing.NextVar(index))
            route.append(list(all_locations[0]))  # Return to start
            logger.info(f"Computed route with {n} locations")
            return route
        logger.warning("No solution found for route computation")
        return None
    except Exception as e:
        logger.error(f"Route computation failed: {str(e)}")
        return None