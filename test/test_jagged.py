import struct
import sys
from collections.abc import Callable
from typing import Any

import jagged
import jagged_added
import jagged_narrow
import jagged_removed
import scalgoproto
from test_base import read_in, require, validate_out


def write_jagged(second_name_offset: int) -> bytes:
    # Nodes 0 and 2 own no entries, the last node owns no names and entry 1
    # owns no bins, so elements without children occur at the start, in the middle
    # and at the end.
    w = scalgoproto.Writer()
    root = w.construct_table(jagged.JaggedOut)
    nodes = root.add_nodes(4)
    entries = root.add_entries(3)
    bins = root.add_bins(3)
    names = root.add_names(3)
    entry_offsets = [0, 0, 2, 2]
    name_offsets = [0, 1, second_name_offset, 3]
    for i in range(4):
        nodes[i].x = 10 + i
        nodes[i].entries_offset = entry_offsets[i]
        nodes[i].names_offset = name_offsets[i]
    for i, (kind, offset) in enumerate([(7, 0), (9, 2), (11, 2)]):
        entries[i].kind = kind
        entries[i].bins_offset = offset
    for i, b in enumerate([1.0, 2.0, 3.0]):
        bins[i] = b
    for i, n in enumerate(["a", "b", "c"]):
        names[i] = n
    root.trailer = 42
    return w.finalize(root)


def write_jagged_claim() -> bytes:
    # The same message as write_jagged(1), written by claiming child ranges.
    w = scalgoproto.Writer()
    root = w.construct_table(jagged.JaggedOut)
    nodes = root.add_nodes(4)
    ne = root.add_jagged_entries(nodes, 3)
    eb = root.add_jagged_bins(ne.children, 3)
    nn = root.add_jagged_names(nodes, 3)
    for i in range(4):
        nodes[i].x = 10 + i
    e = ne.add(nodes[1], 2)
    e[0].kind = 7
    e[1].kind = 9
    ne.add(nodes[3], 1)[0].kind = 11
    b = eb.add(e[0], 2)
    b[0] = 1.0
    b[1] = 2.0
    eb.add(ne.children[2], 1)[0] = 3.0
    nn.add(nodes[0], 1)[0] = "a"
    n = nn.add(nodes[2], 2)
    n[0] = "b"
    n[1] = "c"
    root.trailer = 42
    return w.finalize(root)


def claim_setup() -> tuple[scalgoproto.Writer, Any, Any, Any]:
    w = scalgoproto.Writer()
    root = w.construct_table(jagged.JaggedOut)
    nodes = root.add_nodes(4)
    return w, root, nodes, root.add_jagged_entries(nodes, 3)


def expect_value_error(f: Callable[[], object], what: str) -> bool:
    try:
        f()
    except ValueError:
        return True
    print("Error expected ValueError: " + what, file=sys.stderr)
    return False


def test_claim(path: str) -> bool:
    data = write_jagged_claim()
    if require(data, write_jagged(1)) or require(data, read_in(path)):
        return False

    w, root, nodes, ne = claim_setup()
    ne.add(nodes[2], 1)
    if not expect_value_error(lambda: ne.add(nodes[1], 1), "out of order"):
        return False
    if not expect_value_error(lambda: ne.add(nodes[2], 1), "same element twice"):
        return False
    if not expect_value_error(lambda: ne.add(nodes[3], 3), "over total"):
        return False
    other = root.add_entries(2)
    if not expect_value_error(lambda: ne.add(other[0], 1), "element of another list"):
        return False
    if not expect_value_error(lambda: ne.add(root, 1), "not an element"):
        return False
    # Failed claims leave the view usable.
    ne.add(nodes[3], 1)
    return expect_value_error(lambda: w.finalize(root), "under total")


def test_out(path: str) -> bool:
    return validate_out(write_jagged(1), path)


def test_in(path: str) -> bool:
    data = read_in(path)
    s = scalgoproto.Reader(data).root(jagged.JaggedIn)
    walk = [
        (
            node.x,
            [(entry.kind, list(entry.bins)) for entry in node.entries],
            list(node.names),
        )
        for node in s.nodes
    ]
    checks = [
        (
            walk,
            [
                (10, [], ["a"]),
                (11, [(7, [1.0, 2.0]), (9, [])], []),
                (12, [], ["b", "c"]),
                (13, [(11, [3.0])], []),
            ],
        ),
        ([node.entries.offset for node in s.nodes], [0, 0, 2, 2]),
        ([entry.bins.offset for entry in s.entries], [0, 2, 2]),
        (s.nodes[3].entries[0].kind, 11),
        (s.trailer, 42),
    ]
    for v, e in checks:
        if require(v, e):
            return False

    # Each node element is 14 bytes: the 2-byte x, then entriesOffset and
    # namesOffset as 6-byte little-endian integers.
    raw, width, _ = s.nodes.raw_bytes()
    if require(width, 14):
        return False
    elements = []
    for i in range(4):
        element = raw[width * i : width * (i + 1)]
        elements.append(
            (
                struct.unpack_from("<h", element, 0)[0],
                int.from_bytes(element[2:8], "little"),
                int.from_bytes(element[8:14], "little"),
            )
        )
    return not require(elements, [(10, 0, 0), (11, 0, 1), (12, 2, 1), (13, 2, 3)])


def test_bad(path: str) -> bool:
    s = scalgoproto.Reader(write_jagged(0)).root(jagged.JaggedIn)
    nodes = s.nodes
    if require(len(nodes[0].names), 1):
        return False
    try:
        nodes[1].names
    except scalgoproto.OutOfBoundsError:
        return True
    print("Error expected OutOfBoundsError", file=sys.stderr)
    return False


def test_short(path: str) -> bool:
    # Simulate data written with an older schema by keeping only the first
    # member of the root table. Lists added in newer versions must read as empty.
    data = bytearray(write_jagged(1))
    root = int.from_bytes(data[4:10], "little")
    data[root + 4 : root + 10] = (6).to_bytes(6, "little")
    s = scalgoproto.Reader(bytes(data)).root(jagged.JaggedIn)
    checks = [
        (len(s.nodes), 4),
        (len(s.entries), 0),
        (len(s.bins), 0),
        (len(s.names), 0),
        (s.trailer, 0),
    ]
    return not any(require(v, e) for v, e in checks)


def test_removed(path: str) -> bool:
    # Read data written before members were removed from the schema. The
    # members after the removed ones must keep their offsets.
    data = read_in(path)
    no_entries = scalgoproto.Reader(data).root(jagged_removed.RemovedEntriesIn)
    no_names = scalgoproto.Reader(data).root(jagged_removed.RemovedBinsNamesIn)
    no_nodes = scalgoproto.Reader(data).root(jagged_removed.RemovedNodesIn)
    checks = [
        ([node.x for node in no_entries.nodes], [10, 11, 12, 13]),
        ([list(n.names) for n in no_entries.nodes], [["a"], [], ["b", "c"], []]),
        (list(no_entries.bins), [1.0, 2.0, 3.0]),
        (no_entries.trailer, 42),
        ([node.x for node in no_names.nodes], [10, 11, 12, 13]),
        ([[x.kind for x in n.entries] for n in no_names.nodes], [[], [7, 9], [], [11]]),
        (no_names.trailer, 42),
        ([list(e.bins) for e in no_nodes.entries], [[1.0, 2.0], [], [3.0]]),
        (list(no_nodes.names), ["a", "b", "c"]),
        (no_nodes.trailer, 42),
    ]
    return not any(require(v, e) for v, e in checks)


def test_added(path: str) -> bool:
    # Read data written before a jagged list was added to the schema. The new
    # list reads as empty for every element.
    s = scalgoproto.Reader(read_in(path)).root(jagged_added.AddedTagsIn)
    checks = [
        ([len(n.entries) for n in s.nodes], [0, 2, 0, 1]),
        ([len(n.tags) for n in s.nodes], [0, 0, 0, 0]),
        (s.trailer, 42),
    ]
    return not any(require(v, e) for v, e in checks)


def test_narrow(path: str) -> bool:
    # Offsets of 1, 2 and 4 bytes, written with views and read back.
    w = scalgoproto.Writer()
    root = w.construct_table(jagged_narrow.NarrowOut)
    nodes = root.add_nodes(3)
    ne = root.add_jagged_entries(nodes, 3)
    nn = root.add_jagged_names(nodes, 1)
    nb = root.add_jagged_bins(nodes, 2)
    e = ne.add(nodes[0], 2)
    e[0] = 7
    e[1] = 8
    ne.add(nodes[2], 1)[0] = 9
    nn.add(nodes[1], 1)[0] = "a"
    nb.add(nodes[2], 2)[1] = 2.0
    s = scalgoproto.Reader(w.finalize(root)).root(jagged_narrow.NarrowIn)
    _, width, _ = s.nodes.raw_bytes()
    checks = [
        (width, 2 + 1 + 2 + 4),
        ([list(n.entries) for n in s.nodes], [[7, 8], [], [9]]),
        ([list(n.names) for n in s.nodes], [[], ["a"], []]),
        ([list(n.bins) for n in s.nodes], [[], [], [0.0, 2.0]]),
    ]
    if any(require(v, e) for v, e in checks):
        return False

    w = scalgoproto.Writer()
    root = w.construct_table(jagged_narrow.NarrowOut)
    nodes = root.add_nodes(1)
    if not expect_value_error(
        lambda: root.add_jagged_entries(nodes, 256), "total too large"
    ):
        return False

    def set_offset() -> None:
        nodes[0].entries_offset = 256

    return expect_value_error(set_offset, "offset too large")


def main() -> None:
    test = sys.argv[1]
    path = sys.argv[2]
    ans = False
    if test == "out_jagged":
        ans = test_out(path)
    elif test == "in_jagged":
        ans = test_in(path)
    elif test == "claim_jagged":
        ans = test_claim(path)
    elif test == "bad_jagged":
        ans = test_bad(path)
    elif test == "short_jagged":
        ans = test_short(path)
    elif test == "removed_jagged":
        ans = test_removed(path)
    elif test == "added_jagged":
        ans = test_added(path)
    elif test == "narrow_jagged":
        ans = test_narrow(path)
    if not ans:
        sys.exit(1)


if __name__ == "__main__":
    main()
