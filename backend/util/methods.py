import shutil
import json
import re
import zipfile
import tomllib
from starlette.responses import StreamingResponse
from starlette.background import BackgroundTask
from typing import Dict, Any, List, Optional
from fastapi import UploadFile, HTTPException
from pathlib import Path
from typing import Iterator
from util.consts import EXTENSIONS, FRAMEWORKS, PACKAGES, MAX_UPLOAD, UPLOAD_EXT

# grabs languages from file extensions
def get_languages(files: List[Path]) -> List[str]:
    res = set()

    for f in files:
        extension = f.suffix.lower()

        if extension in EXTENSIONS:
            res.add(EXTENSIONS[extension])

    return sorted(res)

# grabs frameworks from files
def get_frameworks(files: List[Path], sample_limit: int = 400) -> List[str]:
    res = set()
    sample_files = files[:sample_limit]
    file_texts = []

    for f in sample_files:
        file_texts.append((f, read_text_safe(f, max_chars=4000).lower()))

    for framework, keyword in FRAMEWORKS.items():
        found = False
        for f, txt in file_texts:
            if any(k.lower() in txt for k in keyword):
                res.add(framework)
                found = True
                break
        if found:
            continue

    return sorted(res)


# grabs package from files
def get_packages(files: List[Path]) -> Optional[str]:
    names = {f.name for f in files}

    for package, keyword in PACKAGES.items():
        for k in keyword:
            if k in names:
                return package

    return None


# unzips zipfiles
def unzip(zip_path: Path, dest: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as file:
        names = file.namelist()
        for name in names:
            p = Path(name)

            if p.is_absolute() or ".." in p.parts:
                raise HTTPException(status_code=400, detail="Invalid archive entry")
        file.extractall(dest)


# extracts text from files
def read_text_safe(path: Path, max_chars: int = 200_000) -> str:
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
        return txt[:max_chars]
    except Exception:
        return ""


# save upload zipfile to temporary directory
def save_upload(tmp: Path, upload: UploadFile) -> Path:
    filename = Path(upload.filename or "upload.zip").name
    dest = tmp / filename

    if dest.suffix.lower() not in {s.lower() for s in UPLOAD_EXT}:
        raise HTTPException(status_code=400, detail="Not in approved format")

    total = 0

    with dest.open("wb") as f:
        while True:
            chunk = upload.file.read(1024 * 64)

            if not chunk:
                break
            total += len(chunk)

            if total > MAX_UPLOAD:
                try:
                    f.close()
                    dest.unlink(missing_ok=True)
                except Exception:
                    pass
                raise HTTPException(status_code=413, detail="Upload too large")

            f.write(chunk)

    return dest

# list all files out
def get_files(root: Path, entries: int = 2000) -> List[Path]:
    files = []

    for p in root.rglob("*"):
        if p.is_file():
            files.append(p)
            if len(files) >= entries:
                break

    return files

# create a tree structure for file mapping
def make_tree(root: Path, max_depth: int = 6, max_entries: int = 500) -> Dict[str, Any]:

    def node(p: Path, depth: int):
        if depth > max_depth:
            return None

        if p.is_dir():
            children = []

            try:
                iter_children = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            except Exception:
                iter_children = []

            for child in iter_children:
                if len(children) >= 200:
                    break
                cn = node(child, depth + 1)
                if cn:
                    children.append(cn)

            return {"name": p.name, "type": "dir", "children": children}
        else:
            # st_size is an attribute (not a function)
            try:
                size = p.stat().st_size
            except Exception:
                size = None
            return {"name": p.name, "type": "file", "size": size}

    return node(root, 0)


# check for env files
def get_env(root: Path, files: List[Path]) -> List[str]:
    res = set()
    names = {f.name for f in files}

    for i in (".env", ".env.example", ".env.local", ".env.sample"):
        if i in names:
            res.add(i)

    for f in files[:400]:  # sample to limit I/O
        txt = read_text_safe(f, max_chars=2000)
        if "process.env" in txt or "os.environ" in txt or "dotenv" in txt:
            try:
                res.add(str(f.relative_to(root)))
            except Exception:
                res.add(str(f))

    return sorted(res)

# check for testing files
def get_test(root: Path, files: List[Path]) -> bool:
    for f in files:
        if "test" in f.parts:
            return True
        name = f.name.lower()

        if name.startswith("test_") or name.startswith("test") or name.endswith(".spec.js") or name.endswith(".test.js"):
            return True

    return False


# find dependencies based on package
def get_dependencies(root: Path, files: List[Path]) -> Dict[str, List[str]]:
    package = get_packages(files)
    res = {}

    if package:
        if package == "npm":
            pj = root / "package.json"
            if pj.exists():
                pj_txt = json.loads(pj.read_text(encoding="utf-8"))
                for k in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                    if isinstance(pj_txt.get(k), dict):
                        res[k] = list(pj_txt.get(k).keys())[:200]

        elif package == "pip":
            req = root / "requirements.txt"
            if req.exists():
                lines = [l.strip() for l in req.read_text(encoding="utf-8").splitlines() if l.strip() and not l.strip().startswith("#")]
                res["requirements.txt"] = lines[:200]

            pyproj = root / "pyproject.toml"

            if pyproj.exists() and tomllib:
                try:
                    content = pyproj.read_bytes()
                    parsed = tomllib.loads(content) if hasattr(tomllib, "loads") else tomllib.loads(pyproj.read_text())
                    tool = parsed.get("tool", {})
                    poetry = tool.get("poetry") or parsed.get("project")

                    if isinstance(poetry, dict):
                        deps_list = []
                        for k in ("dependencies", "dev-dependencies", "optional-dependencies"):
                            val = poetry.get(k)
                            if isinstance(val, dict):
                                deps_list.extend(list(val.keys()))
                        res["pyproject"] = deps_list[:200]

                except Exception:
                    pass

        elif package == "go":
            gm = root / "go.mod"
            if gm.exists():
                txt = gm.read_text(encoding="utf-8")
                matches = re.findall(r"^\s*require\s+([^\s]+)", txt, flags=re.MULTILINE)
                res["go.mod"] = matches[:200]

        elif package == "cargo":
            cm = root / "Cargo.toml"

            if cm.exists():
                text = cm.read_text(encoding="utf-8", errors="ignore")
                matches = re.findall(r'^\s*([\w_-]+)\s*=\s*".+"', text, flags=re.MULTILINE)
                res["cargo"] = matches[:200]

    if not res:
        heuristic = []
        for f in files[:400]:
            txt = read_text_safe(f, max_chars=4000)

            for m in re.finditer(r"^\s*(?:from\s+([A-Za-z0-9_\.]+)\s+import|import\s+([A-Za-z0-9_\.]+))", txt, flags=re.MULTILINE):
                module = m.group(1) or m.group(2)
                if module:
                    heuristic.append(module.split(".")[0])

            for m in re.finditer(r"(?:require\(|from\s+|import\s+).?['\"]([a-zA-Z0-9@/\-_\.\$]+)['\"]", txt):
                heuristic.append(m.group(1))

        res["heuristic"] = sorted(set(heuristic), key=lambda x: heuristic.count(x), reverse=True)[:200]

    return res

def detect_entry_points(root: Path, files: List[Path]) -> List[str]:
    """
    Small inline heuristic to find common entry points (main files, package.json script).
    We keep it deterministic and based only on files we saw.
    """
    entries = []
    filename_map = {f.name.lower(): f for f in files}

    for cand in ("main.py", "app.py", "server.py", "manage.py", "index.py"):
        if cand in filename_map:
            try:
                entries.append(str(filename_map[cand].relative_to(root)))
            except Exception:
                entries.append(str(filename_map[cand]))

    for cand in ("index.js", "server.js", "app.js", "index.ts"):
        if cand in filename_map:
            try:
                entries.append(str(filename_map[cand].relative_to(root)))
            except Exception:
                entries.append(str(filename_map[cand]))

    pj = root / "package.json"
    if pj.exists():
        try:
            pjtxt = json.loads(pj.read_text(encoding="utf-8"))
            main = pjtxt.get("main")
            if main:
                entries.append(main)
            scripts = pjtxt.get("scripts", {})
            if isinstance(scripts, dict) and "start" in scripts:
                entries.append("npm start (script)")
        except Exception:
            pass

    if (root / "go.mod").exists():
        entries.append("go module (go.mod)")

    # remove duplicates while preserving order
    seen = set()
    out = []
    for e in entries:
        if e not in seen:
            out.append(e)
            seen.add(e)
    return out

# convert file tree structure to .md
def tree_to_markdown(tree: dict, prefix: str = "") -> str:
    lines = []

    def walk(node: dict, indent: str):
        name = node.get("name", "")
        ntype = node.get("type", "dir")
        if ntype == "dir":
            lines.append(f"{indent}{name}/")
            for child in node.get("children", []):
                walk(child, indent + "  ")
        else:
            size = node.get("size")
            if size is None:
                lines.append(f"{indent}{name}")
            else:
                lines.append(f"{indent}{name} ({size} bytes)")

    if not tree:
        return ""
    walk(tree, "")
    return "\n".join(lines)

# replaces blanks in template.md
def render_template(template_path: Path, mapping: dict) -> str:
    txt = template_path.read_text(encoding="utf-8")

    for k, v in mapping.items():
        if isinstance(v, list):
            replacement = "\n".join(v) if v else ""
        elif isinstance(v, dict):
            try:
                replacement = "\n".join(
                    f"- {k}: {', '.join(vals)}" if isinstance(vals, list) else f"- {k}: {vals}"
                    for k, vals in v.items()
                )
            except Exception:
                replacement = json.dumps(v)
        else:
            replacement = str(v) if v is not None else ""
        txt = txt.replace("{" + k + "}", replacement)

    txt = re_placeholder_cleanup(txt := txt)
    return txt

# removes any placeholders still left in template.md
def re_placeholder_cleanup(s: str) -> str:
    return re.sub(r"\{[^\}]+\}", "", s)

# creates iterator through files
def file_iterator(path: Path, chunk_size: int = 8192) -> Iterator[bytes]:
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk

# streams directory out to user
def stream_dir(root_dir: Path, download_name: str) -> StreamingResponse:
    parent = root_dir.parent or Path("/tmp")
    base_name = parent / (root_dir.name + "_archive")
    archive_path_str = shutil.make_archive(base_name=str(base_name), format="zip", root_dir=str(root_dir))
    archive_path = Path(archive_path_str)

    iterator = file_iterator(archive_path)
    filename_header = download_name if download_name.endswith(".zip") else f"{download_name}.zip"
    headers = {"Content-Disposition": f'attachment; filename="{filename_header}"'}

    def _cleanup(archive_p=archive_path, root_p=root_dir):
        try:
            if archive_p.exists():
                archive_p.unlink()
        except Exception:
            pass
        
        try:
            shutil.rmtree(root_p, ignore_errors=True)
        except Exception:
            pass

    return StreamingResponse(iterator, media_type="application/zip", headers=headers, background=BackgroundTask(_cleanup))
