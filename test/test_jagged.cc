// -*- mode: c++; tab-width: 4; indent-tabs-mode: t; eval: (progn (c-set-style "stroustrup") (c-set-offset 'innamespace 0)); -*-
// vi:set ts=4 sts=4 sw=4 noet :

#include "test.hh"

#include "jagged.hh"
#include "jagged_added.hh"
#include "jagged_narrow.hh"
#include "jagged_removed.hh"

using namespace scalgoprototest3;

// Nodes 0 and 2 own no entries, the last node owns no names and entry 1 owns
// no bins, so elements without children occur at the start, in the middle
// and at the end.
static JaggedOut writeJagged(scalgoproto::Writer & w, std::uint64_t secondNameOffset) {
	auto root = w.construct<JaggedOut>();
	auto nodes = root.addNodes(4);
	auto entries = root.addEntries(3);
	auto bins = root.addBins(3);
	auto names = root.addNames(3);
	const std::uint64_t entryOffsets[] = {0, 0, 2, 2};
	const std::uint64_t nameOffsets[] = {0, 1, secondNameOffset, 3};
	for (int i = 0; i < 4; ++i)
		nodes[i].setX(10 + i).setEntriesOffset(entryOffsets[i]).setNamesOffset(nameOffsets[i]);
	entries[0].setKind(7).setBinsOffset(0);
	entries[1].setKind(9).setBinsOffset(2);
	entries[2].setKind(11).setBinsOffset(2);
	bins[0] = 1.0f;
	bins[1] = 2.0f;
	bins[2] = 3.0f;
	names[0] = std::string_view("a");
	names[1] = std::string_view("b");
	names[2] = std::string_view("c");
	root.setTrailer(42);
	return root;
}

// The same message as writeJagged(w, 1), written by claiming child ranges.
static JaggedOut writeJaggedClaim(scalgoproto::Writer & w) {
	auto root = w.construct<JaggedOut>();
	auto nodes = root.addNodes(4);
	auto ne = root.addJaggedEntries(nodes, 3);
	auto eb = root.addJaggedBins(ne.children(), 3);
	auto nn = root.addJaggedNames(nodes, 3);
	for (int i = 0; i < 4; ++i) nodes[i].setX(10 + i);
	auto e = ne.add(nodes[1], 2);
	e[0].setKind(7);
	e[1].setKind(9);
	ne.add(nodes[3], 1)[0].setKind(11);
	auto b = eb.add(e[0], 2);
	b[0] = 1.0f;
	b[1] = 2.0f;
	eb.add(ne.children()[2], 1)[0] = 3.0f;
	nn.add(nodes[0], 1)[0] = std::string_view("a");
	auto n = nn.add(nodes[2], 2);
	n[0] = std::string_view("b");
	n[1] = std::string_view("c");
	root.setTrailer(42);
	return root;
}

template <typename F>
static bool throwsLogicError(F f) {
	try {
		f();
	} catch (std::logic_error &) {
		return true;
	}
	return false;
}

static int claimErrors() {
	scalgoproto::Writer w;
	auto root = w.construct<JaggedOut>();
	auto nodes = root.addNodes(4);
	auto ne = root.addJaggedEntries(nodes, 3);
	auto copy = ne;
	ne.add(nodes[2], 1);
	// Copies share the claim state.
	REQUIRE(throwsLogicError([&] { copy.add(nodes[1], 1); }), true);
	REQUIRE(throwsLogicError([&] { copy.add(nodes[2], 1); }), true);
	REQUIRE(throwsLogicError([&] { ne.add(nodes[3], 3); }), true);
	auto other = root.addNodes(2);
	REQUIRE(throwsLogicError([&] { ne.add(other[0], 1); }), true);
	copy.add(nodes[3], 1);
	REQUIRE(throwsLogicError([&] { w.finalize(root); }), true);
	// clear() drops the registered views.
	w.clear();
	auto root2 = w.construct<JaggedOut>();
	w.finalize(root2);
	return 0;
}

// Offsets of 1, 2 and 4 bytes, written with views and read back.
static int narrow() {
	using namespace scalgoprototest6;
	scalgoproto::Writer w;
	auto root = w.construct<NarrowOut>();
	auto nodes = root.addNodes(3);
	auto ne = root.addJaggedEntries(nodes, 3);
	auto nn = root.addJaggedNames(nodes, 1);
	auto nb = root.addJaggedBins(nodes, 2);
	auto e = ne.add(nodes[0], 2);
	e[0] = 7;
	e[1] = 8;
	ne.add(nodes[2], 1)[0] = 9;
	nn.add(nodes[1], 1)[0] = std::string_view("a");
	nb.add(nodes[2], 2)[1] = 2.0f;
	auto [data, size] = w.finalize(root);
	scalgoproto::Reader r(data, size);
	auto s = r.root<NarrowIn>();
	auto read = s.nodes();
	REQUIRE(read[0].entries().size(), 2);
	REQUIRE(read[0].entries()[1], 8u);
	REQUIRE(read[1].entries().size(), 0);
	REQUIRE(read[2].entries()[0], 9u);
	REQUIRE(read[1].names()[0], "a");
	REQUIRE(read[2].bins().size(), 2);
	REQUIRE(read[2].bins()[1], 2.0f);

	scalgoproto::Writer w2;
	auto root2 = w2.construct<NarrowOut>();
	auto nodes2 = root2.addNodes(1);
	REQUIRE(throwsLogicError([&] { root2.addJaggedEntries(nodes2, 256); }), true);
	return 0;
}

int main(int argc, char ** argv) {
	if (argc < 3) return 4;
	bool useMmap = argc >= 4 && !strcmp(argv[3], "mmap");
	if (!strcmp(argv[1], "out")) {
		auto w = getTestWriter(argv[2], useMmap);
		auto root = writeJagged(w, 1);
		auto [data, size] = w.finalize(root);
		return !validateOut(data, size, argv[2], useMmap);
	} else if (!strcmp(argv[1], "claim")) {
		auto w = getTestWriter(argv[2], useMmap);
		auto root = writeJaggedClaim(w);
		auto [data, size] = w.finalize(root);
		return !validateOut(data, size, argv[2], useMmap);
	} else if (!strcmp(argv[1], "claim_errors")) {
		return claimErrors();
	} else if (!strcmp(argv[1], "narrow")) {
		return narrow();
	} else if (!strcmp(argv[1], "in")) {
		auto o = readIn(argv[2]);
		scalgoproto::Reader r(o.data(), o.size());
		auto s = r.root<JaggedIn>();
		// Walk from each node to its entries and names, and from each entry to its bins.
		std::string walk;
		for (auto node : s.nodes()) {
			walk += std::to_string(node.x()) + "(";
			for (auto entry : node.entries()) {
				walk += std::to_string(entry.kind()) + "[";
				for (float b : entry.bins()) walk += std::to_string(int(b));
				walk += "]";
			}
			for (std::string_view name : node.names()) walk += name;
			walk += ")";
		}
		REQUIRE(walk, std::string("10(a)11(7[12]9[])12(bc)13(11[3])"));
		REQUIRE(s.nodes()[1].entries().offset(), 0);
		REQUIRE(s.nodes()[3].entries().offset(), 2);
		REQUIRE(s.nodes()[3].entries().front().kind(), 11);
		REQUIRE(s.entries()[2].bins().offset(), 2);
		REQUIRE(s.trailer(), 42);
		return 0;
	} else if (!strcmp(argv[1], "removed")) {
		// Read data written before members were removed from the schema.
		// The members after the removed ones must keep their offsets.
		auto o = readIn(argv[2]);
		scalgoproto::Reader r(o.data(), o.size());
		auto e = r.root<scalgoprototest4::RemovedEntriesIn>();
		auto eNodes = e.nodes();
		REQUIRE(eNodes[3].x(), 13);
		REQUIRE(eNodes[0].names().size(), 1);
		REQUIRE(eNodes[2].names().size(), 2);
		REQUIRE(eNodes[2].names()[1], "c");
		REQUIRE(eNodes[3].names().size(), 0);
		REQUIRE(e.bins().size(), 3);
		REQUIRE(e.trailer(), 42);
		auto b = r.root<scalgoprototest4::RemovedBinsNamesIn>();
		auto bNodes = b.nodes();
		REQUIRE(bNodes[3].x(), 13);
		REQUIRE(bNodes[1].entries().size(), 2);
		REQUIRE(bNodes[1].entries()[1].kind(), 9);
		REQUIRE(bNodes[3].entries().front().kind(), 11);
		REQUIRE(b.trailer(), 42);
		auto n = r.root<scalgoprototest4::RemovedNodesIn>();
		auto nEntries = n.entries();
		REQUIRE(nEntries[0].bins().size(), 2);
		REQUIRE(nEntries[2].bins()[0], 3.0f);
		REQUIRE(n.names().size(), 3);
		REQUIRE(n.trailer(), 42);
		return 0;
	} else if (!strcmp(argv[1], "added")) {
		// Read data written before a jagged list was added to the schema. The
		// new list reads as empty for every element.
		auto o = readIn(argv[2]);
		scalgoproto::Reader r(o.data(), o.size());
		auto s = r.root<scalgoprototest5::AddedTagsIn>();
		REQUIRE(s.nodes()[1].entries().size(), 2);
		for (auto node : s.nodes()) REQUIRE(node.tags().size(), 0);
		REQUIRE(s.trailer(), 42);
		return 0;
	} else if (!strcmp(argv[1], "bad")) {
		scalgoproto::Writer w;
		auto root = writeJagged(w, 0);
		auto [data, size] = w.finalize(root);
		scalgoproto::Reader r(data, size);
		auto nodes = r.root<JaggedIn>().nodes();
		REQUIRE(nodes[0].names().size(), 1);
		try {
			nodes[1].names();
			return 1;
		} catch (scalgoproto::OutOfBoundsError &) {
		}
		return 0;
	}
	return 1;
}
