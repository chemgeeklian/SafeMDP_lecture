from __future__ import division, print_function, absolute_import

import numpy as np

from .utilities import max_out_degree

__all__ = ['SafeMDP', 'link_graph_and_safe_set', 'reachable_set',
           'returnable_set']


class SafeMDP(object):
    """Base class for safe exploration in MDPs.

    This class only provides basic options to compute the safely reachable
    and returnable sets. The actual update of the safety feature must be done
    in a class that inherits from `SafeMDP`. See `safempd.GridWorld` for an
    example.

    Parameters
    ----------
    graph: networkx.DiGraph
        The graph that models the MDP. Each edge has an attribute `safe` in its
        metadata, which determines the safety of the transition.
    gp: GPy.core.GPRegression
        A Gaussian process model that can be used to determine the safety of
        transitions. Exact structure depends heavily on the usecase.
    S_hat0: boolean array
        An array that has True on the ith position if the ith node in the graph
        is part of the safe set.
    h: float
        The safety threshold.
    L: float
        The lipschitz constant
    beta: float, optional
        The confidence interval used by the GP model.
    """
    def __init__(self, graph, gp, S_hat0, h, L, beta=2):
        super(SafeMDP, self).__init__()
        # Scalar for gp confidence intervals
        self.beta = beta

        # Threshold
        self.h = h

        # Lipschitz constant
        self.L = L

        # GP model
        self.gp = gp

        self.graph = graph
        self.graph_reverse = self.graph.reverse()

        num_nodes = self.graph.number_of_nodes()
        num_edges = max_out_degree(graph)
        safe_set_size = (num_nodes, num_edges + 1)

        self.reach = np.empty(safe_set_size, dtype=np.bool)
        self.G = np.empty(safe_set_size, dtype=np.bool)

        self.S_hat = S_hat0.copy()
        self.S_hat0 = self.S_hat.copy()
        self.initial_nodes = self.S_hat0[:, 0].nonzero()[0].tolist()

    def compute_S_hat(self):
        """Compute the safely reachable set given the current safe_set."""
        self.reach[:] = False
        reachable_set(self.graph, self.initial_nodes, out=self.reach)

        self.S_hat[:] = False
        returnable_set(self.graph, self.graph_reverse, self.initial_nodes,
                       out=self.S_hat)

        self.S_hat &= self.reach

    def add_gp_observations(self, x_new, y_new):
        """Add observations to the gp mode."""
        # Update GP with observations
        self.gp.set_XY(np.vstack((self.gp.X,
                                  x_new)),
                       np.vstack((self.gp.Y,
                                  y_new)))


def link_graph_and_safe_set(graph, safe_set):
    """Link the safe set to the graph model.

    Parameters
    ----------
    graph: nx.DiGraph()
    safe_set: np.array
        Safe set. For each node the edge (i, j) under action (a) is linked to
        safe_set[i, a]
    """
    for node, next_node in graph.edges():
        edge = graph[node][next_node]
        edge['safe'] = safe_set[node:node + 1, edge['action']]


def reachable_set(graph, initial_nodes, out=None):
    """
    Compute the safe, reachable set of a graph

    Parameters
    ----------
    graph: nx.DiGraph
        Directed graph. Each edge must have associated action metadata,
        which specifies the action that this edge corresponds to.
        Each edge has an attribute ['safe'], which is a boolean that
        indicates safety
    initial_nodes: list
        List of the initial, safe nodes that are used as a starting point to
        compute the reachable set.
    out: np.array
        The array to write the results to. Is assumed to be False everywhere
        except at the initial nodes

    Returns
    -------
    reachable_set: np.array
        Boolean array that indicates whether a node belongs to the reachable
        set.
    """

    if not initial_nodes:
        raise AttributeError('Set of initial nodes needs to be non-empty.')

    if out is None:
        visited = np.zeros((graph.number_of_nodes(),
                            max_out_degree(graph) + 1),
                           dtype=np.bool)
    else:
        visited = out

    # All nodes in the initial set are visited
    visited[initial_nodes, 0] = True

    stack = list(initial_nodes)

    # TODO: rather than checking if things are safe, specify a safe subgraph?
    while stack:
        node = stack.pop(0)
        # iterate over edges going away from node
        for _, next_node, data in graph.edges(node, data=True):
            action = data['action']
            if not visited[node, action] and data['safe']:
                visited[node, action] = True
                if not visited[next_node, 0]:
                    stack.append(next_node)
                    visited[next_node, 0] = True

    if out is None:
        return visited


def returnable_set(graph, reverse_graph, initial_nodes, out=None):
    """
    Compute the safe, returnable set of a graph

    Parameters
    ----------
    graph: nx.DiGraph
        Directed graph. Each edge must have associated action metadata,
        which specifies the action that this edge corresponds to.
        Each edge has an attribute ['safe'], which is a boolean that
        indicates safety
    reverse_graph: nx.DiGraph
        The reversed directed graph, `graph.reverse()`
    initial_nodes: list
        List of the initial, safe nodes that are used as a starting point to
        compute the returnable set.
    out: np.array
        The array to write the results to. Is assumed to be False everywhere
        except at the initial nodes

    Returns
    -------
    returnable_set: np.array
        Boolean array that indicates whether a node belongs to the returnable
        set.
    """

    if not initial_nodes:
        raise AttributeError('Set of initial nodes needs to be non-empty.')

    if out is None:
        visited = np.zeros((graph.number_of_nodes(),
                            max_out_degree(graph) + 1),
                           dtype=np.bool)
    else:
        visited = out

    # All nodes in the initial set are visited
    visited[initial_nodes, 0] = True

    stack = list(initial_nodes)

    # TODO: rather than checking if things are safe, specify a safe subgraph?
    while stack:
        node = stack.pop(0)
        # iterate over edges going into node
        for _, prev_node in reverse_graph.edges(node):
            data = graph.get_edge_data(prev_node, node)
            if not visited[prev_node, data['action']] and data['safe']:
                visited[prev_node, data['action']] = True
                if not visited[prev_node, 0]:
                    stack.append(prev_node)
                    visited[prev_node, 0] = True

    if out is None:
        return visited
