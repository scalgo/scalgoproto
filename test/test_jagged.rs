// Tests of jagged lists. A module of test_all.rs, so it uses its macros.

use crate::{jagged, jagged_added, jagged_narrow, jagged_removed};

// Nodes 0 and 2 own no entries, the last node owns no names and entry 1 owns
// no bins, so elements without children occur at the start, in the middle
// and at the end.
fn write_jagged(second_name_offset: u64) -> Vec<u8> {
    let arena = scalgoproto::Arena::new(vec![]);
    let mut writer = scalgoproto::Writer::new(&arena);
    let mut root = writer.add_root::<jagged::Jagged>();
    let mut nodes = root.add_nodes(4);
    let mut entries = root.add_entries(3);
    let mut bins = root.add_bins(3);
    let mut names = root.add_names(3);
    let entry_offsets = [0, 0, 2, 2];
    let name_offsets = [0, 1, second_name_offset, 3];
    for i in 0..4 {
        let mut n = nodes.get(i);
        n.x(10 + i as i16);
        n.entries_offset(entry_offsets[i]);
        n.names_offset(name_offsets[i]);
    }
    for (i, (kind, offset)) in [(7, 0), (9, 2), (11, 2)].into_iter().enumerate() {
        let mut e = entries.get(i);
        e.kind(kind);
        e.bins_offset(offset);
    }
    for (i, b) in [1.0, 2.0, 3.0].into_iter().enumerate() {
        bins.set(i, b);
    }
    for (i, n) in ["a", "b", "c"].into_iter().enumerate() {
        names.add(i, n);
    }
    root.trailer(42);
    arena.finalize()
}

// The same message as write_jagged(1), written by claiming child ranges.
fn write_jagged_claim() -> Vec<u8> {
    let arena = scalgoproto::Arena::new(vec![]);
    let mut writer = scalgoproto::Writer::new(&arena);
    let mut root = writer.add_root::<jagged::Jagged>();
    let mut nodes = root.add_nodes(4);
    let mut ne = root.add_jagged_entries(&nodes, 3);
    let mut eb = root.add_jagged_bins(&ne.children(), 3);
    let mut nn = root.add_jagged_names(&nodes, 3);
    for i in 0..4 {
        nodes.get(i).x(10 + i as i16);
    }
    let mut e = ne.add(1, 2);
    e.get(0).kind(7);
    e.get(1).kind(9);
    ne.add(3, 1).get(0).kind(11);
    let mut b = eb.add(e.offset(), 2);
    b.set(0, 1.0);
    b.set(1, 2.0);
    eb.add(2, 1).set(0, 3.0);
    nn.add(0, 1).add(0, "a");
    let mut n = nn.add(2, 2);
    n.add(0, "b");
    n.add(1, "c");
    root.trailer(42);
    arena.finalize()
}

fn panics<F: FnOnce()>(f: F) -> bool {
    std::panic::catch_unwind(std::panic::AssertUnwindSafe(f)).is_err()
}

pub fn test_out(path: &str) -> scalgoproto::Result<()> {
    crate::validate_out(&write_jagged(1), path)
}

pub fn test_claim(path: &str) -> scalgoproto::Result<()> {
    crate::validate_out(&write_jagged_claim(), path)
}

pub fn test_claim_errors() -> scalgoproto::Result<()> {
    std::panic::set_hook(Box::new(|_| {}));
    let arena = scalgoproto::Arena::new(vec![]);
    let mut writer = scalgoproto::Writer::new(&arena);
    let mut root = writer.add_root::<jagged::Jagged>();
    let nodes = root.add_nodes(4);
    let mut ne = root.add_jagged_entries(&nodes, 3);
    ne.add(2, 1);
    require!(panics(|| { ne.add(1, 1); }), true);
    require!(panics(|| { ne.add(2, 1); }), true);
    require!(panics(|| { ne.add(3, 3); }), true);
    require!(panics(|| { ne.add(4, 1); }), true);
    // Failed claims leave the view usable.
    ne.add(3, 1);
    require!(panics(|| { arena.finalize(); }), true);

    let arena = scalgoproto::Arena::new(vec![]);
    let mut writer = scalgoproto::Writer::new(&arena);
    let mut root = writer.add_root::<jagged_narrow::Narrow>();
    let nodes = root.add_nodes(1);
    require!(panics(|| { root.add_jagged_entries(&nodes, 256); }), true);
    let _ = std::panic::take_hook();
    Ok(())
}

pub fn test_in(path: &str) -> scalgoproto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let s = scalgoproto::read_message::<jagged::Jagged>(&data)?;
    // Walk from each node to its entries and names, and from each entry to its bins.
    let mut walk = String::new();
    for node in s.nodes()?.iter() {
        let node = node?;
        walk += &format!("{}(", node.x());
        for entry in node.entries()?.iter() {
            let entry = entry?;
            walk += &format!("{}[", entry.kind());
            for b in entry.bins()?.iter() {
                walk += &format!("{}", b);
            }
            walk += "]";
        }
        for name in node.names()?.iter() {
            walk += name?;
        }
        walk += ")";
    }
    require!(walk, "10(a)11(7[12]9[])12(bc)13(11[3])");
    require!(s.nodes()?.get(1)?.entries()?.offset(), 0);
    require!(s.nodes()?.get(3)?.entries()?.offset(), 2);
    require!(s.entries()?.get(2)?.bins()?.offset(), 2);
    require!(s.trailer(), 42);
    Ok(())
}

pub fn test_bad() -> scalgoproto::Result<()> {
    let data = write_jagged(0);
    let s = scalgoproto::read_message::<jagged::Jagged>(&data)?;
    let nodes = s.nodes()?;
    require!(nodes.get(0)?.names()?.len(), 1);
    if nodes.get(1)?.names().is_ok() {
        println!("Error expected decreasing offsets to fail");
        return Err(scalgoproto::Error::Overflow());
    }
    Ok(())
}

// Read data written before members were removed from the schema. The
// members after the removed ones must keep their offsets.
pub fn test_removed(path: &str) -> scalgoproto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let e = scalgoproto::read_message::<jagged_removed::RemovedEntries>(&data)?;
    let nodes = e.nodes()?;
    require!(nodes.get(3)?.x(), 13);
    require!(nodes.get(0)?.names()?.len(), 1);
    require!(nodes.get(2)?.names()?.get(1)?, "c");
    require!(nodes.get(3)?.names()?.len(), 0);
    require!(e.bins()?.len(), 3);
    require!(e.trailer(), 42);

    let b = scalgoproto::read_message::<jagged_removed::RemovedBinsNames>(&data)?;
    let nodes = b.nodes()?;
    require!(nodes.get(3)?.x(), 13);
    require!(nodes.get(1)?.entries()?.get(1)?.kind(), 9);
    require!(nodes.get(3)?.entries()?.get(0)?.kind(), 11);
    require!(b.trailer(), 42);

    let n = scalgoproto::read_message::<jagged_removed::RemovedNodes>(&data)?;
    let entries = n.entries()?;
    require!(entries.get(0)?.bins()?.len(), 2);
    require!(entries.get(2)?.bins()?.get(0), 3.0);
    require!(n.names()?.len(), 3);
    require!(n.trailer(), 42);
    Ok(())
}

// Read data written before a jagged list was added to the schema. The new
// list reads as empty for every element.
pub fn test_added(path: &str) -> scalgoproto::Result<()> {
    let data = std::fs::read(path).expect("Unable to read file");
    let s = scalgoproto::read_message::<jagged_added::AddedTags>(&data)?;
    require!(s.nodes()?.get(1)?.entries()?.len(), 2);
    for node in s.nodes()?.iter() {
        require!(node?.tags()?.len(), 0);
    }
    require!(s.trailer(), 42);
    Ok(())
}

// Offsets of 1, 2 and 4 bytes, written with views and read back.
pub fn test_narrow() -> scalgoproto::Result<()> {
    let arena = scalgoproto::Arena::new(vec![]);
    let mut writer = scalgoproto::Writer::new(&arena);
    let mut root = writer.add_root::<jagged_narrow::Narrow>();
    let nodes = root.add_nodes(3);
    let mut ne = root.add_jagged_entries(&nodes, 3);
    let mut nn = root.add_jagged_names(&nodes, 1);
    let mut nb = root.add_jagged_bins(&nodes, 2);
    let mut e = ne.add(0, 2);
    e.set(0, 7);
    e.set(1, 8);
    ne.add(2, 1).set(0, 9);
    nn.add(1, 1).add(0, "a");
    nb.add(2, 2).set(1, 2.0);
    let data = arena.finalize();

    let s = scalgoproto::read_message::<jagged_narrow::Narrow>(&data)?;
    let nodes = s.nodes()?;
    require!(
        nodes.get(0)?.entries()?.iter().collect::<Vec<u32>>(),
        vec![7, 8]
    );
    require!(nodes.get(1)?.entries()?.len(), 0);
    require!(nodes.get(2)?.entries()?.get(0), 9);
    require!(nodes.get(1)?.names()?.get(0)?, "a");
    require!(
        nodes.get(2)?.bins()?.iter().collect::<Vec<f32>>(),
        vec![0.0, 2.0]
    );
    Ok(())
}
