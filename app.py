#!/usr/bin/env python3
"""
JDAP Orchestrator Tool
======================
Sequentially runs 4 JDAP agents (Integrator, Patcher, Config, CAN Spreadsheet)
with real-time logging and user input collection via a web UI.

Usage:
    python app.py [--workspace PATH] [--port PORT]
"""

import os
import sys
import json
import re
import subprocess
import time
import threading
import queue
import uuid
import shutil
import glob
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, Response, send_file

# ============================================================
# Flask App
# ============================================================
app = Flask(__name__)

# Handle PyInstaller frozen bundle
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = sys._MEIPASS
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))

WORKSPACE_ROOT = ""
HTML_PATH = os.path.join(BUNDLE_DIR, "index.html")


# ============================================================
# Orchestrator State
# ============================================================
class OrchestratorState:
    def __init__(self):
        self.log_entries = []
        self.status = "idle"
        self.current_agent_idx = -1
        self.current_step_idx = -1
        self.input_event = threading.Event()
        self.user_response = None
        self.pending_questions = None
        self.error_message = None
        self.context = {}
        self.agents = []
        self.stop_requested = False
        self.run_agent_ids = None  # None = all, list = specific agents

    def reset(self):
        self.__init__()
        self.agents = build_agents()


state = OrchestratorState()


# ============================================================
# Agent / Step Definitions
# ============================================================
def build_agents():
    return [
        {
            "id": "integrator",
            "name": "JDAP Integrator",
            "icon": "🔧",
            "description": "Integrate JDAP library into EMB32 project (package.json, vcxproj, include paths, preprocessor, tasks)",
            "status": "pending",
            "steps": [
                {"id": "int_01", "name": "Select Project Folder", "type": "user_input", "status": "pending"},
                {"id": "int_02", "name": "Add JDAP Dependency to package.json", "type": "auto", "status": "pending"},
                {"id": "int_03", "name": "Run npm install", "type": "auto", "status": "pending"},
                {"id": "int_04", "name": "Read & Parse Project Files", "type": "auto", "status": "pending"},
                {"id": "int_05", "name": "Select Library & Configuration", "type": "user_input", "status": "pending"},
                {"id": "int_06a", "name": "Extract Preprocessor Definitions", "type": "auto", "status": "pending"},
                {"id": "int_06b", "name": "Modify Preprocessor Values?", "type": "user_input", "status": "pending"},
                {"id": "int_06c", "name": "Set Preprocessor Values", "type": "user_input", "status": "pending"},
                {"id": "int_07", "name": "Enable E2E_SUPPORT", "type": "user_input", "status": "pending"},
                {"id": "int_08", "name": "Copy JDAP Config to APPCFG", "type": "auto", "status": "pending"},
                {"id": "int_09", "name": "Select TaskList File", "type": "user_input", "status": "pending"},
                {"id": "int_10", "name": "Add JDAP Task Code", "type": "auto", "status": "pending"},
                {"id": "int_11", "name": "Update vcxproj.filters", "type": "auto", "status": "pending"},
                {"id": "int_12", "name": "Add Include Paths in vcxproj", "type": "auto", "status": "pending"},
                {"id": "int_13", "name": "Update Preprocessor Definitions", "type": "auto", "status": "pending"},
                {"id": "int_14", "name": "Verify Solution Structure", "type": "auto", "status": "pending"},
            ],
        },
        {
            "id": "patcher",
            "name": "JDAP Patcher",
            "icon": "🩹",
            "description": "Patch CAN driver files (cmcandrv.c, cmcanin.c, osdsnis.h) for JDAP security",
            "status": "pending",
            "steps": [
                {"id": "pat_01", "name": "Locate OS CAN Driver Files", "type": "user_input", "status": "pending"},
                {"id": "pat_02", "name": "cmcandrv.c — Add JDAP Includes", "type": "auto", "status": "pending"},
                {"id": "pat_03", "name": "cmcandrv.c — CAN Receive Filter PGNs", "type": "auto", "status": "pending"},
                {"id": "pat_04", "name": "cmcandrv.c — JDAP_Protect in Transmit", "type": "auto", "status": "pending"},
                {"id": "pat_05", "name": "cmcanin.c — Add JDAP Includes", "type": "auto", "status": "pending"},
                {"id": "pat_06", "name": "cmcanin.c — 2-byte Command Byte", "type": "auto", "status": "pending"},
                {"id": "pat_07", "name": "cmcanin.c — JDAP_Check", "type": "auto", "status": "pending"},
                {"id": "pat_08", "name": "osdsnis.h — JDAP Design Issues", "type": "auto", "status": "pending"},
                {"id": "pat_09", "name": "Patcher Summary", "type": "auto", "status": "pending"},
            ],
        },
        {
            "id": "config",
            "name": "JDAP Config",
            "icon": "⚙️",
            "description": "Configure JDAP_Server_Config.h / JDAP_Client_Config.h (bus, TLA, RCV macros, facilities)",
            "status": "pending",
            "steps": [
                {"id": "cfg_00", "name": "Discover Config Files", "type": "user_input", "status": "pending"},
                {"id": "cfg_01", "name": "Select Config to Modify", "type": "user_input", "status": "pending"},
                {"id": "cfg_02", "name": "Read Current Config", "type": "auto", "status": "pending"},
                {"id": "cfg_03a", "name": "Configure Bus & TLA", "type": "user_input", "status": "pending"},
                {"id": "cfg_03b", "name": "Configure RCV Message Macros", "type": "user_input", "status": "pending"},
                {"id": "cfg_03c", "name": "Configure Functions (Valves, PTO, Hitch...)", "type": "user_input", "status": "pending"},
                {"id": "cfg_03d", "name": "Configure Manufacturer Specific Function Indices", "type": "user_input", "status": "pending"},
                {"id": "cfg_03e", "name": "Configure TIM Standard Facilities", "type": "user_input", "status": "pending"},
                {"id": "cfg_03f", "name": "Configure Manufacturer Specific Facilities", "type": "user_input", "status": "pending"},
                {"id": "cfg_04", "name": "Apply Config Changes", "type": "auto", "status": "pending"},
                {"id": "cfg_05", "name": "Config Summary", "type": "auto", "status": "pending"},
            ],
        },
        {
            "id": "can_spreadsheet",
            "name": "JDAP CAN Spreadsheet",
            "icon": "📊",
            "description": "Check code-gen version and update COM_GENERATOR settings in ProjectSpecific.mk",
            "status": "pending",
            "steps": [
                {"id": "can_01", "name": "Check code-generation Version", "type": "auto", "status": "pending"},
                {"id": "can_02", "name": "Read ProjectSpecific.mk", "type": "auto", "status": "pending"},
                {"id": "can_03", "name": "Update COM_GENERATOR Settings", "type": "auto", "status": "pending"},
                {"id": "can_04", "name": "Report Results", "type": "auto", "status": "pending"},
            ],
        },
    ]


# ============================================================
# Helpers
# ============================================================
def log(msg, level="info", agent=None, step=None):
    entry = {
        "ts": datetime.now().strftime("%H:%M:%S.%f")[:-3],
        "level": level,
        "msg": msg,
        "agent": agent,
        "step": step,
    }
    state.log_entries.append(entry)


def log_info(msg):
    a = state.agents[state.current_agent_idx]["id"] if state.current_agent_idx >= 0 else None
    s = None
    if state.current_agent_idx >= 0 and state.current_step_idx >= 0:
        steps = state.agents[state.current_agent_idx]["steps"]
        if state.current_step_idx < len(steps):
            s = steps[state.current_step_idx]["id"]
    log(msg, "info", a, s)


def log_success(msg):
    a = state.agents[state.current_agent_idx]["id"] if state.current_agent_idx >= 0 else None
    log(msg, "success", a)


def log_warn(msg):
    a = state.agents[state.current_agent_idx]["id"] if state.current_agent_idx >= 0 else None
    log(msg, "warn", a)


def log_error(msg):
    a = state.agents[state.current_agent_idx]["id"] if state.current_agent_idx >= 0 else None
    log(msg, "error", a)


def project_path(*parts):
    pf = state.context.get("project_folder", "")
    return os.path.join(WORKSPACE_ROOT, pf, *parts)


def options_with_current_first(options, current_value):
    """Reorder options list so the current value appears first (marked as current)."""
    if not current_value or current_value in ("N/A", "Not set", ""):
        return options
    first = [o for o in options if o["value"] == current_value]
    rest = [o for o in options if o["value"] != current_value]
    if first:
        first[0] = {**first[0], "label": f"{first[0]['label']} (current)", "recommended": True}
        return first + rest
    # Current value not in list — add it at top
    return [{"label": f"{current_value} (current)", "value": current_value, "recommended": True}] + options


def options_highlight_current(options, current_value):
    """Keep options in original order but mark the current value as recommended/highlighted."""
    if not current_value or current_value in ("N/A", "Not set", ""):
        return options
    result = []
    for o in options:
        if o["value"] == current_value:
            result.append({**o, "label": f"{o['label']} (current)", "recommended": True})
        else:
            result.append(o)
    return result


def read_file_safe(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        log_error(f"Cannot read {path}: {e}")
        return None


def write_file_safe(path, content):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        return True
    except Exception as e:
        log_error(f"Cannot write {path}: {e}")
        return False


def copy_file_safe(src, dst):
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        log_info(f"Copied {os.path.basename(src)} → {os.path.relpath(dst, WORKSPACE_ROOT)}")
        return True
    except Exception as e:
        log_error(f"Copy failed {src} → {dst}: {e}")
        return False


def run_command(cmd, cwd=None):
    log_info(f"$ {cmd}")
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120
        )
        if result.stdout.strip():
            for line in result.stdout.strip().split("\n")[-30:]:
                log_info(f"  {line}")
        if result.stderr.strip():
            for line in result.stderr.strip().split("\n")[-15:]:
                log_warn(f"  {line}")
        if result.returncode != 0:
            log_error(f"Command exited with code {result.returncode}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log_error("Command timed out (120s)")
        return False
    except Exception as e:
        log_error(f"Command failed: {e}")
        return False


def wait_for_input(questions):
    """Block until user submits input. Returns the user's response dict."""
    state.pending_questions = questions
    step = state.agents[state.current_agent_idx]["steps"][state.current_step_idx]
    step["status"] = "waiting_input"
    step["questions"] = questions
    state.status = "paused"
    log_info("⏳ Waiting for user input...")
    state.input_event.clear()
    state.input_event.wait()
    resp = state.user_response
    state.user_response = None
    state.pending_questions = None
    step.pop("questions", None)
    state.status = "running"
    return resp


def file_contains(path, text):
    content = read_file_safe(path)
    if content is None:
        return False
    return text in content


def replace_in_file(path, old, new):
    content = read_file_safe(path)
    if content is None:
        return False
    if old not in content:
        log_warn(f"Pattern not found in {os.path.basename(path)}")
        return False
    content = content.replace(old, new, 1)
    return write_file_safe(path, content)


def insert_before(path, marker, insertion):
    content = read_file_safe(path)
    if content is None:
        return False
    idx = content.find(marker)
    if idx < 0:
        log_warn(f"Marker not found in {os.path.basename(path)}: {marker[:60]}...")
        return False
    content = content[:idx] + insertion + content[idx:]
    return write_file_safe(path, content)


def insert_after(path, marker, insertion):
    content = read_file_safe(path)
    if content is None:
        return False
    idx = content.find(marker)
    if idx < 0:
        log_warn(f"Marker not found in {os.path.basename(path)}: {marker[:60]}...")
        return False
    end = idx + len(marker)
    content = content[:end] + insertion + content[end:]
    return write_file_safe(path, content)


def new_guid():
    return "{" + str(uuid.uuid4()).upper() + "}"


# ============================================================
# AGENT 1: JDAP Integrator
# ============================================================
def integrator_step_01():
    """Select Project Folder"""
    log_info("Scanning workspace for project folders...")
    entries = os.listdir(WORKSPACE_ROOT)
    folders = []
    skip = {".github", ".vscode", ".git", "JDAP", "tools", "node_modules", ".vs"}
    for e in sorted(entries):
        full = os.path.join(WORKSPACE_ROOT, e)
        if os.path.isdir(full) and e not in skip and not e.startswith("."):
            folders.append(e)
    if not folders:
        log_error("No project folders found in workspace!")
        return
    log_info(f"Found {len(folders)} project folder(s): {', '.join(folders)}")
    resp = wait_for_input([
        {
            "id": "project_folder",
            "label": "Project Folder",
            "question": "Which project folder should JDAP be integrated into?",
            "type": "select",
            "options": [{"label": f, "value": f} for f in folders],
        }
    ])
    state.context["project_folder"] = resp["project_folder"]
    log_success(f"Selected project folder: {resp['project_folder']}")


def integrator_step_02():
    """Add JDAP Dependency to package.json"""
    pkg_path = project_path("package.json")
    log_info(f"Reading {pkg_path}")
    content = read_file_safe(pkg_path)
    if content is None:
        log_error("package.json not found!")
        return
    pkg = json.loads(content)
    dep_key = "@deere-embedded/JDAP"
    dep_val = "file:../JDAP"
    if "dependencies" not in pkg:
        pkg["dependencies"] = {}
    if dep_key in pkg["dependencies"]:
        log_info(f"JDAP dependency already exists: {pkg['dependencies'][dep_key]}")
        return
    pkg["dependencies"][dep_key] = dep_val
    write_file_safe(pkg_path, json.dumps(pkg, indent=2) + "\n")
    log_success(f'Added "{dep_key}": "{dep_val}" to package.json')


def integrator_step_03():
    """Run npm install"""
    cwd = project_path()
    log_info(f"Running npm install in {cwd}...")
    run_command("npm i", cwd=cwd)
    log_success("npm install complete")


def integrator_step_04():
    """Read & Parse Project Files"""
    log_info("Reading project files...")
    filters_path = project_path("TinyOs_Win32.vcxproj.filters")
    vcxproj_path = project_path("TinyOs_Win32.vcxproj")
    sln_path = project_path("TinyOs_Win32.sln")

    for fp, key in [
        (filters_path, "filters_content"),
        (vcxproj_path, "vcxproj_content"),
        (sln_path, "sln_content"),
    ]:
        content = read_file_safe(fp)
        if content:
            state.context[key] = content
            log_info(f"  ✓ Read {os.path.basename(fp)} ({len(content)} bytes)")
        else:
            log_warn(f"  ✗ Could not read {os.path.basename(fp)}")

    # Extract configurations from vcxproj
    configs = []
    vcx = state.context.get("vcxproj_content", "")
    for m in re.finditer(r"<ProjectConfiguration\s+Include=\"([^|]+)\|", vcx):
        configs.append(m.group(1))
    configs = sorted(set(configs))
    state.context["available_configs"] = configs
    log_info(f"  Found configurations: {', '.join(configs)}")

    # Extract existing filters
    flt = state.context.get("filters_content", "")
    filters = re.findall(r'<Filter Include="([^"]+)"', flt)
    state.context["existing_filters"] = filters
    log_info(f"  Found {len(filters)} existing filter groups")


def integrator_step_05():
    """Select Library & Configuration"""
    configs = state.context.get("available_configs", [])
    if not configs:
        configs = ["tc37x", "tc37x_Win32"]
        log_warn("No configs extracted, using defaults")

    # Detect existing library from JDAP_ROLE in vcxproj
    vcx = state.context.get("vcxproj_content", "")
    existing_lib = ""
    role_match = re.search(r"JDAP_ROLE\s*=\s*(\d)", vcx)
    if role_match:
        role_val = role_match.group(1)
        existing_lib = {"1": "server", "2": "client", "3": "both"}.get(role_val, "")
        if existing_lib:
            log_info(f"Detected existing JDAP_ROLE={role_val} → library={existing_lib}")

    # Detect which configs already have JDAP defines
    existing_configs = []
    for cfg in configs:
        # Check if this config section has JDAP-related defines
        pattern = rf'<ItemDefinitionGroup\s+Condition="[^"]*{re.escape(cfg)}\|[^"]*"[^>]*>.*?</ItemDefinitionGroup>'
        cfg_block = re.search(pattern, vcx, re.DOTALL)
        if cfg_block and "JDAP_ROLE" in cfg_block.group(0):
            existing_configs.append(cfg)
    if existing_configs:
        log_info(f"Detected JDAP already in configs: {', '.join(existing_configs)}")

    # Build config options with pre-checked state
    config_options = []
    for c in configs:
        opt = {"label": c, "value": c}
        if c in existing_configs:
            opt["checked"] = True
        config_options.append(opt)

    resp = wait_for_input([
        {
            "id": "library",
            "label": "JDAP Library",
            "question": "Which JDAP library do you want to integrate?",
            "type": "select",
            "options": options_with_current_first([
                {"label": "JDAP Client", "value": "client"},
                {"label": "JDAP Server", "value": "server"},
                {"label": "Both", "value": "both"},
            ], existing_lib),
        },
        {
            "id": "configurations",
            "label": "Project Configuration(s)",
            "question": "Which project configuration(s) should JDAP be added to?",
            "type": "multiselect",
            "options": config_options,
        },
    ])
    state.context["library"] = resp["library"]
    raw = resp["configurations"]
    if isinstance(raw, str):
        state.context["selected_configs"] = [x.strip() for x in raw.split(",") if x.strip()]
    elif isinstance(raw, list):
        state.context["selected_configs"] = raw
    else:
        state.context["selected_configs"] = [raw]
    log_success(f"Library: {state.context['library']}, Configs: {', '.join(state.context['selected_configs'])}")


def integrator_step_06a():
    """Extract Preprocessor Definitions"""
    log_info("Extracting current preprocessor definitions...")
    vcx = state.context.get("vcxproj_content", "")
    macros_of_interest = ["USE_BOOT_BLOCK", "UDS_PROGRAMMING_ENABLED", "JD_SECOCE", "JDAP_ROLE"]
    selected = state.context.get("selected_configs", [])
    preproc_current = {}

    for cfg in selected:
        preproc_current[cfg] = {}
        is_win32 = "Win32" in cfg or "_Win32" in cfg.replace("|", "")
        # Find the NMakePreprocessorDefinitions for this config
        pattern = re.escape(cfg)
        # Search for PropertyGroup with this config
        for m in re.finditer(
            r"<(?:NMakePreprocessorDefinitions|PreprocessorDefinitions)[^>]*>([^<]+)</",
            vcx,
        ):
            block_start = max(0, m.start() - 500)
            block = vcx[block_start : m.start()]
            if cfg in block:
                defs = m.group(1)
                for macro in macros_of_interest:
                    if is_win32 and macro in ("USE_BOOT_BLOCK", "UDS_PROGRAMMING_ENABLED"):
                        continue
                    match = re.search(rf"{macro}=(\d+)", defs)
                    preproc_current[cfg][macro] = match.group(1) if match else "Not set"
                break
        else:
            applicable = macros_of_interest if not is_win32 else ["JD_SECOCE", "JDAP_ROLE"]
            for macro in applicable:
                preproc_current[cfg][macro] = "Not set"

    state.context["preproc_current"] = preproc_current

    for cfg, macros in preproc_current.items():
        log_info(f"\n  Preprocessor for {cfg}:")
        for k, v in macros.items():
            log_info(f"    {k} = {v}")


def integrator_step_06b():
    """Ask to modify preprocessor values"""
    resp = wait_for_input([
        {
            "id": "modify_preproc",
            "label": "Modify Preprocessor Definitions",
            "question": "Do you want to change any of the preprocessor definition values shown in the log?",
            "type": "select",
            "options": options_with_current_first([
                {"label": "Yes, let me pick new values", "value": "yes"},
                {"label": "No, keep current values", "value": "no"},
            ], state.context.get("modify_preproc", "")),
        }
    ])
    state.context["modify_preproc"] = resp["modify_preproc"]

    if resp["modify_preproc"] == "no":
        # Apply defaults for missing
        lib = state.context.get("library", "client")
        role_default = {"client": "2", "server": "1", "both": "3"}.get(lib, "2")
        preproc = state.context.get("preproc_current", {})
        for cfg in preproc:
            is_win32 = "_Win32" in cfg
            if not is_win32:
                if preproc[cfg].get("USE_BOOT_BLOCK") == "Not set":
                    preproc[cfg]["USE_BOOT_BLOCK"] = "2"
                if preproc[cfg].get("UDS_PROGRAMMING_ENABLED") == "Not set":
                    preproc[cfg]["UDS_PROGRAMMING_ENABLED"] = "0"
            if preproc[cfg].get("JD_SECOCE") == "Not set":
                preproc[cfg]["JD_SECOCE"] = "0"
            if preproc[cfg].get("JDAP_ROLE") == "Not set":
                preproc[cfg]["JDAP_ROLE"] = role_default
        state.context["preproc_values"] = preproc
        log_success("Using current/default preprocessor values")


def integrator_step_06c():
    """Set preprocessor values (if user chose Yes)"""
    if state.context.get("modify_preproc") == "no":
        state.context["preproc_values"] = state.context.get("preproc_current", {})
        log_info("Skipping — user chose to keep current values")
        return

    lib = state.context.get("library", "client")
    role_rec = {"client": "2", "server": "1", "both": "3"}.get(lib, "2")
    preproc = state.context.get("preproc_current", {})
    selected = state.context.get("selected_configs", [])
    has_non_win32 = any("_Win32" not in c for c in selected)

    questions = []
    if has_non_win32:
        cur_ubb = "Not set"
        cur_udp = "Not set"
        for cfg in selected:
            if "_Win32" not in cfg:
                cur_ubb = preproc.get(cfg, {}).get("USE_BOOT_BLOCK", "Not set")
                cur_udp = preproc.get(cfg, {}).get("UDS_PROGRAMMING_ENABLED", "Not set")
                break
        questions.append({
            "id": "USE_BOOT_BLOCK",
            "label": f"USE_BOOT_BLOCK (currently: {cur_ubb})",
            "question": "Value for USE_BOOT_BLOCK? (non-Win32 configs only)",
            "type": "select",
            "options": options_with_current_first([
                {"label": "1", "value": "1"},
                {"label": "2", "value": "2"},
                {"label": "3", "value": "3"},
            ], cur_ubb if cur_ubb != "Not set" else ""),
        })
        questions.append({
            "id": "UDS_PROGRAMMING_ENABLED",
            "label": f"UDS_PROGRAMMING_ENABLED (currently: {cur_udp})",
            "question": "Value for UDS_PROGRAMMING_ENABLED? (non-Win32 configs only)",
            "type": "select",
            "options": options_with_current_first([
                {"label": "0", "value": "0"},
                {"label": "1", "value": "1"},
            ], cur_udp if cur_udp != "Not set" else ""),
        })

    cur_secoce = "Not set"
    cur_role = "Not set"
    for cfg in selected:
        cur_secoce = preproc.get(cfg, {}).get("JD_SECOCE", "Not set")
        cur_role = preproc.get(cfg, {}).get("JDAP_ROLE", "Not set")
        break

    questions.append({
        "id": "JD_SECOCE",
        "label": f"JD_SECOCE (currently: {cur_secoce})",
        "question": "Value for JD_SECOCE?",
        "type": "select",
        "options": options_with_current_first([
            {"label": "0", "value": "0"},
            {"label": "1", "value": "1"},
        ], cur_secoce if cur_secoce != "Not set" else ""),
    })
    questions.append({
        "id": "JDAP_ROLE",
        "label": f"JDAP_ROLE (1=Server, 2=Client, 3=Both) (currently: {cur_role})",
        "question": f"Value for JDAP_ROLE? (Recommended: {role_rec} for {lib})",
        "type": "select",
        "options": options_with_current_first([
            {"label": "1 (Server)", "value": "1"},
            {"label": "2 (Client)", "value": "2"},
            {"label": "3 (Both)", "value": "3"},
        ], cur_role if cur_role != "Not set" else ""),
    })

    resp = wait_for_input(questions)

    # Validate JDAP_ROLE
    expected_role = role_rec
    actual_role = resp.get("JDAP_ROLE", role_rec)
    if actual_role != expected_role:
        log_warn(f"JDAP_ROLE={actual_role} doesn't match library selection '{lib}' (expected {expected_role}). Using recommended value.")
        resp["JDAP_ROLE"] = expected_role

    # Build preproc_values
    final = {}
    for cfg in selected:
        is_win32 = "_Win32" in cfg
        final[cfg] = {}
        if not is_win32:
            final[cfg]["USE_BOOT_BLOCK"] = resp.get("USE_BOOT_BLOCK", "2")
            final[cfg]["UDS_PROGRAMMING_ENABLED"] = resp.get("UDS_PROGRAMMING_ENABLED", "0")
        final[cfg]["JD_SECOCE"] = resp.get("JD_SECOCE", "0")
        final[cfg]["JDAP_ROLE"] = resp.get("JDAP_ROLE", role_rec)

    state.context["preproc_values"] = final
    log_success("Preprocessor values configured")


def integrator_step_07():
    """Enable E2E_SUPPORT"""
    resp = wait_for_input([
        {
            "id": "e2e_support",
            "label": "E2E_SUPPORT",
            "question": "JDAP requires E2E_SUPPORT. Enable it?",
            "type": "select",
            "options": options_with_current_first([
                {"label": "Enable", "value": "enable"},
                {"label": "Skip (already enabled elsewhere)", "value": "skip"},
            ], state.context.get("e2e_support", "")),
        }
    ])

    if resp["e2e_support"] == "skip":
        log_info("E2E_SUPPORT — skipped by user")
        return

    # Try to enable E2E_SUPPORT in header
    e2e_path = project_path("APPCFG", "HWCFG", "E2E_ModCfg.h")
    if not os.path.exists(e2e_path):
        e2e_path = project_path("APPCFG", "Hwconfig.h")

    if os.path.exists(e2e_path):
        content = read_file_safe(e2e_path)
        if content and "//#define E2E_SUPPORT" in content:
            content = content.replace("//#define E2E_SUPPORT", "#define E2E_SUPPORT", 1)
            write_file_safe(e2e_path, content)
            log_success(f"Uncommented #define E2E_SUPPORT in {os.path.basename(e2e_path)}")
        elif content and "#define E2E_SUPPORT" in content:
            log_info("E2E_SUPPORT already enabled in header")
        else:
            log_warn("E2E_SUPPORT macro not found in header file")
    else:
        log_warn("E2E config header not found")

    # Enable -E2E_Enabled in ProjectSpecific.mk
    mk_path = project_path("ProjectSpecific.mk")
    if os.path.exists(mk_path):
        content = read_file_safe(mk_path)
        if content and "#                            -E2E_Enabled" in content:
            content = content.replace(
                "#                            -E2E_Enabled",
                "                             -E2E_Enabled",
                1,
            )
            write_file_safe(mk_path, content)
            log_success("Uncommented -E2E_Enabled in ProjectSpecific.mk")
        elif content and "-E2E_Enabled" in content and "#" not in content.split("-E2E_Enabled")[0].split("\n")[-1]:
            log_info("-E2E_Enabled already enabled in ProjectSpecific.mk")
        else:
            log_warn("-E2E_Enabled flag not found in ProjectSpecific.mk")


def integrator_step_08():
    """Copy JDAP Config.h to APPCFG"""
    lib = state.context.get("library", "client")
    pf = state.context.get("project_folder", "")
    nm_base = project_path("node_modules", "@deere-embedded", "JDAP")

    copies = []
    if lib in ("client", "both"):
        src = os.path.join(nm_base, "JDAP_Client", "Documentation", "Configfile", "JDAP_Client_Config.h")
        dst = project_path("APPCFG", "JDAP_Client_Config.h")
        copies.append((src, dst, "JDAP_Client_Config.h"))
    if lib in ("server", "both"):
        src = os.path.join(nm_base, "JDAP_Server", "Documentation", "Configfile", "JDAP_Server_Config.h")
        dst = project_path("APPCFG", "JDAP_Server_Config.h")
        copies.append((src, dst, "JDAP_Server_Config.h"))

    for src, dst, name in copies:
        if os.path.exists(dst):
            log_info(f"{name} already exists in APPCFG")
        elif os.path.exists(src):
            copy_file_safe(src, dst)
        else:
            log_warn(f"Source not found: {src}")

    # Add to vcxproj.filters and vcxproj
    filters_path = project_path("TinyOs_Win32.vcxproj.filters")
    vcxproj_path = project_path("TinyOs_Win32.vcxproj")

    for _, _, name in copies:
        include_str = f'APPCFG\\{name}'
        # Add to .filters
        if os.path.exists(filters_path):
            content = read_file_safe(filters_path)
            if content and include_str not in content:
                entry = f'    <ClInclude Include="{include_str}">\n      <Filter>APPCFG</Filter>\n    </ClInclude>\n'
                marker = "</ItemGroup>"
                # Find last ClInclude ItemGroup
                idx = content.rfind("</ItemGroup>")
                if idx > 0:
                    content = content[:idx] + entry + content[idx:]
                    write_file_safe(filters_path, content)
                    log_info(f"Added {name} to vcxproj.filters")

        # Add to .vcxproj — insert before </ItemGroup> that closes the ClInclude section
        if os.path.exists(vcxproj_path):
            content = read_file_safe(vcxproj_path)
            if content and include_str not in content:
                entry = f'    <ClInclude Include="{include_str}" />\n'
                # Find the end of the ClInclude ItemGroup (after last </ClInclude>)
                last_cli = content.rfind('</ClInclude>')
                if last_cli > 0:
                    ig_end = content.find('</ItemGroup>', last_cli)
                    if ig_end > 0:
                        content = content[:ig_end] + entry + content[ig_end:]
                        write_file_safe(vcxproj_path, content)
                        log_info(f"Added {name} to vcxproj")


def integrator_step_09():
    """Select TaskList File"""
    log_info("Reading TaskListDATA.H...")
    tld_path = project_path("APPCFG", "TaskListDATA.H")
    content = read_file_safe(tld_path)
    task_files = []
    if content:
        for m in re.finditer(r'#include\s+"(TaskList\w+\.H)"', content, re.IGNORECASE):
            task_files.append(m.group(1))
    if not task_files:
        task_files = ["TaskListACU.H", "TaskListICU.H", "TaskListCAB.H"]
        log_warn("Could not extract task list files, using defaults")

    log_info(f"Found task list files: {', '.join(task_files)}")
    resp = wait_for_input([
        {
            "id": "tasklist_file",
            "label": "Task List File",
            "question": "Which TaskList file should the JDAP tasks be added to?",
            "type": "select",
            "options": options_with_current_first(
                [{"label": f, "value": f} for f in task_files],
                state.context.get("tasklist_file", "")
            ),
        }
    ])
    state.context["tasklist_file"] = resp["tasklist_file"]
    log_success(f"Selected: {resp['tasklist_file']}")


def integrator_step_10():
    """Add JDAP Task Code"""
    tl_file = state.context.get("tasklist_file", "TaskListACU.H")
    tl_path = project_path("APPCFG", tl_file)
    content = read_file_safe(tl_path)
    if content is None:
        log_error(f"Cannot read {tl_file}")
        return

    lib = state.context.get("library", "client")
    modified = False

    # Client init task
    if lib in ("client", "both") and "JDAP_Client_Task_Init" not in content:
        init_block = '\n#if (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n\nINITTASK(JDAP_Client_Task_Init, TASKLIST_FUNCTION_ID)\n\n#endif // (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n'
        idx = content.find("#ifdef INIT_TASKS")
        if idx >= 0:
            end_idx = content.find("#endif", idx)
            if end_idx >= 0:
                content = content[:end_idx] + init_block + content[end_idx:]
                modified = True
                log_info("Added JDAP_Client_Task_Init to INIT_TASKS")

    # Server init task
    if lib in ("server", "both") and "JDAP_Srv_Init" not in content:
        init_block = '\n#if (JDAP_ROLE == 1) || (JDAP_ROLE == 3)\n\nINITTASK(JDAP_Srv_Init, TASKLIST_FUNCTION_ID)\n\n#endif // (JDAP_ROLE == 1) || (JDAP_ROLE == 3)\n'
        idx = content.find("#ifdef INIT_TASKS")
        if idx >= 0:
            end_idx = content.find("#endif", idx)
            if end_idx >= 0:
                content = content[:end_idx] + init_block + content[end_idx:]
                modified = True
                log_info("Added JDAP_Srv_Init to INIT_TASKS")

    # Client foreground tasks
    if lib in ("client", "both") and "JDAP_Client_Task," not in content:
        fg_block = '\n#if (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\nTASK(JDAP_Client_Task, PHASES(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0), 20, TM_PRIORITY_LEVEL, TASKLIST_FUNCTION_ID)\nTASK(JDAP_Client_RxTask, PHASES(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0), 20, TM_PRIORITY_LEVEL, TASKLIST_FUNCTION_ID)\n\n#endif // (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n'
        idx = content.find("#ifdef TM_PRIORITY_LEVEL_3")
        if idx >= 0:
            end_idx = content.find("#endif", idx)
            if end_idx >= 0:
                content = content[:end_idx] + fg_block + content[end_idx:]
                modified = True
                log_info("Added JDAP Client foreground tasks to TM_PRIORITY_LEVEL_3")

    # Server foreground tasks
    if lib in ("server", "both") and "JDAP_Srv_Task," not in content:
        fg_block = '\n#if (JDAP_ROLE == 1) || (JDAP_ROLE == 3)\nTASK(JDAP_Srv_Task, PHASES(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0), 20, TM_PRIORITY_LEVEL, TASKLIST_FUNCTION_ID)\nTASK(JDAP_RxTask, PHASES(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0), 20, TM_PRIORITY_LEVEL, TASKLIST_FUNCTION_ID)\n\n#endif // (JDAP_ROLE == 1) || (JDAP_ROLE == 3)\n'
        idx = content.find("#ifdef TM_PRIORITY_LEVEL_3")
        if idx >= 0:
            end_idx = content.find("#endif", idx)
            if end_idx >= 0:
                content = content[:end_idx] + fg_block + content[end_idx:]
                modified = True
                log_info("Added JDAP Server foreground tasks to TM_PRIORITY_LEVEL_3")

    if modified:
        write_file_safe(tl_path, content)
        log_success(f"Updated {tl_file} with JDAP task entries")
    else:
        log_info("JDAP tasks already present or no changes needed")


def integrator_step_11():
    """Update vcxproj.filters with JDAP file references"""
    lib = state.context.get("library", "client")
    filters_path = project_path("TinyOs_Win32.vcxproj.filters")
    content = read_file_safe(filters_path)
    if content is None:
        return

    additions = []

    if lib in ("client", "both"):
        client_filters = [
            "jdap_client",
            "jdap_client\\Generic_Client",
            "jdap_client\\Generic_Client\\AutnClient_Common",
            "jdap_client\\Generic_Client\\includes",
            "jdap_client\\Generic_Client\\JDAP_Security",
            "jdap_client\\JDAP_EMB32_Wrapper",
            "jdap_client\\TestApp",
        ]
        for f in client_filters:
            if f'Filter Include="{f}"' not in content:
                additions.append(f'    <Filter Include="{f}">\n      <UniqueIdentifier>{new_guid()}</UniqueIdentifier>\n    </Filter>')

    if lib in ("server", "both"):
        server_filters = [
            "jdap_server",
            "jdap_server\\AutnServ_Common",
            "jdap_server\\AutnServ_Common\\JDClass3Security",
            "jdap_server\\JDAP_Server",
            "jdap_server\\JDAP_Server\\JDAP_Security",
            "jdap_server\\JDAP_Server\\Authentication",
            "jdap_server\\JDAP_Server\\Authentication\\AuthLib_Include",
            "jdap_server\\JDAP_Server\\Authentication\\AuthLib_Include\\authlib",
            "jdap_server\\JDAP_Server\\Authentication\\AuthLib_Source",
            "jdap_server\\JDAP_Server\\Authentication\\CryptoLib_Include",
            "jdap_server\\JDAP_Server\\Authentication\\CryptoLib_Include\\cryptolib",
            "jdap_server\\JDAP_Server\\Authentication\\CryptoLib_Source",
            "jdap_server\\TestApp",
        ]
        for f in server_filters:
            if f'Filter Include="{f}"' not in content:
                additions.append(f'    <Filter Include="{f}">\n      <UniqueIdentifier>{new_guid()}</UniqueIdentifier>\n    </Filter>')

    if additions:
        filter_block = "\n".join(additions) + "\n"
        # Insert before first </ItemGroup> in filter section
        idx = content.find("</ItemGroup>")
        if idx > 0:
            content = content[:idx] + filter_block + "  " + content[idx:]
            write_file_safe(filters_path, content)
            log_success(f"Added {len(additions)} filter entries to vcxproj.filters")
    else:
        log_info("Filter entries already present")

    # Add ClCompile and ClInclude entries for JDAP source files
    _add_jdap_source_refs(filters_path, lib)

    # Also add self-closing entries to .vcxproj (before respective </ItemGroup> tags)
    vcxproj_path = project_path("TinyOs_Win32.vcxproj")
    _add_jdap_source_refs_vcxproj(vcxproj_path, lib)


def _add_jdap_source_refs_vcxproj(vcxproj_path, lib):
    """Add self-closing ClCompile/ClInclude entries to .vcxproj file"""
    content = read_file_safe(vcxproj_path)
    if not content:
        return

    base = "node_modules\\@deere-embedded\\JDAP"
    additions_c = []
    additions_h = []

    file_lists = _get_jdap_file_lists(base, lib)
    for inc, has_c in file_lists:
        if has_c and f'Include="{inc}.c"' not in content:
            additions_c.append(f'    <ClCompile Include="{inc}.c" />')
        if f'Include="{inc}.h"' not in content:
            additions_h.append(f'    <ClInclude Include="{inc}.h" />')

    modified = False

    if additions_c:
        # Find the ClCompile ItemGroup's closing tag (after last </ClCompile>)
        last_cc = content.rfind('</ClCompile>')
        if last_cc < 0:
            last_cc = content.rfind('<ClCompile')
        if last_cc > 0:
            ig_end = content.find('</ItemGroup>', last_cc)
            if ig_end > 0:
                block = "\n".join(additions_c) + "\n"
                content = content[:ig_end] + block + content[ig_end:]
                modified = True

    if additions_h:
        # Find the ClInclude ItemGroup's closing tag (after last </ClInclude>)
        last_cli = content.rfind('</ClInclude>')
        if last_cli < 0:
            last_cli = content.rfind('<ClInclude')
        if last_cli > 0:
            ig_end = content.find('</ItemGroup>', last_cli)
            if ig_end > 0:
                block = "\n".join(additions_h) + "\n"
                content = content[:ig_end] + block + content[ig_end:]
                modified = True

    if modified:
        write_file_safe(vcxproj_path, content)
        log_success(f"Added {len(additions_c)} ClCompile + {len(additions_h)} ClInclude entries to vcxproj")
    else:
        log_info("vcxproj source file entries already present or no additions needed")


def _get_jdap_file_lists(base, lib):
    """Return list of (include_path, has_c_file) tuples for the given library selection"""
    result = []
    if lib in ("client", "both"):
        client_files = {
            "Generic_Client": [
                ("JDAP_Automation_State", True), ("JDAP_Client", True),
                ("JDAP_ClientHeartbeat", True), ("JDAP_ClientStates", True),
                ("JDAP_Client_MessageHandling", True), ("JDAP_FunctionAssignment", True),
                ("JDAP_ServerDatabase", True),
                ("JDAP_client_Settings", False), ("JDAP_SpecDefines", False),
            ],
            "Generic_Client\\AutnClient_Common": [
                ("AutnClient_TimerFunctions", True),
                ("AutnServ_Common_Logic", False),
            ],
            "Generic_Client\\includes": [
                ("JDAP_Client_CAN", False), ("JDAP_Common_Type", False), ("JDAP_Result", False),
            ],
            "Generic_Client\\JDAP_Security": [
                ("JDAPCrc", True), ("JDAP_Security", True),
                ("permutations", True), ("prfs", True), ("printstate", True),
                ("api", False), ("ascon", False), ("config", False), ("constants", False),
                ("forceinline", False), ("lendian", False), ("round", False), ("word", False),
            ],
            "JDAP_EMB32_Wrapper": [("JDAP_CANAbstraction", True), ("JDAP_Client_task", True)],
            "TestApp": [("Jdap_Client_App", True)],
        }
        for subdir, files in client_files.items():
            for fname, has_c in files:
                result.append((f"{base}\\JDAP_Client\\Code\\{subdir}\\{fname}", has_c))
    if lib in ("server", "both"):
        server_files = {
            "AutnServ_Common": [("AutnServ_TimerFunctions", True)],
            "JDAP_Server\\JDAP_Security": [
                ("JDAPCrc", True), ("JDAP_Security", True),
                ("permutations", True), ("prfs", True), ("printstate", True),
                ("api", False), ("ascon", False), ("config", False), ("constants", False),
                ("forceinline", False), ("lendian", False), ("round", False), ("word", False),
            ],
            "JDAP_Server": [
                ("JDAP_Assigned_Facility_Response", True), ("JDAP_Automation_State", True),
                ("JDAP_CANAbstraction", True), ("JDAP_clientDatabase", True),
                ("JDAP_debugUtil", True), ("JDAP_Function_Interface", True),
                ("JDAP_FunctionAssignment", True), ("JDAP_MessageHandling", True),
                ("JDAP_Server", True), ("JDAP_Server_Heartbeat", True),
                ("JDAP_States", True),
                ("JDAP_Server_osdsnis", False), ("JDAP_Server_Settings", False), ("JDAP_SpecDefines", False),
            ],
            "TestApp": [("Jdap_Server_App", True)],
        }
        for subdir, files in server_files.items():
            for fname, has_c in files:
                result.append((f"{base}\\JDAP_Server\\Code\\{subdir}\\{fname}", has_c))
    return result


def _add_jdap_source_refs(filters_path, lib):
    """Add ClCompile/ClInclude entries for JDAP source files"""
    content = read_file_safe(filters_path)
    if not content:
        return

    base = "node_modules\\@deere-embedded\\JDAP"
    additions_c = []
    additions_h = []

    if lib in ("client", "both"):
        client_files = {
            "Generic_Client": [
                ("JDAP_Automation_State", True), ("JDAP_Client", True),
                ("JDAP_ClientHeartbeat", True), ("JDAP_ClientStates", True),
                ("JDAP_Client_MessageHandling", True), ("JDAP_FunctionAssignment", True),
                ("JDAP_ServerDatabase", True),
                ("JDAP_client_Settings", False), ("JDAP_SpecDefines", False),
            ],
            "Generic_Client\\AutnClient_Common": [
                ("AutnClient_TimerFunctions", True),
                ("AutnServ_Common_Logic", False),
            ],
            "Generic_Client\\includes": [
                ("JDAP_Client_CAN", False), ("JDAP_Common_Type", False), ("JDAP_Result", False),
            ],
            "Generic_Client\\JDAP_Security": [
                ("JDAPCrc", True), ("JDAP_Security", True),
                ("permutations", True), ("prfs", True), ("printstate", True),
                ("api", False), ("ascon", False), ("config", False), ("constants", False),
                ("forceinline", False), ("lendian", False), ("round", False), ("word", False),
            ],
            "JDAP_EMB32_Wrapper": [("JDAP_CANAbstraction", True), ("JDAP_Client_task", True)],
            "TestApp": [("Jdap_Client_App", True)],
        }
        for subdir, files in client_files.items():
            for fname, has_c in files:
                inc = f"{base}\\JDAP_Client\\Code\\{subdir}\\{fname}"
                flt = f"jdap_client\\{subdir}"
                if has_c and f'Include="{inc}.c"' not in content:
                    additions_c.append(f'    <ClCompile Include="{inc}.c">\n      <Filter>{flt}</Filter>\n    </ClCompile>')
                if f'Include="{inc}.h"' not in content:
                    additions_h.append(f'    <ClInclude Include="{inc}.h">\n      <Filter>{flt}</Filter>\n    </ClInclude>')

    if lib in ("server", "both"):
        server_files = {
            "AutnServ_Common": [("AutnServ_TimerFunctions", True)],
            "JDAP_Server\\JDAP_Security": [
                ("JDAPCrc", True), ("JDAP_Security", True),
                ("permutations", True), ("prfs", True), ("printstate", True),
                ("api", False), ("ascon", False), ("config", False), ("constants", False),
                ("forceinline", False), ("lendian", False), ("round", False), ("word", False),
            ],
            "JDAP_Server": [
                ("JDAP_Assigned_Facility_Response", True), ("JDAP_Automation_State", True),
                ("JDAP_CANAbstraction", True), ("JDAP_clientDatabase", True),
                ("JDAP_debugUtil", True), ("JDAP_Function_Interface", True),
                ("JDAP_FunctionAssignment", True), ("JDAP_MessageHandling", True),
                ("JDAP_Server", True), ("JDAP_Server_Heartbeat", True),
                ("JDAP_States", True),
                ("JDAP_Server_osdsnis", False), ("JDAP_Server_Settings", False), ("JDAP_SpecDefines", False),
            ],
            "TestApp": [("Jdap_Server_App", True)],
        }
        for subdir, files in server_files.items():
            for fname, has_c in files:
                inc = f"{base}\\JDAP_Server\\Code\\{subdir}\\{fname}"
                flt = f"jdap_server\\{subdir}"
                if has_c and f'Include="{inc}.c"' not in content:
                    additions_c.append(f'    <ClCompile Include="{inc}.c">\n      <Filter>{flt}</Filter>\n    </ClCompile>')
                if f'Include="{inc}.h"' not in content:
                    additions_h.append(f'    <ClInclude Include="{inc}.h">\n      <Filter>{flt}</Filter>\n    </ClInclude>')

    if additions_c or additions_h:
        all_additions = "\n".join(additions_c + additions_h) + "\n"
        idx = content.rfind("</ItemGroup>")
        if idx > 0:
            content = content[:idx] + all_additions + "  " + content[idx:]
            write_file_safe(filters_path, content)
            log_success(f"Added {len(additions_c)} ClCompile + {len(additions_h)} ClInclude entries")
    else:
        log_info("Source file entries already present")


def integrator_step_12():
    """Add Include Paths in vcxproj"""
    vcxproj_path = project_path("TinyOs_Win32.vcxproj")
    content = read_file_safe(vcxproj_path)
    if content is None:
        return

    lib = state.context.get("library", "client")
    selected = state.context.get("selected_configs", [])

    client_paths = (
        r".\node_modules\@deere-embedded\JDAP\JDAP_Client\Code\Generic_Client;"
        r".\node_modules\@deere-embedded\JDAP\JDAP_Client\Code\Generic_Client\AutnClient_Common;"
        r".\node_modules\@deere-embedded\JDAP\JDAP_Client\Code\Generic_Client\includes;"
        r".\node_modules\@deere-embedded\JDAP\JDAP_Client\Code\JDAP_EMB32_Wrapper;"
        r".\node_modules\@deere-embedded\JDAP\JDAP_Client\Code\Generic_Client\JDAP_Security;"
        r".\node_modules\@deere-embedded\JDAP\JDAP_Client\Code\TestApp"
    )
    server_paths = (
        r".\node_modules\@deere-embedded\JDAP\JDAP_Server\Code\AutnServ_Common;"
        r".\node_modules\@deere-embedded\JDAP\JDAP_Server\Code\JDAP_Server;"
        r".\node_modules\@deere-embedded\JDAP\JDAP_Server\Code\JDAP_Server\JDAP_Security;"
        r".\node_modules\@deere-embedded\JDAP\JDAP_Server\Code\TestApp"
    )

    paths_to_add = ""
    if lib in ("client", "both"):
        paths_to_add += ";" + client_paths
    if lib in ("server", "both"):
        paths_to_add += ";" + server_paths

    for cfg in selected:
        is_win32 = "_Win32" in cfg

        if is_win32:
            # Win32 configs use AdditionalIncludeDirectories inside ItemDefinitionGroup > ClCompile
            for m in re.finditer(r"(<AdditionalIncludeDirectories>)([^<]*)(</AdditionalIncludeDirectories>)", content):
                block_start = max(0, m.start() - 800)
                if cfg in content[block_start : m.start()]:
                    current = m.group(2)
                    if "JDAP" not in current:
                        # Insert before %(AdditionalIncludeDirectories)
                        inherit = "%(AdditionalIncludeDirectories)"
                        if inherit in current:
                            new_val = current.replace(inherit, paths_to_add.lstrip(";") + ";" + inherit)
                        else:
                            new_val = current.rstrip(";") + paths_to_add
                        content = content[: m.start(2)] + new_val + content[m.end(2) :]
                        log_info(f"Added JDAP include paths for {cfg} (AdditionalIncludeDirectories)")
                    else:
                        log_info(f"JDAP include paths already present for {cfg}")
                    break
        else:
            # Non-Win32 configs use NMakeIncludeSearchPath in PropertyGroup
            pattern = rf"(<NMakeIncludeSearchPath[^>]*Condition=\"[^\"]*{re.escape(cfg)}[^\"]*\"[^>]*>)([^<]*)(</NMakeIncludeSearchPath>)"
            m = re.search(pattern, content)
            if m:
                current = m.group(2)
                if "JDAP" not in current:
                    new_val = current.rstrip(";") + paths_to_add
                    content = content[: m.start(2)] + new_val + content[m.end(2) :]
                    log_info(f"Added JDAP include paths for {cfg}")
                else:
                    log_info(f"JDAP include paths already present for {cfg}")
            else:
                # Try simpler pattern without Condition
                for m2 in re.finditer(r"(<NMakeIncludeSearchPath>)([^<]*)(</NMakeIncludeSearchPath>)", content):
                    block_start = max(0, m2.start() - 500)
                    if cfg in content[block_start : m2.start()]:
                        current = m2.group(2)
                        if "JDAP" not in current:
                            new_val = current.rstrip(";") + paths_to_add
                            content = content[: m2.start(2)] + new_val + content[m2.end(2) :]
                            log_info(f"Added JDAP include paths for {cfg}")
                        break

    write_file_safe(vcxproj_path, content)
    log_success("Include paths updated")


def integrator_step_13():
    """Update Preprocessor Definitions in vcxproj"""
    vcxproj_path = project_path("TinyOs_Win32.vcxproj")
    content = read_file_safe(vcxproj_path)
    if content is None:
        return

    preproc = state.context.get("preproc_values", {})

    for cfg, macros in preproc.items():
        is_win32 = "_Win32" in cfg
        tag = "PreprocessorDefinitions" if is_win32 else "NMakePreprocessorDefinitions"

        for m in re.finditer(rf"(<{tag}[^>]*>)([^<]*)</{tag}>", content):
            block_start = max(0, m.start() - 800)
            if cfg in content[block_start : m.start()]:
                defs = m.group(2)
                for macro, value in macros.items():
                    pat = rf"{macro}=\d+"
                    replacement = f"{macro}={value}"
                    if re.search(pat, defs):
                        defs = re.sub(pat, replacement, defs)
                    else:
                        sep = ";" if defs and not defs.endswith(";") else ""
                        if is_win32 and "%(PreprocessorDefinitions)" in defs:
                            defs = defs.replace("%(PreprocessorDefinitions)", f"{replacement};%(PreprocessorDefinitions)")
                        else:
                            defs = defs + sep + replacement
                content = content[: m.start(2)] + defs + content[m.end(2) :]
                log_info(f"Updated preprocessor for {cfg}: {macros}")
                break

    write_file_safe(vcxproj_path, content)
    log_success("Preprocessor definitions updated")


def integrator_step_14():
    """Verify Solution Structure"""
    log_info("Verifying solution structure...")
    filters_path = project_path("TinyOs_Win32.vcxproj.filters")
    content = read_file_safe(filters_path)
    if content:
        lib = state.context.get("library", "client")
        if lib in ("client", "both"):
            if 'Filter Include="jdap_client"' in content:
                log_info("  ✓ jdap_client filter group present")
            else:
                log_warn("  ✗ jdap_client filter group missing")
        if lib in ("server", "both"):
            if 'Filter Include="jdap_server"' in content:
                log_info("  ✓ jdap_server filter group present")
            else:
                log_warn("  ✗ jdap_server filter group missing")

    # Summary
    lib = state.context.get("library", "client")
    configs = state.context.get("selected_configs", [])
    pp = state.context.get("preproc_values", {})
    log_success("═══════════════════════════════════════")
    log_success("  JDAP Integration Complete")
    log_success(f"  Project: {state.context.get('project_folder', '?')}")
    log_success(f"  Library: {lib}")
    log_success(f"  Configs: {', '.join(configs)}")
    for cfg, macros in pp.items():
        log_success(f"  {cfg}: {macros}")
    log_success("═══════════════════════════════════════")


# ============================================================
# AGENT 2: JDAP Patcher
# ============================================================
def _find_os_base_file(filename):
    """Search for an OS_BASE file in node_modules"""
    pf = state.context.get("project_folder", "")
    search_base = os.path.join(WORKSPACE_ROOT, pf, "node_modules", "@deere-embedded")
    for root, dirs, files in os.walk(search_base):
        if filename in files:
            return os.path.join(root, filename)
    return None


def patcher_step_01():
    """Locate OS CAN Driver Files"""
    # Ensure project_folder is set (may not be if integrator was skipped)
    if not state.context.get("project_folder"):
        log_info("Project folder not set — scanning workspace...")
        entries = os.listdir(WORKSPACE_ROOT)
        folders = []
        skip = {".github", ".vscode", ".git", "JDAP", "tools", "node_modules", ".vs"}
        for e in sorted(entries):
            full = os.path.join(WORKSPACE_ROOT, e)
            if os.path.isdir(full) and e not in skip and not e.startswith("."):
                folders.append(e)
        if not folders:
            log_error("No project folders found in workspace!")
            return
        if len(folders) == 1:
            state.context["project_folder"] = folders[0]
            log_info(f"Auto-selected project folder: {folders[0]}")
        else:
            resp = wait_for_input([
                {
                    "id": "project_folder",
                    "label": "Project Folder",
                    "question": "Which project folder contains the node_modules/ directory?",
                    "type": "select",
                    "options": [{"label": f, "value": f} for f in folders],
                }
            ])
            state.context["project_folder"] = resp["project_folder"]
            log_info(f"Selected project folder: {resp['project_folder']}")

    log_info("Searching for CAN driver files in node_modules...")
    targets = {"cmcandrv.c": None, "cmcanin.c": None, "osdsnis.h": None}
    for fname in targets:
        path = _find_os_base_file(fname)
        if path:
            targets[fname] = path
            log_info(f"  ✓ Found {fname}: {os.path.relpath(path, WORKSPACE_ROOT)}")
        else:
            log_warn(f"  ✗ {fname} not found")
    state.context["patcher_files"] = targets


def patcher_step_02():
    """cmcandrv.c — Add JDAP Includes"""
    path = state.context.get("patcher_files", {}).get("cmcandrv.c")
    if not path:
        log_warn("cmcandrv.c not found, skipping")
        return
    content = read_file_safe(path)
    if not content:
        return
    if "JDAP_Security.h" in content:
        log_info("JDAP includes already present in cmcandrv.c — skipped")
        return

    jdap_includes = (
        '\n#if (JDAP_ROLE == 1) || (JDAP_ROLE == 3)\n'
        '#include "JDAP_Security.h"\n'
        '#endif // (JDAP_ROLE == 1) || (JDAP_ROLE == 3)\n'
        '#if (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n'
        '#include "JDAP_CANAbstraction.h"\n'
        '#endif // (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n'
    )
    marker = '#include "hwconfig.h"'
    idx = content.find(marker)
    if idx >= 0:
        end = content.find("\n", idx) + 1
        content = content[:end] + jdap_includes + content[end:]
        write_file_safe(path, content)
        log_success("Added JDAP includes to cmcandrv.c")
    else:
        log_warn("Could not find #include \"hwconfig.h\" in cmcandrv.c")


def patcher_step_03():
    """cmcandrv.c — CAN Receive Filter PGNs"""
    path = state.context.get("patcher_files", {}).get("cmcandrv.c")
    if not path:
        return
    content = read_file_safe(path)
    if not content:
        return
    if "0x3C00" in content and "0x3D00" in content:
        log_info("JDAP PGN filters already present in cmcandrv.c — skipped")
        return

    old = '(messagePGN.messagePDU.PDU_Format == (PROPA_MSG >> 8)))\n         { // Proprietary messages that have a command bytes.'
    new = (
        '(messagePGN.messagePDU.PDU_Format == (PROPA_MSG >> 8)) \n'
        '#if (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n'
        '            || ((messagePGN.PGN & 0xFF00) == 0x3C00)\n'
        '#endif// (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n'
        '#if (JDAP_ROLE == 1) || (JDAP_ROLE == 3)\n'
        '            || ((messagePGN.PGN & 0xFF00) == 0x3D00)\n'
        '#endif// (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n'
        '                         ) \n'
        '         { // Proprietary messages that have a command bytes.'
    )
    if old in content:
        content = content.replace(old, new, 1)
        write_file_safe(path, content)
        log_success("Added JDAP PGN filters to CAN_ReceiveFilter")
    else:
        log_warn("Could not find exact CAN_ReceiveFilter pattern — may need manual patch")


def patcher_step_04():
    """cmcandrv.c — JDAP_Protect in Transmit"""
    path = state.context.get("patcher_files", {}).get("cmcandrv.c")
    if not path:
        return
    content = read_file_safe(path)
    if not content:
        return
    if "JDAP_Protect" in content:
        log_info("JDAP_Protect already present in cmcandrv.c — skipped")
        return

    old_pattern = '      if(!E2E_JD1Protect(bufferHandle))\n      {\n         return FALSE;\n      }\n   }\n#endif // E2E_SUPPORT'
    new_block = (
        '      /* JDAP_Protect(bufferHandle, (((destNameId == GLOBAL_ID) ? GLOBAL_ID : CAN_Name_GetSrcAddrFromIndex(\n'
        'destNameId, canId))), recordPtr->TxArbitration_SrcAddr);*/ // fijfu5g // add logic to skip message send, if this opration failed. add this call in function \n\n'
        '#if (JDAP_ROLE == 1) || (JDAP_ROLE == 3)\n'
        '      if (0x3C00 == (CAN_ComputePgn(bufferHandle->arbitration) & 0xFF00))\n'
        '      {\n'
        '         JDAP_Protect(bufferHandle, (((destNameId == GLOBAL_ID) ? GLOBAL_ID : CAN_Name_GetSrcAddrFromIndex(destNameId, canId))), sourceAddress);\n'
        '      }\n'
        '      else\n'
        '#endif   // (JDAP_ROLE == 1)  || (JDAP_ROLE == 3)\n'
        '      {\n'
        '#if (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n'
        '         if (0x3D00 == (CAN_ComputePgn(bufferHandle->arbitration) & 0xFF00))\n'
        '         {\n'
        '            JDAP_Protect(bufferHandle, (((destNameId == GLOBAL_ID) ? GLOBAL_ID : CAN_Name_GetSrcAddrFromIndex(destNameId, canId))), sourceAddress);\n'
        '         }\n'
        '         else\n'
        '#endif   //  (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n'
        '         {\n'
        '#if defined E2E_SUPPORT\n'
        '            if (!E2E_JD1Protect(bufferHandle))\n'
        '            {\n'
        '               return FALSE;\n'
        '            }\n'
        '#endif\n'
        '         }\n'
        '      }\n'
        '      \n'
        '   }'
    )
    if old_pattern in content:
        content = content.replace(old_pattern, new_block, 1)
        write_file_safe(path, content)
        log_success("Added JDAP_Protect to CAN transmit path")
    else:
        log_warn("Could not find exact E2E protect pattern in cmcandrv.c — may need manual patch")


def patcher_step_05():
    """cmcanin.c — Add JDAP Includes"""
    path = state.context.get("patcher_files", {}).get("cmcanin.c")
    if not path:
        log_warn("cmcanin.c not found, skipping")
        return
    content = read_file_safe(path)
    if not content:
        return
    if "JDAP_Security.h" in content:
        log_info("JDAP includes already present in cmcanin.c — skipped")
        return

    jdap_includes = (
        '\n#if (JDAP_ROLE == 1) || (JDAP_ROLE == 3)\n'
        '#include "JDAP_Security.h"\n'
        '#endif // (JDAP_ROLE == 1) || (JDAP_ROLE == 3)\n'
        '#if (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n'
        '#include "JDAP_CANAbstraction.h"\n'
        '#endif // (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n\n'
    )
    marker = "#endif //E2E_SUPPORT"
    idx = content.find(marker)
    if idx >= 0:
        end = content.find("\n", idx) + 1
        content = content[:end] + jdap_includes + content[end:]
        write_file_safe(path, content)
        log_success("Added JDAP includes to cmcanin.c")
    else:
        log_warn("Could not find #endif //E2E_SUPPORT in cmcanin.c")


def patcher_step_06():
    """cmcanin.c — 2-byte Command Byte"""
    path = state.context.get("patcher_files", {}).get("cmcanin.c")
    if not path:
        return
    content = read_file_safe(path)
    if not content:
        return
    if "0x3D00" in content and "0x3C00" in content and "checkCommandByte = TRUE" in content:
        log_info("JDAP command byte handlers already present in cmcanin.c — skipped")
        return

    jdap_cmd = (
        '#if (JDAP_ROLE == 1) || (JDAP_ROLE == 3)\n'
        '               else if ((canRcvdMsgInfo.PGN & 0xFF00) == 0x3D00)\n'
        '               {\n'
        '                  checkCommandByte = TRUE;\n'
        '                  commandByte = ((((UInt16_T)canRcvdMsgInfo.msgData[0]) << 8) | (UInt16_T)canRcvdMsgInfo.msgData[1]);\n'
        '               }\n'
        '#endif  // (JDAP_ROLE == 1) || (JDAP_ROLE == 3)\n'
        '#if (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n'
        '               else if ((canRcvdMsgInfo.PGN & 0xFF00) == 0x3C00)\n'
        '               {\n'
        '                  checkCommandByte = TRUE;\n'
        '                  commandByte = ((((UInt16_T)canRcvdMsgInfo.msgData[0]) << 8) | (UInt16_T)canRcvdMsgInfo.msgData[1]);\n'
        '               }\n'
        '#endif  // (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n'
    )
    # Find the Proprietary B command byte section and insert after
    marker = "PROPB_MSG >> 8))"
    idx = content.find(marker)
    if idx >= 0:
        # Find the closing brace of this block
        brace_idx = content.find("}", idx)
        if brace_idx >= 0:
            end = content.find("\n", brace_idx) + 1
            content = content[:end] + jdap_cmd + content[end:]
            write_file_safe(path, content)
            log_success("Added JDAP 2-byte command byte handlers to cmcanin.c")
            return

    log_warn("Could not find exact insertion point for command byte in cmcanin.c")


def patcher_step_07():
    """cmcanin.c — JDAP_Check"""
    path = state.context.get("patcher_files", {}).get("cmcanin.c")
    if not path:
        return
    content = read_file_safe(path)
    if not content:
        return
    if "JDAP_Check" in content:
        log_info("JDAP_Check already present in cmcanin.c — skipped")
        return

    old = (
        '                  retVal = E2E_STATUS_OK;\n'
        '                  retVal = E2E_JD1CheckPeriodic(&canRcvdMsgInfo, RcvMsgListInfoPtr->RcvMsgList[i].E2E_TYPE, RcvMsgListInfoPtr->RcvMsgList[i].E2E_LIST_IDX, canRcvdMsgInfo.can_id);\n'
        '                  if (E2E_STATUS_OK != retVal)\n'
        '                  {\n'
        '                      //perform corrective action or provide flag to upper layer by indicating\n'
        '                  }\n'
        '                  else\n'
        '                  {'
    )
    new = (
        '\n                  retVal = E2E_STATUS_OK;\n'
        '#if (JDAP_ROLE == 1) || (JDAP_ROLE == 3)\n'
        '                  if ((canRcvdMsgInfo.PGN & 0xFF00) == 0x3D00)\n'
        '                  {\n'
        '                      retVal = JDAP_Check(&canRcvdMsgInfo);\n'
        '                  }\n'
        '                  else\n'
        '#endif // (JDAP_ROLE == 1) || (JDAP_ROLE == 3)\n'
        '                                        {\n'
        '#if (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n'
        '                  if ((canRcvdMsgInfo.PGN & 0xFF00) == 0x3C00)\n'
        '                  {\n'
        '                      retVal = JDAP_Check(&canRcvdMsgInfo);\n'
        '                  }\n'
        '                  else\n'
        '#endif // (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n\n'
        '                  {\n'
        '                  retVal = E2E_JD1CheckPeriodic(&canRcvdMsgInfo, RcvMsgListInfoPtr->RcvMsgList[i].E2E_TYPE, RcvMsgListInfoPtr->RcvMsgList[i].E2E_LIST_IDX, canRcvdMsgInfo.can_id);\n'
        '                  }\n'
        '                                  }\n'
        '                  if (E2E_STATUS_OK != retVal)\n'
        '                  {\n'
        '                      //perform corrective action or provide flag to upper layer by indicating\n'
        '                  }\n'
        '                  else\n'
        '                  {'
    )
    if old in content:
        content = content.replace(old, new, 1)
        write_file_safe(path, content)
        log_success("Added JDAP_Check to cmcanin.c E2E verification")
    else:
        log_warn("Could not find exact E2E check pattern in cmcanin.c — may need manual patch")


def patcher_step_08():
    """osdsnis.h — JDAP Design Issues"""
    path = state.context.get("patcher_files", {}).get("osdsnis.h")
    if not path:
        log_warn("osdsnis.h not found, skipping")
        return
    content = read_file_safe(path)
    if not content:
        return
    if "TIMShadowTECSupportedFunctionsListFull" in content:
        log_info("JDAP design issues already present in osdsnis.h — skipped")
        return

    design_issues = (
        '#if (JDAP_ROLE == 1) || (JDAP_ROLE == 3)\n'
        '         DESIGN_ISSUE(TIMShadowTECSupportedFunctionsListFull)\n'
        '         DESIGN_ISSUE(TIMServerModule_GenericError)\n'
        '         DESIGN_ISSUE(JDC3_TransmitQueueFail)\n'
        '         DESIGN_ISSUE(TIMTransmitQueueFull)\n'
        '         DESIGN_ISSUE(TIMReceiveQueueFull)\n'
        '         DESIGN_ISSUE(TIMClientDatabaseFull)\n'
        '         DESIGN_ISSUE(TIMClientDatabaseAccessOutOfBound)\n'
        '         DESIGN_ISSUE(TIMFunctionAssignmentMsgBufferIssue)\n'
        '         DESIGN_ISSUE(TIMFunctionAssignmentInvalidMessageData)\n'
        '         DESIGN_ISSUE(TIMAuthenticationAccessOutOfBound)\n'
        '         DESIGN_ISSUE(TIMAuthServerCertExceedsLengthOfField)\n'
        '         DESIGN_ISSUE(TIMAuthenticationError)\n'
        '         DESIGN_ISSUE(TIMAuthLibError)\n'
        '         DESIGN_ISSUE(TIMAuthICCMessageVersionNotSupported)\n'
        '         DESIGN_ISSUE(SecAuthMemWriteAddrOOR_TEC)\n'
        '         DESIGN_ISSUE(SECAUTH_UnknownJDVFacility_TEC)\n'
        '         DESIGN_ISSUE(SecAuthMemReadAddrOOR_TEC)\n'
        '#endif \n\n'
        '#if (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n'
        'DESIGN_ISSUE(JDAPReceiveQueueFull)\n'
        'DESIGN_ISSUE(JDAPServerModule_GenericError)\n'
        'DESIGN_ISSUE(TIMClientDatabaseAccessOutOfBound)\n'
        'DESIGN_ISSUE(TIMClientDatabaseFull)\n'
        'DESIGN_ISSUE(TIMServerModule_GenericError)\n'
        'DESIGN_ISSUE(TIMTransmitQueueFull)\n'
        '#endif // (JDAP_ROLE == 2) || (JDAP_ROLE == 3)\n\n'
    )
    marker = "#ifdef JD_VOLTAGE_DIAGNOSTICS"
    if marker in content:
        content = content.replace(marker, design_issues + marker, 1)
        write_file_safe(path, content)
        log_success("Added JDAP design issues to osdsnis.h")
    else:
        log_warn("Could not find #ifdef JD_VOLTAGE_DIAGNOSTICS in osdsnis.h")


def patcher_step_09():
    """Patcher Summary"""
    files = state.context.get("patcher_files", {})
    log_success("═══════════════════════════════════════")
    log_success("  JDAP Patch Summary")
    log_success("═══════════════════════════════════════")
    for fname, path in files.items():
        status = "✓ Found" if path else "✗ Not found"
        log_success(f"  {fname}: {status}")
    log_success("  Changes: includes, PGN filters, JDAP_Protect, command bytes, JDAP_Check, design issues")
    log_success("═══════════════════════════════════════")


# ============================================================
# AGENT 3: JDAP Config
# ============================================================
def config_step_00():
    """Discover Config Files"""
    # Ensure project_folder is set (may not be if integrator was skipped)
    if not state.context.get("project_folder"):
        log_info("Project folder not set — scanning workspace...")
        entries = os.listdir(WORKSPACE_ROOT)
        folders = []
        skip = {".github", ".vscode", ".git", "JDAP", "tools", "node_modules", ".vs"}
        for e in sorted(entries):
            full = os.path.join(WORKSPACE_ROOT, e)
            if os.path.isdir(full) and e not in skip and not e.startswith("."):
                folders.append(e)
        if not folders:
            log_error("No project folders found in workspace!")
            state.context["config_agent_stopped"] = True
            return
        if len(folders) == 1:
            state.context["project_folder"] = folders[0]
            log_info(f"Auto-selected project folder: {folders[0]}")
        else:
            resp = wait_for_input([
                {
                    "id": "project_folder",
                    "label": "Project Folder",
                    "question": "Which project folder contains the APPCFG/ directory?",
                    "type": "select",
                    "options": [{"label": f, "value": f} for f in folders],
                }
            ])
            state.context["project_folder"] = resp["project_folder"]
            log_info(f"Selected project folder: {resp['project_folder']}")

    log_info("Searching APPCFG/ for JDAP config files...")
    appcfg = project_path("APPCFG")
    found = []
    if os.path.isdir(appcfg):
        for f in os.listdir(appcfg):
            if "JDAP" in f and "Config" in f and f.endswith(".h"):
                found.append(f)
    state.context["jdap_config_files"] = found
    if found:
        log_info(f"Found: {', '.join(found)}")
    else:
        log_warn("No JDAP config files found in APPCFG/.")
        resp = wait_for_input([
            {
                "id": "config_missing_action",
                "label": "No JDAP Config Files Found",
                "question": "No JDAP config files (JDAP*Config*.h) were found in APPCFG/. "
                            "Would you like to provide the config file path manually, or stop the config agent?",
                "type": "select",
                "options": [
                    {"label": "Provide path manually", "value": "manual"},
                    {"label": "Stop config agent", "value": "stop"},
                ],
            }
        ])
        if resp.get("config_missing_action") == "manual":
            path_resp = wait_for_input([
                {
                    "id": "config_manual_path",
                    "label": "Config File Path",
                    "question": "Enter the relative path to the JDAP config file (relative to project root, e.g. APPCFG/JDAP_Server_Config.h):",
                    "type": "text",
                    "placeholder": "e.g., APPCFG/JDAP_Server_Config.h",
                }
            ])
            manual_path = path_resp.get("config_manual_path", "").strip()
            if manual_path:
                full_path = project_path(manual_path)
                if os.path.isfile(full_path):
                    fname = os.path.basename(manual_path)
                    state.context["jdap_config_files"] = [fname]
                    state.context["config_manual_dir"] = os.path.dirname(full_path)
                    log_success(f"Using manually provided config file: {fname}")
                else:
                    log_error(f"File not found: {full_path}")
                    state.context["config_agent_stopped"] = True
            else:
                log_error("No path provided.")
                state.context["config_agent_stopped"] = True
        else:
            log_info("Config agent stopped by user.")
            state.context["config_agent_stopped"] = True


def config_step_01():
    """Select Config to Modify"""
    if state.context.get("config_agent_stopped"):
        log_info("Config agent was stopped in previous step — skipping.")
        return

    found = state.context.get("jdap_config_files", [])
    if not found:
        resp = wait_for_input([
            {
                "id": "config_provide_file",
                "label": "No Config Files Available",
                "question": "No JDAP config files are available. Please provide the filename to create/use, or type 'stop' to halt the config agent.",
                "type": "text",
                "placeholder": "e.g., JDAP_Server_Config.h or 'stop'",
            }
        ])
        answer = resp.get("config_provide_file", "").strip()
        if not answer or answer.lower() == "stop":
            log_info("Config agent stopped by user.")
            state.context["config_agent_stopped"] = True
            return
        state.context["config_target"] = answer
        log_success(f"User provided config file: {answer}")
        return

    options = [{"label": f, "value": f} for f in found]
    if len(found) == 1:
        state.context["config_target"] = found[0]
        log_info(f"Only one config file found, auto-selecting: {found[0]}")
        return

    resp = wait_for_input([
        {
            "id": "config_target",
            "label": "Config File",
            "question": "Which JDAP config file do you want to modify?",
            "type": "select",
            "options": options,
        }
    ])
    state.context["config_target"] = resp["config_target"]
    log_success(f"Selected: {resp['config_target']}")


def config_step_02():
    """Read Current Config"""
    if state.context.get("config_agent_stopped"):
        log_info("Config agent was stopped — skipping.")
        return
    target = state.context.get("config_target")
    if not target:
        log_warn("No config target set — cannot proceed.")
        return
    # Support manually provided directory from step 00
    manual_dir = state.context.get("config_manual_dir")
    if manual_dir:
        path = os.path.join(manual_dir, target)
    else:
        path = project_path("APPCFG", target)
    content = read_file_safe(path)
    if not content:
        return
    state.context["config_content"] = content

    # Extract current #define values
    defines = {}
    for m in re.finditer(r"#define\s+(\w+)\s+(.+?)(?:\s*//.*)?$", content, re.MULTILINE):
        defines[m.group(1)] = m.group(2).strip()
    state.context["config_defines"] = defines

    log_info(f"Current configuration values in {target}:")
    for k, v in sorted(defines.items()):
        log_info(f"  {k} = {v}")


def config_step_03a():
    """Configure Bus & TLA"""
    if state.context.get("config_agent_stopped"):
        log_info("Config agent was stopped — skipping.")
        return
    target = state.context.get("config_target", "")
    if not target:
        return
    defines = state.context.get("config_defines", {})
    is_server = "Server" in target

    questions = []
    if is_server:
        questions.append({
            "id": "JDAP_SRV_TLA",
            "label": f"JDAP_SRV_TLA (currently: {defines.get('JDAP_SRV_TLA', 'N/A')})",
            "question": "Which TLA for the server?",
            "type": "text",
            "placeholder": "e.g., TMS, TEI, ACU, ICU, CAB",
        })
        bus_current = defines.get('JDAP_BUS', '')
        bus_opts = [{"label": f"CAN{i}", "value": f"CAN{i}"} for i in range(1, 7)]
        questions.append({
            "id": "JDAP_BUS",
            "label": f"JDAP_BUS (currently: {bus_current or 'N/A'})",
            "question": "CAN bus for JDAP communication?",
            "type": "select",
            "options": options_with_current_first(bus_opts, bus_current),
        })
        # Search can_FnId.ch for InfoID values
        fn_id_path = project_path("APPCFG", "CAN", "can_FnId.ch")
        info_ids = []
        fn_content = read_file_safe(fn_id_path)
        if fn_content:
            for m in re.finditer(r"(\w+_InfoID)", fn_content):
                info_ids.append(m.group(1))
        if not info_ids:
            info_ids = ["TMS_InfoID", "TEI_InfoID", "ACU_InfoID", "ICU_InfoID", "CAB_InfoID"]
            log_warn("Could not read can_FnId.ch, using default InfoID options")
        tla_addr_current = defines.get('JDAP_SRV_TLA_ADDRESS_ID', '')
        tla_addr_opts = [{"label": iid, "value": iid} for iid in info_ids[:30]]
        questions.append({
            "id": "JDAP_SRV_TLA_ADDRESS_ID",
            "label": f"JDAP_SRV_TLA_ADDRESS_ID (currently: {tla_addr_current or 'N/A'})",
            "question": "TLA Address ID for the server?",
            "type": "select",
            "options": options_with_current_first(tla_addr_opts, tla_addr_current),
        })
    else:
        questions.append({
            "id": "JDAP_Client_TLA",
            "label": f"JDAP_Client_TLA (currently: {defines.get('JDAP_Client_TLA', 'N/A')})",
            "question": "Which TLA for the client?",
            "type": "text",
            "placeholder": "e.g., GTC, ACU, ICU",
        })
        bus_current_c = defines.get('JDAP_BUS', '')
        bus_opts_c = [{"label": f"CAN{i}", "value": f"CAN{i}"} for i in range(1, 7)]
        questions.append({
            "id": "JDAP_BUS",
            "label": f"JDAP_BUS (currently: {bus_current_c or 'N/A'})",
            "question": "CAN bus for JDAP communication?",
            "type": "select",
            "options": options_with_current_first(bus_opts_c, bus_current_c),
        })

    resp = wait_for_input(questions)
    state.context["config_bus_tla"] = resp
    log_success(f"Bus & TLA configured: {resp}")


def config_step_03b():
    """Configure RCV Message Macros"""
    if state.context.get("config_agent_stopped"):
        log_info("Config agent was stopped — skipping.")
        return
    target = state.context.get("config_target", "")
    if not target:
        return
    is_server = "Server" in target

    # Determine which rcv xref files to scan based on selected JDAP_BUS
    jdap_bus = state.context.get("config_bus_tla", {}).get("JDAP_BUS", "CAN1")
    bus_num = re.search(r"\d+", jdap_bus)
    bus_idx = int(bus_num.group()) if bus_num else 1

    # Always read rcv_xref.h (CAN1), and the bus-specific xref if different
    xref_files = ["rcv_xref.h"]
    if bus_idx >= 2:
        xref_files.append(f"rcv{bus_idx}xref.h")
    # Also check rcv2xref.h if not already included
    if "rcv2xref.h" not in xref_files:
        xref_files.append("rcv2xref.h")

    rcv_options = []
    for xref in xref_files:
        xref_path = project_path("APPCFG", "CAN", xref)
        content = read_file_safe(xref_path)
        if content:
            for m in re.finditer(r"PGN_XREF_MACRO\((RCV\d?_PGN_\w+)\)", content):
                rcv_options.append(m.group(1))

    if not rcv_options:
        rcv_options = ["RCV_PGN_EXAMPLE_1", "RCV_PGN_EXAMPLE_2"]
        log_warn("No RCV xref entries found, using placeholders")

    log_info(f"Found {len(rcv_options)} RCV PGN entries from {', '.join(xref_files)}")

    questions = []
    defines = state.context.get("config_defines", {})

    if is_server:
        macros = [
            ("JDAP_RCV_MACRO_CANx_CLIENT_TO_SERVER", "TIM Client to Server"),
            ("JDAP_RCV_MACRO_CANx_SERVER_TO_CLIENT", "TIM Server to Client"),
            ("JDAP_AUTH_RCV_MACRO_CLIENT_TO_SERVER", "Authentication Client to Server"),
        ]
    else:
        macros = [
            ("JDAP_RCV_MACRO_CANx_SERVER_TO_CLIENT", "TIM Server to Client"),
            ("JDAP_AUTH_RCV_MACRO_SERVER_TO_CLIENT", "Authentication Server to Client"),
        ]

    for macro_name, desc in macros:
        current = defines.get(macro_name, "")
        all_opts = [{"label": r, "value": r} for r in rcv_options[:30]]
        questions.append({
            "id": macro_name,
            "label": f"{macro_name} ({desc}) — currently: {current or 'Not set'}",
            "question": f"Select RCV macro for {desc}",
            "type": "select",
            "options": options_with_current_first(all_opts, current),
        })

    resp = wait_for_input(questions)
    state.context["config_rcv"] = resp
    log_success("RCV macros configured")


def config_step_03c():
    """Configure Functions"""
    if state.context.get("config_agent_stopped"):
        log_info("Config agent was stopped — skipping.")
        return
    questions = []
    funcs = [
        "AUX_VALVE_SUPERSET", "FRONT_PTO", "REAR_PTO",
        "FRONT_HITCH", "REAR_HITCH", "EXTERNAL_GUIDANCE", "VEHICLE_SPEED",
    ]
    defines = state.context.get("config_defines", {})
    target = state.context.get("config_target", "")
    prefix = "JDAP_SERVER_" if "Server" in target else "JDAP_CLIENT_"

    for func in funcs:
        macro = prefix + func
        current = defines.get(macro, "")
        questions.append({
            "id": macro,
            "label": f"{macro} (currently: {current or 'Not set'})",
            "question": f"Enable {func}?",
            "type": "select",
            "options": options_highlight_current([
                {"label": "TRUE", "value": "TRUE"},
                {"label": "FALSE", "value": "FALSE"},
            ], current),
        })

    questions.append({
        "id": "aux_valve_count",
        "label": "Number of Aux Valves (1-32)",
        "question": "How many auxiliary valves to enable? (0 for none)",
        "type": "text",
        "placeholder": "0-32",
    })

    resp = wait_for_input(questions)
    state.context["config_functions"] = resp
    log_success("Functions configured")


def config_step_03d():
    """Configure Manufacturer Specific Function Indices"""
    if state.context.get("config_agent_stopped"):
        log_info("Config agent was stopped — skipping.")
        return
    questions = []
    defines = state.context.get("config_defines", {})
    for i in range(5):
        macro = f"JDAP_MS_FUNCTION_INDEX_B{i}"
        current = defines.get(macro, "Not set")
        display_macro = macro.replace("JDAP_MS_", "JDAP_Manufacturer_Specific_")
        questions.append({
            "id": macro,
            "label": f"{display_macro} (currently: {current})",
            "question": f"Enable Manufacturer Specific Function Index B{i}?",
            "type": "select",
            "options": options_highlight_current([
                {"label": "TRUE", "value": "TRUE"},
                {"label": "FALSE", "value": "FALSE"},
            ], current if current != "Not set" else ""),
        })

    resp = wait_for_input(questions)
    state.context["config_ms_indices"] = resp
    log_success("Manufacturer Specific Function Indices configured")


def config_step_03e():
    """Configure TIM Standard Facilities"""
    if state.context.get("config_agent_stopped"):
        log_info("Config agent was stopped — skipping.")
        return
    funcs = state.context.get("config_functions", {})
    defines = state.context.get("config_defines", {})
    questions = []

    # Only ask about enabled functions — per agent.md Section E
    facility_map = {
        "AUX_VALVE_SUPERSET": ["Valve_State", "Valve_Flow"],
        "FRONT_PTO": ["Disengagement", "Engagement_CCW", "Engagement_CW", "Speed_CCW", "Speed_CW"],
        "REAR_PTO": ["Disengagement", "Engagement_CCW", "Engagement_CW", "Speed_CCW", "Speed_CW"],
        "FRONT_HITCH": ["Hitch_Motion", "Hitch_Position"],
        "REAR_HITCH": ["Hitch_Motion", "Hitch_Position"],
        "VEHICLE_SPEED": [
            "Forward_Direction", "Reverse_Direction",
            "Start_Vehicle_Motion", "Stop_Vehicle_Motion",
            "Forward_Direction_SSBTS", "Reverse_Direction_SSBTS",
            "Vehicle_Change_of_Direction",
        ],
        "EXTERNAL_GUIDANCE": ["Curvature"],
    }

    target = state.context.get("config_target", "")
    prefix = "JDAP_SERVER_" if "Server" in target else "JDAP_CLIENT_"

    for func_key, facilities in facility_map.items():
        full_key = prefix + func_key
        if funcs.get(full_key) == "TRUE":
            for fac in facilities:
                fac_macro = f"{prefix}{func_key}_{fac}"
                fac_current = defines.get(fac_macro, "") if defines else ""
                questions.append({
                    "id": fac_macro,
                    "label": f"{fac_macro}",
                    "question": f"Enable {func_key} → {fac}?",
                    "type": "select",
                    "options": options_highlight_current([
                        {"label": "ON", "value": "ON"},
                        {"label": "OFF", "value": "OFF"},
                    ], fac_current),
                })

    if not questions:
        log_info("No functions enabled — skipping TIM facilities")
        state.context["config_facilities"] = {}
        return

    resp = wait_for_input(questions)
    state.context["config_facilities"] = resp
    log_success("TIM Standard Facilities configured")


def config_step_03f():
    """Configure Manufacturer Specific Facilities"""
    if state.context.get("config_agent_stopped"):
        log_info("Config agent was stopped — skipping.")
        return
    ms_indices = state.context.get("config_ms_indices", {})
    enabled_indices = [k for k, v in ms_indices.items() if v == "TRUE"]

    if not enabled_indices:
        log_info("No Manufacturer Specific indices enabled — skipping Manufacturer Specific facilities")
        state.context["config_ms_facilities"] = {}
        return

    # Per agent.md Section F: ask per function category AND per enabled B-index
    # Only include categories whose corresponding control function is enabled (TRUE)
    config_functions = state.context.get("config_functions", {})
    target = state.context.get("config_target", "")
    prefix = "JDAP_SERVER_" if "Server" in target else "JDAP_CLIENT_"

    # Map category name to the function macro key
    category_to_func = {
        "Manufacturer Specific Aux Valve": prefix + "AUX_VALVE_SUPERSET",
        "Manufacturer Specific Front PTO": prefix + "FRONT_PTO",
        "Manufacturer Specific Rear PTO": prefix + "REAR_PTO",
        "Manufacturer Specific Front Hitch": prefix + "FRONT_HITCH",
        "Manufacturer Specific Rear Hitch": prefix + "REAR_HITCH",
        "Manufacturer Specific Vehicle Speed": prefix + "VEHICLE_SPEED",
        "Manufacturer Specific External Guidance": prefix + "EXTERNAL_GUIDANCE",
    }

    ms_function_categories = []
    for cat, func_macro in category_to_func.items():
        # Check if enabled in user's Section C answers or in original defines
        func_val = config_functions.get(func_macro, "")
        if not func_val:
            defines = state.context.get("config_defines", {})
            func_val = defines.get(func_macro, "FALSE")
        if func_val == "TRUE":
            ms_function_categories.append(cat)

    # Also MS B0-B4 entries for enabled indices (always shown)
    for idx_macro in enabled_indices:
        b_idx = idx_macro.replace("JDAP_MS_FUNCTION_INDEX_", "")
        ms_function_categories.append(f"Manufacturer Specific {b_idx}")

    questions = []
    # For function-specific categories (Aux Valve, PTO, etc.) — one question per category (no B-index)
    for category in ms_function_categories:
        if category.startswith("Manufacturer Specific B"):
            continue  # Handle B-index categories separately below
        q_id = f"{category.replace(' ', '_')}_all_not_available"
        questions.append({
            "id": q_id,
            "label": f"{category} — All NOT_AVAILABLE?",
            "question": f"Keep all byte/bit values as NOT_AVAILABLE for {category}?",
            "type": "select",
            "options": [
                {"label": "Yes — all NOT_AVAILABLE", "value": "yes"},
                {"label": "No — configure individually (ON/OFF/NOT_AVAILABLE)", "value": "no"},
            ],
        })

    # For B-index categories — one question per enabled B-index
    for category in ms_function_categories:
        if not category.startswith("Manufacturer Specific B"):
            continue
        q_id = f"{category.replace(' ', '_')}_all_not_available"
        questions.append({
            "id": q_id,
            "label": f"{category} — All NOT_AVAILABLE?",
            "question": f"Keep all byte/bit values as NOT_AVAILABLE for {category}?",
            "type": "select",
            "options": [
                {"label": "Yes — all NOT_AVAILABLE", "value": "yes"},
                {"label": "No — configure individually (ON/OFF/NOT_AVAILABLE)", "value": "no"},
            ],
        })

    resp = wait_for_input(questions)

    # For categories where user chose "no" (configure individually), ask byte/bit details
    configure_individually = [q_id for q_id, val in resp.items() if val == "no"]
    if configure_individually:
        defines = state.context.get("config_defines", {})
        detail_questions = []

        for q_id in configure_individually:
            category_key = q_id.replace("_all_not_available", "")

            # Map category names to macro prefixes
            prefix = None
            if "Aux_Valve" in category_key:
                prefix = "JDAP_MS_AUX_VAlVE_"
            elif "Front_PTO" in category_key:
                prefix = "JDAP_MS_FRONT_PTO_"
            elif "Rear_PTO" in category_key:
                prefix = "JDAP_MS_REAR_PTO_"
            elif "Front_Hitch" in category_key:
                prefix = "JDAP_MS_FRONT_HITCH_FACILITIES_"
            elif "Rear_Hitch" in category_key:
                prefix = "JDAP_MS_REAR_HITCH_FACILITIES_"
            elif "Vehicle_Speed" in category_key:
                prefix = "JDAP_MS_VEHICLE_SPEED_FACILITIES_"
            elif "External_Guidance" in category_key:
                prefix = "JDAP_MS_EXT_GUIDANCE_FACILITIES_"
            else:
                # Check for B-index category (e.g., "Manufacturer_Specific_B0")
                import re as _re
                b_match = _re.search(r"B(\d)", category_key)
                if b_match:
                    prefix = f"JDAP_MS_B{b_match.group(1)}_"

            if not prefix:
                continue

            # Find all defines that match this prefix
            matching_macros = []
            for macro_name, macro_val in sorted(defines.items()):
                if macro_name.startswith(prefix) and "BYTE" in macro_name and "BIT" in macro_name:
                    matching_macros.append((macro_name, macro_val))

            for macro_name, current_val in matching_macros:
                detail_questions.append({
                    "id": macro_name,
                    "label": f"{macro_name} (currently: {current_val})",
                    "question": f"Set {macro_name}?",
                    "type": "select",
                    "options": options_highlight_current([
                        {"label": "ON", "value": "ON"},
                        {"label": "OFF", "value": "OFF"},
                        {"label": "NOT_AVAILABLE", "value": "NOT_AVAILABLE"},
                    ], current_val),
                })

        if detail_questions:
            detail_resp = wait_for_input(detail_questions)
            resp.update(detail_resp)

    state.context["config_ms_facilities"] = resp
    log_success("Manufacturer Specific Facilities configured")


def config_step_04():
    """Apply Config Changes"""
    if state.context.get("config_agent_stopped"):
        log_info("Config agent was stopped — skipping.")
        return
    target = state.context.get("config_target")
    if not target:
        log_info("No config target — skipping apply")
        return
    # Support manually provided directory from step 00
    manual_dir = state.context.get("config_manual_dir")
    if manual_dir:
        path = os.path.join(manual_dir, target)
    else:
        path = project_path("APPCFG", target)
    content = read_file_safe(path)
    if not content:
        return

    changes = 0
    all_settings = {}
    for key in ["config_bus_tla", "config_rcv", "config_functions", "config_ms_indices", "config_facilities", "config_ms_facilities"]:
        vals = state.context.get(key, {})
        all_settings.update(vals)

    for macro, value in all_settings.items():
        if macro.endswith("_all_not_available") or macro == "aux_valve_count":
            continue
        pattern = rf"(#define\s+{re.escape(macro)}\s+)(\S+)"
        m = re.search(pattern, content)
        if m:
            old_val = m.group(2)
            if old_val != value:
                content = content[: m.start(2)] + value + content[m.end(2) :]
                log_info(f"  {macro}: {old_val} → {value}")
                changes += 1

    # Handle aux valve count
    valve_count = int(state.context.get("config_functions", {}).get("aux_valve_count", "0") or "0")
    prefix = "JDAP_SERVER_" if "Server" in target else "JDAP_CLIENT_"
    for i in range(1, 33):
        macro = f"{prefix}AUX_VALVE_{i:02d}"
        value = "TRUE" if i <= valve_count else "FALSE"
        pattern = rf"(#define\s+{re.escape(macro)}\s+)(\S+)"
        m = re.search(pattern, content)
        if m and m.group(2) != value:
            content = content[: m.start(2)] + value + content[m.end(2) :]
            changes += 1

    if changes > 0:
        write_file_safe(path, content)
        log_success(f"Applied {changes} changes to {target}")
    else:
        log_info("No changes needed")


def config_step_05():
    """Config Summary"""
    if state.context.get("config_agent_stopped"):
        log_info("Config agent was stopped by user — no changes were made.")
        return
    log_success("═══════════════════════════════════════")
    log_success("  JDAP Config Summary")
    log_success(f"  File: {state.context.get('config_target', 'N/A')}")
    for key in ["config_bus_tla", "config_rcv", "config_functions"]:
        vals = state.context.get(key, {})
        for k, v in vals.items():
            log_success(f"  {k} = {v}")
    log_success("═══════════════════════════════════════")


# ============================================================
# AGENT 4: JDAP CAN Spreadsheet
# ============================================================
def can_step_01():
    """Check code-generation version"""
    pkg_path = project_path("package.json")
    content = read_file_safe(pkg_path)
    if not content:
        log_error("package.json not found")
        return
    pkg = json.loads(content)
    codegen_key = "@deere-embedded/isg-embedded-tools.code-generation"
    version = None
    for section in ["dependencies", "devDependencies"]:
        if section in pkg and codegen_key in pkg[section]:
            version = pkg[section][codegen_key]
            break

    if not version:
        log_warn(f"{codegen_key} not found in package.json — stopping CAN spreadsheet agent")
        state.context["can_skip"] = True
        return

    clean_ver = re.sub(r"^[\^~>=]+", "", version)
    state.context["codegen_version"] = clean_ver
    log_info(f"Code-generation version: {clean_ver}")

    parts = clean_ver.split(".")
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
    if (major, minor, patch) <= (14, 13, 0):
        log_info(f"Version {clean_ver} is ≤ 14.13.0 — COM_GENERATOR JDAP settings not required")
        state.context["can_skip"] = True
    else:
        log_info(f"Version {clean_ver} is > 14.13.0 — proceeding with COM_GENERATOR update")
        state.context["can_skip"] = False


def can_step_02():
    """Read ProjectSpecific.mk"""
    if state.context.get("can_skip"):
        log_info("Skipped — version check indicated no changes needed")
        return
    mk_path = project_path("ProjectSpecific.mk")
    content = read_file_safe(mk_path)
    if not content:
        log_error("ProjectSpecific.mk not found")
        state.context["can_skip"] = True
        return

    state.context["mk_content"] = content

    # Check if CANGENSPREADSHEET is commented
    for line in content.split("\n"):
        stripped = line.strip()
        if "CANGENSPREADSHEET" in stripped:
            if stripped.startswith("#"):
                log_info("CANGENSPREADSHEET is commented out — CAN code generation is disabled")
                state.context["can_skip"] = True
                return
            else:
                log_info(f"CANGENSPREADSHEET found: {stripped[:80]}")
                break

    # Find CANBUS_MAPPING line
    if "CANBUS_MAPPING" in content:
        log_info("CANBUS_MAPPING found in ProjectSpecific.mk")
    else:
        log_warn("CANBUS_MAPPING not found — will try to insert at end of CAN section")


def can_step_03():
    """Update COM_GENERATOR Settings"""
    if state.context.get("can_skip"):
        log_info("Skipped — no update needed")
        return

    mk_path = project_path("ProjectSpecific.mk")
    content = read_file_safe(mk_path)
    if not content:
        return

    lines_to_add = [
        "COM_GENERATOR_GENERATE_CAN = $(TRUE)",
        "COM_GEN_TOOL_USER_ARGUMENTS = -jdap",
        "COM_GENERATOR_GENERATE_GETSETS = $(TRUE)",
    ]

    already_present = all(line in content for line in lines_to_add)
    if already_present:
        log_info("COM_GENERATOR settings already present — no changes needed")
        state.context["can_action"] = "already_present"
        return

    # Insert after CANBUS_MAPPING
    insertion = "\n".join(lines_to_add)
    idx = content.find("CANBUS_MAPPING")
    if idx >= 0:
        line_end = content.find("\n", idx)
        if line_end >= 0:
            content = content[: line_end + 1] + insertion + "\n" + content[line_end + 1 :]
            write_file_safe(mk_path, content)
            log_success("Inserted COM_GENERATOR settings after CANBUS_MAPPING")
            state.context["can_action"] = "added"
            return

    log_warn("Could not find insertion point — appending at end")
    content += "\n" + insertion + "\n"
    write_file_safe(mk_path, content)
    state.context["can_action"] = "appended"


def can_step_04():
    """Report Results"""
    ver = state.context.get("codegen_version", "N/A")
    action = state.context.get("can_action", "skipped")
    log_success("═══════════════════════════════════════")
    log_success("  JDAP CAN Spreadsheet Summary")
    log_success(f"  Code-gen version: {ver}")
    log_success(f"  Action: {action}")
    log_success("═══════════════════════════════════════")


# ============================================================
# Step Handler Registry
# ============================================================
STEP_HANDLERS = {
    # Integrator
    "int_01": integrator_step_01,
    "int_02": integrator_step_02,
    "int_03": integrator_step_03,
    "int_04": integrator_step_04,
    "int_05": integrator_step_05,
    "int_06a": integrator_step_06a,
    "int_06b": integrator_step_06b,
    "int_06c": integrator_step_06c,
    "int_07": integrator_step_07,
    "int_08": integrator_step_08,
    "int_09": integrator_step_09,
    "int_10": integrator_step_10,
    "int_11": integrator_step_11,
    "int_12": integrator_step_12,
    "int_13": integrator_step_13,
    "int_14": integrator_step_14,
    # Patcher
    "pat_01": patcher_step_01,
    "pat_02": patcher_step_02,
    "pat_03": patcher_step_03,
    "pat_04": patcher_step_04,
    "pat_05": patcher_step_05,
    "pat_06": patcher_step_06,
    "pat_07": patcher_step_07,
    "pat_08": patcher_step_08,
    "pat_09": patcher_step_09,
    # Config
    "cfg_00": config_step_00,
    "cfg_01": config_step_01,
    "cfg_02": config_step_02,
    "cfg_03a": config_step_03a,
    "cfg_03b": config_step_03b,
    "cfg_03c": config_step_03c,
    "cfg_03d": config_step_03d,
    "cfg_03e": config_step_03e,
    "cfg_03f": config_step_03f,
    "cfg_04": config_step_04,
    "cfg_05": config_step_05,
    # CAN Spreadsheet
    "can_01": can_step_01,
    "can_02": can_step_02,
    "can_03": can_step_03,
    "can_04": can_step_04,
}


# ============================================================
# Orchestrator Thread
# ============================================================
def run_orchestrator():
    try:
        state.status = "running"
        log("═══════════════════════════════════════════════════════════", "info")
        log("  JDAP Orchestrator — Starting Agent Execution", "info")
        log(f"  Workspace: {WORKSPACE_ROOT}", "info")
        log(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "info")
        if state.run_agent_ids:
            log(f"  Running agents: {', '.join(state.run_agent_ids)}", "info")
        else:
            log("  Running: ALL agents sequentially", "info")
        log("═══════════════════════════════════════════════════════════", "info")

        for agent_idx, agent in enumerate(state.agents):
            # Check stop flag
            if state.stop_requested:
                agent["status"] = "stopped"
                log(f"\n  ⛔ Stopped by user before agent '{agent['name']}'", "warn")
                break

            # Skip agents not in run list
            if state.run_agent_ids and agent["id"] not in state.run_agent_ids:
                continue

            state.current_agent_idx = agent_idx
            agent["status"] = "running"
            log("", "info")
            log(f"{'━' * 55}", "info")
            log(f"  {agent['icon']}  AGENT {agent_idx + 1}/4: {agent['name']}", "info")
            log(f"  {agent['description']}", "info")
            log(f"{'━' * 55}", "info")

            for step_idx, step in enumerate(agent["steps"]):
                # Check stop flag
                if state.stop_requested:
                    step["status"] = "stopped"
                    log(f"\n  ⛔ Stopped by user at step '{step['name']}'", "warn")
                    break

                state.current_step_idx = step_idx
                step["status"] = "running"
                log("", "info")
                log(f"  ▶ Step {step['id']}: {step['name']}", "info")
                log(f"    Type: {'🔄 Auto' if step['type'] == 'auto' else '👤 User Input'}", "info")

                handler = STEP_HANDLERS.get(step["id"])
                if handler:
                    try:
                        handler()
                        if step["status"] not in ("error", "stopped"):
                            step["status"] = "completed"
                    except Exception as e:
                        step["status"] = "error"
                        log_error(f"Step failed: {e}")
                        import traceback
                        log_error(traceback.format_exc())
                else:
                    step["status"] = "completed"
                    log_warn(f"No handler for step {step['id']}")

                log(f"  ✓ Step {step['id']} — {step['status']}", "success" if step["status"] == "completed" else "warn")

            if state.stop_requested:
                agent["status"] = "stopped"
                break

            agent["status"] = "completed"
            log(f"\n  ✅ Agent '{agent['name']}' completed", "success")

        if state.stop_requested:
            state.status = "stopped"
            log("", "warn")
            log("═══════════════════════════════════════════════════════════", "warn")
            log("  ⛔ ORCHESTRATOR STOPPED BY USER", "warn")
            log("═══════════════════════════════════════════════════════════", "warn")
        else:
            state.status = "completed"
            log("", "info")
            log("═══════════════════════════════════════════════════════════", "success")
            log("  🎉 ALL SELECTED AGENTS COMPLETED SUCCESSFULLY", "success")
            log("═══════════════════════════════════════════════════════════", "success")

    except Exception as e:
        state.status = "error"
        state.error_message = str(e)
        log_error(f"Orchestrator error: {e}")
        import traceback
        log_error(traceback.format_exc())


# ============================================================
# Flask Routes
# ============================================================
@app.route("/")
def index():
    return send_file(HTML_PATH)


@app.route("/api/start", methods=["POST"])
def api_start():
    if state.status == "running" or state.status == "paused":
        return jsonify({"error": "Already running"}), 400
    data = request.json or {}
    state.reset()
    agent_ids = data.get("agents")  # None = all, list = specific
    if agent_ids:
        state.run_agent_ids = agent_ids
    t = threading.Thread(target=run_orchestrator, daemon=True)
    t.start()
    return jsonify({"ok": True})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    if state.status not in ("running", "paused"):
        return jsonify({"error": "Not running"}), 400
    state.stop_requested = True
    # Unblock if waiting for input
    state.user_response = {}
    state.input_event.set()
    return jsonify({"ok": True})


@app.route("/api/status")
def api_status():
    agents_summary = []
    for a in state.agents:
        agents_summary.append({
            "id": a["id"],
            "name": a["name"],
            "icon": a["icon"],
            "description": a["description"],
            "status": a["status"],
            "steps": [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "type": s["type"],
                    "status": s["status"],
                    "questions": s.get("questions"),
                }
                for s in a["steps"]
            ],
        })
    return jsonify({
        "status": state.status,
        "currentAgent": state.current_agent_idx,
        "currentStep": state.current_step_idx,
        "agents": agents_summary,
        "pendingQuestions": state.pending_questions,
    })


@app.route("/api/input", methods=["POST"])
def api_input():
    data = request.json
    if not data:
        return jsonify({"error": "No data"}), 400
    state.user_response = data
    state.input_event.set()
    return jsonify({"ok": True})


@app.route("/api/logs")
def api_logs():
    since = int(request.args.get("since", 0))
    entries = state.log_entries[since:]
    return jsonify({"logs": entries, "total": len(state.log_entries)})


@app.route("/api/stream")
def api_stream():
    def generate():
        last_idx = 0
        while True:
            current = len(state.log_entries)
            if current > last_idx:
                batch = state.log_entries[last_idx:current]
                last_idx = current
                yield f"data: {json.dumps({'type': 'logs', 'logs': batch})}\n\n"
            # Also send status
            yield f"data: {json.dumps({'type': 'status', 'status': state.status, 'agent': state.current_agent_idx, 'step': state.current_step_idx})}\n\n"
            time.sleep(0.4)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/reset", methods=["POST"])
def api_reset():
    state.reset()
    return jsonify({"ok": True})


@app.route("/api/shutdown", methods=["POST"])
def api_shutdown():
    """Shutdown the server when the browser tab is closed."""
    import signal
    os.kill(os.getpid(), signal.SIGTERM)
    return jsonify({"ok": True})


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    # Default workspace: when frozen (exe), use exe's parent directory;
    # when running as script, go 3 levels up from tools/jdap_orchestrator/app.py
    if getattr(sys, 'frozen', False):
        default_workspace = os.path.dirname(os.path.dirname(sys.executable))
    else:
        default_workspace = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    parser = argparse.ArgumentParser(description="JDAP Orchestrator Tool")
    parser.add_argument("--workspace", default=default_workspace,
                        help="Workspace root directory")
    parser.add_argument("--port", type=int, default=5500, help="Port number")
    args = parser.parse_args()

    WORKSPACE_ROOT = os.path.abspath(args.workspace)
    state.agents = build_agents()

    print(f"╔══════════════════════════════════════════════════╗")
    print(f"║  JDAP Orchestrator Tool                         ║")
    print(f"║  Workspace: {WORKSPACE_ROOT[:36]:36s}  ║")
    print(f"║  URL: http://localhost:{args.port:<25d} ║")
    print(f"╚══════════════════════════════════════════════════╝")

    app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)
