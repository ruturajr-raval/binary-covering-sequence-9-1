#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <numeric>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

using Flow = std::vector<std::pair<int, int>>;
using Walk = std::vector<int>;

constexpr int kN = 9;
constexpr int kCandidateLength = 70;
constexpr int kExactOverlap = 61;
constexpr int kResidualMass = kCandidateLength - kExactOverlap;
constexpr int kWordCount = 1 << kN;
constexpr int kVertexCount = 1 << (kN - 1);

int edge_prefix(int edge) {
    return edge >> 1;
}

int edge_suffix(int edge) {
    return edge & (kVertexCount - 1);
}

Flow normalize_flow(const std::vector<int>& edges) {
    std::array<int, kWordCount> counts{};
    for (int edge : edges) {
        if (edge < 0 || edge >= kWordCount) {
            throw std::runtime_error("flow contains an invalid edge");
        }
        ++counts[edge];
    }
    Flow flow;
    for (int edge = 0; edge < kWordCount; ++edge) {
        if (counts[edge] > 0) {
            flow.emplace_back(edge, counts[edge]);
        }
    }
    return flow;
}

Flow add_flows(const Flow& first, const Flow& second) {
    std::array<int, kWordCount> counts{};
    for (const auto& [edge, multiplicity] : first) {
        counts[edge] += multiplicity;
    }
    for (const auto& [edge, multiplicity] : second) {
        counts[edge] += multiplicity;
    }
    Flow result;
    for (int edge = 0; edge < kWordCount; ++edge) {
        if (counts[edge] > 0) {
            result.emplace_back(edge, counts[edge]);
        }
    }
    return result;
}

int flow_mass(const Flow& flow) {
    int mass = 0;
    for (const auto& [edge, multiplicity] : flow) {
        static_cast<void>(edge);
        mass += multiplicity;
    }
    return mass;
}

bool flow_uses_forbidden(
    const Flow& flow,
    const std::array<bool, kWordCount>& forbidden
) {
    return std::any_of(
        flow.begin(),
        flow.end(),
        [&](const auto& entry) { return forbidden[entry.first]; }
    );
}

std::array<int, kVertexCount> flow_divergence(const Flow& flow) {
    std::array<int, kVertexCount> divergence{};
    for (const auto& [edge, multiplicity] : flow) {
        divergence[edge_prefix(edge)] += multiplicity;
        divergence[edge_suffix(edge)] -= multiplicity;
    }
    return divergence;
}

std::vector<int> cyclic_word_edges(int value, int length) {
    std::vector<int> bits(length);
    for (int index = 0; index < length; ++index) {
        bits[index] = (value >> (length - 1 - index)) & 1;
    }
    std::vector<int> edges;
    edges.reserve(length);
    for (int start = 0; start < length; ++start) {
        int edge = 0;
        for (int offset = 0; offset < kN; ++offset) {
            edge = (edge << 1) | bits[(start + offset) % length];
        }
        edges.push_back(edge);
    }
    return edges;
}

std::vector<std::set<Flow>> balanced_cycle_flows(int maximum_mass) {
    std::vector<std::set<Flow>> closed_walks(maximum_mass + 1);
    for (int length = 1; length <= maximum_mass; ++length) {
        for (int value = 0; value < (1 << length); ++value) {
            closed_walks[length].insert(
                normalize_flow(cyclic_word_edges(value, length))
            );
        }
    }

    std::vector<std::set<Flow>> balanced(maximum_mass + 1);
    balanced[0].insert(Flow{});
    for (int total = 1; total <= maximum_mass; ++total) {
        for (int length = 1; length <= total; ++length) {
            for (const Flow& prior : balanced[total - length]) {
                for (const Flow& closed_walk : closed_walks[length]) {
                    balanced[total].insert(add_flows(prior, closed_walk));
                }
            }
        }
        for (const Flow& flow : balanced[total]) {
            const auto divergence = flow_divergence(flow);
            if (
                flow_mass(flow) != total
                || std::any_of(
                    divergence.begin(),
                    divergence.end(),
                    [](int value) { return value != 0; }
                )
            ) {
                throw std::runtime_error("invalid balanced flow");
            }
        }
    }
    return balanced;
}

std::vector<int> load_selected_edges(const std::string& path) {
    std::ifstream stream(path);
    if (!stream) {
        throw std::runtime_error("could not open support file");
    }
    const std::string text{
        std::istreambuf_iterator<char>(stream),
        std::istreambuf_iterator<char>()
    };
    const std::string key = "\"selected_edges\"";
    const std::size_t key_position = text.find(key);
    if (key_position == std::string::npos) {
        throw std::runtime_error("support file has no selected_edges field");
    }
    const std::size_t open = text.find('[', key_position + key.size());
    const std::size_t close = text.find(']', open);
    if (
        open == std::string::npos
        || close == std::string::npos
        || close <= open
    ) {
        throw std::runtime_error("selected_edges is not an array");
    }

    std::vector<int> edges;
    std::size_t position = open + 1;
    while (position < close) {
        while (
            position < close
            && !std::isdigit(static_cast<unsigned char>(text[position]))
        ) {
            ++position;
        }
        if (position >= close) {
            break;
        }
        int value = 0;
        while (
            position < close
            && std::isdigit(static_cast<unsigned char>(text[position]))
        ) {
            value = 10 * value + (text[position] - '0');
            ++position;
        }
        edges.push_back(value);
    }
    std::sort(edges.begin(), edges.end());
    if (
        edges.size() != 64
        || std::adjacent_find(edges.begin(), edges.end()) != edges.end()
        || edges.front() < 0
        || edges.back() >= kWordCount
    ) {
        throw std::runtime_error("support must contain 64 distinct 9-bit edges");
    }
    return edges;
}

using WalkTable = std::map<std::pair<int, int>, std::vector<Walk>>;

WalkTable precompute_walks(const std::vector<int>& support) {
    std::set<int> start_vertices;
    for (int edge : support) {
        start_vertices.insert(edge_prefix(edge));
        start_vertices.insert(edge_suffix(edge));
    }

    WalkTable walks;
    for (int source : start_vertices) {
        std::vector<std::pair<int, Walk>> frontier{{source, {}}};
        for (int step = 0; step < kResidualMass; ++step) {
            std::vector<std::pair<int, Walk>> next_frontier;
            for (const auto& [vertex, path] : frontier) {
                for (int bit : {0, 1}) {
                    const int edge = (vertex << 1) | bit;
                    const int target = edge_suffix(edge);
                    Walk extended = path;
                    extended.push_back(edge);
                    walks[{source, target}].push_back(extended);
                    next_frontier.emplace_back(target, std::move(extended));
                }
            }
            frontier = std::move(next_frontier);
        }
    }
    return walks;
}

int component_count(const std::array<bool, kWordCount>& selected) {
    std::array<std::vector<int>, kVertexCount> adjacency;
    std::array<bool, kVertexCount> active{};
    for (int edge = 0; edge < kWordCount; ++edge) {
        if (!selected[edge]) {
            continue;
        }
        const int prefix = edge_prefix(edge);
        const int suffix = edge_suffix(edge);
        active[prefix] = true;
        active[suffix] = true;
        adjacency[prefix].push_back(suffix);
        adjacency[suffix].push_back(prefix);
    }

    std::array<bool, kVertexCount> seen{};
    int components = 0;
    for (int start = 0; start < kVertexCount; ++start) {
        if (!active[start] || seen[start]) {
            continue;
        }
        ++components;
        std::vector<int> stack{start};
        while (!stack.empty()) {
            const int vertex = stack.back();
            stack.pop_back();
            if (seen[vertex]) {
                continue;
            }
            seen[vertex] = true;
            for (int neighbor : adjacency[vertex]) {
                if (!seen[neighbor]) {
                    stack.push_back(neighbor);
                }
            }
        }
    }
    return components;
}

std::vector<int> uncovered_words(
    const std::array<bool, kWordCount>& selected
) {
    std::array<bool, kWordCount> covered{};
    for (int edge = 0; edge < kWordCount; ++edge) {
        if (!selected[edge]) {
            continue;
        }
        covered[edge] = true;
        for (int bit = 0; bit < kN; ++bit) {
            covered[edge ^ (1 << bit)] = true;
        }
    }
    std::vector<int> uncovered;
    for (int word = 0; word < kWordCount; ++word) {
        if (!covered[word]) {
            uncovered.push_back(word);
        }
    }
    return uncovered;
}

struct Completion {
    std::array<int, 3> omitted{};
    Flow residual;
    int support_size = 0;
    std::vector<int> uncovered;
};

struct Summary {
    int omission_sets_checked = 0;
    int precomputed_walks = 0;
    std::array<int, 4> source_histogram{};
    int active_omission_sets = 0;
    int distinct_path_flows = 0;
    int raw_decompositions = 0;
    int distinct_residual_flows = 0;
    std::map<int, int> residual_count_histogram;
    std::map<int, int> component_histogram;
    std::map<int, int> connected_support_histogram;
    std::map<int, int> connected_gap_histogram;
    std::vector<Completion> connected;
};

void enumerate_path_products(
    const std::vector<std::vector<Walk>>& options,
    std::size_t index,
    std::vector<int>& edges,
    const std::array<bool, kWordCount>& forbidden,
    const std::vector<std::set<Flow>>& balanced,
    std::set<Flow>& path_flows,
    std::set<Flow>& residual_flows,
    int& raw_decompositions
) {
    if (index == options.size()) {
        if (static_cast<int>(edges.size()) > kResidualMass) {
            return;
        }
        const Flow path_flow = normalize_flow(edges);
        path_flows.insert(path_flow);
        const int remaining = kResidualMass - static_cast<int>(edges.size());
        for (const Flow& cycle_flow : balanced[remaining]) {
            if (flow_uses_forbidden(cycle_flow, forbidden)) {
                continue;
            }
            ++raw_decompositions;
            residual_flows.insert(add_flows(path_flow, cycle_flow));
        }
        return;
    }

    for (const Walk& walk : options[index]) {
        if (edges.size() + walk.size() > kResidualMass) {
            continue;
        }
        const std::size_t prior_size = edges.size();
        edges.insert(edges.end(), walk.begin(), walk.end());
        enumerate_path_products(
            options,
            index + 1,
            edges,
            forbidden,
            balanced,
            path_flows,
            residual_flows,
            raw_decompositions
        );
        edges.resize(prior_size);
    }
}

Summary run_enumeration(const std::vector<int>& support) {
    Flow support_flow;
    for (int edge : support) {
        support_flow.emplace_back(edge, 1);
    }
    const auto support_divergence = flow_divergence(support_flow);
    if (
        std::any_of(
            support_divergence.begin(),
            support_divergence.end(),
            [](int value) { return value != 0; }
        )
    ) {
        throw std::runtime_error("reference support is not balanced");
    }

    const WalkTable walks = precompute_walks(support);
    const std::vector<std::set<Flow>> balanced = balanced_cycle_flows(
        kResidualMass
    );
    Summary summary;
    for (const auto& [endpoints, paths] : walks) {
        static_cast<void>(endpoints);
        summary.precomputed_walks += static_cast<int>(paths.size());
    }

    for (std::size_t first = 0; first < support.size(); ++first) {
        for (std::size_t second = first + 1; second < support.size(); ++second) {
            for (
                std::size_t third = second + 1;
                third < support.size();
                ++third
            ) {
                ++summary.omission_sets_checked;
                const std::array<int, 3> omitted{
                    support[first],
                    support[second],
                    support[third],
                };
                std::array<bool, kWordCount> forbidden{};
                for (int edge : omitted) {
                    forbidden[edge] = true;
                }
                std::array<bool, kWordCount> required{};
                std::array<int, kVertexCount> divergence{};
                for (int edge : support) {
                    if (forbidden[edge]) {
                        continue;
                    }
                    required[edge] = true;
                    --divergence[edge_prefix(edge)];
                    ++divergence[edge_suffix(edge)];
                }

                std::vector<int> sources;
                std::vector<int> sinks;
                for (int vertex = 0; vertex < kVertexCount; ++vertex) {
                    if (divergence[vertex] > 0) {
                        sources.insert(
                            sources.end(),
                            divergence[vertex],
                            vertex
                        );
                    } else if (divergence[vertex] < 0) {
                        sinks.insert(
                            sinks.end(),
                            -divergence[vertex],
                            vertex
                        );
                    }
                }
                if (
                    sources.size() != sinks.size()
                    || sources.empty()
                    || sources.size() > 3
                ) {
                    throw std::runtime_error("unexpected divergence terminals");
                }
                ++summary.source_histogram[sources.size()];

                std::set<Flow> path_flows;
                std::set<Flow> residual_flows;
                int case_raw_decompositions = 0;
                std::sort(sinks.begin(), sinks.end());
                do {
                    std::vector<std::vector<Walk>> options;
                    bool possible = true;
                    for (std::size_t index = 0; index < sources.size(); ++index) {
                        std::vector<Walk> allowed;
                        const auto found = walks.find(
                            {sources[index], sinks[index]}
                        );
                        if (found != walks.end()) {
                            for (const Walk& walk : found->second) {
                                if (
                                    std::none_of(
                                        walk.begin(),
                                        walk.end(),
                                        [&](int edge) {
                                            return forbidden[edge];
                                        }
                                    )
                                ) {
                                    allowed.push_back(walk);
                                }
                            }
                        }
                        if (allowed.empty()) {
                            possible = false;
                            break;
                        }
                        options.push_back(std::move(allowed));
                    }
                    if (!possible) {
                        continue;
                    }
                    std::vector<int> path_edges;
                    enumerate_path_products(
                        options,
                        0,
                        path_edges,
                        forbidden,
                        balanced,
                        path_flows,
                        residual_flows,
                        case_raw_decompositions
                    );
                } while (std::next_permutation(sinks.begin(), sinks.end()));

                summary.distinct_path_flows += static_cast<int>(
                    path_flows.size()
                );
                summary.raw_decompositions += case_raw_decompositions;
                summary.distinct_residual_flows += static_cast<int>(
                    residual_flows.size()
                );
                ++summary.residual_count_histogram[residual_flows.size()];
                if (!residual_flows.empty()) {
                    ++summary.active_omission_sets;
                }

                for (const Flow& residual : residual_flows) {
                    if (
                        flow_mass(residual) != kResidualMass
                        || flow_uses_forbidden(residual, forbidden)
                        || flow_divergence(residual) != divergence
                    ) {
                        throw std::runtime_error("invalid residual flow");
                    }

                    std::array<int, kWordCount> counts{};
                    for (int edge = 0; edge < kWordCount; ++edge) {
                        if (required[edge]) {
                            counts[edge] = 1;
                        }
                    }
                    for (const auto& [edge, multiplicity] : residual) {
                        counts[edge] += multiplicity;
                    }
                    if (
                        std::accumulate(counts.begin(), counts.end(), 0)
                        != kCandidateLength
                    ) {
                        throw std::runtime_error(
                            "completion has the wrong total multiplicity"
                        );
                    }
                    std::array<int, kVertexCount> combined_divergence{};
                    std::array<bool, kWordCount> selected{};
                    for (int edge = 0; edge < kWordCount; ++edge) {
                        if (counts[edge] <= 0) {
                            continue;
                        }
                        selected[edge] = true;
                        combined_divergence[edge_prefix(edge)] += counts[edge];
                        combined_divergence[edge_suffix(edge)] -= counts[edge];
                    }
                    if (
                        std::any_of(
                            combined_divergence.begin(),
                            combined_divergence.end(),
                            [](int value) { return value != 0; }
                        )
                    ) {
                        throw std::runtime_error(
                            "completion is not a circulation"
                        );
                    }
                    const int components = component_count(selected);
                    ++summary.component_histogram[components];
                    if (components != 1) {
                        continue;
                    }

                    const int support_size = static_cast<int>(
                        std::count(selected.begin(), selected.end(), true)
                    );
                    std::vector<int> uncovered = uncovered_words(selected);
                    ++summary.connected_support_histogram[support_size];
                    ++summary.connected_gap_histogram[uncovered.size()];
                    summary.connected.push_back(
                        Completion{
                            omitted,
                            residual,
                            support_size,
                            std::move(uncovered),
                        }
                    );
                }
            }
        }
    }
    return summary;
}

void print_integer_map(const std::map<int, int>& values) {
    std::cout << "{";
    bool first = true;
    for (const auto& [key, value] : values) {
        if (!first) {
            std::cout << ",";
        }
        first = false;
        std::cout << "\"" << key << "\":" << value;
    }
    std::cout << "}";
}

void print_flow(const Flow& flow) {
    std::cout << "[";
    for (std::size_t index = 0; index < flow.size(); ++index) {
        if (index > 0) {
            std::cout << ",";
        }
        std::cout << "[" << flow[index].first << "," << flow[index].second
                  << "]";
    }
    std::cout << "]";
}

void print_vector(const std::vector<int>& values) {
    std::cout << "[";
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index > 0) {
            std::cout << ",";
        }
        std::cout << values[index];
    }
    std::cout << "]";
}

void print_summary(
    const Summary& summary,
    const std::vector<std::set<Flow>>& balanced,
    const std::vector<int>& support
) {
    std::cout << "{";
    std::cout << "\"schema_version\":1,";
    std::cout << "\"implementation\":"
              << "\"independent-cpp-exact-overlap61-v1\",";
    std::cout << "\"parameters\":{"
              << "\"n\":" << kN << ","
              << "\"radius\":1,"
              << "\"candidate_length\":" << kCandidateLength << ","
              << "\"reference_support_size\":" << support.size() << ","
              << "\"exact_overlap\":" << kExactOverlap << ","
              << "\"omitted_support_edges\":3,"
              << "\"residual_mass\":" << kResidualMass << "},";
    std::cout << "\"support_edges\":";
    print_vector(support);
    std::cout << ",";
    std::cout << "\"omission_sets_checked\":"
              << summary.omission_sets_checked << ",";
    std::cout << "\"precomputed_directed_walks\":"
              << summary.precomputed_walks << ",";
    std::cout << "\"balanced_flow_counts_by_mass\":[";
    for (std::size_t index = 0; index < balanced.size(); ++index) {
        if (index > 0) {
            std::cout << ",";
        }
        std::cout << balanced[index].size();
    }
    std::cout << "],";
    std::cout << "\"source_count_histogram\":{"
              << "\"1\":" << summary.source_histogram[1] << ","
              << "\"2\":" << summary.source_histogram[2] << ","
              << "\"3\":" << summary.source_histogram[3] << "},";
    std::cout << "\"active_omission_sets\":"
              << summary.active_omission_sets << ",";
    std::cout << "\"distinct_path_flows\":"
              << summary.distinct_path_flows << ",";
    std::cout << "\"raw_exact_decompositions\":"
              << summary.raw_decompositions << ",";
    std::cout << "\"distinct_residual_flows\":"
              << summary.distinct_residual_flows << ",";
    std::cout << "\"residual_flow_count_histogram\":";
    print_integer_map(summary.residual_count_histogram);
    std::cout << ",\"component_count_histogram\":";
    print_integer_map(summary.component_histogram);
    std::cout << ",\"connected_support_size_histogram\":";
    print_integer_map(summary.connected_support_histogram);
    std::cout << ",\"connected_coverage_gap_histogram\":";
    print_integer_map(summary.connected_gap_histogram);
    std::cout << ",\"connected_completion_count\":"
              << summary.connected.size() << ",";
    const int covering_count = static_cast<int>(
        std::count_if(
            summary.connected.begin(),
            summary.connected.end(),
            [](const Completion& completion) {
                return completion.uncovered.empty();
            }
        )
    );
    std::cout << "\"covering_completion_count\":" << covering_count << ",";
    std::cout << "\"connected_completions\":[";
    for (std::size_t index = 0; index < summary.connected.size(); ++index) {
        if (index > 0) {
            std::cout << ",";
        }
        const Completion& completion = summary.connected[index];
        std::cout << "{\"omitted_edges\":["
                  << completion.omitted[0] << ","
                  << completion.omitted[1] << ","
                  << completion.omitted[2] << "],";
        std::cout << "\"residual_flow\":";
        print_flow(completion.residual);
        std::cout << ",\"combined_support_size\":"
                  << completion.support_size << ",";
        std::cout << "\"uncovered_words\":";
        print_vector(completion.uncovered);
        std::cout << "}";
    }
    std::cout << "]}\n";
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 2) {
            std::cerr << "usage: exact-overlap-checker SUPPORT_JSON\n";
            return 2;
        }
        const std::vector<int> support = load_selected_edges(argv[1]);
        const Summary summary = run_enumeration(support);
        const std::vector<std::set<Flow>> balanced = balanced_cycle_flows(
            kResidualMass
        );
        print_summary(summary, balanced, support);
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << "\n";
        return 1;
    }
    return 0;
}
