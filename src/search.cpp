#include <algorithm>
#include <atomic>
#include <bit>
#include <chrono>
#include <cstdint>
#include <exception>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <mutex>
#include <optional>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <tuple>
#include <unordered_set>
#include <utility>
#include <vector>

namespace {

constexpr std::int64_t kUncoveredWeight = 10000000;
constexpr std::int64_t kDistanceWeight = 1000;
constexpr std::uint64_t kInitialBreakoutWeight = 1;
constexpr std::size_t kDistantArchiveLimit = 4096;

struct Options {
    int n = 9;
    int radius = 1;
    int length = 70;
    int expected_length = -1;
    int workers = 1;
    int target_samples = 24;
    int pair_samples = 16;
    int triple_samples = 8;
    int max_target_flips = 5;
    int ejection_beam_width = 128;
    int ejection_depth = 12;
    int ejection_max_action = 3;
    int ejection_damage = 20;
    int ejection_endpoint_damage = 6;
    int ejection_targets = 1;
    std::uint64_t breakout_stagnation = 250;
    std::uint64_t breakout_increment = 1;
    std::uint64_t breakout_max_weight = 1000000;
    std::uint64_t iterations = 10000;
    std::uint64_t seed = 1;
    std::string baseline_path;
    std::string output_path;
    std::string verify_path;
    bool breakout = false;
    bool ejection = false;
    bool self_test = false;
};

struct Evaluation {
    int uncovered = 0;
    int distance_deficit = 0;
    int singletons = 0;

    [[nodiscard]] std::int64_t energy() const {
        return static_cast<std::int64_t>(uncovered) * kUncoveredWeight +
               static_cast<std::int64_t>(distance_deficit) * kDistanceWeight +
               singletons;
    }
};

struct WeightedEvaluation {
    Evaluation raw;
    std::uint64_t uncovered_weight = 0;
};

using Move = std::vector<int>;

[[nodiscard]] std::uint64_t checked_add(
    std::uint64_t left,
    std::uint64_t right,
    const char* message
) {
    if (right > std::numeric_limits<std::uint64_t>::max() - left) {
        throw std::overflow_error(message);
    }
    return left + right;
}

[[nodiscard]] std::uint64_t checked_multiply_add(
    std::uint64_t value,
    std::uint64_t multiplier,
    std::uint64_t addend,
    const char* message
) {
    if (value != 0 &&
        multiplier >
            (std::numeric_limits<std::uint64_t>::max() - addend) / value) {
        throw std::overflow_error(message);
    }
    return value * multiplier + addend;
}

struct Scratch {
    explicit Scratch(int length, int word_count)
        : delta(static_cast<std::size_t>(word_count), 0),
          marked(static_cast<std::size_t>(word_count), 0),
          affected(static_cast<std::size_t>(length), 0),
          toggled(static_cast<std::size_t>(length), 0) {}

    std::vector<int> delta;
    std::vector<std::uint8_t> marked;
    std::vector<int> touched_words;
    std::vector<std::uint8_t> affected;
    std::vector<int> affected_starts;
    std::vector<std::uint8_t> toggled;
};

class State {
  public:
    State(std::vector<std::uint8_t> bits, int n, int radius)
        : n_(n),
          radius_(radius),
          length_(static_cast<int>(bits.size())),
          word_count_(0),
          bits_(std::move(bits)) {
        if (n_ <= 0 || n_ >= 31) {
            throw std::invalid_argument("n must be between 1 and 30");
        }
        if (radius_ < 0 || radius_ > 1) {
            throw std::invalid_argument("radius must be 0 or 1");
        }
        if (length_ < n_) {
            throw std::invalid_argument("sequence length must be at least n");
        }
        if (std::any_of(bits_.begin(), bits_.end(), [](std::uint8_t bit) {
                return bit > 1U;
            })) {
            throw std::invalid_argument("sequence must contain only binary digits");
        }
        word_count_ = static_cast<int>(std::uint32_t{1} << n_);
        windows_.assign(static_cast<std::size_t>(length_), 0);
        coverage_.assign(static_cast<std::size_t>(word_count_), 0);
        rebuild();
    }

    [[nodiscard]] int n() const { return n_; }
    [[nodiscard]] int radius() const { return radius_; }
    [[nodiscard]] int length() const { return length_; }
    [[nodiscard]] int word_count() const { return word_count_; }
    [[nodiscard]] int uncovered() const { return uncovered_; }
    [[nodiscard]] int distance_deficit() const { return distance_deficit_; }
    [[nodiscard]] int singletons() const { return singletons_; }
    [[nodiscard]] std::int64_t energy() const {
        return static_cast<std::int64_t>(uncovered_) * kUncoveredWeight +
               static_cast<std::int64_t>(distance_deficit_) * kDistanceWeight +
               singletons_;
    }
    [[nodiscard]] const std::vector<std::uint8_t>& bits() const { return bits_; }
    [[nodiscard]] const std::vector<std::uint32_t>& windows() const {
        return windows_;
    }

    [[nodiscard]] std::vector<int> uncovered_words() const {
        std::vector<int> result;
        for (int word = 0; word < word_count_; ++word) {
            if (coverage_[static_cast<std::size_t>(word)] == 0) {
                result.push_back(word);
            }
        }
        return result;
    }

    [[nodiscard]] std::uint64_t weighted_uncovered(
        const std::vector<std::uint64_t>& weights
    ) const {
        validate_weight_count(weights);
        std::uint64_t total = 0;
        for (int word = 0; word < word_count_; ++word) {
            const std::uint64_t weight =
                weights[static_cast<std::size_t>(word)];
            if (weight == 0) {
                throw std::invalid_argument(
                    "breakout weights must be positive"
                );
            }
            if (coverage_[static_cast<std::size_t>(word)] == 0) {
                total = checked_add(
                    total,
                    weight,
                    "weighted uncovered cost overflow"
                );
            }
        }
        return total;
    }

    [[nodiscard]] bool equivalent_to(const State& other) const {
        return n_ == other.n_ && radius_ == other.radius_ &&
               length_ == other.length_ && bits_ == other.bits_ &&
               windows_ == other.windows_ && coverage_ == other.coverage_ &&
               uncovered_ == other.uncovered_ &&
               distance_deficit_ == other.distance_deficit_ &&
               singletons_ == other.singletons_;
    }

    Evaluation evaluate(const Move& move, Scratch& scratch) const {
        prepare_move(move, scratch);

        for (const int start : scratch.affected_starts) {
            const int old_word = windows_[static_cast<std::size_t>(start)];
            const int new_word = toggled_window(start, old_word, scratch);
            if (old_word == new_word) {
                continue;
            }
            add_ball_delta(old_word, -1, scratch);
            add_ball_delta(new_word, 1, scratch);
        }

        Evaluation result{uncovered_, 0, singletons_};
        for (const int word : scratch.touched_words) {
            const int old_count = coverage_[static_cast<std::size_t>(word)];
            const int new_count =
                old_count + scratch.delta[static_cast<std::size_t>(word)];

            if (old_count == 0) {
                --result.uncovered;
            }
            if (old_count == 1) {
                --result.singletons;
            }
            if (new_count == 0) {
                ++result.uncovered;
            }
            if (new_count == 1) {
                ++result.singletons;
            }
        }
        result.distance_deficit = candidate_distance_deficit(scratch);

        clear_scratch(move, scratch);
        return result;
    }

    Evaluation evaluate_coverage(const Move& move, Scratch& scratch) const {
        prepare_move(move, scratch);

        for (const int start : scratch.affected_starts) {
            const int old_word = windows_[static_cast<std::size_t>(start)];
            const int new_word = toggled_window(start, old_word, scratch);
            if (old_word == new_word) {
                continue;
            }
            add_ball_delta(old_word, -1, scratch);
            add_ball_delta(new_word, 1, scratch);
        }

        Evaluation result{uncovered_, 0, singletons_};
        for (const int word : scratch.touched_words) {
            const int old_count = coverage_[static_cast<std::size_t>(word)];
            const int new_count =
                old_count + scratch.delta[static_cast<std::size_t>(word)];
            if (new_count < 0) {
                throw std::logic_error("coverage count became negative");
            }

            if (old_count == 0) {
                --result.uncovered;
            }
            if (old_count == 1) {
                --result.singletons;
            }
            if (new_count == 0) {
                ++result.uncovered;
            }
            if (new_count == 1) {
                ++result.singletons;
            }
        }

        clear_scratch(move, scratch);
        return result;
    }

    WeightedEvaluation evaluate_weighted(
        const Move& move,
        Scratch& scratch,
        const std::vector<std::uint64_t>& weights,
        std::uint64_t current_uncovered_weight
    ) const {
        validate_weight_count(weights);
        prepare_move(move, scratch);

        for (const int start : scratch.affected_starts) {
            const int old_word = windows_[static_cast<std::size_t>(start)];
            const int new_word = toggled_window(start, old_word, scratch);
            if (old_word == new_word) {
                continue;
            }
            add_ball_delta(old_word, -1, scratch);
            add_ball_delta(new_word, 1, scratch);
        }

        WeightedEvaluation result{
            Evaluation{uncovered_, 0, singletons_},
            current_uncovered_weight
        };
        for (const int word : scratch.touched_words) {
            const auto index = static_cast<std::size_t>(word);
            const int old_count = coverage_[index];
            const int new_count = old_count + scratch.delta[index];
            if (new_count < 0) {
                throw std::logic_error("coverage count became negative");
            }

            if (old_count == 0) {
                --result.raw.uncovered;
                const std::uint64_t weight = weights[index];
                if (weight == 0) {
                    throw std::invalid_argument(
                        "breakout weights must be positive"
                    );
                }
                if (result.uncovered_weight < weight) {
                    throw std::logic_error(
                        "weighted uncovered cost became negative"
                    );
                }
                result.uncovered_weight -= weight;
            }
            if (old_count == 1) {
                --result.raw.singletons;
            }
            if (new_count == 0) {
                ++result.raw.uncovered;
                if (weights[index] == 0) {
                    throw std::invalid_argument(
                        "breakout weights must be positive"
                    );
                }
                result.uncovered_weight = checked_add(
                    result.uncovered_weight,
                    weights[index],
                    "weighted uncovered cost overflow"
                );
            }
            if (new_count == 1) {
                ++result.raw.singletons;
            }
        }
        result.raw.distance_deficit = candidate_distance_deficit(scratch);

        clear_scratch(move, scratch);
        return result;
    }

    void apply(const Move& move, Scratch& scratch) {
        prepare_move(move, scratch);

        for (const int start : scratch.affected_starts) {
            const int old_word = windows_[static_cast<std::size_t>(start)];
            const int new_word = toggled_window(start, old_word, scratch);
            if (old_word == new_word) {
                continue;
            }
            adjust_ball(old_word, -1);
            adjust_ball(new_word, 1);
            windows_[static_cast<std::size_t>(start)] =
                static_cast<std::uint32_t>(new_word);
        }

        for (const int position : move) {
            bits_[static_cast<std::size_t>(position)] ^= 1U;
        }
        distance_deficit_ = current_distance_deficit();
        clear_scratch(move, scratch);
    }

  private:
    int n_;
    int radius_;
    int length_;
    int word_count_;
    std::vector<std::uint8_t> bits_;
    std::vector<std::uint32_t> windows_;
    std::vector<int> coverage_;
    int uncovered_ = 0;
    int distance_deficit_ = 0;
    int singletons_ = 0;

    void validate_weight_count(
        const std::vector<std::uint64_t>& weights
    ) const {
        if (weights.size() != coverage_.size()) {
            throw std::invalid_argument(
                "breakout weight count does not match the word count"
            );
        }
    }

    void rebuild() {
        std::fill(coverage_.begin(), coverage_.end(), 0);
        for (int start = 0; start < length_; ++start) {
            int word = 0;
            for (int offset = 0; offset < n_; ++offset) {
                const int position = (start + offset) % length_;
                if (bits_[static_cast<std::size_t>(position)] != 0U) {
                    word |= 1 << offset;
                }
            }
            windows_[static_cast<std::size_t>(start)] =
                static_cast<std::uint32_t>(word);
            ++coverage_[static_cast<std::size_t>(word)];
            if (radius_ == 1) {
                for (int bit = 0; bit < n_; ++bit) {
                    ++coverage_[static_cast<std::size_t>(word ^ (1 << bit))];
                }
            }
        }

        uncovered_ = 0;
        singletons_ = 0;
        for (const int count : coverage_) {
            if (count == 0) {
                ++uncovered_;
            }
            if (count == 1) {
                ++singletons_;
            }
        }
        distance_deficit_ = current_distance_deficit();
    }

    void mark_delta(int word, int amount, Scratch& scratch) const {
        const auto index = static_cast<std::size_t>(word);
        if (scratch.marked[index] == 0U) {
            scratch.marked[index] = 1U;
            scratch.touched_words.push_back(word);
        }
        scratch.delta[index] += amount;
    }

    void add_ball_delta(int word, int amount, Scratch& scratch) const {
        mark_delta(word, amount, scratch);
        if (radius_ == 1) {
            for (int bit = 0; bit < n_; ++bit) {
                mark_delta(word ^ (1 << bit), amount, scratch);
            }
        }
    }

    void adjust_word(int word, int amount) {
        const auto index = static_cast<std::size_t>(word);
        const int old_count = coverage_[index];
        const int new_count = old_count + amount;
        if (new_count < 0) {
            throw std::logic_error("coverage count became negative");
        }

        if (old_count == 0) {
            --uncovered_;
        }
        if (old_count == 1) {
            --singletons_;
        }
        coverage_[index] = new_count;
        if (new_count == 0) {
            ++uncovered_;
        }
        if (new_count == 1) {
            ++singletons_;
        }
    }

    void adjust_ball(int word, int amount) {
        adjust_word(word, amount);
        if (radius_ == 1) {
            for (int bit = 0; bit < n_; ++bit) {
                adjust_word(word ^ (1 << bit), amount);
            }
        }
    }

    void prepare_move(const Move& move, Scratch& scratch) const {
        for (const int position : move) {
            if (position < 0 || position >= length_) {
                throw std::out_of_range("move position is out of range");
            }
            const auto index = static_cast<std::size_t>(position);
            if (scratch.toggled[index] != 0U) {
                throw std::invalid_argument("move contains a duplicate position");
            }
            scratch.toggled[index] = 1U;

            for (int offset = 0; offset < n_; ++offset) {
                const int start = (position - offset + length_) % length_;
                const auto start_index = static_cast<std::size_t>(start);
                if (scratch.affected[start_index] == 0U) {
                    scratch.affected[start_index] = 1U;
                    scratch.affected_starts.push_back(start);
                }
            }
        }
    }

    [[nodiscard]] int toggled_window(
        int start,
        int old_word,
        const Scratch& scratch
    ) const {
        int new_word = old_word;
        for (int offset = 0; offset < n_; ++offset) {
            const int position = (start + offset) % length_;
            if (scratch.toggled[static_cast<std::size_t>(position)] != 0U) {
                new_word ^= 1 << offset;
            }
        }
        return new_word;
    }

    [[nodiscard]] int current_distance_deficit() const {
        int total = 0;
        for (int word = 0; word < word_count_; ++word) {
            if (coverage_[static_cast<std::size_t>(word)] != 0) {
                continue;
            }
            int best_distance = n_ + 1;
            for (const std::uint32_t window : windows_) {
                const int distance = std::popcount(
                    static_cast<unsigned int>(word ^ window)
                );
                best_distance = std::min(best_distance, distance);
            }
            total += best_distance - radius_;
        }
        return total;
    }

    [[nodiscard]] int candidate_distance_deficit(
        const Scratch& scratch
    ) const {
        int total = 0;
        for (int word = 0; word < word_count_; ++word) {
            const auto index = static_cast<std::size_t>(word);
            const int count = coverage_[index] + scratch.delta[index];
            if (count != 0) {
                continue;
            }

            int best_distance = n_ + 1;
            for (int start = 0; start < length_; ++start) {
                const int old_window =
                    windows_[static_cast<std::size_t>(start)];
                const int window = toggled_window(start, old_window, scratch);
                const int distance = std::popcount(
                    static_cast<unsigned int>(word ^ window)
                );
                best_distance = std::min(best_distance, distance);
            }
            total += best_distance - radius_;
        }
        return total;
    }

    void clear_scratch(const Move& move, Scratch& scratch) const {
        for (const int word : scratch.touched_words) {
            const auto index = static_cast<std::size_t>(word);
            scratch.delta[index] = 0;
            scratch.marked[index] = 0U;
        }
        scratch.touched_words.clear();

        for (const int start : scratch.affected_starts) {
            scratch.affected[static_cast<std::size_t>(start)] = 0U;
        }
        scratch.affected_starts.clear();

        for (const int position : move) {
            scratch.toggled[static_cast<std::size_t>(position)] = 0U;
        }
    }
};

struct SharedBest {
    std::atomic<bool> found{false};
    std::atomic<bool> stop{false};
    std::mutex mutex;
    int uncovered = std::numeric_limits<int>::max();
    int distance_deficit = std::numeric_limits<int>::max();
    int singletons = std::numeric_limits<int>::max();
    std::uint64_t seed = 0;
    int worker = -1;
    int error_worker = -1;
    std::vector<std::uint8_t> bits;
    std::exception_ptr error;
};

[[nodiscard]] bool better_tuple(
    int uncovered,
    int distance_deficit,
    int singletons,
    int other_uncovered,
    int other_distance_deficit,
    int other_singletons
) {
    return std::tuple{uncovered, distance_deficit, singletons} <
           std::tuple{
               other_uncovered,
               other_distance_deficit,
               other_singletons
           };
}

[[nodiscard]] bool bits_equal(
    const std::vector<std::uint8_t>& left,
    const std::vector<std::uint8_t>& right
) {
    if (left.size() != right.size()) {
        return false;
    }
    for (std::size_t index = 0; index < left.size(); ++index) {
        if (left[index] != right[index]) {
            return false;
        }
    }
    return true;
}

[[nodiscard]] bool bits_less(
    const std::vector<std::uint8_t>& left,
    const std::vector<std::uint8_t>& right
) {
    const std::size_t common = std::min(left.size(), right.size());
    for (std::size_t index = 0; index < common; ++index) {
        if (left[index] != right[index]) {
            return left[index] < right[index];
        }
    }
    return left.size() < right.size();
}

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

    if (tokens.size() == 1U && tokens.front().find_first_not_of("01") ==
                                    std::string::npos) {
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
        stream.close();
        std::error_code ignored;
        std::filesystem::remove(temporary, ignored);
        throw std::runtime_error("failed to flush sequence file: " + path);
    }
    stream.close();
    if (!stream) {
        std::error_code ignored;
        std::filesystem::remove(temporary, ignored);
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

Move random_move(std::mt19937_64& rng, int length, int size) {
    if (size <= 0 || size > length) {
        throw std::invalid_argument("move size must be between 1 and length");
    }
    Move move;
    move.reserve(static_cast<std::size_t>(size));
    std::uniform_int_distribution<int> position_distribution(0, length - 1);
    while (static_cast<int>(move.size()) < size) {
        const int position = position_distribution(rng);
        if (std::find(move.begin(), move.end(), position) == move.end()) {
            move.push_back(position);
        }
    }
    std::sort(move.begin(), move.end());
    return move;
}

void update_shared(
    SharedBest& shared,
    const State& state,
    int worker,
    std::uint64_t seed,
    const std::string& output_path
) {
    std::lock_guard<std::mutex> lock(shared.mutex);
    if (!better_tuple(
            state.uncovered(),
            state.distance_deficit(),
            state.singletons(),
            shared.uncovered,
            shared.distance_deficit,
            shared.singletons
        )) {
        return;
    }

    shared.uncovered = state.uncovered();
    shared.distance_deficit = state.distance_deficit();
    shared.singletons = state.singletons();
    shared.worker = worker;
    shared.seed = seed;
    shared.bits = state.bits();

    std::cerr << "best worker=" << worker << " seed=" << seed
              << " uncovered=" << shared.uncovered
              << " distance_deficit=" << shared.distance_deficit
              << " singletons=" << shared.singletons << '\n';

    if (state.uncovered() == 0) {
        if (!output_path.empty()) {
            write_bits(output_path, state.bits());
        }
        shared.found.store(true);
        shared.stop.store(true);
    }
}

std::vector<std::vector<std::uint8_t>> ranked_starts(
    const std::vector<std::uint8_t>& baseline,
    int target_length,
    int n,
    int radius
) {
    std::vector<std::vector<std::uint8_t>> starts;
    if (static_cast<int>(baseline.size()) == target_length) {
        starts.push_back(baseline);
    } else if (static_cast<int>(baseline.size()) == target_length + 1) {
        for (int deleted = 0; deleted < static_cast<int>(baseline.size());
             ++deleted) {
            std::vector<std::uint8_t> candidate = baseline;
            candidate.erase(candidate.begin() + deleted);
            starts.push_back(std::move(candidate));
        }
    } else {
        throw std::invalid_argument(
            "baseline length must equal target length or target length plus one"
        );
    }

    std::sort(starts.begin(), starts.end(), bits_less);
    starts.erase(
        std::unique(starts.begin(), starts.end(), bits_equal),
        starts.end()
    );
    std::sort(
        starts.begin(),
        starts.end(),
        [n, radius](
            const std::vector<std::uint8_t>& left,
            const std::vector<std::uint8_t>& right
        ) {
            const State left_state(left, n, radius);
            const State right_state(right, n, radius);
            const auto left_score = std::tuple{
                       left_state.uncovered(),
                       left_state.distance_deficit(),
                       left_state.singletons()
                   };
            const auto right_score = std::tuple{
                right_state.uncovered(),
                right_state.distance_deficit(),
                right_state.singletons()
            };
            return left_score != right_score ? left_score < right_score
                                             : bits_less(left, right);
        }
    );
    return starts;
}

struct BreakoutContext {
    const std::vector<std::uint64_t>* weights = nullptr;
    std::uint64_t current_uncovered_weight = 0;
    std::uint64_t local_best_uncovered_weight = 0;
    int local_best_distance_deficit = 0;
    int local_best_singletons = 0;
};

struct BreakoutMoveScore {
    std::uint64_t uncovered_weight = 0;
    int distance_deficit = 0;
    int singletons = 0;
    std::uint64_t jitter = 0;
};

[[nodiscard]] bool breakout_objective_less(
    std::uint64_t uncovered_weight,
    int distance_deficit,
    int singletons,
    std::uint64_t other_uncovered_weight,
    int other_distance_deficit,
    int other_singletons
) {
    return std::tuple{uncovered_weight, distance_deficit, singletons} <
           std::tuple{
               other_uncovered_weight,
               other_distance_deficit,
               other_singletons
           };
}

[[nodiscard]] bool breakout_score_less(
    const BreakoutMoveScore& left,
    const BreakoutMoveScore& right
) {
    return std::tuple{
               left.uncovered_weight,
               left.distance_deficit,
               left.singletons,
               left.jitter
           } <
           std::tuple{
               right.uncovered_weight,
               right.distance_deficit,
               right.singletons,
               right.jitter
           };
}

[[nodiscard]] std::uint64_t secondary_energy(
    int distance_deficit,
    int singletons
) {
    if (distance_deficit < 0 || singletons < 0) {
        throw std::logic_error("negative secondary objective");
    }
    return checked_multiply_add(
        static_cast<std::uint64_t>(distance_deficit),
        static_cast<std::uint64_t>(kDistanceWeight),
        static_cast<std::uint64_t>(singletons),
        "secondary objective overflow"
    );
}

[[nodiscard]] bool breakout_accepts(
    const WeightedEvaluation& candidate,
    const Evaluation& current,
    std::uint64_t current_uncovered_weight,
    std::uint64_t threshold
) {
    if (candidate.uncovered_weight != current_uncovered_weight) {
        return candidate.uncovered_weight < current_uncovered_weight;
    }
    const std::uint64_t allowed = checked_add(
        secondary_energy(current.distance_deficit, current.singletons),
        threshold,
        "breakout acceptance threshold overflow"
    );
    return secondary_energy(
               candidate.raw.distance_deficit,
               candidate.raw.singletons
           ) <= allowed;
}

[[nodiscard]] int choose_uncovered_target(
    const std::vector<int>& uncovered,
    const std::vector<std::uint64_t>* breakout_weights,
    std::mt19937_64& rng
) {
    if (uncovered.empty()) {
        throw std::invalid_argument("cannot choose from an empty target set");
    }
    if (breakout_weights == nullptr) {
        return uncovered[static_cast<std::size_t>(rng() % uncovered.size())];
    }

    std::uint64_t maximum = 0;
    for (const int word : uncovered) {
        const auto index = static_cast<std::size_t>(word);
        if (index >= breakout_weights->size()) {
            throw std::out_of_range("uncovered target is out of range");
        }
        maximum = std::max(maximum, (*breakout_weights)[index]);
    }

    std::size_t count = 0;
    for (const int word : uncovered) {
        if ((*breakout_weights)[static_cast<std::size_t>(word)] == maximum) {
            ++count;
        }
    }
    const std::size_t selected = static_cast<std::size_t>(rng() % count);
    std::size_t seen = 0;
    for (const int word : uncovered) {
        if ((*breakout_weights)[static_cast<std::size_t>(word)] != maximum) {
            continue;
        }
        if (seen == selected) {
            return word;
        }
        ++seen;
    }
    throw std::logic_error("failed to choose a breakout target");
}

bool increase_breakout_weights(
    const State& state,
    std::vector<std::uint64_t>& weights,
    std::uint64_t increment,
    std::uint64_t maximum
) {
    if (weights.size() != static_cast<std::size_t>(state.word_count())) {
        throw std::invalid_argument(
            "breakout weight count does not match the word count"
        );
    }

    bool changed = false;
    for (const int word : state.uncovered_words()) {
        std::uint64_t& weight = weights[static_cast<std::size_t>(word)];
        if (weight == 0 || weight > maximum) {
            throw std::logic_error("breakout weight is outside its limits");
        }
        const std::uint64_t room = maximum - weight;
        const std::uint64_t next =
            increment >= room ? maximum : weight + increment;
        changed = changed || next != weight;
        weight = next;
    }
    return changed;
}

void consider_move(
    const Move& move,
    State& state,
    Scratch& scratch,
    const std::vector<std::uint64_t>& tabu_until,
    std::uint64_t iteration,
    std::int64_t local_best_energy,
    const BreakoutContext* breakout,
    std::mt19937_64& rng,
    std::optional<Move>& selected_move,
    Evaluation& selected_evaluation,
    std::uint64_t& selected_score,
    std::optional<BreakoutMoveScore>& selected_breakout_score
) {
    Evaluation evaluation;
    std::uint64_t uncovered_weight = 0;
    if (breakout == nullptr) {
        evaluation = state.evaluate(move, scratch);
    } else {
        const WeightedEvaluation weighted = state.evaluate_weighted(
            move,
            scratch,
            *breakout->weights,
            breakout->current_uncovered_weight
        );
        evaluation = weighted.raw;
        uncovered_weight = weighted.uncovered_weight;
    }

    bool tabu = false;
    for (const int position : move) {
        if (tabu_until[static_cast<std::size_t>(position)] > iteration) {
            tabu = true;
            break;
        }
    }
    if (tabu) {
        if (breakout == nullptr) {
            if (evaluation.energy() >= local_best_energy) {
                return;
            }
        } else if (!breakout_objective_less(
                       uncovered_weight,
                       evaluation.distance_deficit,
                       evaluation.singletons,
                       breakout->local_best_uncovered_weight,
                       breakout->local_best_distance_deficit,
                       breakout->local_best_singletons
                   )) {
            return;
        }
    }

    const std::uint64_t jitter = rng() & 31U;
    if (breakout == nullptr) {
        const std::int64_t energy = evaluation.energy();
        if (energy < 0) {
            throw std::logic_error("move energy became negative");
        }
        const std::uint64_t score = checked_multiply_add(
            static_cast<std::uint64_t>(energy),
            32U,
            jitter,
            "move score overflow"
        );
        if (!selected_move.has_value() || score < selected_score) {
            selected_move = move;
            selected_evaluation = evaluation;
            selected_score = score;
        }
        return;
    }

    const BreakoutMoveScore score{
        uncovered_weight,
        evaluation.distance_deficit,
        evaluation.singletons,
        jitter
    };
    if (!selected_breakout_score.has_value() ||
        breakout_score_less(score, *selected_breakout_score)) {
        selected_move = move;
        selected_evaluation = evaluation;
        selected_breakout_score = score;
    }
}

std::vector<Move> target_repair_moves(
    const State& state,
    int target,
    int maximum_action_size
) {
    if (target < 0 || target >= state.word_count()) {
        throw std::out_of_range("repair target is out of range");
    }
    if (maximum_action_size <= 0) {
        throw std::invalid_argument(
            "maximum ejection action size must be positive"
        );
    }
    if (state.radius() != 1) {
        throw std::invalid_argument(
            "ejection repair moves currently require radius 1"
        );
    }

    std::vector<Move> moves;
    for (int start = 0; start < state.length(); ++start) {
        const int difference =
            static_cast<int>(
                state.windows()[static_cast<std::size_t>(start)]
            ) ^ target;
        if (std::popcount(static_cast<unsigned int>(difference)) < 2) {
            continue;
        }

        // The repaired window may equal the target or differ in one bit.
        for (int remaining_mismatch = -1;
             remaining_mismatch < state.n();
             ++remaining_mismatch) {
            Move move;
            for (int bit = 0; bit < state.n(); ++bit) {
                const bool mismatch =
                    (difference & (1 << bit)) != 0;
                const bool keep_mismatch =
                    bit == remaining_mismatch;
                if (mismatch != keep_mismatch) {
                    move.push_back((start + bit) % state.length());
                }
            }
            if (move.empty() ||
                move.size() >
                    static_cast<std::size_t>(maximum_action_size)) {
                continue;
            }
            std::sort(move.begin(), move.end());
            moves.push_back(std::move(move));
        }
    }
    std::sort(moves.begin(), moves.end());
    moves.erase(std::unique(moves.begin(), moves.end()), moves.end());
    return moves;
}

std::size_t least_rotation_index(
    const std::vector<std::uint8_t>& bits
) {
    if (bits.empty()) {
        return 0;
    }

    const std::size_t size = bits.size();
    std::size_t left = 0;
    std::size_t right = 1;
    std::size_t offset = 0;
    while (left < size && right < size && offset < size) {
        const std::uint8_t left_bit = bits[(left + offset) % size];
        const std::uint8_t right_bit = bits[(right + offset) % size];
        if (left_bit == right_bit) {
            ++offset;
            continue;
        }
        if (left_bit > right_bit) {
            left += offset + 1;
            if (left == right) {
                ++left;
            }
        } else {
            right += offset + 1;
            if (left == right) {
                ++right;
            }
        }
        offset = 0;
    }
    return std::min(left, right);
}

std::string rotation_key(
    const std::vector<std::uint8_t>& bits,
    std::size_t start
) {
    std::string key;
    key.reserve(bits.size());
    for (std::size_t offset = 0; offset < bits.size(); ++offset) {
        const std::uint8_t bit = bits[(start + offset) % bits.size()];
        key.push_back(static_cast<char>('0' + bit));
    }
    return key;
}

std::string canonical_bit_key(
    const std::vector<std::uint8_t>& bits
) {
    if (bits.empty()) {
        return {};
    }

    const std::string forward = rotation_key(
        bits,
        least_rotation_index(bits)
    );
    const std::vector<std::uint8_t> reversed(
        bits.rbegin(),
        bits.rend()
    );
    const std::string reflected = rotation_key(
        reversed,
        least_rotation_index(reversed)
    );
    return std::min(forward, reflected);
}

std::string canonical_state_key(const State& state) {
    return canonical_bit_key(state.bits());
}

std::string oriented_state_key(const State& state) {
    return rotation_key(state.bits(), 0);
}

int bit_distance(
    const std::vector<std::uint8_t>& left,
    const std::vector<std::uint8_t>& right
) {
    if (left.size() != right.size()) {
        throw std::invalid_argument(
            "cannot compare bit vectors of different lengths"
        );
    }
    int result = 0;
    for (std::size_t index = 0; index < left.size(); ++index) {
        result += left[index] != right[index];
    }
    return result;
}

int cyclic_orbit_distance(
    const std::vector<std::uint8_t>& left,
    const std::vector<std::uint8_t>& right
) {
    if (left.size() != right.size()) {
        throw std::invalid_argument(
            "cannot compare bit vectors of different lengths"
        );
    }
    if (left.empty()) {
        return 0;
    }

    int result = static_cast<int>(left.size());
    for (int reflected = 0; reflected < 2; ++reflected) {
        for (std::size_t shift = 0; shift < left.size(); ++shift) {
            int distance = 0;
            for (std::size_t index = 0; index < left.size(); ++index) {
                const std::size_t right_index = reflected == 0
                    ? (index + shift) % left.size()
                    : (
                        shift + left.size() - index
                    ) % left.size();
                distance += left[index] != right[right_index];
            }
            result = std::min(result, distance);
        }
    }
    return result;
}

int distance_after_move(
    const State& state,
    const std::vector<std::uint8_t>& root_bits,
    int current_distance,
    const Move& move
) {
    int result = current_distance;
    for (const int position : move) {
        const auto index = static_cast<std::size_t>(position);
        if (state.bits()[index] == root_bits[index]) {
            ++result;
        } else {
            --result;
        }
    }
    return result;
}

std::vector<int> newly_uncovered(
    const std::vector<int>& parent,
    const std::vector<int>& child
) {
    std::vector<int> result;
    std::size_t parent_index = 0;
    for (const int word : child) {
        while (parent_index < parent.size() &&
               parent[parent_index] < word) {
            ++parent_index;
        }
        if (parent_index == parent.size() ||
            parent[parent_index] != word) {
            result.push_back(word);
        }
    }
    return result;
}

std::vector<int> ordered_ejection_targets(
    const std::vector<int>& gaps,
    const std::vector<int>& preferred,
    std::mt19937_64& rng
) {
    if (gaps.empty()) {
        return {};
    }

    std::vector<int> targets;
    targets.reserve(gaps.size());
    auto add_target = [&](int word) {
        if (!std::binary_search(gaps.begin(), gaps.end(), word) ||
            std::find(targets.begin(), targets.end(), word) !=
                targets.end()) {
            return;
        }
        targets.push_back(word);
    };

    if (!preferred.empty()) {
        const std::size_t offset =
            static_cast<std::size_t>(rng() % preferred.size());
        for (std::size_t step = 0;
             step < preferred.size();
             ++step) {
            add_target(
                preferred[(offset + step) % preferred.size()]
            );
        }
    }

    const std::size_t offset =
        static_cast<std::size_t>(rng() % gaps.size());
    for (std::size_t step = 0;
         step < gaps.size();
         ++step) {
        add_target(gaps[(offset + step) % gaps.size()]);
    }
    return targets;
}

struct ActionableRepair {
    Move move;
    Evaluation evaluation;
};

struct ActionableTarget {
    int target = 0;
    std::vector<ActionableRepair> repairs;
};

std::vector<ActionableTarget> collect_actionable_repairs(
    const State& state,
    const std::vector<int>& gaps,
    const std::vector<int>& preferred,
    int maximum_action_size,
    int maximum_targets,
    std::int64_t damage_limit,
    std::mt19937_64& rng,
    Scratch& scratch,
    std::uint64_t& evaluations
) {
    if (maximum_targets <= 0) {
        throw std::invalid_argument(
            "maximum actionable targets must be positive"
        );
    }

    std::vector<ActionableTarget> result;
    const std::vector<int> targets =
        ordered_ejection_targets(gaps, preferred, rng);
    for (const int target : targets) {
        ActionableTarget batch;
        batch.target = target;
        for (const Move& move : target_repair_moves(
                 state,
                 target,
                 maximum_action_size
             )) {
            const Evaluation evaluation =
                state.evaluate_coverage(move, scratch);
            ++evaluations;
            if (evaluation.uncovered <= damage_limit) {
                batch.repairs.push_back(
                    ActionableRepair{move, evaluation}
                );
            }
        }
        if (batch.repairs.empty()) {
            continue;
        }
        result.push_back(std::move(batch));
        if (result.size() >=
            static_cast<std::size_t>(maximum_targets)) {
            break;
        }
    }
    return result;
}

struct EjectionNode {
    State state;
    std::vector<int> gaps;
    int root_distance = 0;
};

struct EjectionCandidate {
    std::size_t parent = 0;
    Move move;
    int uncovered = 0;
    int singletons = 0;
    int root_distance = 0;
    std::uint64_t jitter = 0;
};

bool ejection_candidate_less(
    const EjectionCandidate& left,
    const EjectionCandidate& right
) {
    return std::tuple{
               left.uncovered,
               -left.root_distance,
               left.singletons,
               left.jitter
           } <
           std::tuple{
               right.uncovered,
               -right.root_distance,
               right.singletons,
               right.jitter
           };
}

bool ejection_node_less(
    const EjectionNode& left,
    const EjectionNode& right
) {
    const auto left_score = std::tuple{
        left.state.uncovered(),
        left.state.distance_deficit(),
        left.state.singletons(),
        -left.root_distance
    };
    const auto right_score = std::tuple{
        right.state.uncovered(),
        right.state.distance_deficit(),
        right.state.singletons(),
        -right.root_distance
    };
    return left_score < right_score;
}

void run_ejection_worker(
    const Options& options,
    int worker,
    const std::vector<std::vector<std::uint8_t>>& starts,
    SharedBest& shared
) {
    const std::uint64_t worker_seed =
        options.seed + 0x9e3779b97f4a7c15ULL *
                           static_cast<std::uint64_t>(worker + 1);
    std::mt19937_64 rng(worker_seed);
    State current(
        starts[static_cast<std::size_t>(worker) % starts.size()],
        options.n,
        options.radius
    );
    const std::vector<std::uint8_t> origin_bits = current.bits();
    State local_best = current;
    update_shared(shared, current, worker, worker_seed, options.output_path);

    Scratch evaluation_scratch(current.length(), current.word_count());
    Scratch apply_scratch(current.length(), current.word_count());
    std::uint64_t chains_since_improvement = 0;
    std::uint64_t candidate_evaluations = 0;
    std::uint64_t beam_states = 0;
    std::uint64_t accepted_endpoints = 0;
    std::uint64_t completed_chains = 0;
    std::uint64_t exploration_chains = 0;
    int maximum_raw_origin_distance = 0;
    int maximum_six_gap_orbit_distance = 0;
    std::unordered_set<std::string> distant_six_gap_states;
    std::uint64_t distant_six_gap_visits = 0;
    bool distant_archive_capped = false;
    std::optional<State> best_distant_state;
    int best_distant_orbit_distance = 0;
    auto print_metrics = [&]() {
        if (best_distant_state.has_value() &&
            !options.output_path.empty()) {
            write_bits(
                options.output_path + ".distant." +
                    std::to_string(worker),
                best_distant_state->bits()
            );
        }
        std::lock_guard<std::mutex> lock(shared.mutex);
        std::cerr
            << "ejection worker=" << worker
            << " chains=" << completed_chains
            << " evaluations=" << candidate_evaluations
            << " beam_states=" << beam_states
            << " accepted_endpoints=" << accepted_endpoints
            << " exploration_chains=" << exploration_chains
            << " max_raw_origin_distance="
            << maximum_raw_origin_distance
            << " max_six_gap_orbit_distance="
            << maximum_six_gap_orbit_distance
            << " distant_six_gap_visits="
            << distant_six_gap_visits
            << " distinct_distant_six_gap_states="
            << distant_six_gap_states.size()
            << " distant_archive_capped="
            << (distant_archive_capped ? 1 : 0)
            << " best_distant_uncovered="
            << (
                best_distant_state.has_value()
                    ? best_distant_state->uncovered()
                    : -1
            )
            << " best_distant_orbit_distance="
            << best_distant_orbit_distance << '\n';
    };

    for (std::uint64_t chain = 0;
         chain < options.iterations && !shared.stop.load();
         ++chain) {
        const std::vector<std::uint8_t> root_bits = current.bits();
        const std::vector<int> root_gaps = current.uncovered_words();
        const std::int64_t damage_limit =
            static_cast<std::int64_t>(current.uncovered()) +
            options.ejection_damage;
        std::vector<EjectionNode> beam;
        beam.push_back(EjectionNode{
            current,
            root_gaps,
            0
        });
        std::unordered_set<std::string> seen_states{
            oriented_state_key(current)
        };
        std::optional<EjectionNode> best_chain_endpoint;
        std::vector<std::optional<EjectionNode>>
            exploratory_by_uncovered(
                static_cast<std::size_t>(current.word_count() + 1)
            );
        bool generated_state = false;
        bool improved_local_best = false;

        for (int depth = 0;
             depth < options.ejection_depth &&
             !beam.empty() &&
             !shared.stop.load();
             ++depth) {
            std::vector<EjectionCandidate> candidates;
            for (std::size_t parent = 0; parent < beam.size(); ++parent) {
                const EjectionNode& node = beam[parent];
                const std::vector<int> preferred =
                    newly_uncovered(root_gaps, node.gaps);
                const std::vector<ActionableTarget> batches =
                    collect_actionable_repairs(
                        node.state,
                        node.gaps,
                        preferred,
                        options.ejection_max_action,
                        options.ejection_targets,
                        damage_limit,
                        rng,
                        evaluation_scratch,
                        candidate_evaluations
                    );
                for (const ActionableTarget& batch : batches) {
                    for (const ActionableRepair& repair : batch.repairs) {
                        candidates.push_back(EjectionCandidate{
                            parent,
                            repair.move,
                            repair.evaluation.uncovered,
                            repair.evaluation.singletons,
                            distance_after_move(
                                node.state,
                                root_bits,
                                node.root_distance,
                                repair.move
                            ),
                            rng()
                        });
                    }
                }
            }
            if (candidates.empty()) {
                break;
            }
            std::sort(
                candidates.begin(),
                candidates.end(),
                ejection_candidate_less
            );

            std::vector<EjectionNode> next;
            next.reserve(
                std::min(
                    candidates.size(),
                    static_cast<std::size_t>(
                        options.ejection_beam_width
                    )
                )
            );
            for (const EjectionCandidate& candidate : candidates) {
                if (
                    next.size() >=
                    static_cast<std::size_t>(
                        options.ejection_beam_width
                    )
                ) {
                    break;
                }
                const EjectionNode& parent = beam[candidate.parent];
                State child = parent.state;
                child.apply(candidate.move, apply_scratch);
                const std::string oriented_key =
                    oriented_state_key(child);
                if (!seen_states.insert(oriented_key).second) {
                    continue;
                }
                generated_state = true;
                ++beam_states;
                const int raw_origin_distance =
                    bit_distance(child.bits(), origin_bits);
                maximum_raw_origin_distance = std::max(
                    maximum_raw_origin_distance,
                    raw_origin_distance
                );
                if (child.uncovered() <= 6) {
                    const int orbit_distance = cyclic_orbit_distance(
                        child.bits(),
                        origin_bits
                    );
                    maximum_six_gap_orbit_distance = std::max(
                        maximum_six_gap_orbit_distance,
                        orbit_distance
                    );
                    const bool better_distant =
                        !best_distant_state.has_value() ||
                        std::tuple{
                            child.uncovered(),
                            child.distance_deficit(),
                            child.singletons(),
                            -orbit_distance
                        } <
                        std::tuple{
                            best_distant_state->uncovered(),
                            best_distant_state->distance_deficit(),
                            best_distant_state->singletons(),
                            -best_distant_orbit_distance
                        };
                    if (orbit_distance >= 9 && better_distant) {
                        best_distant_state = child;
                        best_distant_orbit_distance = orbit_distance;
                    }
                    if (orbit_distance >= 9) {
                        const std::string orbit_key =
                            canonical_state_key(child);
                        ++distant_six_gap_visits;
                        if (
                            distant_six_gap_states.find(orbit_key) ==
                            distant_six_gap_states.end()
                        ) {
                            if (
                                distant_six_gap_states.size() <
                                kDistantArchiveLimit
                            ) {
                                distant_six_gap_states.insert(orbit_key);
                            } else {
                                distant_archive_capped = true;
                            }
                        }
                    }
                }
                std::vector<int> child_gaps = child.uncovered_words();
                EjectionNode node{
                    std::move(child),
                    std::move(child_gaps),
                    candidate.root_distance
                };

                if (better_tuple(
                        node.state.uncovered(),
                        node.state.distance_deficit(),
                        node.state.singletons(),
                        local_best.uncovered(),
                        local_best.distance_deficit(),
                        local_best.singletons()
                    )) {
                    local_best = node.state;
                    chains_since_improvement = 0;
                    improved_local_best = true;
                    update_shared(
                        shared,
                        local_best,
                        worker,
                        worker_seed,
                        options.output_path
                    );
                }
                if (node.state.uncovered() == 0) {
                    update_shared(
                        shared,
                        node.state,
                        worker,
                        worker_seed,
                        options.output_path
                    );
                    ++completed_chains;
                    print_metrics();
                    return;
                }
                if (
                    !best_chain_endpoint.has_value() ||
                    ejection_node_less(node, *best_chain_endpoint)
                ) {
                    best_chain_endpoint = node;
                }
                auto& exploratory = exploratory_by_uncovered[
                    static_cast<std::size_t>(
                        node.state.uncovered()
                    )
                ];
                if (
                    !exploratory.has_value() ||
                    std::tuple{
                        raw_origin_distance,
                        -node.state.singletons()
                    } >
                    std::tuple{
                        bit_distance(
                            exploratory->state.bits(),
                            origin_bits
                        ),
                        -exploratory->state.singletons()
                    }
                ) {
                    exploratory = node;
                }
                next.push_back(std::move(node));
            }
            beam = std::move(next);
        }

        if (!generated_state) {
            current = local_best;
            ++chains_since_improvement;
            ++completed_chains;
            continue;
        }
        const EjectionNode* endpoint = &*best_chain_endpoint;
        const bool exploration_chain = chain % 4U == 3U;
        if (exploration_chain) {
            ++exploration_chains;
            const std::int64_t allowed_uncovered =
                static_cast<std::int64_t>(local_best.uncovered()) +
                options.ejection_endpoint_damage;
            const EjectionNode* exploratory = nullptr;
            const int maximum_allowed = static_cast<int>(
                std::min<std::int64_t>(
                    allowed_uncovered,
                    current.word_count()
                )
            );
            for (int uncovered = 0;
                 uncovered <= maximum_allowed;
                 ++uncovered) {
                const auto& candidate = exploratory_by_uncovered[
                    static_cast<std::size_t>(uncovered)
                ];
                if (!candidate.has_value()) {
                    continue;
                }
                const int candidate_distance =
                    bit_distance(candidate->state.bits(), origin_bits);
                if (
                    exploratory == nullptr ||
                    std::tuple{
                        candidate_distance,
                        -candidate->state.uncovered(),
                        -candidate->state.singletons()
                    } >
                    std::tuple{
                        bit_distance(
                            exploratory->state.bits(),
                            origin_bits
                        ),
                        -exploratory->state.uncovered(),
                        -exploratory->state.singletons()
                    }
                ) {
                    exploratory = &*candidate;
                }
            }
            if (exploratory != nullptr) {
                endpoint = exploratory;
            }
        }
        const bool improves_current = better_tuple(
            endpoint->state.uncovered(),
            endpoint->state.distance_deficit(),
            endpoint->state.singletons(),
            current.uncovered(),
            current.distance_deficit(),
            current.singletons()
        );
        const bool ties_current =
            endpoint->state.uncovered() == current.uncovered() &&
            endpoint->state.distance_deficit() ==
                current.distance_deficit() &&
            endpoint->state.singletons() == current.singletons();
        const int gap_increase =
            endpoint->state.uncovered() - current.uncovered();
        const std::int64_t allowed_endpoint_uncovered =
            static_cast<std::int64_t>(local_best.uncovered()) +
            options.ejection_endpoint_damage;
        const bool annealed =
            gap_increase >= 0 &&
            endpoint->state.uncovered() <=
                allowed_endpoint_uncovered &&
            rng() % (
                4U +
                2U * static_cast<std::uint64_t>(gap_increase)
            ) == 0;
        if (
            improves_current ||
            ties_current ||
            annealed ||
            (
                exploration_chain &&
                endpoint->state.uncovered() <=
                    allowed_endpoint_uncovered
            )
        ) {
            current = endpoint->state;
            ++accepted_endpoints;
        }

        if (!improved_local_best) {
            ++chains_since_improvement;
        }
        if (
            chains_since_improvement >= 64U ||
            current.uncovered() >
                allowed_endpoint_uncovered
        ) {
            current = local_best;
            chains_since_improvement = 0;
        }
        ++completed_chains;
    }
    print_metrics();
}

void run_worker(
    const Options& options,
    int worker,
    const std::vector<std::vector<std::uint8_t>>& starts,
    SharedBest& shared
) {
    if (options.ejection) {
        run_ejection_worker(options, worker, starts, shared);
        return;
    }

    const std::uint64_t worker_seed =
        options.seed + 0x9e3779b97f4a7c15ULL *
                           static_cast<std::uint64_t>(worker + 1);
    std::mt19937_64 rng(worker_seed);

    State state(
        starts[static_cast<std::size_t>(worker) % starts.size()],
        options.n,
        options.radius
    );
    Scratch scratch(state.length(), state.word_count());

    if (worker >= static_cast<int>(starts.size())) {
        const int kick_size = std::min(state.length(), 2 + worker % 5);
        state.apply(random_move(rng, state.length(), kick_size), scratch);
    }

    State local_best = state;
    State breakout_best = state;
    std::vector<std::uint64_t> tabu_until(
        static_cast<std::size_t>(state.length()),
        0
    );
    std::uniform_int_distribution<int> position_distribution(
        0,
        state.length() - 1
    );
    std::vector<std::uint64_t> breakout_weights;
    if (options.breakout) {
        breakout_weights.assign(
            static_cast<std::size_t>(state.word_count()),
            kInitialBreakoutWeight
        );
    }

    update_shared(shared, state, worker, worker_seed, options.output_path);
    std::uint64_t stagnation = 0;
    std::uint64_t breakout_plateau = 0;
    std::uint64_t breakout_best_uncovered_weight = options.breakout
        ? state.weighted_uncovered(breakout_weights)
        : 0;

    for (std::uint64_t iteration = 1;
         options.iterations != 0 && !shared.stop.load();) {
        std::optional<Move> selected_move;
        Evaluation selected_evaluation;
        std::uint64_t selected_score = std::numeric_limits<std::uint64_t>::max();
        std::optional<BreakoutMoveScore> selected_breakout_score;
        std::optional<BreakoutContext> breakout_context;
        if (options.breakout) {
            breakout_context = BreakoutContext{
                &breakout_weights,
                state.weighted_uncovered(breakout_weights),
                breakout_best_uncovered_weight,
                breakout_best.distance_deficit(),
                breakout_best.singletons()
            };
        }
        const BreakoutContext* scoring = breakout_context.has_value()
            ? &*breakout_context
            : nullptr;

        for (int position = 0; position < state.length(); ++position) {
            consider_move(
                Move{position},
                state,
                scratch,
                tabu_until,
                iteration,
                local_best.energy(),
                scoring,
                rng,
                selected_move,
                selected_evaluation,
                selected_score,
                selected_breakout_score
            );
        }

        const std::vector<int> uncovered = state.uncovered_words();
        if (!uncovered.empty()) {
            const int target = choose_uncovered_target(
                uncovered,
                options.breakout ? &breakout_weights : nullptr,
                rng
            );
            for (int sample = 0; sample < options.target_samples; ++sample) {
                const int start = position_distribution(rng);
                const int difference =
                    state.windows()[static_cast<std::size_t>(start)] ^ target;
                const int distance =
                    std::popcount(static_cast<unsigned int>(difference));
                if (distance < 2 ||
                    distance - 1 > options.max_target_flips) {
                    continue;
                }

                std::vector<int> mismatches;
                for (int bit = 0; bit < state.n(); ++bit) {
                    if ((difference & (1 << bit)) != 0) {
                        mismatches.push_back(bit);
                    }
                }
                const int leave = mismatches[
                    static_cast<std::size_t>(rng() % mismatches.size())
                ];
                Move repair;
                for (const int bit : mismatches) {
                    if (bit != leave) {
                        repair.push_back((start + bit) % state.length());
                    }
                }
                std::sort(repair.begin(), repair.end());
                consider_move(
                    repair,
                    state,
                    scratch,
                    tabu_until,
                    iteration,
                    local_best.energy(),
                    scoring,
                    rng,
                    selected_move,
                    selected_evaluation,
                    selected_score,
                    selected_breakout_score
                );
            }
        }

        if (state.length() >= 2) {
            for (int sample = 0; sample < options.pair_samples; ++sample) {
                consider_move(
                    random_move(rng, state.length(), 2),
                    state,
                    scratch,
                    tabu_until,
                    iteration,
                    local_best.energy(),
                    scoring,
                    rng,
                    selected_move,
                    selected_evaluation,
                    selected_score,
                    selected_breakout_score
                );
            }
        }
        if (state.length() >= 3) {
            for (int sample = 0; sample < options.triple_samples; ++sample) {
                consider_move(
                    random_move(rng, state.length(), 3),
                    state,
                    scratch,
                    tabu_until,
                    iteration,
                    local_best.energy(),
                    scoring,
                    rng,
                    selected_move,
                    selected_evaluation,
                    selected_score,
                    selected_breakout_score
                );
            }
        }

        const int cycle = 4000;
        const int cycle_position = static_cast<int>(iteration % cycle);
        const std::int64_t threshold =
            (cycle - cycle_position) * kUncoveredWeight / cycle;

        bool accept_selected = false;
        if (selected_move.has_value()) {
            if (!options.breakout) {
                accept_selected =
                    selected_evaluation.energy() <= state.energy() + threshold;
            } else {
                if (!selected_breakout_score.has_value() ||
                    !breakout_context.has_value()) {
                    throw std::logic_error(
                        "missing breakout score for selected move"
                    );
                }
                const Evaluation current{
                    state.uncovered(),
                    state.distance_deficit(),
                    state.singletons()
                };
                accept_selected = breakout_accepts(
                    WeightedEvaluation{
                        selected_evaluation,
                        selected_breakout_score->uncovered_weight
                    },
                    current,
                    breakout_context->current_uncovered_weight,
                    static_cast<std::uint64_t>(threshold)
                );
            }
        }

        if (accept_selected) {
            state.apply(*selected_move, scratch);
            for (const int position : *selected_move) {
                const std::uint64_t tenure = 5U + (rng() % 11U);
                tabu_until[static_cast<std::size_t>(position)] =
                    checked_add(
                        iteration,
                        tenure,
                        "tabu expiration overflow"
                    );
            }
        } else {
            const int kick_size = std::min(
                state.length(),
                2 + static_cast<int>(rng() % 4U)
            );
            state.apply(
                random_move(rng, state.length(), kick_size),
                scratch
            );
        }

        if (state.energy() < local_best.energy()) {
            local_best = state;
            stagnation = 0;
            update_shared(shared, state, worker, worker_seed, options.output_path);
        } else {
            ++stagnation;
        }

        if (state.uncovered() == 0) {
            update_shared(shared, state, worker, worker_seed, options.output_path);
            break;
        }

        if (options.breakout) {
            const std::uint64_t state_uncovered_weight =
                state.weighted_uncovered(breakout_weights);
            if (breakout_objective_less(
                    state_uncovered_weight,
                    state.distance_deficit(),
                    state.singletons(),
                    breakout_best_uncovered_weight,
                    breakout_best.distance_deficit(),
                    breakout_best.singletons()
                )) {
                breakout_best = state;
                breakout_best_uncovered_weight = state_uncovered_weight;
                breakout_plateau = 0;
            } else {
                if (breakout_plateau < options.breakout_stagnation) {
                    ++breakout_plateau;
                }
                if (breakout_plateau >= options.breakout_stagnation) {
                    const bool weights_changed = increase_breakout_weights(
                        state,
                        breakout_weights,
                        options.breakout_increment,
                        options.breakout_max_weight
                    );
                    if (weights_changed) {
                        breakout_best = state;
                        breakout_best_uncovered_weight =
                            state.weighted_uncovered(breakout_weights);
                        breakout_plateau = 0;
                    }
                }
            }
        }

        if (!options.breakout && stagnation >= 1500U) {
            state = local_best;
            const int kick_size = std::min(
                state.length(),
                3 + static_cast<int>(rng() % 5U)
            );
            state.apply(random_move(rng, state.length(), kick_size), scratch);
            std::fill(tabu_until.begin(), tabu_until.end(), 0);
            stagnation = 0;
        }

        if (iteration == options.iterations) {
            break;
        }
        ++iteration;
    }
}

bool run_self_test() {
    {
        for (int length = 1; length <= 10; ++length) {
            const std::uint64_t limit =
                std::uint64_t{1} << length;
            for (std::uint64_t mask = 0; mask < limit; ++mask) {
                std::vector<std::uint8_t> bits(
                    static_cast<std::size_t>(length),
                    0
                );
                for (int index = 0; index < length; ++index) {
                    bits[static_cast<std::size_t>(index)] =
                        static_cast<std::uint8_t>(
                            (mask >> index) & 1U
                        );
                }

                std::string expected(
                    static_cast<std::size_t>(length),
                    '2'
                );
                for (int reflected = 0; reflected < 2; ++reflected) {
                    std::vector<std::uint8_t> orientation = bits;
                    if (reflected != 0) {
                        std::reverse(
                            orientation.begin(),
                            orientation.end()
                        );
                    }
                    for (int shift = 0; shift < length; ++shift) {
                        expected = std::min(
                            expected,
                            rotation_key(
                                orientation,
                                static_cast<std::size_t>(shift)
                            )
                        );
                    }
                }
                if (canonical_bit_key(bits) != expected) {
                    std::cerr
                        << "self-test failed: canonical state key mismatch\n";
                    return false;
                }

                std::vector<std::uint8_t> rotated = bits;
                std::rotate(
                    rotated.begin(),
                    rotated.begin() + length / 2,
                    rotated.end()
                );
                std::vector<std::uint8_t> reflected(
                    bits.rbegin(),
                    bits.rend()
                );
                if (
                    canonical_bit_key(rotated) != expected ||
                    canonical_bit_key(reflected) != expected ||
                    cyclic_orbit_distance(bits, rotated) != 0 ||
                    cyclic_orbit_distance(bits, reflected) != 0
                ) {
                    std::cerr
                        << "self-test failed: cyclic orbit mismatch\n";
                    return false;
                }
            }
        }
    }

    {
        const std::vector<std::uint8_t> zero(70, 0);
        std::vector<std::uint8_t> half(70, 0);
        std::fill(half.begin(), half.begin() + 35, 1);
        if (cyclic_orbit_distance(zero, half) != 35) {
            std::cerr
                << "self-test failed: nonzero cyclic orbit distance\n";
            return false;
        }
    }

    {
        const std::vector<std::uint8_t> de_bruijn{
            0, 0, 0, 1, 0, 1, 1, 1
        };
        const State state(de_bruijn, 3, 0);
        if (state.uncovered() != 0) {
            std::cerr << "self-test failed: de Bruijn sequence was rejected\n";
            return false;
        }
    }

    {
        std::vector<std::uint8_t> bits(17, 0);
        State state(bits, 17, 0);
        Scratch scratch(state.length(), state.word_count());
        const Move move{16};
        const Evaluation evaluation = state.evaluate(move, scratch);
        state.apply(move, scratch);
        const State rebuilt(state.bits(), 17, 0);
        if (state.uncovered() != evaluation.uncovered ||
            state.distance_deficit() != evaluation.distance_deficit ||
            state.singletons() != evaluation.singletons ||
            !state.equivalent_to(rebuilt)) {
            std::cerr << "self-test failed: 17-bit window mismatch\n";
            return false;
        }
    }

    std::mt19937_64 rng(123456789U);
    std::vector<std::uint8_t> bits(17, 0);
    for (std::uint8_t& bit : bits) {
        bit = static_cast<std::uint8_t>(rng() & 1U);
    }
    State state(bits, 5, 1);
    Scratch scratch(state.length(), state.word_count());
    std::vector<std::uint64_t> random_weights(
        static_cast<std::size_t>(state.word_count()),
        1
    );
    for (std::uint64_t& weight : random_weights) {
        weight = 1U + (rng() % 100U);
    }

    for (int trial = 0; trial < 200; ++trial) {
        const Move move =
            random_move(rng, state.length(), 1 + static_cast<int>(rng() % 5U));
        const int predicted_root_distance = distance_after_move(
            state,
            bits,
            bit_distance(state.bits(), bits),
            move
        );
        const Evaluation evaluation = state.evaluate(move, scratch);
        const Evaluation coverage_evaluation =
            state.evaluate_coverage(move, scratch);
        const WeightedEvaluation weighted = state.evaluate_weighted(
            move,
            scratch,
            random_weights,
            state.weighted_uncovered(random_weights)
        );
        State changed = state;
        Scratch changed_scratch(changed.length(), changed.word_count());
        changed.apply(move, changed_scratch);
        State rebuilt(changed.bits(), changed.n(), 1);

        if (changed.uncovered() != evaluation.uncovered ||
            changed.distance_deficit() != evaluation.distance_deficit ||
            changed.singletons() != evaluation.singletons ||
            changed.uncovered() != coverage_evaluation.uncovered ||
            changed.singletons() != coverage_evaluation.singletons ||
            changed.uncovered() != weighted.raw.uncovered ||
            changed.distance_deficit() != weighted.raw.distance_deficit ||
            changed.singletons() != weighted.raw.singletons ||
            changed.weighted_uncovered(random_weights) !=
                weighted.uncovered_weight ||
            predicted_root_distance !=
                bit_distance(changed.bits(), bits) ||
            !changed.equivalent_to(rebuilt)) {
            std::cerr << "self-test failed: incremental update mismatch\n";
            return false;
        }
        state = changed;
    }

    {
        std::mt19937_64 repair_rng(987654321U);
        for (int trial = 0; trial < 50; ++trial) {
            std::vector<std::uint8_t> repair_bits(8, 0);
            for (std::uint8_t& bit : repair_bits) {
                bit = static_cast<std::uint8_t>(repair_rng() & 1U);
            }
            const State repair_state(repair_bits, 4, 1);
            for (int target = 0;
                 target < repair_state.word_count();
                 ++target) {
                const std::vector<Move> repairs =
                    target_repair_moves(repair_state, target, 3);
                for (const Move& move : repairs) {
                    State changed = repair_state;
                    Scratch changed_scratch(
                        changed.length(),
                        changed.word_count()
                    );
                    changed.apply(move, changed_scratch);
                    const std::vector<int> gaps =
                        changed.uncovered_words();
                    if (
                        std::binary_search(
                            gaps.begin(),
                            gaps.end(),
                            target
                        )
                    ) {
                        std::cerr
                            << "self-test failed: ejection move did not "
                            << "repair target\n";
                        return false;
                    }
                }
            }
        }

        bool rejected_radius_zero = false;
        try {
            const State radius_zero({0, 0, 0, 0}, 3, 0);
            static_cast<void>(
                target_repair_moves(radius_zero, 7, 3)
            );
        } catch (const std::invalid_argument&) {
            rejected_radius_zero = true;
        }
        if (!rejected_radius_zero) {
            std::cerr
                << "self-test failed: radius-zero ejection was accepted\n";
            return false;
        }
    }

    {
        const std::vector<int> gaps{1, 3, 5, 7};
        const std::vector<int> preferred{5, 1};
        std::mt19937_64 target_rng(123U);
        const std::vector<int> ordered = ordered_ejection_targets(
            gaps,
            preferred,
            target_rng
        );
        std::vector<int> sorted = ordered;
        std::sort(sorted.begin(), sorted.end());
        if (sorted != gaps) {
            std::cerr
                << "self-test failed: ejection target ordering lost gaps\n";
            return false;
        }
    }

    {
        const State repair_state({0, 0, 0, 0}, 3, 1);
        const std::vector<Move> repairs =
            target_repair_moves(repair_state, 7, 2);
        if (repairs.empty()) {
            std::cerr
                << "self-test failed: no ejection repair moves generated\n";
            return false;
        }
        for (const Move& move : repairs) {
            State changed = repair_state;
            Scratch changed_scratch(
                changed.length(),
                changed.word_count()
            );
            changed.apply(move, changed_scratch);
            const std::vector<int> gaps = changed.uncovered_words();
            if (std::binary_search(gaps.begin(), gaps.end(), 7)) {
                std::cerr
                    << "self-test failed: ejection move did not repair target\n";
                return false;
            }
        }
    }

    {
        const State quota_state({0, 0, 0, 1, 1}, 5, 1);
        Scratch quota_scratch(
            quota_state.length(),
            quota_state.word_count()
        );
        std::mt19937_64 quota_rng(2U);
        std::uint64_t evaluations = 0;
        const std::vector<ActionableTarget> batches =
            collect_actionable_repairs(
                quota_state,
                quota_state.uncovered_words(),
                {},
                3,
                1,
                quota_state.uncovered(),
                quota_rng,
                quota_scratch,
                evaluations
            );
        if (
            batches.size() != 1U ||
            batches.front().target != 5 ||
            batches.front().repairs.empty() ||
            evaluations == 0
        ) {
            std::cerr
                << "self-test failed: damage-rejected target consumed "
                << "the ejection quota\n";
            return false;
        }
        for (const ActionableRepair& repair : batches.front().repairs) {
            if (repair.evaluation.uncovered > quota_state.uncovered()) {
                std::cerr
                    << "self-test failed: inadmissible repair entered "
                    << "an actionable target batch\n";
                return false;
            }
        }
    }

    {
        const State exact_state({0, 0, 1, 0, 1, 1}, 6, 1);
        Scratch exact_scratch(
            exact_state.length(),
            exact_state.word_count()
        );
        std::mt19937_64 exact_rng(1U);
        std::uint64_t evaluations = 0;
        const std::vector<ActionableTarget> batches =
            collect_actionable_repairs(
                exact_state,
                {11},
                {},
                3,
                1,
                exact_state.uncovered(),
                exact_rng,
                exact_scratch,
                evaluations
            );
        std::vector<Move> admissible;
        if (batches.size() == 1U) {
            for (const ActionableRepair& repair : batches.front().repairs) {
                admissible.push_back(repair.move);
            }
        }
        std::sort(admissible.begin(), admissible.end());
        const std::vector<Move> expected{
            {0, 4},
            {1, 2},
            {1, 5},
            {3, 4}
        };
        if (
            batches.size() != 1U ||
            batches.front().target != 11 ||
            admissible != expected ||
            evaluations == 0
        ) {
            std::cerr
                << "self-test failed: exact-target ejection repairs "
                << "were incomplete\n";
            return false;
        }
    }

    {
        State weighted_state({0, 1}, 2, 1);
        Scratch weighted_scratch(
            weighted_state.length(),
            weighted_state.word_count()
        );
        const std::vector<std::uint64_t> weights{9, 1, 1, 2};
        const std::uint64_t current =
            weighted_state.weighted_uncovered(weights);
        const WeightedEvaluation leave_zero =
            weighted_state.evaluate_weighted(
                Move{0},
                weighted_scratch,
                weights,
                current
            );
        const WeightedEvaluation leave_three =
            weighted_state.evaluate_weighted(
                Move{1},
                weighted_scratch,
                weights,
                current
            );
        const BreakoutMoveScore zero_score{
            leave_zero.uncovered_weight,
            leave_zero.raw.distance_deficit,
            leave_zero.raw.singletons,
            0
        };
        const BreakoutMoveScore three_score{
            leave_three.uncovered_weight,
            leave_three.raw.distance_deficit,
            leave_three.raw.singletons,
            0
        };
        if (leave_zero.raw.uncovered != 1 ||
            leave_three.raw.uncovered != 1 ||
            leave_zero.uncovered_weight != 9 ||
            leave_three.uncovered_weight != 2 ||
            !breakout_score_less(three_score, zero_score)) {
            std::cerr << "self-test failed: breakout move ordering mismatch\n";
            return false;
        }
    }

    {
        const State broken({1, 1}, 2, 1);
        std::vector<std::uint64_t> weights(4, 1);
        const bool first_changed = increase_breakout_weights(
            broken,
            weights,
            std::numeric_limits<std::uint64_t>::max(),
            3
        );
        const bool second_changed =
            increase_breakout_weights(broken, weights, 1, 3);
        if (!first_changed || second_changed || weights[0] != 3 ||
            weights[1] != 1 || weights[2] != 1 || weights[3] != 1) {
            std::cerr << "self-test failed: breakout weight update mismatch\n";
            return false;
        }
    }

    {
        const State overflow_state({0, 0}, 2, 0);
        const std::vector<std::uint64_t> weights(
            4,
            std::numeric_limits<std::uint64_t>::max()
        );
        bool overflow_detected = false;
        try {
            static_cast<void>(overflow_state.weighted_uncovered(weights));
        } catch (const std::overflow_error&) {
            overflow_detected = true;
        }
        if (!overflow_detected) {
            std::cerr << "self-test failed: breakout overflow was not detected\n";
            return false;
        }
    }

    {
        const std::vector<int> targets{0, 3};
        std::vector<std::uint64_t> weights{5, 1, 1, 5};
        std::mt19937_64 left_rng(987654321U);
        std::mt19937_64 right_rng(987654321U);
        for (int trial = 0; trial < 64; ++trial) {
            if (choose_uncovered_target(targets, &weights, left_rng) !=
                choose_uncovered_target(targets, &weights, right_rng)) {
                std::cerr
                    << "self-test failed: breakout target was nondeterministic\n";
                return false;
            }
        }
        weights[0] = 6;
        if (choose_uncovered_target(targets, &weights, left_rng) != 0) {
            std::cerr
                << "self-test failed: breakout target ignored maximum weight\n";
            return false;
        }
    }

    {
        const WeightedEvaluation candidate{
            Evaluation{2, 100, 100},
            4
        };
        const Evaluation current{1, 0, 0};
        if (!breakout_accepts(candidate, current, 5, 0)) {
            std::cerr
                << "self-test failed: breakout rejected weighted improvement\n";
            return false;
        }
    }

    std::cout << "self-test passed\n";
    return true;
}

void print_usage(const char* program) {
    std::cout
        << "Usage:\n"
        << "  " << program
        << " --length L --baseline FILE [search options]\n"
        << "  " << program
        << " --verify FILE --n N --radius R --expected-length L\n"
        << "  " << program << " --self-test\n\n"
        << "Search options:\n"
        << "  --workers N\n"
        << "  --iterations N\n"
        << "  --seed N\n"
        << "  --output FILE\n"
        << "  --target-samples N\n"
        << "  --pair-samples N\n"
        << "  --triple-samples N\n"
        << "  --max-target-flips N\n"
        << "  --ejection\n"
        << "  --ejection-beam-width N\n"
        << "  --ejection-depth N\n"
        << "  --ejection-max-action N\n"
        << "  --ejection-damage N\n"
        << "  --ejection-endpoint-damage N\n"
        << "  --ejection-targets N\n"
        << "  --breakout\n"
        << "  --breakout-stagnation N  Iterations before increasing weights\n"
        << "  --breakout-increment N   Weight increase per breakout\n"
        << "  --breakout-max-weight N  Maximum weight per uncovered word\n"
        << "\nFixed --seed with --workers 1 reproduces the trajectory "
        << "with the same binary and toolchain.\n";
}

std::uint64_t parse_unsigned(const std::string& value, const std::string& name) {
    if (value.empty() ||
        !std::all_of(value.begin(), value.end(), [](char character) {
            return character >= '0' && character <= '9';
        })) {
        throw std::invalid_argument("invalid value for " + name);
    }
    std::size_t consumed = 0;
    const std::uint64_t result = std::stoull(value, &consumed);
    if (consumed != value.size()) {
        throw std::invalid_argument("invalid value for " + name);
    }
    return result;
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

Options parse_options(int argc, char** argv) {
    Options options;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        auto require_value = [&](const std::string& name) -> std::string {
            if (index + 1 >= argc) {
                throw std::invalid_argument("missing value for " + name);
            }
            return argv[++index];
        };

        if (argument == "--n") {
            options.n = parse_int(require_value(argument), argument);
        } else if (argument == "--radius") {
            options.radius = parse_int(require_value(argument), argument);
        } else if (argument == "--length") {
            options.length = parse_int(require_value(argument), argument);
        } else if (argument == "--expected-length") {
            options.expected_length =
                parse_int(require_value(argument), argument);
        } else if (argument == "--workers") {
            options.workers = parse_int(require_value(argument), argument);
        } else if (argument == "--iterations") {
            options.iterations =
                parse_unsigned(require_value(argument), argument);
        } else if (argument == "--seed") {
            options.seed = parse_unsigned(require_value(argument), argument);
        } else if (argument == "--target-samples") {
            options.target_samples =
                parse_int(require_value(argument), argument);
        } else if (argument == "--pair-samples") {
            options.pair_samples =
                parse_int(require_value(argument), argument);
        } else if (argument == "--triple-samples") {
            options.triple_samples =
                parse_int(require_value(argument), argument);
        } else if (argument == "--max-target-flips") {
            options.max_target_flips =
                parse_int(require_value(argument), argument);
        } else if (argument == "--ejection") {
            options.ejection = true;
        } else if (argument == "--ejection-beam-width") {
            options.ejection_beam_width =
                parse_int(require_value(argument), argument);
        } else if (argument == "--ejection-depth") {
            options.ejection_depth =
                parse_int(require_value(argument), argument);
        } else if (argument == "--ejection-max-action") {
            options.ejection_max_action =
                parse_int(require_value(argument), argument);
        } else if (argument == "--ejection-damage") {
            options.ejection_damage =
                parse_int(require_value(argument), argument);
        } else if (argument == "--ejection-endpoint-damage") {
            options.ejection_endpoint_damage =
                parse_int(require_value(argument), argument);
        } else if (argument == "--ejection-targets") {
            options.ejection_targets =
                parse_int(require_value(argument), argument);
        } else if (argument == "--breakout") {
            options.breakout = true;
        } else if (argument == "--breakout-stagnation") {
            options.breakout_stagnation =
                parse_unsigned(require_value(argument), argument);
        } else if (argument == "--breakout-increment") {
            options.breakout_increment =
                parse_unsigned(require_value(argument), argument);
        } else if (argument == "--breakout-max-weight") {
            options.breakout_max_weight =
                parse_unsigned(require_value(argument), argument);
        } else if (argument == "--baseline") {
            options.baseline_path = require_value(argument);
        } else if (argument == "--output") {
            options.output_path = require_value(argument);
        } else if (argument == "--verify") {
            options.verify_path = require_value(argument);
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

int verify_file(const Options& options) {
    const std::vector<std::uint8_t> bits = load_bits(options.verify_path);
    const State state(bits, options.n, options.radius);
    const bool length_matches =
        options.expected_length < 0 ||
        static_cast<int>(bits.size()) == options.expected_length;
    const bool valid = state.uncovered() == 0 && length_matches;

    std::cout << "{\"valid\":" << (valid ? "true" : "false")
              << ",\"length\":" << bits.size()
              << ",\"uncovered\":" << state.uncovered()
              << ",\"distance_deficit\":" << state.distance_deficit()
              << ",\"singletons\":" << state.singletons() << "}\n";
    return valid ? 0 : 1;
}

int search(const Options& options) {
    if (options.baseline_path.empty()) {
        throw std::invalid_argument("--baseline is required for search");
    }
    if (options.workers <= 0 || options.length <= 0 ||
        options.target_samples < 0 || options.pair_samples < 0 ||
        options.triple_samples < 0 || options.max_target_flips <= 0) {
        throw std::invalid_argument("search parameters must be positive");
    }
    if (options.ejection &&
        (options.ejection_beam_width <= 0 ||
         options.ejection_depth <= 0 ||
         options.ejection_max_action <= 0 ||
         options.ejection_damage < 0 ||
         options.ejection_endpoint_damage < 0 ||
         options.ejection_targets <= 0)) {
        throw std::invalid_argument(
            "ejection parameters must be positive"
        );
    }
    if (options.ejection && options.radius != 1) {
        throw std::invalid_argument(
            "ejection mode currently requires --radius 1"
        );
    }
    if (options.ejection && options.breakout) {
        throw std::invalid_argument(
            "--ejection and --breakout are separate search modes"
        );
    }
    if (options.breakout &&
        (options.breakout_stagnation == 0 ||
         options.breakout_increment == 0 ||
         options.breakout_max_weight < kInitialBreakoutWeight)) {
        throw std::invalid_argument(
            "breakout parameters must be positive"
        );
    }

    const std::vector<std::uint8_t> baseline =
        load_bits(options.baseline_path);
    const auto starts = ranked_starts(
        baseline,
        options.length,
        options.n,
        options.radius
    );

    const State best_start(starts.front(), options.n, options.radius);
    if (
        options.ejection &&
        (
            options.ejection_max_action > best_start.n() ||
            options.ejection_damage > best_start.word_count() ||
            options.ejection_endpoint_damage >
                best_start.word_count() ||
            options.ejection_targets > best_start.word_count()
        )
    ) {
        throw std::invalid_argument(
            "ejection parameters exceed the problem dimensions"
        );
    }
    if (options.breakout &&
        options.breakout_max_weight >
            std::numeric_limits<std::uint64_t>::max() /
                static_cast<std::uint64_t>(best_start.word_count())) {
        throw std::invalid_argument(
            "--breakout-max-weight is too large for the word count"
        );
    }
    std::cout << "ranked_starts=" << starts.size()
              << " best_uncovered=" << best_start.uncovered()
              << " best_distance_deficit="
              << best_start.distance_deficit()
              << " best_singletons=" << best_start.singletons() << '\n';

    SharedBest shared;
    std::vector<std::thread> threads;
    threads.reserve(static_cast<std::size_t>(options.workers));
    try {
        for (int worker = 0; worker < options.workers; ++worker) {
            threads.emplace_back([&options, worker, &starts, &shared]() {
                try {
                    run_worker(options, worker, starts, shared);
                } catch (...) {
                    std::lock_guard<std::mutex> lock(shared.mutex);
                    if (shared.error == nullptr) {
                        shared.error = std::current_exception();
                        shared.error_worker = worker;
                    }
                    shared.stop.store(true);
                }
            });
        }
    } catch (...) {
        shared.stop.store(true);
        for (std::thread& thread : threads) {
            thread.join();
        }
        throw;
    }
    for (std::thread& thread : threads) {
        thread.join();
    }

    std::exception_ptr worker_error;
    int error_worker = -1;
    {
        std::lock_guard<std::mutex> lock(shared.mutex);
        worker_error = shared.error;
        error_worker = shared.error_worker;
    }
    if (worker_error != nullptr) {
        try {
            std::rethrow_exception(worker_error);
        } catch (const std::exception& error) {
            throw std::runtime_error(
                "worker " + std::to_string(error_worker) +
                " failed: " + error.what()
            );
        } catch (...) {
            throw std::runtime_error(
                "worker " + std::to_string(error_worker) +
                " failed with a non-standard exception"
            );
        }
    }

    {
        std::lock_guard<std::mutex> lock(shared.mutex);
        if (!shared.found.load() && !options.output_path.empty() &&
            !shared.bits.empty()) {
            write_bits(options.output_path + ".best", shared.bits);
        }
        std::cout << "found=" << (shared.found.load() ? "true" : "false")
                  << " best_uncovered=" << shared.uncovered
                  << " best_distance_deficit=" << shared.distance_deficit
                  << " best_singletons=" << shared.singletons
                  << " worker=" << shared.worker
                  << " seed=" << shared.seed << '\n';
    }
    return shared.found.load() ? 0 : 3;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const Options options = parse_options(argc, argv);
        if (options.self_test) {
            return run_self_test() ? 0 : 1;
        }
        if (!options.verify_path.empty()) {
            return verify_file(options);
        }
        return search(options);
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        print_usage(argv[0]);
        return 2;
    }
}
