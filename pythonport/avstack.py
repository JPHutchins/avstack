"""AVR stack checker.

Copyright (C) 2013 Daniel Beer <dlbeer@gmail.com>
Copyright (C) 2023 J.P. Hutchins <jphutchins@gmail.com>

See original/avstack.pl for the original license text.
See LICENSE for the updated license text.
"""

import re
import subprocess
import sys
from typing import Dict, Literal, Union, cast

# Configuration: set these as appropriate for your architecture/project.

OBJ_DUMP = "avr-objdump"
CALL_COST = 4

# Define constants for regex pattern groups

ADDRESS_AND_NAME_PATTERN = re.compile(r"^([0-9a-fA-F]+) <(.*)>:")
R_FUNC_CALL_PATTERN = re.compile(r": R_[A-Za-z0-9_]+_CALL[ \t]+(.*)")
TEXT_0X_PATTERN = re.compile(r"^\.text\+0x(.*)")
OBJECT_FILE_NAME_PATTERN = re.compile(r"^(.*).o")
SU_FILE_LINE_PATTERN = re.compile(r"^.*:([^\t ]+)[ \t]+([0-9]+)")
VECTOR_PATTERN = re.compile(r"^__vector_")
KEY_PATTERN = re.compile(r"^(.*)@(.*)")
MAIN_PATTERN = re.compile(r"^main@")

# First, we need to read all object and corresponding .su files. We're
# gathering a mapping of functions to callees and functions to frame
# sizes. We're just parsing at this stage -- callee name resolution
# comes later.

frame_size: Dict[str, int] = {}  # "func@file" -> size
call_graph: Dict[str, Dict] = {}  # "func@file" -> {callees}
addresses: Dict[str, str] = {}  # "addr@file" -> "func@file"

global_name: Dict[str, str] = {}  # "func" -> "func@file"
ambiguous: Dict[str, Literal[1]] = {}  # "func" -> 1

for objfile in sys.argv[1:]:
    # Disassemble this object file to obtain a callees. Sources in the
    # call graph are named "func@file". Targets in the call graph are
    # named either "offset@file" or "funcname". We also keep a list of
    # the addresses and names of each function we encounter.

    process = subprocess.run([OBJ_DUMP, "-dr", objfile], stdout=subprocess.PIPE)
    assert process.returncode == 0

    disassembly = process.stdout.decode().splitlines()

    for line in disassembly:

        if match := ADDRESS_AND_NAME_PATTERN.match(line):
            address, name = match.group(1, 2)

            source = f"{name}@{objfile}"
            call_graph[source] = {}
            if name in global_name:
                ambiguous[name] = 1
            global_name[name] = f"{name}@{objfile}"
        
        if match := R_FUNC_CALL_PATTERN.match(line):
            t = match.group(1)

            if t == ".text":
                t = f"@{objfile}"
            elif match := TEXT_0X_PATTERN.match(t):
                t = f"{match.group(1)}@{objfile}"
            
            call_graph[source][t] = 1
    
    # Extract frame sizes from the corresponding .su file.
    if match := OBJECT_FILE_NAME_PATTERN.match(objfile):
        sufile = f"{match.group(1)}.su"
    
        with open(sufile, "r") as f:
            for line in f.readlines():
                if match := SU_FILE_LINE_PATTERN.match(line):
                    function_name, stack_usage = match.group(1, 2)
                    frame_size[f"{function_name}@{objfile}"] = int(stack_usage) + CALL_COST
                
# In this step, we enumerate each list of callees in the call graph and
# try to resolve the symbols. We omit ones we can't resolve, but keep a
# set of them anyway.

unresolved: Dict[str, Literal[1]] = {}

for called_from in call_graph.keys():
    resolved: Dict[str, Literal[1]] = {}

    for t in call_graph[called_from]:
        if t in addresses:
            resolved[addresses[t]] = 1
        elif t in global_name:
            resolved[global_name[t]] = 1
            if t in ambiguous:
                print(f"Ambiguous resolution: {t}")
        elif t in call_graph:
            resolved[t] = 1
        else:
            unresolved[t] = 1
    
    call_graph[called_from] = resolved

# Create fake edges and nodes to account for dynamic behaviour.
call_graph["INTERRUPT"] = {}

for call in call_graph.keys():
    if VECTOR_PATTERN.match(call):
        call_graph["INTERRUPT"][call] = 1

# Trace the call graph and calculate, for each function:
#
#    - inherited frames: maximum inherited frame of callees, plus own
#      frame size.
#    - height: maximum height of callees, plus one.
#    - recursion: is the function called recursively (including indirect
#      recursion)?

has_caller: Dict[str, Literal[1]] = {}
visited: Dict[str, Union[Literal[" "], Literal["R"], Literal["?"]]] = {}
total_cost: Dict[str, int] = {}
call_depth: Dict[str, int] = {}

def trace(fn: str):
    if fn in visited and visited[fn] == "?":
        visited[fn] = "R"
        return
    
    visited[fn] = "?"

    max_depth = 0
    max_frame = 0

    targets = call_graph[fn]
    for t in targets.keys():
        has_caller[t] = 1
        trace(t)

        cost = total_cost[t]
        depth = call_depth[t]

        max_frame = max(cost, max_frame)
        max_depth = max(depth, max_depth)

    call_depth[fn] = max_depth + 1
    total_cost[fn] = max_frame + frame_size[fn] if fn in frame_size else 0
    if visited[fn] == "?":
        visited[fn] = " "

for call in call_graph.keys():
    trace(call)

# Now, print results in a nice table.
print("  %-30s %8s %8s %8s" % ("Func", "Cost", "Frame", "Height"))
print("------------------------------------", end="")
print("------------------------------------")

max_iv = 0
main = 0

visited_sorted = sorted(visited, key=lambda x: total_cost[x], reverse=True)
for name in visited_sorted:
    _name = name
    if (match := KEY_PATTERN.match(name)) and name not in ambiguous:
        name = match.group(1)
    
    tag = visited[_name]
    cost = total_cost[_name]

    name = _name if name in ambiguous else name  # redundant line?
    if _name not in has_caller:
        tag = ">"
    
    if VECTOR_PATTERN.match(_name) and cost > max_iv:
        max_iv = cost
    elif MAIN_PATTERN.match(_name):
        main = cost
    
    if name in ambiguous:  # redundant lines?
        name = _name
    
    print(
        "%s %-30s %8d %8d %8d" % (
            tag,
            name,
            cost,
            frame_size[_name] if _name in frame_size else 0,
            call_depth[_name]
        )
    )

print()

print("Peak execution estimate (main + worst-case IV):")
print(
    "  main = %d, worst IV = %d, total = %d" % (
        total_cost[global_name["main"]],
        total_cost["INTERRUPT"],
        total_cost[global_name["main"]] + total_cost["INTERRUPT"]
    )
)
print()

print("The following functions were not resolved:")
for fn in unresolved:
    print(f"  {fn}")
