#include "handle_recombination.hpp"
#include <fwdpp/debug.hpp>
#include <fwdpp/recombination.hpp>

namespace py = pybind11;

std::pair<std::vector<std::pair<double, double>>,
          std::vector<std::pair<double, double>>>
split_breakpoints(const std::vector<double>& breakpoints, const double start,
                  const double stop)
{
    std::vector<std::pair<double, double>> r1, r2;
    if (breakpoints.front() != 0.0)
        {
            r1.emplace_back(std::make_pair(start, breakpoints.front()));
        }
    for (unsigned j = 1; j < breakpoints.size(); ++j)
        {
            double a = breakpoints[j - 1];
            double b = (j < breakpoints.size() - 1) ? breakpoints[j] : stop;
            if (j % 2 == 0.)
                {
                    r1.emplace_back(a, b);
                }
            else
                {
                    r2.emplace_back(a, b);
                }
        }
    return std::make_pair(std::move(r1), std::move(r2));
}

KTfwd::uint_t
ancestry_recombination_details(
    fwdpy11::singlepop_t& pop, ancestry_tracker& ancestry,
    std::queue<std::size_t>& gamete_recycling_bin,
    const KTfwd::uint_t parental_gamete1, const KTfwd::uint_t parental_gamete2,
    std::vector<double>& breakpoints,
    const std::tuple<ancestry_tracker::integer_type,
                     ancestry_tracker::integer_type>& pid,
    const ancestry_tracker::integer_type offspring_index)
{
	// This has the effect of removing any double x-overs.
	// Internally, fwdpp will do the right thing, but leaving
	// them in causes msprime to throw an error.  We could filter them
	// later, but doing it here is less code.
    breakpoints.erase(std::unique(breakpoints.begin(), breakpoints.end()),
                      breakpoints.end());
    if (breakpoints.empty())
        {
            ancestry.temp.emplace_back(
                make_edge(0., 1., std::get<0>(pid), offspring_index));
            return parental_gamete1;
        }
    auto breakpoints_per_parental_chrom = split_breakpoints(breakpoints);
    ancestry.add_edges(breakpoints_per_parental_chrom.first, std::get<0>(pid),
                       offspring_index);
    ancestry.add_edges(breakpoints_per_parental_chrom.second, std::get<1>(pid),
                       offspring_index);
    return KTfwd::recombine_gametes(
        breakpoints, pop.gametes, pop.mutations, parental_gamete1,
        parental_gamete2, gamete_recycling_bin, pop.neutral, pop.selected);
}
