# -*- mode: python; tab-width: 4; indent-tabs-mode: nil; python-indent-offset: 4; coding: utf-8 -*-
"""
Test that everything works
"""

import os
import subprocess
import sys
import tempfile
import json
import shutil
from typing import Callable, List

failures = []


def runValidate(schema: str, fail: bool = False) -> bool:
    code = subprocess.call(["python3", "-m", "scalgoprotoc", "validate", schema])
    return fail == (code != 0)


def runCppSetup(schemas: List[str], cpp: str) -> bool:
    for schema in schemas:
        subprocess.check_call(
            ["python3", "-m", "scalgoprotoc", "cpp", schema, "tmp/", "--single"]
        )
    subprocess.check_call(
        [
            "g++",
            "-ggdb",
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-I",
            "tmp",
            "-I",
            "lib/cpp",
            cpp,
            "-o",
            "tmp/bin",
        ]
    )
    return True


def runCpp(name: str, bin: str) -> bool:
    subprocess.check_call(["tmp/bin", name, bin])
    subprocess.check_call(["tmp/bin", name, bin, "mmap"])
    return True


def runRustSetup(schemas: List[str], main_file: str) -> bool:
    os.makedirs("tmp/rust/src", exist_ok=True)
    shutil.copyfile("lib/rust/scalgoproto.rs", "tmp/rust/src/scalgoproto.rs")
    shutil.copyfile("test/test_all.rs", "tmp/rust/src/test_all.rs")
    with open("tmp/rust/Cargo.toml", "w") as f:
        f.write(
            """
    [package]
name = "test"
version = "0.1.0"
edition = "2018"

[lib]
name = "scalgoproto"
path = "src/scalgoproto.rs"

[[bin]]
name = "ptest"
path = "src/test_all.rs"
"""
        )

    for schema in schemas:
        subprocess.check_call(
            ["python3", "-m", "scalgoprotoc", "rust", schema, "tmp/rust/src"]
        )

    subprocess.check_call(["cargo", "build"], cwd="tmp/rust")
    return True


def runRust(name: str, bin: str) -> bool:
    subprocess.check_call(["tmp/rust/target/debug/ptest", name, bin])
    return True


def runPySetup(schemas: List[str]) -> bool:
    for schema in schemas:
        subprocess.check_call(["python3", "-m", "scalgoprotoc", "py", schema, "tmp"])
    return True


def runPy(name: str, bin: str, mod="test_base.py") -> bool:
    subprocess.check_call(
        ["python3", "test/%s" % mod, name, bin],
        env={"PYTHONPATH": "lib/python:tmp:test"},
    )
    return True


def runTsSetup(schemas: List[str]) -> bool:
    if not os.path.exists("./node_modules/.bin/ts-node"):
        print("Run npm i to install ts-node")
        return False
    for schema in schemas:
        subprocess.check_call(["python3", "-m", "scalgoprotoc", "ts", schema, "tmp"])
    return True


def runTs(name: str, bin: str, mod="test_base.ts") -> bool:
    subprocess.check_call(
        [
            "./node_modules/.bin/ts-node",
            "-r",
            "tsconfig-paths/register",
            "--compiler-options",
            json.dumps(
                {
                    "module": "commonjs",
                    "strict": True,
                    "rootDirs": [os.path.abspath("lib/ts")],
                }
            ),
            "./%s" % mod,
            name,
            bin,
        ],
        cwd="test/",
    )
    return True


def runTest(name: str, func: Callable[[], bool]) -> bool:
    l = 80 - len(name) - 4
    print("%s> %s <%s" % ("=" * (l // 2), name, "=" * (l - l // 2)))
    ok = False
    try:
        ok = func()
    except:
        pass
    if ok:
        print("SUCCESS")
        return True
    else:
        print("FAILURE")
        failures.append(name)
        return False


def runNeg(name: str, base: str, bad: str, good: str) -> None:
    l = 80 - len(name) - 4
    print("%s> %s <%s" % ("=" * (l // 2), name, "=" * (l - l // 2)))
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as f:
        f.write(base % bad)
        f.flush()
        code = subprocess.call(
            ["python3", "-m", "scalgoprotoc", "validate", f.name],
            stderr=subprocess.DEVNULL,
        )
        if code == 0:
            print("FAILURE1")
            failures.append(name)
            return
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as f:
        f.write(base % good)
        f.flush()
        code = subprocess.call(["python3", "-m", "scalgoprotoc", "validate", f.name])
        if code != 0:
            print("FAILURE2")
            failures.append(name)
            return
    print("SUCCESS")


def main():
    if not os.path.isdir("tmp"):
        os.mkdir("tmp")

    # Test names
    for (bad, good) in (("monkey", "Monkey"), ("Monkey_Cat", "MonkeyCat")):
        runNeg("bad table name %s" % bad, "table %s @8908828A {}", bad, good)
    for (bad, good) in (("Cat", "cat"), ("type", "myType"), ("cat_dog", "catDog")):
        runNeg(
            "bad table member name %s" % bad,
            "table Monkey @8908828A {%s : U32}",
            bad,
            good,
        )
    # Test table types
    for (bad, good) in (
        ("Int", "I32"),
        ("int32", "I32"),
        ("bool", "Bool"),
        ("bytes", "Bytes"),
        ("text", "Text"),
        ("String", "Text"),
    ):
        runNeg(
            "bad table member type %s" % bad,
            "table Monkey @8908828A {a: %s}",
            bad,
            good,
        )

    # Test struct types
    for (bad, good) in (
        ("optional U32", "U32"),
        ("U64 = 7", "U64"),
        ("list Bool", "Bool"),
        ("Bytes", "U8"),
        ("Text", "U16"),
        ("union {}", "F32"),
    ):
        runNeg("bad struct member type %s" % bad, "struct Monkey {a: %s}", bad, good)

    # Test table id
    for (bad, good) in (
        ("0x1234567", "@8908828A"),
        ("@8908828X", "@8908828A"),
        ("@8908828a", "@8908828A"),
        ("@8908828A78", "@8908828A"),
        ("", "@8908828A"),
    ):
        runNeg("table id %s" % bad, "table Monkey %s {}", bad, good)
    runNeg(
        "table id inplace a", "table Monkey @8908828A {a: table %s {}}", "", "@8908828B"
    )
    runNeg(
        "table id inplace b",
        "/*HAT*/ table Monkey @8908828A {a: %s table {}}",
        "",
        "inplace",
    )
    runNeg("table id inplace c", "union Monkey {a: table %s {}}", "", "@8908828B")
    runNeg(
        "table id inplace d",
        "table Monkey @8908828A {a: union { a: table %s {}}}",
        "",
        "@8908828B",
    )
    runNeg(
        "table id inplace e",
        "table Monkey @8908828A {a: %s union { a: table {}}}",
        "",
        "inplace",
    )
    runNeg(
        "table id inplace f",
        "table Monkey @8908828A {a: %s union { a: {}}}",
        "",
        "inplace",
    )

    runNeg(
        "multi inplace",
        "table Monkey @8908828A {a: inplace Bytes; b: %s Text}",
        "inplace",
        "",
    )

    runNeg("direct text list", "table Monkey @8908828A {a: %s list Text}", "direct", "")

    runNeg(
        "direct list",
        "table Monkey @8908828A {a: direct list %s}",
        "struct {}",
        "table @8908828B {}",
    )

    runTest("validate base", lambda: runValidate("test/base.spr"))
    runTest("validate complex2", lambda: runValidate("test/complex2.spr"))
    if runTest(
        "cpp setup",
        lambda: runCppSetup(
            ["test/base.spr", "test/complex2.spr"], "test/test_base.cc"
        ),
    ):
        runTest(
            "cpp mmap stress test",
            lambda: subprocess.check_call(["tmp/bin", "mmap_stress", "test/mmap.bin"])
            or True,
        )
        runTest(
            "cpp out default simple",
            lambda: runCpp("out_default", "test/simple_default.bin"),
        )
        runTest(
            "cpp in default simple",
            lambda: runCpp("in_default", "test/simple_default.bin"),
        )
        runTest("cpp out simple", lambda: runCpp("out", "test/simple.bin"))
        runTest("cpp in simple", lambda: runCpp("in", "test/simple.bin"))
        runTest("cpp out complex", lambda: runCpp("out_complex", "test/complex.bin"))
        runTest("cpp in complex", lambda: runCpp("in_complex", "test/complex.bin"))

        runTest("cpp out inplace", lambda: runCpp("out_inplace", "test/inplace.bin"))
        runTest("cpp in inplace", lambda: runCpp("in_inplace", "test/inplace.bin"))
        runTest("cpp out extend1", lambda: runCpp("out_extend1", "test/extend1.bin"))
        runTest("cpp in extend1", lambda: runCpp("in_extend1", "test/extend1.bin"))
        runTest("cpp out extend2", lambda: runCpp("out_extend2", "test/extend2.bin"))
        runTest("cpp in extend2", lambda: runCpp("in_extend2", "test/extend2.bin"))
        runTest("cpp out complex2", lambda: runCpp("out_complex2", "test/complex2.bin"))
        runTest("cpp in complex2", lambda: runCpp("in_complex2", "test/complex2.bin"))

    if runTest(
        "cpp union setup", lambda: runCppSetup(["test/union.spr"], "test/test_union.cc")
    ):
        runTest("cpp out union", lambda: runCpp("out", "test/union.bin"))
        runTest("cpp in union", lambda: runCpp("in", "test/union.bin"))

    if runTest(
        "py setup",
        lambda: runPySetup(["test/base.spr", "test/complex2.spr", "test/union.spr"]),
    ):
        runTest(
            "py out default simple",
            lambda: runPy("out_default", "test/simple_default.bin"),
        )
        runTest(
            "py in default simple",
            lambda: runPy("in_default", "test/simple_default.bin"),
        )
        runTest("py out simple", lambda: runPy("out", "test/simple.bin"))
        runTest("py in simple", lambda: runPy("in", "test/simple.bin"))
        runTest("py out complex", lambda: runPy("out_complex", "test/complex.bin"))
        runTest("py in complex", lambda: runPy("in_complex", "test/complex.bin"))
        runTest("py out complex2", lambda: runPy("out_complex2", "test/complex2.bin"))
        runTest("py in complex2", lambda: runPy("in_complex2", "test/complex2.bin"))
        runTest("py out inplace", lambda: runPy("out_inplace", "test/inplace.bin"))
        runTest("py in inplace", lambda: runPy("in_inplace", "test/inplace.bin"))
        runTest("py out extend1", lambda: runPy("out_extend1", "test/extend1.bin"))
        runTest("py in extend1", lambda: runPy("in_extend1", "test/extend1.bin"))
        runTest("py out extend2", lambda: runPy("out_extend2", "test/extend2.bin"))
        runTest("py in extend2", lambda: runPy("in_extend2", "test/extend2.bin"))
        runTest("py copy extend2", lambda: runPy("copy_extend2", "test/extend2.bin"))

    if runTest("py setup union", lambda: runPySetup(["test/union.spr"])):
        runTest(
            "py out union",
            lambda: runPy("out_union", "test/union.bin", "test_union.py"),
        )
        runTest(
            "py in union", lambda: runPy("in_union", "test/union.bin", "test_union.py")
        )

    if runTest(
        "ts setup",
        lambda: runTsSetup(["test/base.spr", "test/complex2.spr", "test/union.spr"]),
    ):
        runTest(
            "ts out default simple",
            lambda: runTs("out_default", "test/simple_default.bin"),
        )
        runTest(
            "ts in default simple",
            lambda: runTs("in_default", "test/simple_default.bin"),
        )
        runTest("ts out simple", lambda: runTs("out", "test/simple.bin"))
        runTest("ts in simple", lambda: runTs("in", "test/simple.bin"))
        runTest("ts out complex", lambda: runTs("out_complex", "test/complex.bin"))
        runTest("ts in complex", lambda: runTs("in_complex", "test/complex.bin"))
        runTest("ts out complex2", lambda: runTs("out_complex2", "test/complex2.bin"))
        runTest("ts in complex2", lambda: runTs("in_complex2", "test/complex2.bin"))
        runTest("ts out inplace", lambda: runTs("out_inplace", "test/inplace.bin"))
        runTest("ts in inplace", lambda: runTs("in_inplace", "test/inplace.bin"))
        runTest("ts out extend1", lambda: runTs("out_extend1", "test/extend1.bin"))
        runTest("ts in extend1", lambda: runTs("in_extend1", "test/extend1.bin"))
        runTest("ts out extend2", lambda: runTs("out_extend2", "test/extend2.bin"))
        runTest("ts in extend2", lambda: runTs("in_extend2", "test/extend2.bin"))

    if runTest("ts setup union", lambda: runTsSetup(["test/union.spr"])):
        runTest(
            "ts out union",
            lambda: runTs("out_union", "test/union.bin", "test_union.ts"),
        )
        runTest(
            "ts in union", lambda: runTs("in_union", "test/union.bin", "test_union.ts")
        )

    if runTest(
        "rs setup",
        lambda: runRustSetup(
            ["test/base.spr", "test/complex2.spr", "test/union.spr"],
            "test/test_base.rs",
        ),
    ):
        runTest(
            "rs out default simple",
            lambda: runRust("out_default", "test/simple_default.bin"),
        )
        runTest(
            "rs in default simple",
            lambda: runRust("in_default", "test/simple_default.bin"),
        )
        runTest("rs out simple", lambda: runRust("out", "test/simple.bin"))
        runTest("rs in simple", lambda: runRust("in", "test/simple.bin"))
        runTest("rs out complex", lambda: runRust("out_complex", "test/complex.bin"))
        runTest("rs in complex", lambda: runRust("in_complex", "test/complex.bin"))
        runTest("rs out complex2", lambda: runRust("out_complex2", "test/complex2.bin"))
        runTest("rs in complex2", lambda: runRust("in_complex2", "test/complex2.bin"))
        runTest("rs out inplace", lambda: runRust("out_inplace", "test/inplace.bin"))
        runTest("rs in inplace", lambda: runRust("in_inplace", "test/inplace.bin"))
        runTest("rs out extend1", lambda: runRust("out_extend1", "test/extend1.bin"))
        runTest("rs in extend1", lambda: runRust("in_extend1", "test/extend1.bin"))
        runTest("rs out extend2", lambda: runRust("out_extend2", "test/extend2.bin"))
        runTest("rs in extend2", lambda: runRust("in_extend2", "test/extend2.bin"))
        runTest("rs out union", lambda: runRust("out_union", "test/union.bin"))
        runTest("rs in union", lambda: runRust("in_union", "test/union.bin"))

    print("=" * 80)
    if not failures:
        print("ALL GOOD")
        sys.exit(0)
    else:
        for t in failures:
            print("%s failed" % t)
        sys.exit(1)


if __name__ == "__main__":
    main()
