import shutil
import tempfile
import re
import os
import sys
import logging
import util.methods as methods
import util.diagram as diagram
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title = "repo analyzer")
logger = logging.getLogger(__name__)

def _cors_origins() -> list[str]:
    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [origin.strip() for origin in origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMPLATE_PATH = Path(__file__).resolve().parent / "util" / "template.md"

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post('/analyze')
async def generate(file: UploadFile = File(...)):
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
        if not TEMPLATE_PATH.exists():
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
            template_path_text = TEMPLATE_PATH.read_text(encoding="utf-8")

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

        try:
            diagram_info = diagram.make_docs_with_diagram(
                repo_dir=repo_dir,
                project_name=project_name,
                frameworks=frameworks,
                dependencies=dependencies,
                file_tree=file_tree,
            )
        except Exception:
            logger.exception("Diagram generation failed")
            diagram_info = {"mmd": None, "svg": None, "rendered": False}

        if diagram_info.get("rendered") and diagram_info.get("svg"):
            readme += "\n\n## Automatically generated architecture diagram\n\n"
            readme += f"![Architecture](docs/diagram.svg)\n"
        else:
            mmd_path = diagram_info.get("mmd")
            
            if mmd_path:
                try:
                    mermaid_source = Path(mmd_path).read_text(encoding="utf-8")
                except Exception:
                    mermaid_source = ""
                
                if mermaid_source:
                    readme += "\n\n## Automatically generated architecture diagram (Mermaid)\n\n"
                    readme += "```mermaid\n" + mermaid_source + "\n```\n"

        readme_path.write_text(readme, encoding="utf-8")

        safe_name = (project_name or "project").replace(" ", "_")
        download_filename = f"{safe_name}.zip"

        return methods.stream_dir(repo_dir, download_filename)

    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
