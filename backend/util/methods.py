import zipfile
import shutil
import tempfile
import json
import re
import uvicorn
import tomllib
from typing import Dict, Any, List, Optional
from fastapi import UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pathlib import Path
from consts import EXTENSIONS, FRAMEWORKS, PACKAGES, MAX_UPLOAD, UPLOAD_EXT

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