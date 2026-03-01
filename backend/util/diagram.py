from pathlib import Path
import subprocess
import shutil
import os
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional
import zlib
import base64

try:
    from .consts import DB_KEYWORDS, FRONTEND_KEYWORDS, SERVICE_DIR_KEYWORDS, MODEL_DIR_KEYWORDS, STATIC_DIR_KEYWORDS
except ImportError:
    from util.consts import DB_KEYWORDS, FRONTEND_KEYWORDS, SERVICE_DIR_KEYWORDS, MODEL_DIR_KEYWORDS, STATIC_DIR_KEYWORDS

PUPPETEER_CONFIG_PATH = Path(__file__).resolve().with_name("puppeteer-config.json")
_DISABLE_REMOTE = os.getenv("DOX_DISABLE_REMOTE_RENDER", "false").lower() in ("1", "true", "yes")

# find database from dependencies
def choose_db(deps: Dict[str, List[str]]) -> Optional[str]:
    if not deps:
        return None

    flat = []
    for v in deps.values():
        if isinstance(v, list):
            flat.extend(v)
    flat_lower = {p.lower() for p in flat}

    for db in DB_KEYWORDS:
        if any(db in pkg for pkg in flat_lower):
            if db in ("psycopg2", "postgresql", "postgres"):
                return "postgres"
            if db in ("sqlite",):
                return "sqlite"
            if db in ("mongodb", "mongo"):
                return "mongodb"
            if db in ("mysql",):
                return "mysql"
            if db in ("redis",):
                return "redis"
            return db

    return None

# grabs info from file tree
def detect_layers(file_tree: Dict[str, Any]) -> Dict[str, bool]:
    flags = {"has_routes": False, "has_models": False, "has_frontend": False, "has_static": False}

    def walk(node, depth=0):
        if not node or depth > 3:
            return

        name = node.get("name", "") or ""
        lower = name.lower()

        if any(k in lower for k in ("frontend", "web", "client", "ui")):
            flags["has_frontend"] = True
        if any(k in lower for k in SERVICE_DIR_KEYWORDS):
            flags["has_routes"] = True
        if any(k in lower for k in MODEL_DIR_KEYWORDS):
            flags["has_models"] = True
        if any(k in lower for k in STATIC_DIR_KEYWORDS):
            flags["has_static"] = True
        for c in node.get("children", []) or []:
            walk(c, depth + 1)

    walk(file_tree, 0)
    return flags

# keep labels clean
def sanitize_label(s: str) -> str:
    return s.replace('"', "'").replace("\n", " ").strip()

# produces mermaid flowchart from inputs
def generate_mermaid_syntax(project_name: str,
                            frameworks: List[str],
                            dependencies: Dict[str, List[str]],
                            file_tree: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("flowchart TD")
    flags = detect_layers(file_tree)

    has_frontend = any(f.lower() in FRONTEND_KEYWORDS for f in frameworks) or flags.get("has_frontend", False)
    if has_frontend:
        lines.append('  subgraph CLIENT["Client / Frontend"]')
        ff = [f for f in frameworks if f.lower() in FRONTEND_KEYWORDS]
        if ff:
            for fe in ff:
                lines.append(f'    FE_{sanitize_label(fe)}["{sanitize_label(fe)}"]')
            lines.append("  end")
        else:
            lines.append("  end")
    else:
        lines.append('  CLIENT[Client]')

    server_label = frameworks[0] if frameworks else project_name or "Server"
    server_label = sanitize_label(server_label)
    lines.append(f'  subgraph SERVER["{sanitize_label(project_name)}"]')
    lines.append(f'    S1[{server_label}]')
    lines.append("  end")

    if has_frontend:
        ff = [f for f in frameworks if f.lower() in FRONTEND_KEYWORDS]
        if ff:
            for fe in ff:
                lines.append(f'  FE_{sanitize_label(fe)} --> S1')
        else:
            lines.append('  CLIENT --> S1')
    else:
        lines.append('  CLIENT --> S1')

    db = choose_db(dependencies)

    if db:
        lines.append(f'  S1 --> DB[{db.upper()}]')

    if flags.get("has_routes") or flags.get("has_models"):
        if flags.get("has_routes"):
            lines.append('  ROUTES[Routes / Controllers]')
            lines.append('  S1 --> ROUTES')
            if flags.get("has_models"):
                lines.append('  ROUTES --> MODELS[Models]')
                lines.append('  MODELS --> DB' if db else '  MODELS')
        elif flags.get("has_models"):
            lines.append('  S1 --> MODELS[Models]')
            lines.append('  MODELS --> DB' if db else '  MODELS')

    heur = None
    if isinstance(dependencies, dict):
        heur = dependencies.get("heuristic")

        if not heur:
            for k, v in dependencies.items():
                if isinstance(v, list) and v:
                    heur = v
                    break

    if heur and isinstance(heur, list):
        top = heur[:4]
        if top:
            lines.append('  subgraph EXTRAS["Detected libraries"]')
            for i, pkg in enumerate(top, start=1):
                lbl = sanitize_label(str(pkg))
                lines.append(f'    E{i}[{lbl}]')
                lines.append(f'    S1 --> E{i}')
            lines.append('  end')

    def _find_entry(node):
        if not node:
            return None

        if node.get("type") == "file":
            nm = node.get("name", "").lower()
            if nm in ("main.py", "app.py", "server.py", "index.js", "app.js", "server.js"):
                return node.get("name")
            return None

        for c in node.get("children", []) or []:
            res = _find_entry(c)
            if res:
                return res

        return None

    entry = _find_entry(file_tree)
    if entry:
        lines.append(f'  S1 --> ENTRY["Entry: {entry}"]')

    return "\n".join(lines)

# render via Kroki (POST)
def render_via_kroki(mermaid_text: str, svg_path: Path, timeout: int = 15) -> bool:
    url = "https://kroki.io/mermaid/svg"
    data = mermaid_text.encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "text/plain; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                svg_bytes = resp.read()
                svg_path.write_bytes(svg_bytes)
                return True
    except urllib.error.HTTPError:
        pass
    except Exception:
        pass
    return False

# render via mermaid.ink compressed GET
def render_via_mermaid_ink(mermaid_text: str, svg_path: Path) -> bool:
    try:
        compressed = zlib.compress(mermaid_text.encode("utf-8"), level=9)
        b64 = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
        url = f"https://r.mermaid.ink/svg/{b64}"
        req = urllib.request.Request(url, headers={"Accept": "image/svg+xml"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                svg_path.write_bytes(resp.read())
                return True
    except Exception:
        pass
    return False

# consolidated render function: try CLI then remote fallbacks
def render_mermaid_to_svg(mmd_path: Path, svg_path: Path, timeout: int = 20) -> bool:
    use_puppet_flag = PUPPETEER_CONFIG_PATH.exists()

    cmds = []
    if use_puppet_flag:
        cmds.append(["mmdc", "-p", str(PUPPETEER_CONFIG_PATH), "-i", str(mmd_path), "-o", str(svg_path)])
        cmds.append(["npx", "-y", "@mermaid-js/mermaid-cli", "-p", str(PUPPETEER_CONFIG_PATH), "-i", str(mmd_path), "-o", str(svg_path), "--quiet"])
    else:
        cmds.append(["mmdc", "-i", str(mmd_path), "-o", str(svg_path)])
        cmds.append(["npx", "@mermaid-js/mermaid-cli", "-i", str(mmd_path), "-o", str(svg_path), "--quiet"])

    for cmd in cmds:
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)
            if svg_path.exists():
                return True
        except FileNotFoundError:
            continue
        except subprocess.CalledProcessError:
            continue
        except Exception:
            continue

    if _DISABLE_REMOTE:
        return False

    try:
        mermaid_text = mmd_path.read_text(encoding="utf-8")
    except Exception:
        return False

    if render_via_kroki(mermaid_text, svg_path, timeout=15):
        return True

    if render_via_mermaid_ink(mermaid_text, svg_path):
        return True

    return False

# creates the docs folder and puts diagram in it
def make_docs_with_diagram(repo_dir: Path,
                           project_name: str,
                           frameworks: List[str],
                           dependencies: Dict[str, List[str]],
                           file_tree: Dict[str, Any]) -> Dict[str, Optional[str]]:
    docs = repo_dir / "docs"
    mmd_path = docs / "diagram.mmd"
    svg_path = docs / "diagram.svg"

    try:
        docs.mkdir(parents=True, exist_ok=True)
    except Exception:
        return {"mmd": None, "svg": None, "rendered": False}

    try:
        mermaid_text = generate_mermaid_syntax(project_name, frameworks, dependencies, file_tree)
    except Exception:
        mermaid_text = "flowchart TD\n  A[Architecture diagram unavailable]\n"

    try:
        mmd_path.parent.mkdir(parents=True, exist_ok=True)
        mmd_path.write_text(mermaid_text, encoding="utf-8")
    except Exception:
        return {"mmd": None, "svg": None, "rendered": False}

    try:
        rendered = render_mermaid_to_svg(mmd_path, svg_path)
        if rendered and svg_path.exists():
            return {"mmd": str(mmd_path), "svg": str(svg_path), "rendered": True}
    except Exception:
        pass

    return {"mmd": str(mmd_path), "svg": None, "rendered": False}