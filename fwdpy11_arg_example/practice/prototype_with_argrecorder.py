# Prototype of our C++ implementation
# in Python using NumPy arrays and
# a VERY simple W-F simulations.
# Similar to what is in ftprime
# test suite, but with diploids.
# The data structures map to what
# I'm doing on the C++ side.
# NumPy arrays containing node_dy
# and edge_dt
# are built up the same way that
# I'm populating vector<node> and
# vector<edge>.

import numpy as np
import msprime
import sys
import ftprime

node_dt = np.dtype([('id', np.uint32),
                    ('generation', np.float),
                    ('population', np.int32)])

edge_dt = np.dtype([('left', np.float),
                    ('right', np.float),
                    ('parent', np.int32),
                    ('child', np.int32)])


class MockAncestryTracker(object):
    """
    Mimicking the public API of AncestryTracker.
    """
    __nodes = None
    __edges = None

    def __init__(self):
        self.nodes = np.empty([0], dtype=node_dt)
        self.edges = np.empty([0], dtype=edge_dt)

    @property
    def nodes(self):
        return self.__nodes

    @nodes.setter
    def nodes(self, value):
        self.__nodes = value

    @property
    def edges(self):
        return self.__edges

    @edges.setter
    def edges(self, value):
        self.__edges = value


def xover():
    breakpoint = np.random.sample()
    while breakpoint == 0.0 or breakpoint == 1.0:
        breakpoint = np.random.sample()
    return breakpoint


def wf(N, tracker, ngens, args):
    """
    For N diploids, the diploids list contains 2N values.
    For the i-th diploids, diploids[2*i] and diploids[2*i+1]
    represent the two chromosomes.

    We simulate constant N here, according to a Wright-Fisher
    scheme:

    1. Pick two parental indexes, each [0,N-1]
    2. The two chromosome ids are diploids[2*p] and diploids[2*p+1]
       for each parental index 'p'.
    3. We pass one parental index on to each offspring, according to
       Mendel, which means we swap parental chromosome ids 50% of the time.
    4. We do a single crossover for every mating, just so that there are
       a lot of breakpoints to handle
    """
    diploids = np.arange(2 * N, dtype=np.uint32)
    # so we pre-allocate the space. We only need
    # to do this once b/c N is constant.
    tracker.nodes = np.empty([2 * N * (ngens + 1)], dtype=node_dt)
    tracker.nodes['id'][:len(diploids)] = diploids
    tracker.nodes['generation'][:len(diploids)] = 0.0
    # Our simple WF sim makes 1 xover per parent
    # in each mating.  Thus, each offspring inherits
    # two new edges, and 4N new edges are formed each generation.
    tracker.edges = np.empty([ngens * 4 * N], dtype=edge_dt)
    edge_index = int(0)
    node_id = int(len(diploids))
    next_id = len(diploids)  # This will be the next unique ID to use
    assert(max(diploids) < next_id)
    for gen in range(ngens):
        # Empty offspring list.
        # We also use this to mark the "samples" for simplify
        new_diploids = np.empty([len(diploids)], dtype=diploids.dtype)

        # Pick 2N parents:
        parents = np.random.randint(0, N, 2 * N)
        assert(parents.max() < N)
        dip = int(0)  # dummy index for filling contents of new_diploids

        # Iterate over our chosen parents via fancy indexing.
        for parent1, parent2 in zip(parents[::2], parents[1::2]):
            args.add_individual(input_id=next_id, time=gen+1)
            # p1g1 = parent 1, gamete (chrom) 1, etc.:
            p1g1, p1g2 = diploids[2 * parent1], diploids[2 * parent1 + 1]
            p2g1, p2g2 = diploids[2 * parent2], diploids[2 * parent2 + 1]
            assert(p1g2 - p1g1 == 1)
            assert(p2g2 - p2g1 == 1)

            # Apply Mendel to p1g1 et al.
            mendel = np.random.random_sample(2)
            if mendel[0] < 0.5:
                p1g1, p1g2 = p1g2, p1g1
            if mendel[1] < 0.5:
                p2g1, p2g2 = p2g2, p2g1

            # We'll make every mating have 1 x-over
            # in each parent

            # Crossing-over and edges due to
            # contribution from parent 1
            breakpoint = xover()

            # Add the edges. Parent 1 will contribute [0,breakpoint)
            # from p1g1 and [breakpoint,1.0) from p1g2. Note that
            # we've already done the Mendel thing above. Both of these
            # segments are inherited by the next diploid, whose value
            # is next_id
            tracker.edges[edge_index] = (0.0, breakpoint, p1g1, next_id)
            tracker.edges[edge_index + 1] = (breakpoint, 1.0, p1g2, next_id)
            args.add_record(left=0.0, right=breakpoint, parent=p1g1, children=(next_id,))
            args.add_record(left=breakpoint, right=1.0, parent=p1g2, children=(next_id,))

            # Update offspring container for
            # offspring dip, chrom 1:
            new_diploids[2 * dip] = next_id

            # Add new node for offpsring dip, chrom 1
            tracker.nodes[node_id] = (next_id, gen + 1, 0)

            # Repeat process for parent 2's contribution.
            args.add_individual(input_id=next_id+1, time=gen+1)
            # Stuff is now being inherited by node next_id + 1
            breakpoint = xover()
            tracker.edges[edge_index +
                          2] = (0.0, breakpoint, p2g1, next_id + 1)
            tracker.edges[edge_index +
                          3] = (breakpoint, 1.0, p2g2, next_id + 1)
            args.add_record(left=0.0, right=breakpoint, parent=p2g1, children=(next_id+1,))
            args.add_record(left=breakpoint, right=1.0, parent=p2g2, children=(next_id+1,))

            new_diploids[2 * dip + 1] = next_id + 1

            tracker.nodes[node_id + 1] = (next_id + 1, gen + 1, 0)

            # python -O to turn this stuff off
            # if __debug__:
            #     print("generation ", gen, diploids.min(), diploids.max(),
            #           tracker.edges[edge_index:edge_index + 4])

            # Update our dummy variables.
            # We have two new nodes,
            # have used up two ids,
            # processed one diploid (offspring),
            # and added 4 edges
            node_id += 2
            next_id += 2
            dip += 1
            edge_index += 4
            print("dips:", diploids)
            print("next dips:", new_diploids)

        assert(dip == N)
        assert(len(new_diploids) == 2 * N)
        diploids = new_diploids
        assert(max(diploids) < next_id)

    return (diploids)


def expensive_check(popsize, edges, nodes):
    """
    A brute-force post-hoc check of the
    nodes and edges that we generated
    in the simulation
    """
    assert(len(edges) == 10 * popsize * 4 * popsize)

    # Check that all parent/child IDs are
    # in expected range.
    for gen in range(1, 10 * popsize + 1):
        min_parental_id = 2 * popsize * (gen - 1)
        max_parental_id = 2 * popsize * (gen - 1) + 2 * popsize
        min_child_id = max_parental_id
        max_child_id = min_child_id + 2 * popsize

        node_gen_m1 = nodes[np.argwhere(
            nodes['generation'] == float(gen - 1)).flatten()]
        assert(len(node_gen_m1) == 2 * popsize)
        if any(i < min_parental_id or i >= max_parental_id for i in node_gen_m1['id']) is True:
            raise RuntimeError("generation", gen - 1, "confused")

        node_gen = nodes[np.argwhere(
            nodes['generation'] == float(gen)).flatten()]
        assert(len(node_gen) == 2 * popsize)
        if any(i < min_child_id or i >= max_child_id for i in node_gen['id']) is True:
            raise RuntimeError("generation", gen, "confused")

        edges_gen = edges[(gen - 1) * 4 * popsize:(gen - 1)
                          * 4 * popsize + 4 * popsize]

        if any(i not in node_gen_m1['id'] for i in edges_gen['parent']) is True:
            raise RuntimeError(
                "parent not found in expected slice of node table")

        if any(i not in node_gen['id'] for i in edges_gen['child']) is True:
            raise RuntimeError(
                "child not found in expected slice of node table")

        if any(i < min_parental_id or i >= max_parental_id for i in edges_gen['parent']) is True:
            raise RuntimeError("Bad parent")

        if any(i < min_child_id or i >= max_child_id for i in edges_gen['child']) is True:
            raise RuntimeError("Bad child")
    assert(float(gen) == nodes['generation'].max())


if __name__ == "__main__":
    popsize = int(sys.argv[1])
    theta = float(sys.argv[2])
    nsam = int(sys.argv[3])  # sample size to take and add mutations to
    seed = int(sys.argv[4])

    np.random.seed(seed)

    tracker = MockAncestryTracker()
    args = ftprime.ARGrecorder(node_ids=enumerate(range(2*popsize)), ts=msprime.simulate(2*popsize))
    samples = wf(popsize, tracker, 10 * popsize, args)

    args.simplify(samples=range(10*popsize*2*popsize, (10*popsize+1)*2*popsize))
    ts = args.tree_sequence()
    # for x in ts.dump_tables():
    #     print(x)
    MRCAS=[t.get_time(t.get_root()) for t in ts.trees()]
    print("ARGrecorder MRCAS:", MRCAS)

    # Check that our sample IDs are as expected:
    if __debug__:
        min_sample = 10 * popsize * 2 * popsize
        max_sample = 10 * popsize * 2 * popsize + 2 * popsize
        if any(i < min_sample or i >= max_sample for i in samples) is True:
            raise RuntimeError("Houston, we have a problem.")

    # Make local names for convenience
    nodes = tracker.nodes
    edges = tracker.edges

    if __debug__:
        expensive_check(popsize, edges, nodes)

    max_gen = nodes['generation'].max()
    assert(int(max_gen) == 10 * popsize)

    # Convert node times from forwards to backwards
    nodes['generation'] = nodes['generation'] - max_gen
    nodes['generation'] = nodes['generation'] * -1.0

    # Construct and populate msprime's tables
    flags = np.empty([len(nodes)], dtype=np.uint32)
    flags.fill(1)
    nt = msprime.NodeTable()
    nt.set_columns(flags=flags,
                   population=nodes['population'],
                   time=nodes['generation'])

    es = msprime.EdgeTable()
    es.set_columns(left=edges['left'],
                   right=edges['right'],
                   parent=edges['parent'],
                   child=edges['child'])

    # Sort
    msprime.sort_tables(nodes=nt, edges=es)

    # Simplify: this is where the magic happens
    msprime.simplify_tables(samples=samples.tolist(), nodes=nt, edges=es)

    # Create a tree sequence
    x = msprime.load_tables(nodes=nt, edges=es)

    # Lets look at the MRCAS.
    # This is where things go badly:
    MRCAS=[t.get_time(t.get_root()) for t in x.trees()]
    print("other MRCAS", MRCAS)


    # Throw down some mutations
    # onto a sample of size nsam
    nt_s = msprime.NodeTable()
    es_s = msprime.EdgeTable()

    nsam_samples = np.random.choice(2 * popsize, nsam, replace=False)
    xs = x.simplify(nsam_samples.tolist())
    xs.dump_tables(nodes=nt_s, edges=es_s)
    msp_rng = msprime.RandomGenerator(seed)
    mutations = msprime.MutationTable()
    sites = msprime.SiteTable()
    mutgen = msprime.MutationGenerator(msp_rng, theta / float(4 * popsize))
    mutgen.generate(nt_s, es_s, sites, mutations)
    x = msprime.load_tables(nodes=nt_s, edges=es_s,
                            sites=sites, mutations=mutations)
    print(sites.num_rows)

