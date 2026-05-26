# pylint: disable=too-many-locals, invalid-name
from typing import Dict, Any, Optional, Tuple
import pulp
import networkx as nx


class ILPRouting:
    def __init__(
        self,
        graph:  nx.DiGraph,
        r_max:  Dict[Any, int], # switch rule capacity
        solver: Optional[pulp.LpSolver] = None,
    ):
        self.graph  = graph
        self.r_max  = r_max
        self.solver = solver if solver is not None else pulp.PULP_CBC_CMD(msg=False)


    def solve_routing_ilp(
        self,
        flows: Dict[int, Dict[str, Any]],
    ):
        L = list(self.graph.edges())
        V = list(self.graph.nodes())

        C = {(u, v): float(self.graph[u][v].get("capacity", 0.0)) for (u, v) in L}
        b = {f: float(flows[f]["bandwidth"]) for f in flows}
        s = {f: flows[f]["source"] for f in flows}
        t = {f: flows[f]["target"] for f in flows}

        prob = pulp.LpProblem("ILP_MinActiveLinks_RuleCap", pulp.LpMinimize)

        alpha = {(f, u, v): pulp.LpVariable(f"alpha_{f}_{u}_{v}", cat="Binary")
                 for f in flows for (u, v) in L}

        x = {(u, v): pulp.LpVariable(f"x_{u}_{v}", cat="Binary") for (u, v) in L}
        for (u, v) in L:
            for f in flows:
                prob += alpha[(f, u, v)] <= x[(u, v)], f"LinkActive_{f}_{u}_{v}"

        R_util = {v: pulp.LpVariable(f"Rutil_{v}", lowBound=0, cat="Integer") for v in V}

        C_util = {(u, v): pulp.LpVariable(f"Cutil_{u}_{v}", lowBound=0) for (u, v) in L}
        C_res  = {(u, v): pulp.LpVariable(f"Cres_{u}_{v}",  lowBound=0) for (u, v) in L}

        r_max = pulp.LpVariable("r_max", lowBound=0, upBound=1)

        y = {(u, v): pulp.LpVariable(f"y_{u}_{v}", lowBound=0, upBound=1) for (u, v) in L}

        # Linearization helpers
        w = {(f, u, v): pulp.LpVariable(f"w_{f}_{u}_{v}", lowBound=0, upBound=1)
             for f in flows for (u, v) in L}
        z = {(f, u, v): pulp.LpVariable(f"z_{f}_{u}_{v}", lowBound=0, upBound=1)
             for f in flows for (u, v) in L}

        # Flow conservation rule
        for f in flows:
            for v in V:
                outflow = pulp.lpSum(alpha[(f, v, w_)]
                                     for w_ in self.graph.successors(v)
                                     if (v, w_) in C)
                inflow  = pulp.lpSum(alpha[(f, u_, v)]
                                     for u_ in self.graph.predecessors(v)
                                     if (u_, v) in C)

                if v == s[f]:
                    prob += (outflow - inflow == 1),  f"FlowCons_{f}_{v}_src"
                elif v == t[f]:
                    prob += (outflow - inflow == -1), f"FlowCons_{f}_{v}_dst"
                else:
                    prob += (outflow - inflow == 0),  f"FlowCons_{f}_{v}_mid"

                # No flow splitting
                prob += pulp.lpSum(alpha[(f,v,w)] for w in self.graph.successors(v)) <= 1
                prob += pulp.lpSum(alpha[(f,u,v)] for u in self.graph.predecessors(v)) <= 1

            for (u, v) in L:
                a = alpha[(f, u, v)]
                # Linearization: w = r_max * alpha
                prob += (w[(f, u, v)] <= r_max),                 f"Lin_w1_{f}_{u}_{v}"
                prob += (w[(f, u, v)] <= a),                     f"Lin_w2_{f}_{u}_{v}"
                prob += (w[(f, u, v)] >= r_max - (1 - a)),       f"Lin_w3_{f}_{u}_{v}"

                # Linearization: z = y * alpha
                prob += (z[(f, u, v)] <= y[(u, v)]),             f"Lin_z1_{f}_{u}_{v}"
                prob += (z[(f, u, v)] <= a),                     f"Lin_z2_{f}_{u}_{v}"
                prob += (z[(f, u, v)] >= y[(u, v)] - (1 - a)),   f"Lin_z3_{f}_{u}_{v}"

        for v in V:
            prob += (
                R_util[v] ==
                pulp.lpSum(alpha[(f, v, w_)]
                           for f in flows
                           for w_ in self.graph.successors(v)
                           if (v, w_) in C),
                f"Def_Rutil_{v}"
            )
            prob += (R_util[v] <= int(self.r_max[v])), f"RuleCap_{v}"
            prob += (R_util[v] <= r_max * float(self.r_max[v])), f"MaxRuleUtil_{v}"

        for (u, v) in L:
            prob += (
                C_util[(u, v)] ==
                pulp.lpSum(alpha[(f, u, v)] * b[f] for f in flows),
                f"Def_Cutil_{u}_{v}"
            )
            prob += (C_res[(u, v)] == C[(u, v)] - C_util[(u, v)]), f"Def_Cres_{u}_{v}"
            prob += (C_res[(u, v)] >= 0), f"CresNonNeg_{u}_{v}"
            prob += (C_util[(u, v)] <= C[(u, v)]), f"LinkCap_{u}_{v}"
            prob += (C_util[(u, v)] == y[(u, v)] * C[(u, v)]), f"Def_y_{u}_{v}"

        M = 10_000
        primary_obj = pulp.lpSum(x[(u, v)] for (u, v) in L)
        secondary_obj = pulp.lpSum(
            alpha[(f, u, v)] + w[(f, u, v)] + z[(f, u, v)]
            for f in flows for (u, v) in L
        )
        prob += M * primary_obj + secondary_obj

        prob.solve(self.solver)

        return prob, alpha


    def _calculate_paths(
        self,
        flows: Dict[int, Dict[str, Any]],
        alpha: Dict[Tuple[int, str, str], pulp.LpVariable],
    ):
        paths = {}
        for flow_id, flow_data in flows.items():
            source = flow_data["source"]
            target = flow_data["target"]
            nodes_outgoing = {}

            for (var_flow_id, u, v), var in alpha.items():
                if var_flow_id != flow_id or var.value() == 0:
                    continue
                if var.value() == 1:
                    nodes_outgoing[u] = v

            if source not in nodes_outgoing:
                paths[flow_id] = None
                continue

            reconstructed_path = [source]
            current_node       = source
            success            = True

            while current_node != target:
                next_node = nodes_outgoing.get(current_node, None)
                if not next_node:
                    success = False
                    break

                reconstructed_path.append(next_node)
                current_node = next_node

            paths[flow_id] = reconstructed_path if success else None

        return paths


    def print_paths(
        self,
        flows: Dict[int, Dict[str, Any]],
        alpha: Dict[Tuple[int, str, str], pulp.LpVariable],
    ):
        paths = self._calculate_paths(flows, alpha)
        print('[INFO]: Paths for each demand:')
        for i, path in paths.items():
            print(f"\t{i}: {path}")
