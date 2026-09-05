CXX ?= c++
CXXFLAGS ?= -std=c++20 -O3 -Wall -Wextra -Wpedantic -Werror
PYTHON ?= python3
DRAT_TRIM ?= drat-trim

BUILD_DIR := build
SEARCH_BIN := $(BUILD_DIR)/cover-search
NEIGHBOR_BIN := $(BUILD_DIR)/cover-neighborhood
OVERLAP_CHECKER := $(BUILD_DIR)/exact-overlap-checker
DISTANCE4_CNF := $(BUILD_DIR)/l9-r1-70-distance4-pattern.cnf
DISTANCE4_PROOF := $(BUILD_DIR)/l9-r1-70-distance4-core.drat

.PHONY: all build test solver-test verify-baseline analyze-baseline \
	analyze-backbone analyze-exact-overlap verify-publication search-smoke \
	breakout-smoke ejection-smoke cnf pattern-cnf pattern-neighborhood-cnf \
	exact-support-cnf backbone-overlap-cnf distance4-cnf \
	distance4-proof-check paper-build paper-bundle paper-replay clean

all: build

build: $(SEARCH_BIN) $(NEIGHBOR_BIN) $(OVERLAP_CHECKER)

$(SEARCH_BIN): src/search.cpp
	mkdir -p $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $< -o $@

$(NEIGHBOR_BIN): src/neighborhood.cpp
	mkdir -p $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $< -o $@

$(OVERLAP_CHECKER): src/exact_overlap_checker.cpp
	mkdir -p $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $< -o $@

test: build
	$(PYTHON) -m unittest discover -s tests -v
	$(SEARCH_BIN) --self-test
	$(NEIGHBOR_BIN) --self-test

solver-test:
	$(PYTHON) -m unittest \
		tests.test_analyze_support \
		tests.test_find_cover_support \
		tests.test_flow_cp_sat \
		tests.test_graph_repair_evidence \
		tests.test_graph_repair70_evidence \
		tests.test_repair_support \
		-v

verify-baseline: build
	$(PYTHON) tools/verify.py data/baseline/l9-r1-71.txt \
		--n 9 --radius 1 --expected-length 71
	$(SEARCH_BIN) --verify data/baseline/l9-r1-71.txt \
		--n 9 --radius 1 --expected-length 71

analyze-baseline:
	$(PYTHON) tools/analyze_baseline.py data/baseline/l9-r1-71.txt

analyze-backbone:
	$(PYTHON) tools/analyze_common_backbone.py \
		data/candidates/l9-r1-common-backbone-64.json \
		build/l9-r1-common-backbone-analysis.json \
		--baseline data/baseline/l9-r1-71.txt \
		--overlap-witness \
			data/candidates/l9-r1-70-backbone-overlap-61.txt \
		--n 9 --radius 1 --candidate-length 70

analyze-exact-overlap: $(OVERLAP_CHECKER)
	$(PYTHON) tools/analyze_exact_backbone_overlap.py \
		data/candidates/l9-r1-common-backbone-64.json \
		build/l9-r1-exact-overlap61-analysis.json \
		--overlap-witness \
			data/candidates/l9-r1-70-backbone-overlap-61.txt \
		--n 9 --radius 1 --candidate-length 70 --exact-overlap 61
	$(OVERLAP_CHECKER) \
		data/candidates/l9-r1-common-backbone-64.json \
		> build/l9-r1-exact-overlap61-independent.json
	$(PYTHON) tools/verify_exact_backbone_overlap.py \
		build/l9-r1-exact-overlap61-analysis.json \
		build/l9-r1-exact-overlap61-independent.json \
		--support data/candidates/l9-r1-common-backbone-64.json \
		--analyzer tools/analyze_exact_backbone_overlap.py \
		--witness data/candidates/l9-r1-70-backbone-overlap-61.txt

verify-publication:
	$(PYTHON) tools/verify_common_backbone.py \
		evidence/common-backbone-lemma-20260905/analysis.json \
		--support data/candidates/l9-r1-common-backbone-64.json \
		--witness data/candidates/l9-r1-70-backbone-overlap-61.txt
	$(PYTHON) tools/verify_exact_backbone_overlap.py \
		evidence/exact-backbone-overlap61-20260905/analysis.json \
		evidence/exact-backbone-overlap61-20260905/independent-check.json \
		--support data/candidates/l9-r1-common-backbone-64.json \
		--analyzer \
			evidence/exact-backbone-overlap61-20260905/source/analyze_exact_backbone_overlap_v2.py \
		--witness data/candidates/l9-r1-70-backbone-overlap-61.txt

search-smoke: build
	@$(SEARCH_BIN) --length 70 \
		--baseline data/baseline/l9-r1-71.txt \
		--workers 1 --iterations 100 --seed 1; \
	status=$$?; \
	if [ $$status -ne 0 ] && [ $$status -ne 3 ]; then exit $$status; fi

breakout-smoke: build
	@$(SEARCH_BIN) --length 70 \
		--baseline data/candidates/l9-r1-70-uncovered-6.txt \
		--workers 1 --iterations 10 --seed 1 \
		--breakout --breakout-stagnation 2; \
	status=$$?; \
	if [ $$status -ne 0 ] && [ $$status -ne 3 ]; then exit $$status; fi

ejection-smoke: build
	@output="$$($(SEARCH_BIN) --length 70 \
		--baseline data/candidates/l9-r1-70-uncovered-6.txt \
		--workers 1 --iterations 4 --seed 1 \
		--ejection --ejection-beam-width 16 --ejection-depth 3 \
		--ejection-damage 8 --ejection-endpoint-damage 4 2>&1)"; \
	status=$$?; \
	if [ $$status -ne 0 ] && [ $$status -ne 3 ]; then \
		printf '%s\n' "$$output"; \
		exit $$status; \
	fi; \
	if ! printf '%s\n' "$$output" | \
		grep -Eq 'beam_states=[1-9][0-9]*'; then \
		printf '%s\n' "$$output"; \
		exit 1; \
	fi; \
	if ! printf '%s\n' "$$output" | \
		grep -Eq 'exploration_chains=[1-9][0-9]*'; then \
		printf '%s\n' "$$output"; \
		exit 1; \
	fi

cnf:
	mkdir -p build
	$(PYTHON) tools/generate_cnf.py build/l9-r1-70.cnf \
		--n 9 --radius 1 --length 70

pattern-cnf:
	mkdir -p build
	$(PYTHON) tools/generate_cnf.py build/l9-r1-70-pattern.cnf \
		--n 9 --radius 1 --length 70 --encoding pattern

pattern-neighborhood-cnf:
	mkdir -p build
	$(PYTHON) tools/generate_cnf.py build/l9-r1-70-neighborhood.cnf \
		--n 9 --radius 1 --length 70 --encoding pattern \
		--seed-sequence data/candidates/l9-r1-70-uncovered-6.txt \
		--max-distance 6 --no-symmetry

exact-support-cnf:
	mkdir -p build
	$(PYTHON) tools/generate_cnf.py build/l9-r1-70-support69-pattern.cnf \
		--n 9 --radius 1 --length 70 --encoding pattern \
		--exact-support 69
	$(PYTHON) tools/generate_cnf.py build/l9-r1-70-support70-pattern.cnf \
		--n 9 --radius 1 --length 70 --encoding pattern \
		--exact-support 70

backbone-overlap-cnf:
	mkdir -p build
	$(PYTHON) tools/generate_backbone_overlap_cnf.py \
		data/candidates/l9-r1-common-backbone-64.json \
		build/l9-r1-70-backbone-overlap62.cnf \
		--n 9 --length 70 --minimum-overlap 62

distance4-cnf:
	mkdir -p build
	$(PYTHON) tools/generate_cnf.py $(DISTANCE4_CNF) \
		--n 9 --radius 1 --length 70 --encoding pattern \
		--seed-sequence data/candidates/l9-r1-70-uncovered-6.txt \
		--max-distance 4 --no-symmetry

distance4-proof-check: distance4-cnf
	gzip -dc evidence/sat/distance4-core-binary.drat.gz \
		> $(DISTANCE4_PROOF)
	$(DRAT_TRIM) $(DISTANCE4_CNF) $(DISTANCE4_PROOF) -i

paper-build:
	mkdir -p build/paper
	latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error \
		-output-directory=build/paper paper/main.tex

paper-bundle:
	$(PYTHON) tools/build_arxiv_bundle.py

paper-replay: paper-bundle
	CXX="$(CXX)" $(PYTHON) tools/replay_arxiv_bundle.py

clean:
	rm -rf $(BUILD_DIR)
