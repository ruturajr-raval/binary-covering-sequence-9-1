#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <cstdint>
#include <exception>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {

struct Options {
    int n = 9;
    int radius = 1;
    int max_distance = 4;
    int workers = 1;
    std::string seed_path;
    std::string output_path;
    bool self_test = false;
};

struct Result {
    bool found = false;
    std::uint64_t evaluated = 0;
    int best_uncovered = std::numeric_limits<int>::max();
    int best_distance = -1;
    std::vector<std::uint8_t> best_bits;
};

class CoverageEvaluator {
  public:
    CoverageEvaluator(int n, int radius)
        : n_(n),
          radius_(radius),
          word_count_(static_cast<int>(std::uint32_t{1} << n)),
          marks_(static_cast<std::size_t>(word_count_), 0) {}

    [[nodiscard]] int uncovered(const std::vector<std::uint8_t>& bits) {
        ++generation_;
        if (generation_ == 0U) {
            std::fill(marks_.begin(), marks_.end(), 0U);
            generation_ = 1U;
        }

        int covered = 0;
        const int length = static_cast<int>(bits.size());
        for (int start = 0; start < length; ++start) {
            int word = 0;
            for (int offset = 0; offset < n_; ++offset) {
                word = (word << 1) |
                       bits[static_cast<std::size_t>((start + offset) % length)];
            }
            mark(word, covered);
            if (radius_ == 1) {
                for (int bit = 0; bit < n_; ++bit) {
                    mark(word ^ (1 << bit), covered);
                }
            }
        }
        return word_count_ - covered;
    }

  private:
    int n_;
    int radius_;
    int word_count_;
    std::vector<std::uint32_t> marks_;
    std::uint32_t generation_ = 0;

    void mark(int word, int& covered) {
        const auto index = static_cast<std::size_t>(word);
        if (marks_[index] != generation_) {
            marks_[index] = generation_;
            ++covered;
        }
    }
};

struct Shared {
    std::atomic<bool> found{false};
    std::atomic<bool> failed{false};
    std::atomic<std::uint64_t> evaluated{0};
    std::atomic<int> best_uncovered{std::numeric_limits<int>::max()};
    std::mutex mutex;
    std::exception_ptr worker_error;
    int best_distance = -1;
    std::vector<std::uint8_t> best_bits;
};

struct PrefixTask {
    std::array<int, 3> positions{};
    int count = 0;
    int next_position = 0;
};

std::vector<std::uint8_t> load_bits(const std::string& path) {
    std::ifstream stream(path);
    if (!stream) {
        throw std::runtime_error("failed to open sequence file: " + path);
    }

    std::vector<std::string> tokens;
    std::string token;
    while (stream >> token) {
        tokens.push_back(token);
    }
    if (tokens.empty()) {
        throw std::runtime_error("sequence file is empty: " + path);
    }
    if (tokens.size() == 1U &&
        tokens.front().find_first_not_of("01") == std::string::npos) {
        const std::string compact = tokens.front();
        tokens.clear();
        for (const char bit : compact) {
            tokens.emplace_back(1, bit);
        }
    }

    std::vector<std::uint8_t> bits;
    bits.reserve(tokens.size());
    for (const std::string& value : tokens) {
        if (value != "0" && value != "1") {
            throw std::runtime_error("sequence contains a nonbinary token");
        }
        bits.push_back(static_cast<std::uint8_t>(value == "1"));
    }
    return bits;
}

void write_bits(
    const std::string& path,
    const std::vector<std::uint8_t>& bits
) {
    const std::filesystem::path destination(path);
    const std::filesystem::path temporary(path + ".tmp");
    std::ofstream stream(temporary, std::ios::out | std::ios::trunc);
    if (!stream) {
        throw std::runtime_error("failed to write sequence file: " + path);
    }
    for (std::size_t index = 0; index < bits.size(); ++index) {
        if (index != 0U) {
            stream << ' ';
        }
        stream << static_cast<int>(bits[index]);
    }
    stream << '\n';
    stream.flush();
    if (!stream) {
        throw std::runtime_error("failed to flush sequence file: " + path);
    }
    stream.close();
    if (!stream) {
        throw std::runtime_error("failed to close sequence file: " + path);
    }

    std::error_code error;
    std::filesystem::rename(temporary, destination, error);
    if (error) {
        std::error_code ignored;
        std::filesystem::remove(temporary, ignored);
        throw std::runtime_error(
            "failed to publish sequence file: " + path + ": " + error.message()
        );
    }
}

void update_shared(
    Shared& shared,
    const std::vector<std::uint8_t>& bits,
    int distance,
    int uncovered
) {
    if (uncovered >= shared.best_uncovered.load()) {
        return;
    }
    std::lock_guard<std::mutex> lock(shared.mutex);
    if (uncovered >= shared.best_uncovered.load()) {
        return;
    }
    shared.best_distance = distance;
    shared.best_bits = bits;
    shared.best_uncovered.store(uncovered);
    if (uncovered == 0) {
        shared.found.store(true);
    }
}

[[nodiscard]] bool should_stop(const Shared& shared) {
    return shared.found.load() || shared.failed.load();
}

void record_worker_error(Shared& shared) {
    {
        std::lock_guard<std::mutex> lock(shared.mutex);
        if (!shared.worker_error) {
            shared.worker_error = std::current_exception();
        }
    }
    shared.failed.store(true);
}

void build_prefix_tasks(
    int length,
    int distance,
    int prefix_length,
    int depth,
    int next_position,
    PrefixTask task,
    std::vector<PrefixTask>& tasks
) {
    if (depth == prefix_length) {
        task.count = prefix_length;
        task.next_position = next_position;
        tasks.push_back(task);
        return;
    }

    const int upper = length - (distance - depth);
    for (int position = next_position; position <= upper; ++position) {
        task.positions[static_cast<std::size_t>(depth)] = position;
        build_prefix_tasks(
            length,
            distance,
            prefix_length,
            depth + 1,
            position + 1,
            task,
            tasks
        );
    }
}

std::vector<PrefixTask> make_prefix_tasks(int length, int distance) {
    const int prefix_length = std::min(distance, 3);
    std::vector<PrefixTask> tasks;
    build_prefix_tasks(
        length,
        distance,
        prefix_length,
        0,
        0,
        PrefixTask{},
        tasks
    );
    return tasks;
}

void enumerate_tail(
    std::vector<std::uint8_t>& bits,
    int next_position,
    int remaining,
    int distance,
    CoverageEvaluator& evaluator,
    Shared& shared,
    std::uint64_t& local_evaluated
) {
    if (should_stop(shared)) {
        return;
    }
    if (remaining == 0) {
        const int uncovered = evaluator.uncovered(bits);
        ++local_evaluated;
        if (uncovered < shared.best_uncovered.load()) {
            update_shared(shared, bits, distance, uncovered);
        }
        return;
    }

    const int length = static_cast<int>(bits.size());
    for (int position = next_position;
         position <= length - remaining && !should_stop(shared);
         ++position) {
        bits[static_cast<std::size_t>(position)] ^= 1U;
        enumerate_tail(
            bits,
            position + 1,
            remaining - 1,
            distance,
            evaluator,
            shared,
            local_evaluated
        );
        bits[static_cast<std::size_t>(position)] ^= 1U;
    }
}

Result search_neighborhood(
    const std::vector<std::uint8_t>& seed,
    int n,
    int radius,
    int max_distance,
    int workers,
    bool verbose
) {
    Shared shared;
    CoverageEvaluator seed_evaluator(n, radius);
    const int seed_uncovered = seed_evaluator.uncovered(seed);
    shared.evaluated.store(1);
    update_shared(shared, seed, 0, seed_uncovered);

    if (verbose) {
        std::cout << "distance=0 evaluated=1 best_uncovered="
                  << seed_uncovered << '\n';
    }

    const int length = static_cast<int>(seed.size());
    for (int distance = 1;
         distance <= max_distance && !should_stop(shared);
         ++distance) {
        const std::vector<PrefixTask> tasks =
            make_prefix_tasks(length, distance);
        std::atomic<std::size_t> next_task{0};
        std::vector<std::thread> threads;
        const int worker_count = std::min(
            workers,
            static_cast<int>(tasks.size())
        );
        threads.reserve(static_cast<std::size_t>(worker_count));

        try {
            for (int worker = 0; worker < worker_count; ++worker) {
                threads.emplace_back([&, distance]() {
                    std::uint64_t local_evaluated = 0;
                    try {
                        CoverageEvaluator evaluator(n, radius);
                        while (!should_stop(shared)) {
                            const std::size_t index =
                                next_task.fetch_add(1);
                            if (index >= tasks.size()) {
                                break;
                            }
                            const PrefixTask& task = tasks[index];
                            std::vector<std::uint8_t> bits = seed;
                            for (int prefix = 0;
                                 prefix < task.count;
                                 ++prefix) {
                                const int position = task.positions[
                                    static_cast<std::size_t>(prefix)
                                ];
                                bits[static_cast<std::size_t>(position)] ^= 1U;
                            }
                            enumerate_tail(
                                bits,
                                task.next_position,
                                distance - task.count,
                                distance,
                                evaluator,
                                shared,
                                local_evaluated
                            );
                        }
                    } catch (...) {
                        record_worker_error(shared);
                    }
                    shared.evaluated.fetch_add(local_evaluated);
                });
            }
        } catch (...) {
            shared.failed.store(true);
            for (std::thread& thread : threads) {
                thread.join();
            }
            throw;
        }
        for (std::thread& thread : threads) {
            thread.join();
        }

        std::exception_ptr worker_error;
        {
            std::lock_guard<std::mutex> lock(shared.mutex);
            worker_error = shared.worker_error;
        }
        if (worker_error) {
            std::rethrow_exception(worker_error);
        }

        if (verbose) {
            std::lock_guard<std::mutex> lock(shared.mutex);
            std::cout << "distance=" << distance
                      << " evaluated=" << shared.evaluated.load()
                      << " best_uncovered="
                      << shared.best_uncovered.load() << '\n';
        }
    }

    std::lock_guard<std::mutex> lock(shared.mutex);
    return Result{
        shared.found.load(),
        shared.evaluated.load(),
        shared.best_uncovered.load(),
        shared.best_distance,
        shared.best_bits,
    };
}

int parse_int(const std::string& value, const std::string& name) {
    std::size_t consumed = 0;
    const long long result = std::stoll(value, &consumed);
    if (consumed != value.size() ||
        result < std::numeric_limits<int>::min() ||
        result > std::numeric_limits<int>::max()) {
        throw std::invalid_argument("invalid value for " + name);
    }
    return static_cast<int>(result);
}

void print_usage(const char* program) {
    std::cout
        << "Usage:\n"
        << "  " << program
        << " --seed FILE --n N --radius R --max-distance K [options]\n"
        << "  " << program << " --self-test\n\n"
        << "Options:\n"
        << "  --workers N\n"
        << "  --output FILE\n";
}

Options parse_options(int argc, char** argv) {
    Options options;
    options.workers = std::max(
        1U,
        std::thread::hardware_concurrency()
    );
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        auto require_value = [&](const std::string& name) -> std::string {
            if (index + 1 >= argc) {
                throw std::invalid_argument("missing value for " + name);
            }
            return argv[++index];
        };

        if (argument == "--seed") {
            options.seed_path = require_value(argument);
        } else if (argument == "--n") {
            options.n = parse_int(require_value(argument), argument);
        } else if (argument == "--radius") {
            options.radius = parse_int(require_value(argument), argument);
        } else if (argument == "--max-distance") {
            options.max_distance = parse_int(require_value(argument), argument);
        } else if (argument == "--workers") {
            options.workers = parse_int(require_value(argument), argument);
        } else if (argument == "--output") {
            options.output_path = require_value(argument);
        } else if (argument == "--self-test") {
            options.self_test = true;
        } else if (argument == "--help" || argument == "-h") {
            print_usage(argv[0]);
            std::exit(0);
        } else {
            throw std::invalid_argument("unknown argument: " + argument);
        }
    }
    return options;
}

int reference_uncovered(
    const std::vector<std::uint8_t>& bits,
    int n,
    int radius
) {
    std::vector<int> windows;
    const int length = static_cast<int>(bits.size());
    windows.reserve(static_cast<std::size_t>(length));
    for (int start = 0; start < length; ++start) {
        int word = 0;
        for (int offset = 0; offset < n; ++offset) {
            word = (word << 1) |
                   bits[static_cast<std::size_t>((start + offset) % length)];
        }
        windows.push_back(word);
    }

    int uncovered = 0;
    for (int target = 0; target < (1 << n); ++target) {
        const bool covered = std::any_of(
            windows.begin(),
            windows.end(),
            [&](int word) {
                return std::popcount(
                    static_cast<unsigned int>(target ^ word)
                ) <= radius;
            }
        );
        uncovered += static_cast<int>(!covered);
    }
    return uncovered;
}

bool run_self_test() {
    const Result found = search_neighborhood(
        std::vector<std::uint8_t>{0, 0, 0, 0},
        2,
        1,
        1,
        2,
        false
    );
    if (!found.found || found.best_uncovered != 0) {
        std::cerr << "self-test failed: expected a radius-one solution\n";
        return false;
    }

    const Result missing = search_neighborhood(
        std::vector<std::uint8_t>{0},
        1,
        0,
        0,
        1,
        false
    );
    if (missing.found || missing.evaluated != 1U ||
        missing.best_uncovered != 1) {
        std::cerr << "self-test failed: invalid singleton result\n";
        return false;
    }

    for (int workers : {1, 8}) {
        const Result exhaustive = search_neighborhood(
            std::vector<std::uint8_t>(8, 0),
            7,
            0,
            8,
            workers,
            false
        );
        if (exhaustive.found || exhaustive.evaluated != 256U) {
            std::cerr
                << "self-test failed: incomplete exhaustive enumeration\n";
            return false;
        }
    }

    for (int n = 1; n <= 4; ++n) {
        for (int length = n; length <= 6; ++length) {
            for (int radius = 0; radius <= 1; ++radius) {
                CoverageEvaluator evaluator(n, radius);
                const int sequence_count = 1 << length;
                for (int mask = 0; mask < sequence_count; ++mask) {
                    std::vector<std::uint8_t> bits(
                        static_cast<std::size_t>(length),
                        0
                    );
                    for (int position = 0; position < length; ++position) {
                        bits[static_cast<std::size_t>(position)] =
                            static_cast<std::uint8_t>(
                                (mask >> position) & 1
                            );
                    }
                    if (evaluator.uncovered(bits) !=
                        reference_uncovered(bits, n, radius)) {
                        std::cerr
                            << "self-test failed: coverage mismatch\n";
                        return false;
                    }
                }
            }
        }
    }

    std::cout << "neighborhood self-test passed\n";
    return true;
}

int run(const Options& options) {
    if (options.seed_path.empty()) {
        throw std::invalid_argument("--seed is required");
    }
    if (options.n <= 0 || options.n >= 31 ||
        options.radius < 0 || options.radius > 1 ||
        options.max_distance < 0 || options.workers <= 0) {
        throw std::invalid_argument("invalid search parameters");
    }

    const std::vector<std::uint8_t> seed = load_bits(options.seed_path);
    if (static_cast<int>(seed.size()) < options.n) {
        throw std::invalid_argument("sequence length must be at least n");
    }
    if (options.max_distance > static_cast<int>(seed.size())) {
        throw std::invalid_argument("max distance exceeds sequence length");
    }

    const Result result = search_neighborhood(
        seed,
        options.n,
        options.radius,
        options.max_distance,
        options.workers,
        true
    );
    std::cout << "{\"found\":" << (result.found ? "true" : "false")
              << ",\"evaluated\":" << result.evaluated
              << ",\"best_uncovered\":" << result.best_uncovered
              << ",\"best_distance\":" << result.best_distance << "}\n";

    if (!options.output_path.empty() && !result.best_bits.empty()) {
        write_bits(
            result.found ? options.output_path : options.output_path + ".best",
            result.best_bits
        );
    }
    return result.found ? 0 : 3;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const Options options = parse_options(argc, argv);
        if (options.self_test) {
            return run_self_test() ? 0 : 1;
        }
        return run(options);
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        print_usage(argv[0]);
        return 2;
    }
}
