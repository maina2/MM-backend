from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from geopy.distance import geodesic

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
    solution = routing.SolveWithParameters(search_parameters)
    if solution:
        route = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            route.append(list(all_locations[node]))  # Convert tuple to list [lat, lng]
            index = solution.Value(routing.NextVar(index))
        route.append(list(all_locations[0]))  # Return to start
        return route
    return None