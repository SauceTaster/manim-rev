from __future__ import annotations

from importlib.metadata import entry_points

import manim_rev

EXPECTED_PUBLIC_API = {
    "AARCH64",
    "DEFAULT_THEME",
    "RV64",
    "X86_64",
    "AccessKind",
    "Address",
    "AddressRangeRef",
    "AddressRef",
    "AnalysisWorkbench",
    "ArchitectureSpec",
    "BasicBlock",
    "BasicBlockSpec",
    "BlockRef",
    "CFGEdgeSpec",
    "CPUBlockDiagram",
    "ConstraintPanel",
    "ControlFlowGraph",
    "CoverageBitmap",
    "CoverageMap",
    "CrashCard",
    "CrossReferencePanel",
    "DebuggerWorkbench",
    "EdgeKind",
    "Endianness",
    "ExecutedAddressRef",
    "ExecutionTrace",
    "FlagRef",
    "FlagRegister",
    "FlagSpec",
    "FuzzingDashboard",
    "HexAddressCell",
    "HexAsciiCell",
    "HexByteCell",
    "HexDump",
    "HexDumpRow",
    "HitValues",
    "InstructionEncoding",
    "InstructionField",
    "InstructionSpec",
    "InstructionView",
    "KeyValueRow",
    "MemoryAccess",
    "MemoryAccessBadge",
    "MemoryAddressRef",
    "MemoryMap",
    "MemoryRangeRef",
    "MemorySegment",
    "MemorySegmentSpec",
    "Panel",
    "PipelineDiagram",
    "PipelineInstruction",
    "PipelineSlotRef",
    "RefResolver",
    "ReferenceLink",
    "RegisterBank",
    "RegisterRef",
    "RegisterSpec",
    "RevScene",
    "RevTheme",
    "SourceAssemblyLinkSpec",
    "SourceAssemblyMap",
    "SourceListing",
    "SourceRef",
    "StackFrame",
    "StackOverflowDiagram",
    "StashPanel",
    "StashValue",
    "StateStatus",
    "StatusDot",
    "SymbolicEdgeSpec",
    "SymbolicExecutionTree",
    "SymbolicStateNode",
    "SymbolicStateRef",
    "SymbolicStateSpec",
    "TaintFlow",
    "TaintFlowDiagram",
    "TraceEvent",
    "TracePhase",
    "TraceRow",
    "TraceTimeline",
    "VisualRef",
    "VulnerabilityCard",
    "XRefSpec",
    "cfg_from_angr",
    "cfg_from_ghidra_json",
    "focus_across",
    "format_address",
    "instruction_from_capstone",
    "instructions_from_capstone",
    "label_text",
    "light_theme",
    "mono_text",
    "trace_events_from_records",
}


def test_public_api_is_complete_and_versioned() -> None:
    assert manim_rev.__version__ == "0.1.0"
    assert len(manim_rev.__all__) == len(set(manim_rev.__all__))
    assert set(manim_rev.__all__) == EXPECTED_PUBLIC_API
    for name in manim_rev.__all__:
        assert hasattr(manim_rev, name), name


def test_manim_plugin_entry_point_loads_package() -> None:
    matches = [
        entry_point
        for entry_point in entry_points(group="manim.plugins")
        if entry_point.name == "manim_rev"
    ]
    assert len(matches) == 1
    assert matches[0].load() is manim_rev
