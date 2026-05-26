from typing import Dict, Tuple
import pulp
import matplotlib.pyplot as plt
import networkx as nx


class DisplayResults:
    def __init__(
        self,
        graph: nx.DiGraph,
    ):
        self.graph = graph


    def _get_active_links(
        self,
        alpha: Dict[Tuple[int, str, str], pulp.LpVariable],
    ):
        active = set()
        for (_, u, v), var in alpha.items():
            if var.value() == 1:
                active.add((u, v))
        return active


    def print_active_links(
        self,
        alpha: Dict[Tuple[int, str, str], pulp.LpVariable],
    ):
        active_links = self._get_active_links(alpha)
        print('[INFO]: Active links:')
        for link in active_links:
            print(f"\t{link}")


    def draw_network(
        self,
        alpha: Dict[Tuple[int, str, str], pulp.LpVariable],
        title: str = "Graph"
    ):
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(self.graph, seed=42)

        nx.draw(self.graph, pos, with_labels=True, node_size=2200, font_size=10, arrows=True)

        if alpha:
            active_links = self._get_active_links(alpha)
            nx.draw_networkx_edges(self.graph, pos, edgelist=list(active_links), width=4)

        edge_labels = {
            (u, v): f"capacity={d.get('capacity','?')}" for u, v, d in self.graph.edges(data=True)
        }
        nx.draw_networkx_edge_labels(self.graph, pos, edge_labels=edge_labels, font_size=8)

        plt.title(title)
        plt.axis("off")
        plt.show()


    @staticmethod
    def print_header(number: int):
        print(f"---------- SCENARIO {number} ----------")
