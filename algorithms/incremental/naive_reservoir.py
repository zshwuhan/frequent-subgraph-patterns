import numpy as np

from collections import Counter, defaultdict

from datetime import datetime, timedelta

from graph.simple_graph import SimpleGraph

from subgraph.util import make_subgraph
from subgraph.pattern import canonical_label

from sampling.subgraph_reservoir import SubgraphReservoir

from algorithms.exploration.optimized_quadruplet import get_new_subgraphs

from util.set import flatten

class IncrementalNaiveReservoirAlgorithm:
    k = None
    M = None # reservoir size
    N = None # number of subgraphs seen
    graph = None
    patterns = None
    reservoir = None
    metrics = None


    def __init__(self, k, M):
        self.k = k
        self.M = M
        self.N = 0

        self.graph = SimpleGraph()
        self.patterns = Counter()
        self.reservoir = SubgraphReservoir()
        self.metrics = defaultdict(list)


    def add_edge(self, edge):
        if edge in self.graph:
            return False

        e_add_start = datetime.now()

        u = edge.get_u()
        v = edge.get_v()

        # replace update all existing subgraphs with u and v in the reservoir
        s_rep_start = datetime.now()
        for s in self.reservoir.get_common_subgraphs(u, v):
            self.remove_subgraph_from_reservoir(s)
            self.add_subgraph_to_reservoir(make_subgraph(s.nodes, s.edges+(edge,)))
        s_rep_end = datetime.now()

        # find new subgraph candidates for the reservoir
        s_add_start = datetime.now()
        additions = get_new_subgraphs(self.graph, u, v, self.k)

        # perform reservoir sampling for each new subgraph candidate
        I = 0
        for nodes in additions:
            edges = self.graph.get_induced_edges(nodes)
            subgraph = make_subgraph(nodes, edges+[edge])
            if self.add_subgraph(subgraph):
                I += 1
        s_add_end = datetime.now()

        self.graph.add_edge(edge)

        e_add_end = datetime.now()

        ms = timedelta(microseconds=1)
        self.metrics['edge_add_ms'].append((e_add_end - e_add_start) / ms)
        self.metrics['subgraph_add_ms'].append((s_add_end - s_add_start) / ms)
        self.metrics['subgraph_replace_ms'].append((s_rep_end - s_rep_start) / ms)
        self.metrics['new_subgraph_count'].append(len(additions))
        self.metrics['included_subgraph_count'].append(I)
        self.metrics['reservoir_full_bool'].append(int(len(self.reservoir) >= self.M))

        return True


    def add_subgraph(self, subgraph):
        self.N += 1

        success = False

        if len(self.reservoir) < self.M:
            success = True
        elif np.random.rand() < (self.M / float(self.N)):
            success = True
            self.remove_subgraph_from_reservoir(self.reservoir.random())

        if success:
            self.add_subgraph_to_reservoir(subgraph)

        return success


    def add_subgraph_to_reservoir(self, subgraph):
        self.reservoir.add(subgraph)
        self.patterns.update([canonical_label(subgraph)])


    def remove_subgraph_from_reservoir(self, subgraph):
        self.reservoir.remove(subgraph)
        self.patterns.subtract([canonical_label(subgraph)])
