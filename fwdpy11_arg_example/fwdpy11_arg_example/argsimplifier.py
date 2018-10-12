import numpy as np
import msprime
import time
import itertools


class ArgSimplifier(object):
    """
    Python class to interface between an
    AncestryTracker and msprime
    """

    from .wfarg import reverse_time
    from .wfarg import update_indexes

    def __init__(self, gc_interval, trees=None):
        """
        :param gc_interval: Garbage collection interval
        :param trees: An instance of :class:`msprime.TreeSequence`
        """
        self.gc_interval = gc_interval
        self.last_gc_time = 0.0
        self.__nodes = msprime.NodeTable()
        self.__edges = msprime.EdgeTable()
        self.__process = True
        if trees is not None:
            self.__process = False
            trees.dump_tables(nodes=self.__nodes, edges=self.__edges)
        self.__time_sorting = 0.0
        self.__time_appending = 0.0
        self.__time_simplifying = 0.0
        self.__time_prepping = 0.0

    def simplify(self, generation, ancestry):
        # print(type(ancestry))
        # update node times:
        if self.__nodes.num_rows > 0:
            tc = self.__nodes.time
            dt = float(generation) - self.last_gc_time
            tc += dt
            self.last_gc_time = generation
            flags = np.ones(self.__nodes.num_rows, dtype=np.uint32)
            self.__nodes.set_columns(
                flags=flags, population=self.__nodes.population, time=tc)

        before = time.process_time()
        # Acquire mutex 
        ancestry.acquire()
        self.reverse_time(ancestry.nodes)
        na = np.array(ancestry.nodes, copy=False)
        ea = np.array(ancestry.edges, copy=False)
        new_min_id = na['id'][0]
        new_max_id = na['id'][-1]
        delta = new_min_id - len(self.__nodes)
        if delta != 0:
            self.update_indexes(ancestry.edges,ancestry.samples,delta, new_min_id, new_max_id)
        samples = np.array(ancestry.samples, copy=False)
        flags = np.ones(len(na), dtype=np.uint32)
        self.__time_prepping += time.process_time() - before

        before = time.process_time()
        clen = len(self.__nodes)
        self.__nodes.append_columns(flags=flags,
                                    population=na['population'],
                                    time=na['generation'])
        # Copy the already sorted edges to local arrays
        left = self.__edges.left[:]
        right = self.__edges.right[:]
        parent = self.__edges.parent[:]
        child = self.__edges.child[:]
        # Get the new edges and reverse them. After this, we know that all edges
        # are correctly sorted with respect to time. We then sort each time slice
        # individually, reducing the overall cost of the sort.
        new_left = ea['left'][::-1]
        new_right = ea['right'][::-1]
        new_parent = ea['parent'][::-1]
        new_child = ea['child'][::-1]

        parent_time = self.__nodes.time[new_parent]
        breakpoints = np.where(parent_time[1:] != parent_time[:-1])[0] + 1
        self.__edges.reset()
        self.__time_appending += time.process_time() - before

        before = time.process_time()
        start = 0
        for end in itertools.chain(breakpoints, [-1]):
            assert np.all(parent_time[start: end] == parent_time[start])
            self.__edges.append_columns(left=new_left[start: end],
                                        right=new_right[start: end],
                                        parent=new_parent[start: end],
                                        child=new_child[start: end])
            msprime.sort_tables(nodes=self.__nodes,
                                edges=self.__edges,
                                edge_start=start)
            start = end
        self.__time_sorting += time.process_time() - before

        # Append the old sorted edges to the table.
        self.__edges.append_columns(
            left=left, right=right, parent=parent, child=child)
        before = time.process_time()
        msprime.simplify_tables(samples=samples.tolist(),
                                nodes=self.__nodes, edges=self.__edges)

        # Release any locks on the ancestry object
        ancestry.release()
        self.__last_edge_start = len(self.__edges)
        self.__time_simplifying += time.process_time() - before
        self.__process = True
        return (True, self.__nodes.num_rows)

    def __call__(self, generation, ancestry):
        """
        This is called from C++ during a simulation.

        :param generation: Current generation in a simulation.
        :param ancestry: An instance of AncestryTracker

        :rtype: tuple

        :returns: A bool and an int
        """
        if generation > 0 and generation % self.gc_interval == 0.0:
            return self.simplify(generation, ancestry)
        # Keep tuple size constant,
        # for sake of sanity.
        return (False, None)

    @property
    def nodes(self):
        """
        A NumPy record array representing the nodes.
        """
        return self.__nodes

    @property
    def edges(self):
        """
        A NumPy record array representing the edge sets.
        """
        return self.__edges

    @property
    def gc_interval(self):
        """
        The GC interval
        """
        return self.__gc_interval

    @gc_interval.setter
    def gc_interval(self, value):
        try:
            int(value)
        except:
            raise ValueError("GC interval must be an integer")
        if value <= 0:
            raise ValueError("GC interval must be and integer > 0")
        self.__gc_interval = int(value)

    @property
    def last_gc_time(self):
        """
        The last time GC was performed
        """
        return self.__last_gc_time

    @last_gc_time.setter
    def last_gc_time(self, value):
        self.__last_gc_time = float(value)

    @property
    def times(self):
        """
        A dict representing times spent in various
        steps.
        """
        return {'prepping': self.__time_prepping,
                'sorting': self.__time_sorting,
                'appending': self.__time_appending,
                'simplifying': self.__time_simplifying}
