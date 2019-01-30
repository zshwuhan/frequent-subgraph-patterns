import random

import numpy as np

from collections import Counter, defaultdict

from datetime import datetime, timedelta

from graph.simple_graph import SimpleGraph

from subgraph.util import make_subgraph
from subgraph.pattern import canonical_label

from sampling.subgraph_reservoir import SubgraphReservoir
from sampling.skip_rs import SkipRS

from algorithms.exploration.optimized_quadruplet import get_new_subgraphs

from util.set import flatten

class IncerementalOptimizedReservoirAlgorithm:
    k = None
    M = None # reservoir size
    N = None # number of subgraphs seen
    s = None # number of surplus subgraps to skip this iteration

    graph = None
    patterns = None
    reservoir = None
    skip_rs = None
    metrics = None


    def __init__(self, k, M):
        self.k = k
        self.M = M
        self.N = 0
        self.s = 0

        self.graph = SimpleGraph()
        self.patterns = Counter()
        self.reservoir = SubgraphReservoir()
        self.skip_rs = SkipRS(M)
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
        subgraph_candidates = list(get_new_subgraphs(self.graph, u, v, self.k))

        W = len(subgraph_candidates)
        I = 0 # number of subgraph candidates to include in sample

        if len(self.reservoir) < self.M:
            # if the reservoir is not full,
            # we must include the next M - N subgraphs
            I = min(W, self.M - len(self.reservoir))
            self.s = I
            self.N += I

        # determine the number of candidates I to include in the sample
        while self.s < W:
            I += 1
            Z_rs = self.skip_rs.apply(self.N)
            self.N += Z_rs + 1
            self.s += Z_rs + 1

        # sample I subgraphs from the W candidates
        if I < W:
            additions = random.sample(subgraph_candidates, I)
        else:
            additions = subgraph_candidates

        # add all sampled subgraphs
        for nodes in additions:
            edges = self.graph.get_induced_edges(nodes)
            subgraph = make_subgraph(nodes, edges+[edge])
            self.add_subgraph(subgraph)

        s_add_end = datetime.now()

        self.graph.add_edge(edge)
        self.s -= W

        e_add_end = datetime.now()

        ms = timedelta(microseconds=1)
        self.metrics['edge_add_ms'].append((e_add_end - e_add_start) / ms)
        self.metrics['subgraph_add_ms'].append((s_add_end - s_add_start) / ms)
        self.metrics['subgraph_replace_ms'].append((s_rep_end - s_rep_start) / ms)
        self.metrics['new_subgraph_count'].append(W)
        self.metrics['included_subgraph_count'].append(I)
        self.metrics['reservoir_full_bool'].append(int(len(self.reservoir) >= self.M))
        self.metrics['skiprs_treshold_bool'].append(int(self.skip_rs.is_threshold_reached(self.N)))

        return True


    def add_subgraph(self, subgraph):
        if len(self.reservoir) >= self.M:
            self.remove_subgraph_from_reservoir(self.reservoir.random())

        self.add_subgraph_to_reservoir(subgraph)


    def add_subgraph_to_reservoir(self, subgraph):
        self.reservoir.add(subgraph)
        self.patterns.update([canonical_label(subgraph)])


    def remove_subgraph_from_reservoir(self, subgraph):
        self.reservoir.remove(subgraph)
        self.patterns.subtract([canonical_label(subgraph)])
