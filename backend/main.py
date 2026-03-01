import zipfile
import shutil
import tempfile
import json
import re
import uvicorn
import util.methods as methods
import util.consts as consts
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title = "repo analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post('/analyze')
async def generate_md(file: UploadFile = File(...)):
    tmp = tempfile.mkdtemp(prefix="dox_analyze_")
    tmpdir = Path(tmp)
    
    try:
        try:
            zip_path = methods.save_upload(tmpdir, file)
        except HTTPException:
            raise
        except Exception as e:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise HTTPException(status_code=500, detail=f"Failed saving upload: {e}")

        repo_dir = tmpdir / "repo"
        repo_dir.mkdir(exist_ok=True)

        try:
            methods.unzip(zip_path, repo_dir)
        except HTTPException:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise
        except Exception as e:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise HTTPException(status_code=400, detail=f"Failed to unpack zip: {e}")

        files = methods.get_files(repo_dir)

        if not files:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise HTTPException(status_code=400, detail="Archive contained no files")

        languages = methods.get_languages(files)
        frameworks = methods.get_frameworks(files)
        package_manager = methods.get_packages(files)
        entry_points = methods.detect_entry_points(repo_dir, files)
        dependencies = methods.get_dependencies(repo_dir, files)
        env_files = methods.get_env(repo_dir, files)
        has_tests = methods.get_test(repo_dir, files)
        file_tree = methods.make_tree(repo_dir)

        project_name = repo_dir.name
        summary_bits = []

        if languages:
            summary_bits.append("built with " + ", ".join(languages))

        if frameworks:
            summary_bits.append("uses " + ", ".join(frameworks))

        summary = "; ".join(summary_bits) if summary_bits else ""

        languages_txt = "\n".join(languages) if languages else "None detected"
        frameworks_txt = "\n".join(frameworks) if frameworks else "None detected"
        package_manager_txt = package_manager or "None detected"
        entry_points_txt = "\n".join(entry_points) if entry_points else "None detected"
        project_structure_txt = methods.tree_to_markdown(file_tree)

        if dependencies:
            parts = []
            for k, v in dependencies.items():
                if isinstance(v, list) and v:
                    parts.append(f"**{k}**\n" + "\n".join(f"- {x}" for x in v))
                elif isinstance(v, list):
                    parts.append(f"**{k}**: (none detected)")
                else:
                    parts.append(f"**{k}**: {v}")
            deps_txt = "\n\n".join(parts)
        else:
            deps_txt = "None detected"

        env_txt = "\n".join(env_files) if env_files else "None detected"
        test_status = "Yes" if has_tests else "No"
        template_path = Path("util") / "template.md"

        if not template_path.exists():
            template_text = (
                "# {project_name}\n\n"
                "{summary}\n\n"
                "## Detected Languages\n\n"
                "{languages}\n\n"
                "## Detected Frameworks\n\n"
                "{frameworks}\n\n"
                "## Package Manager\n\n"
                "{package_manager}\n\n"
                "## Entry Points\n\n"
                "{entry_points}\n\n"
                "## Project Structure\n\n"
                "```\n"
                "{project_structure}\n"
                "```\n\n"
                "## Dependencies\n\n"
                "{dependencies}\n\n"
                "## Environment Configuration\n\n"
                "{environment_files}\n\n"
                "## Test Files Detected\n\n"
                "{test_status}\n"
            )
            template_path_text = template_text
        else:
            template_path_text = template_path.read_text(encoding="utf-8")

        mapping = {
            "project_name": project_name,
            "summary": summary,
            "languages": languages_txt,
            "frameworks": frameworks_txt,
            "package_manager": package_manager_txt,
            "entry_points": entry_points_txt,
            "project_structure": project_structure_txt,
            "dependencies": deps_txt,
            "environment_files": env_txt,
            "test_status": test_status,
        }

        readme = template_path_text
        for k, v in mapping.items():
            readme = readme.replace("{" + k + "}", str(v))

        readme = re.sub(r"\{[^\}]+\}", "", readme)

        metadata = {
            "projectName": project_name,
            "languages": languages,
            "frameworks": frameworks,
            "package_manager": package_manager,
            "entry_points": entry_points,
            "dependencies": dependencies,
            "has_tests": has_tests,
            "env_files": env_files,
            "file_tree": file_tree,
            "summary": summary,
        }

        readme_path = repo_dir / "README.md"
        readme_path.write_text(readme, encoding="utf-8")

        safe_name = (project_name or "project").replace(" ", "_")
        download_filename = f"{safe_name}.zip"

        return methods.stream_dir(repo_dir, download_filename)

    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise