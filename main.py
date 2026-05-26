from typing import List, Any
import json
import pulp
import networkx as nx
from ilp_routing_model import ILPRouting
from display_results import DisplayResults
from data_models import Demand


def create_graph(file_path: str):
    with open(file_path, encoding="utf-8") as file:
        topology = json.load(file)

    graph = nx.DiGraph()
    graph.add_edges_from(topology)

    return graph


def get_flows(demands: List[Any]):
    flows = {}
    for i, demand in enumerate(demands, start=1):
        flows[i] = {
            "source":    demand.src,
            "target":    demand.dst,
            "bandwidth": demand.volume
        }

    return flows


def route_flows(
    r_number:      int,
    demands:       List[Any],
    topology_file: str = 'network_topology.json',
) -> None:
    graph       = create_graph(topology_file)
    r_max       = {n: r_number for n in graph.nodes()} # switch rule capacity
    model       = ILPRouting(graph, r_max)
    res         = DisplayResults(graph)
    flows       = get_flows(demands)
    prob, alpha = model.solve_routing_ilp(flows)
    ilp_status  = pulp.LpStatus[prob.status]

    if ilp_status == "Optimal":
        print("[INFO]: ILP Status - optimal")
        model.print_paths(flows, alpha)
        res.print_active_links(alpha)
        res.draw_network(alpha)
    else:
        print("[INFO]: No optimal solution found for defined constraints")


DisplayResults.print_header(1)
print("Objective:       Minimizing active network links")
print("Expected result: All flows are routed through Vienna")
demands1 = [
    Demand('Stockholm', 'Bratislava', 10),
    Demand('Stockholm', 'Budapest', 10),
    Demand('Stockholm', 'Berlin', 10),
]
route_flows(5, demands1)

DisplayResults.print_header(2)
print("Objective:       Ensure link capacity for each flow")
print("Expected result: 1st and 2nd flows consume most of the Stockholm–Vienna link capacity.")
print("                 Therefore, the 3rd flow must be routed to Berlin via Prague.")
demands2 = [
    Demand('Stockholm', 'Bratislava', 70),
    Demand('Stockholm', 'Budapest', 70),
    Demand('Stockholm', 'Berlin', 70),
]
route_flows(5, demands2)

DisplayResults.print_header(3)
print("Objective:       Limiting the maximum number of flow table entries to 3 per switch")
print("Expected result: Not all flows can be routed via the shortest path through Vienna.")
print("                 One of the flows must take an alternative path due to entry constraints.")
demands3 = [
    Demand('Stockholm', 'Bratislava', 10),
    Demand('Stockholm', 'Budapest', 10),
    Demand('Stockholm', 'Berlin', 10),
    Demand('Prague', 'Helsinki', 10)
]
route_flows(3, demands3)
